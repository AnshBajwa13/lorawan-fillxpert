import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import './DeviceConfig.css';
import { toLocalStr } from '../utils/time';


const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// No emojis — clean text labels
const SENSOR_OPTIONS = [
  { value: 'moisture',    label: 'Soil Moisture' },
  { value: 'temperature', label: 'Temperature' },
  { value: 'npk',         label: 'NPK (Nitrogen / Phosphorus / Potassium)' },
  { value: 'ph',          label: 'Soil pH' },
  { value: 'ultrasonic',  label: 'Ultrasonic (Water Level)' },
  { value: 'humidity',    label: 'Air Humidity' },
];

// Supported readings per day — user decides; each slot gets a time picker
const FREQ_OPTIONS = [1, 2, 3, 4];

export default function DeviceConfig() {
  const { deviceId } = useParams();
  const navigate     = useNavigate();

  const [device,  setDevice]  = useState(null);
  const [loading, setLoading] = useState(true);
  const [pushing, setPushing] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error,   setError]   = useState(null);
  const [history, setHistory] = useState([]);

  // Form state
  const [sensorType, setSensorType] = useState('moisture');
  const [freq,       setFreq]       = useState(2);
  // reading times — one slot per reading; up to 4
  const [times, setTimes] = useState(['10:00', '14:00', '08:00', '16:00']);

  // ── WebSocket ref (for auto-updating Applied badge on ACK) ────────────
  const wsRef = useRef(null);

  // ── Load device — extracted so Refresh button + WebSocket can call it ──
  const load = useCallback(async () => {
    try {
      const [devRes, histRes] = await Promise.all([
        axios.get(`${API_URL}/api/devices/${deviceId}`),
        axios.get(`${API_URL}/api/devices/${deviceId}/configs`),
      ]);
      const dev = devRes.data;
      setDevice(dev);
      setHistory(histRes.data);

      if (dev.latest_config) {
        const lc = dev.latest_config;
        setSensorType(lc.sensor_type || 'moisture');
        const f = lc.freq || 2;
        setFreq(f);
        const newTimes = [...times];
        if (lc.time1) newTimes[0] = lc.time1;
        if (lc.time2) newTimes[1] = lc.time2;
        setTimes(newTimes);
      } else {
        setSensorType(dev.sensor_type || 'moisture');
      }
    } catch {
      setError('Device not found.');
    } finally {
      setLoading(false);
    }
  }, [deviceId]); // eslint-disable-line

  // Initial load on mount
  useEffect(() => { load(); }, [deviceId]); // eslint-disable-line

  // ── WebSocket: auto-update Applied badge when device sends config ACK ──
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws/realtime';
    const ws = new WebSocket(`${WS_URL}?token=${token}`);
    wsRef.current = ws;

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        // When THIS device sends a config ACK, re-fetch so badge flips to Applied
        if (msg.event === 'config_acked' && msg.device_id === deviceId) {
          load();
        }
      } catch { /* ignore parse errors */ }
    };

    return () => ws.close();
  }, [deviceId, load]);

  // ── Payload preview — format: [sensor:2][freq:2][timeN:4×freq][ver:2] ──
  const buildPayloadPreview = () => {
    const codes = { moisture:'01', temperature:'02', npk:'03', ph:'04', ultrasonic:'05', humidity:'06' };
    const code     = codes[sensorType] || '01';
    const freqStr  = String(freq).padStart(2, '0');
    const nextVer  = String((device?.cfg_version || 0) + 1).padStart(2, '0');
    let slots = '';
    for (let i = 0; i < freq; i++) {
      const [h, m] = times[i].split(':');
      slots += h.padStart(2,'0') + m.padStart(2,'0');
    }
    return `${code}${freqStr}${slots}${nextVer}`;
  };

  const updateTime = (idx, value) => {
    const t = [...times]; t[idx] = value; setTimes(t);
  };

  // ── Push config ─────────────────────────────────────────────────────
  const handlePush = async (e) => {
    e.preventDefault();
    setPushing(true); setSuccess(null); setError(null);
    try {
      const body = {
        sensor_type: sensorType,
        freq,
        time1: times[0],
        time2: freq >= 2 ? times[1] : null,
        time3: freq >= 3 ? times[2] : null,
        time4: freq >= 4 ? times[3] : null,
      };
      const res = await axios.post(`${API_URL}/api/devices/${deviceId}/config`, body);
      setSuccess(res.data.message || `Config v${res.data.cfg_version} pushed successfully.`);

      const [devRes, histRes] = await Promise.all([
        axios.get(`${API_URL}/api/devices/${deviceId}`),
        axios.get(`${API_URL}/api/devices/${deviceId}/configs`),
      ]);
      setDevice(devRes.data);
      setHistory(histRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to push config.');
    } finally {
      setPushing(false);
    }
  };

  if (loading) return (
    <div className="dconfig-page">
      <button className="back-btn" onClick={() => navigate('/devices')}>Back to Fleet</button>
      <div className="dconfig-loading">Loading device...</div>
    </div>
  );

  if (!device) return (
    <div className="dconfig-page">
      <button className="back-btn" onClick={() => navigate('/devices')}>Back to Fleet</button>
      <div className="dconfig-error">{error || 'Device not found. It may have been deleted or does not belong to your account.'}</div>
    </div>
  );

  const payloadPreview = buildPayloadPreview();

  return (
    <div className="dconfig-page">

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '16px' }}>
        <button className="back-btn" onClick={() => navigate('/devices')} style={{ margin: 0 }}>
          Back to Fleet
        </button>
        <button
          className="back-btn"
          onClick={load}
          style={{ margin: 0, background: '#f4f4f5', color: '#3f3f46' }}
        >
          Refresh
        </button>
      </div>

      {/* Device header */}
      <div className="dconfig-header">
        <div>
          <h1>
            {device.device_id}
            <span className={`status-pill ${device.is_online ? 'pill-online' : 'pill-offline'}`}>
              {device.is_online ? 'Online' : 'Offline'}
            </span>
          </h1>
          <p>{device.name} · {device.location}</p>
        </div>
        <div className="device-meta">
          <div className="meta-item">
            <span>Battery</span>
            <strong style={{ color: device.battery_pct > 20 ? '#16a34a' : '#dc2626' }}>
              {device.battery_pct != null ? `${device.battery_pct}%` : '—'}
            </strong>
          </div>
          <div className="meta-item">
            <span>Signal</span>
            <strong>{device.rssi_dbm != null ? `${device.rssi_dbm} dBm` : '—'}</strong>
          </div>
          <div className="meta-item">
            <span>Config</span>
            <strong>
              v{device.cfg_version}
              {device.config_applied
                ? <span className="ack-badge">Applied</span>
                : <span className="pending-badge">Pending ACK</span>}
            </strong>
          </div>
        </div>
      </div>

      <div className="dconfig-layout">

        {/* Config form */}
        <div className="dconfig-form-card">
          <h2>Push New Configuration</h2>
          <p className="form-hint">
            Sent as a <strong>retained MQTT message</strong> to <code>{device.location}/{deviceId}/config</code>.
            Device receives it on next wakeup — no button press needed.
          </p>

          {success && <div className="alert-success">{success}</div>}
          {error   && <div className="alert-error">{error}</div>}

          <form onSubmit={handlePush}>

            {/* Sensor type */}
            <div className="field">
              <label>Sensor Type (currently attached to transmitter)</label>
              <select value={sensorType} onChange={e => setSensorType(e.target.value)}>
                {SENSOR_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <p className="field-hint">Update this when you swap the physical sensor. Dashboard will update all config and labels.</p>
            </div>

            {/* Readings per day */}
            <div className="field">
              <label>Readings Per Day (user-configurable)</label>
              <div className="freq-buttons">
                {FREQ_OPTIONS.map(n => (
                  <button key={n} type="button"
                    className={freq === n ? 'freq-btn active' : 'freq-btn'}
                    onClick={() => setFreq(n)}>
                    {n}x
                  </button>
                ))}
              </div>
              <p className="field-hint">Choose how many readings the device takes each day. Each reading has its own schedule time below.</p>
            </div>

            {/* Time slots — one per selected freq */}
            {[...Array(freq)].map((_, i) => (
              <div key={i} className="field">
                <label>Reading {i + 1} — Time of Day</label>
                <input type="time" value={times[i]} onChange={e => updateTime(i, e.target.value)} />
              </div>
            ))}

            {/* Payload preview */}
            <div className="payload-preview">
              <span className="payload-label">
                Firmware Payload String ({2 + 2 + (freq * 4) + 2}-char · dynamic)
              </span>
              <div className="payload-grid">
                <div className="payload-box">
                  <span className="payload-value">{payloadPreview}</span>
                  <span className="payload-desc">sent via MQTT retained</span>
                </div>
                <div className="payload-breakdown">
                  <span>Topic: <code>{device.location}/{deviceId}/config</code></span>
                  <span>Retained: yes · QoS: 1</span>
                  <span>Sensor code: {payloadPreview.slice(0,2)}</span>
                  <span>Freq: {payloadPreview.slice(2,4)} ({freq}×/day)</span>
                  {[...Array(freq)].map((_, i) => (
                    <span key={i}>Slot {i+1}: {times[i]}</span>
                  ))}
                  <span>Version: v{(device?.cfg_version || 0) + 1} → last 2 chars = {payloadPreview.slice(-2)}</span>
                </div>
              </div>
            </div>

            <button type="submit" className="btn-push" disabled={pushing}>
              {pushing ? 'Pushing...' : 'Push Config to Device'}
            </button>
          </form>
        </div>

        {/* Config history */}
        <div className="dconfig-history-card">
          <h2>Config History</h2>
          {history.length === 0 && <p className="no-history">No config pushed yet.</p>}
          {history.map(cfg => (
            <div key={cfg.id} className="history-row">
              <div className="history-version">v{cfg.cfg_version}</div>
              <div className="history-details">
                  <span>
                    {cfg.sensor_type}
                    {' · '}{cfg.time1}
                    {cfg.time2 ? ` & ${cfg.time2}` : ''}
                    {cfg.time3 ? ` & ${cfg.time3}` : ''}
                    {cfg.time4 ? ` & ${cfg.time4}` : ''}
                    {' · '}{cfg.freq}×/day
                  </span>
                <code>{cfg.payload_str}</code>
                <small>Pushed: {toLocalStr(cfg.published_at)}</small>
              </div>
              <div className="history-ack">
                {cfg.ack_received
                  ? <span className="ack-ok">Applied</span>
                  : <span className="ack-wait">Waiting</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
