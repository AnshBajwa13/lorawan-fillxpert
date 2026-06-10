import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import './Devices.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_URL  = (API_URL.replace('http', 'ws')) + '/ws/realtime';

// No emojis — plain text labels
const SENSOR_LABELS = {
  moisture:    'Moisture',
  temperature: 'Temperature',
  npk:         'NPK',
  ph:          'pH',
  ultrasonic:  'Ultrasonic',
  humidity:    'Humidity',
};

export default function Devices() {
  const [devices, setDevices]     = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [showAdd, setShowAdd]     = useState(false);
  const [addError, setAddError]   = useState('');
  const [newDevice, setNewDevice] = useState({ device_id: '', name: '', location: '', sensor_type: 'moisture' });
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
      const res = await axios.post(`${API_URL}/api/devices`, newDevice);
      setDevices(prev => [res.data, ...prev]);
      setShowAdd(false);
      setNewDevice({ device_id: '', name: '', location: '', sensor_type: 'moisture' });
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
                  required placeholder="e.g. SNR001"
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

      {/* Device grid */}
      {!loading && devices.length > 0 && (
        <div className="devices-grid">
          {devices.map(device => (
            <div
              key={device.device_id}
              className={`device-card ${device.is_online ? 'online' : 'offline'}`}
              onClick={() => navigate(`/devices/${device.device_id}/config`)}
            >
              <div className="device-card-header">
                <div>
                  <div className="device-name">{device.name || device.device_id}</div>
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
                <button
                  className="btn-configure"
                  onClick={e => { e.stopPropagation(); navigate(`/devices/${device.device_id}/config`); }}
                >
                  Configure
                </button>
              </div>
            </div>
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
