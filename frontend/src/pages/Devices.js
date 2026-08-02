import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import './Devices.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_URL  = (API_URL.replace('http', 'ws')) + '/ws/realtime';

// Sensor type → human-readable label
const SENSOR_LABELS = {
  moisture:    'Moisture',
  temperature: 'Temperature',
  npk:         'NPK',
  ph:          'pH',
  ultrasonic:  'Ultrasonic',
  humidity:    'Humidity',
};

const DEVICE_TYPE_LABELS = {
  gateway:     'LoRa Gateway',
  sensor_node: 'LoRa Node',
  direct_esim: 'eSIM Node',
};

const DEVICE_TYPE_COLORS = {
  gateway:     '#7c3aed',   // purple
  sensor_node: '#15803d',   // green
  direct_esim: '#0369a1',   // blue
};

export default function Devices() {
  const [devices, setDevices]     = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [showAdd, setShowAdd]     = useState(false);
  const [addError, setAddError]   = useState('');
  const [newDevice, setNewDevice] = useState({
    device_id: '', name: '', location: '', sensor_type: 'moisture',
    device_type: 'direct_esim', gateway_device_id: '', lora_addr: '',
  });
  const [adding, setAdding]       = useState(false);
  const wsRef                     = useRef(null);
  const navigate                  = useNavigate();

  // ── Fetch device list ─────────────────────────────────────────────────
  const fetchDevices = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/devices`);
      setDevices(res.data);
      setError(null);
    } catch (err) {
      setError('Failed to load devices. Make sure you are logged in.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDevices(); }, []);

  // ── WebSocket: live updates ───────────────────────────────────────────
  useEffect(() => {
    const connectWS = () => {
      const token = localStorage.getItem('access_token');
      const ws = new WebSocket(`${WS_URL}?token=${token}`);
      wsRef.current = ws;

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);

          if (msg.event === 'device_status') {
            setDevices(prev => prev.map(d =>
              d.device_id === msg.device_id
                ? { ...d, is_online: msg.status === 'online' } : d
            ));
          }
          if (msg.event === 'new_reading') {
            setDevices(prev => prev.map(d =>
              d.device_id === msg.device_id
                ? { ...d, is_online: true, last_seen: msg.timestamp,
                    battery_mv: msg.battery_mv ?? d.battery_mv,
                    battery_pct: msg.battery_pct ?? d.battery_pct,
                    rssi_dbm: msg.rssi_dbm ?? d.rssi_dbm,
                    signal_label: msg.signal ?? d.signal_label } : d
            ));
          }
          if (msg.event === 'config_acked') {
            setDevices(prev => prev.map(d =>
              d.device_id === msg.device_id
                ? { ...d, cfg_version_acked: msg.cfg_ver, config_applied: true } : d
            ));
          }
        } catch (_) {}
      };
      ws.onclose = () => setTimeout(connectWS, 3000);
    };
    connectWS();
    return () => wsRef.current?.close();
  }, []);

  // ── Register new device ───────────────────────────────────────────────
  const handleAddDevice = async (e) => {
    e.preventDefault();
    setAdding(true);
    setAddError('');
    try {
      const payload = {
        device_id:   newDevice.device_id,
        name:        newDevice.name || undefined,
        location:    newDevice.location,
        sensor_type: newDevice.sensor_type,
        device_type: newDevice.device_type,
        // Only include optional LoRa fields if they have values
        ...(newDevice.gateway_device_id ? { gateway_device_id: newDevice.gateway_device_id } : {}),
        ...(newDevice.lora_addr !== '' && newDevice.lora_addr != null
          ? { lora_addr: parseInt(newDevice.lora_addr, 10) }
          : {}),
      };
      const res = await axios.post(`${API_URL}/api/devices`, payload);
      setDevices(prev => [res.data, ...prev]);
      setShowAdd(false);
      setNewDevice({
        device_id: '', name: '', location: '', sensor_type: 'moisture',
        device_type: 'direct_esim', gateway_device_id: '', lora_addr: '',
      });
    } catch (err) {
      setAddError(err.response?.data?.detail || 'Failed to register device.');
    } finally {
      setAdding(false);
    }
  };

  // ── Helpers ───────────────────────────────────────────────────────────
  const batteryClass = (pct) => {
    if (pct == null) return 'muted';
    if (pct > 50) return 'good';
    if (pct > 20) return 'warn';
    return 'bad';
  };

  const signalClass = (label) => {
    const map = { excellent: 'good', good: 'good', fair: 'warn', poor: 'bad' };
    return map[label] || 'muted';
  };

  const timeAgo = (isoStr) => {
    if (!isoStr) return 'Never';
    const diff = Math.floor((Date.now() - new Date(isoStr + 'Z')) / 1000);
    if (diff < 60)    return `${diff}s ago`;
    if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  const onlineCount = devices.filter(d => d.is_online).length;

  // ── Device grouping for LoRa architecture ────────────────────────────
  // Gateways render first with their sensor_nodes nested inside.
  // direct_esim devices render in their own flat section after.
  const gateways    = devices.filter(d => d.device_type === 'gateway');
  const sensorNodes = devices.filter(d => d.device_type === 'sensor_node');
  const directEsim  = devices.filter(d => d.device_type === 'direct_esim' || !d.device_type);
  const gatewayIds  = new Set(gateways.map(g => g.device_id));
  // Ungrouped sensor nodes (gateway not registered yet)
  const ungroupedNodes = sensorNodes.filter(n => !gatewayIds.has(n.gateway_device_id));

  // Helper: render a single device card
  const DeviceCard = ({ device, compact = false }) => (
    <div
      key={device.device_id}
      className={`device-card ${device.is_online ? 'online' : 'offline'}${compact ? ' compact' : ''}`}
      onClick={() => navigate(`/devices/${device.device_id}/config`)}
      style={compact ? { marginLeft: '24px', marginTop: '8px', borderLeft: '3px solid #e4e4e7' } : {}}
    >
      <div className="device-card-header">
        <div>
          <div className="device-name">
            {device.name || device.device_id}
            {/* Device type badge */}
            <span style={{
              marginLeft: '8px', fontSize: '0.65rem', fontWeight: 600,
              padding: '2px 6px', borderRadius: '4px',
              background: DEVICE_TYPE_COLORS[device.device_type] || '#71717a',
              color: '#fff', letterSpacing: '0.03em', verticalAlign: 'middle',
            }}>
              {DEVICE_TYPE_LABELS[device.device_type] || device.device_type || 'eSIM Node'}
            </span>
          </div>
          <div className="device-id">{device.device_id}</div>
        </div>
        <span className={`device-status ${device.is_online ? 'status-online' : 'status-offline'}`}>
          {device.is_online ? 'Online' : 'Offline'}
        </span>
      </div>

      <div className="device-metrics">
        <div className="metric-item">
          <span className="metric-label">Battery</span>
          <span className={`metric-value ${batteryClass(device.battery_pct)}`}>
            {device.battery_pct != null ? `${device.battery_pct}%` : '—'}
            {device.battery_mv  != null ? ` · ${(device.battery_mv/1000).toFixed(2)}V` : ''}
          </span>
        </div>
        <div className="metric-item">
          <span className="metric-label">Signal</span>
          <span className={`metric-value ${signalClass(device.signal_label)}`}>
            {device.rssi_dbm != null ? `${device.rssi_dbm} dBm` : '—'}
          </span>
        </div>
        <div className="metric-item">
          <span className="metric-label">Last Seen</span>
          <span className="metric-value">{timeAgo(device.last_seen)}</span>
        </div>
        <div className="metric-item">
          <span className="metric-label">Config</span>
          <span className="metric-value">
            v{device.cfg_version ?? 0}
            {device.config_applied
              ? <> · <span style={{color:'#16a34a',fontSize:'0.72rem'}}>Applied</span></>
              : device.cfg_version > 0
                ? <> · <span style={{color:'#ea580c',fontSize:'0.72rem'}}>Pending</span></>
                : null}
          </span>
        </div>
      </div>

      <div className="device-footer">
        <span className="device-location">{device.location}</span>
        <span className="device-sensor">{SENSOR_LABELS[device.sensor_type] || device.sensor_type}</span>
        {device.device_type === 'sensor_node' && device.lora_addr != null && (
          <span style={{ fontSize: '0.72rem', color: '#71717a' }}>LoRa addr: 0x{device.lora_addr.toString(16).toUpperCase().padStart(2,'0')}</span>
        )}
        <button
          className="btn-configure"
          onClick={e => { e.stopPropagation(); navigate(`/devices/${device.device_id}/config`); }}
        >
          Configure
        </button>
      </div>
    </div>
  );

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className="devices-page">

      {/* Header */}
      <div className="devices-header">
        <div>
          <h1>Device Fleet</h1>
          <p>Manage transmitter devices and push configuration via MQTT</p>
        </div>
        <button className="btn-register" onClick={() => setShowAdd(true)}>
          + Register Device
        </button>
      </div>

      {/* Stats bar */}
      <div className="devices-stats">
        <span>{devices.length} devices registered</span>
        <span className="stat-sep">·</span>
        <span className="stat-online">{onlineCount} online</span>
        {gateways.length > 0 && (
          <><span className="stat-sep">·</span>
          <span style={{ color: '#7c3aed', fontWeight: 500 }}>{gateways.length} LoRa {gateways.length === 1 ? 'gateway' : 'gateways'}</span></>
        )}
        {sensorNodes.length > 0 && (
          <><span className="stat-sep">·</span>
          <span style={{ color: '#15803d', fontWeight: 500 }}>{sensorNodes.length} LoRa {sensorNodes.length === 1 ? 'node' : 'nodes'}</span></>
        )}
      </div>

      {/* Register modal */}
      {showAdd && (
        <div className="modal-overlay" onClick={() => setShowAdd(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <h2>Register New Device</h2>

            {addError && <div className="modal-alert error">{addError}</div>}

            <form onSubmit={handleAddDevice}>
              <div className="modal-field">
                <label>Device ID (from firmware)</label>
                <input
                  required placeholder="e.g. GW001 or D001"
                  value={newDevice.device_id}
                  onChange={e => setNewDevice(p => ({ ...p, device_id: e.target.value.toUpperCase() }))}
                />
              </div>

              <div className="modal-field">
                <label>Display Name</label>
                <input
                  placeholder="e.g. Field A – North corner"
                  value={newDevice.name}
                  onChange={e => setNewDevice(p => ({ ...p, name: e.target.value }))}
                />
              </div>

              <div className="modal-field">
                <label>Location (matches MQTT topic prefix)</label>
                <input
                  required placeholder="e.g. chandigarh"
                  value={newDevice.location}
                  onChange={e => setNewDevice(p => ({ ...p, location: e.target.value.toLowerCase() }))}
                />
              </div>

              <div className="modal-field">
                <label>Device Type</label>
                <select
                  value={newDevice.device_type}
                  onChange={e => setNewDevice(p => ({ ...p, device_type: e.target.value, gateway_device_id: '', lora_addr: '' }))}
                >
                  <option value="direct_esim">eSIM Node (Direct Cellular)</option>
                  <option value="gateway">LoRa Gateway (eSIM + LoRa receiver)</option>
                  <option value="sensor_node">LoRa Sensor Node (no SIM — sends via gateway)</option>
                </select>
              </div>

              {/* LoRa-specific fields — only for sensor_node */}
              {newDevice.device_type === 'sensor_node' && (
                <>
                  <div className="modal-field">
                    <label>Parent Gateway Device ID</label>
                    <select
                      value={newDevice.gateway_device_id}
                      onChange={e => setNewDevice(p => ({ ...p, gateway_device_id: e.target.value }))}
                    >
                      <option value="">— Select Gateway —</option>
                      {gateways.map(g => (
                        <option key={g.device_id} value={g.device_id}>
                          {g.device_id}{g.name ? ` — ${g.name}` : ''} ({g.location})
                        </option>
                      ))}
                    </select>
                    <small style={{ color: '#a1a1aa', fontSize: '0.75rem' }}>
                      The LoRa gateway that relays this node's packets to MQTT.
                    </small>
                  </div>
                  <div className="modal-field">
                    <label>LoRa Address Byte (decimal — e.g. 1 for 0x01)</label>
                    <input
                      type="number" min="1" max="254" placeholder="e.g. 1"
                      value={newDevice.lora_addr}
                      onChange={e => setNewDevice(p => ({ ...p, lora_addr: e.target.value }))}
                    />
                    <small style={{ color: '#a1a1aa', fontSize: '0.75rem' }}>
                      Must match the source address byte in the node's LoRa packet header.
                    </small>
                  </div>
                </>
              )}

              <div className="modal-field">
                <label>Initial Sensor Type</label>
                <select
                  value={newDevice.sensor_type}
                  onChange={e => setNewDevice(p => ({ ...p, sensor_type: e.target.value }))}
                >
                  {Object.entries(SENSOR_LABELS).map(([k, v]) =>
                    <option key={k} value={k}>{v}</option>
                  )}
                </select>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn-cancel" onClick={() => setShowAdd(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-register-submit" disabled={adding}>
                  {adding ? 'Registering...' : 'Register'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* States */}
      {loading && <div className="devices-loading">Loading devices...</div>}
      {error   && <div className="devices-error">{error}</div>}

      {/* Device grid — grouped by type */}
      {!loading && devices.length > 0 && (
        <div className="devices-grid">

          {/* LoRa Gateways with their sensor nodes nested underneath */}
          {gateways.map(gw => (
            <div key={gw.device_id} style={{ gridColumn: '1 / -1' }}>
              <DeviceCard device={gw} />
              {sensorNodes.filter(n => n.gateway_device_id === gw.device_id).map(node => (
                <DeviceCard key={node.device_id} device={node} compact />
              ))}
            </div>
          ))}

          {/* Ungrouped LoRa sensor nodes (gateway not yet registered) */}
          {ungroupedNodes.map(node => (
            <div key={node.device_id}>
              <div style={{ fontSize: '0.7rem', color: '#f59e0b', marginBottom: '4px', fontWeight: 600 }}>
                ⚠ Gateway "{node.gateway_device_id || 'unknown'}" not registered
              </div>
              <DeviceCard device={node} />
            </div>
          ))}

          {/* Direct eSIM nodes (old / legacy architecture) */}
          {directEsim.map(device => (
            <DeviceCard key={device.device_id} device={device} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && devices.length === 0 && !error && (
        <div className="devices-empty">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="2" y="7" width="20" height="14" rx="2"/>
            <path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/>
          </svg>
          <h3>No devices registered</h3>
          <p>Click "Register Device" to add your first field transmitter.</p>
        </div>
      )}
    </div>
  );
}
