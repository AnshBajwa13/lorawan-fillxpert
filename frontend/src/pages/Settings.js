import React, { useState, useEffect, useCallback } from 'react';
import './Settings.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function Settings() {
  const [apiKeys,           setApiKeys]           = useState([]);
  const [keysLoading,       setKeysLoading]       = useState(true);
  const [error,             setError]             = useState(null);
  const [showCreateModal,   setShowCreateModal]   = useState(false);
  const [newKeyName,        setNewKeyName]        = useState('');
  const [newKeyExpiration,  setNewKeyExpiration]  = useState('never');
  const [createdKey,        setCreatedKey]        = useState(null);
  const [copied,            setCopied]            = useState(false);

  const getToken = () => localStorage.getItem('access_token');

  // ── Fetch API keys ────────────────────────────────────────────────────
  const fetchApiKeys = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/auth/api-keys`, {
        headers: { Authorization: `Bearer ${getToken()}` }
      });
      if (!res.ok) throw new Error('Failed to fetch API keys');
      const data = await res.json();
      setApiKeys(data.keys || []);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setKeysLoading(false);
    }
  }, []);

  useEffect(() => { fetchApiKeys(); }, [fetchApiKeys]);

  const createApiKey = async () => {
    if (!newKeyName.trim()) return;
    try {
      const res = await fetch(`${API_URL}/api/auth/api-keys`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ key_name: newKeyName, expiration: newKeyExpiration }),
      });
      if (!res.ok) throw new Error('Failed to create API key');
      const data = await res.json();
      setCreatedKey(data);
      setNewKeyName('');
      fetchApiKeys();
    } catch (err) {
      setError(err.message);
    }
  };

  const copyToClipboard = async (text) => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch {}
  };

  const toggleApiKey = async (keyId, isActive) => {
    try {
      await fetch(`${API_URL}/api/auth/api-keys/${keyId}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !isActive }),
      });
      fetchApiKeys();
    } catch (err) { setError(err.message); }
  };

  const deleteApiKey = async (keyId) => {
    if (!window.confirm('Delete this API key?')) return;
    try {
      await fetch(`${API_URL}/api/auth/api-keys/${keyId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      fetchApiKeys();
    } catch (err) { setError(err.message); }
  };

  // ─────────────────────────────────────────────────────────────────────
  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Settings</h1>
        <p>System configuration and integration reference</p>
      </div>

      {/* ── MQTT Topic Structure ─────────────────────────────────────────── */}
      <div className="settings-section">
        <h3>MQTT Topic Structure</h3>
        <div style={{ background:'#18181b', borderRadius:8, padding:'14px 18px' }}>
          <div style={{ fontSize:'0.7rem', fontWeight:600, color:'#a1a1aa', marginBottom:8, textTransform:'uppercase', letterSpacing:'0.05em' }}>
            Topic Structure (agreed with firmware)
          </div>
          <code style={{ color:'#22c55e', fontSize:'0.82rem', fontFamily:'monospace', lineHeight:2.2, display:'block' }}>
            {'{'}<span style={{color:'#fbbf24'}}>location</span>{'}'}/{'{'}<span style={{color:'#60a5fa'}}>device_id</span>{'}'}/telemetry    → sensor readings (device → server)<br/>
            {'{'}<span style={{color:'#fbbf24'}}>location</span>{'}'}/{'{'}<span style={{color:'#60a5fa'}}>device_id</span>{'}'}/config        → config push (server → device, retained)<br/>
            {'{'}<span style={{color:'#fbbf24'}}>location</span>{'}'}/{'{'}<span style={{color:'#60a5fa'}}>device_id</span>{'}'}/config/ack   → device confirms config applied<br/>
            {'{'}<span style={{color:'#fbbf24'}}>location</span>{'}'}/{'{'}<span style={{color:'#60a5fa'}}>device_id</span>{'}'}/status       → online/offline (LWT)
          </code>
        </div>
      </div>

      {/* ── Config Frequency Info ───────────────────────────────────────── */}
      <div className="settings-section">
        <h3>Reading Schedule — Calibration Mode</h3>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>
          <div className="settings-preview">
            <h4>Normal Mode (Schedule)</h4>
            <ul>
              <li>Dashboard pushes config with 1-4 reading times per day</li>
              <li>Device wakes at each scheduled time, takes reading, sleeps</li>
              <li>Trigger field in telemetry will be <code>schedule</code></li>
              <li>Dashboard receives via WebSocket live</li>
            </ul>
          </div>
          <div className="settings-preview">
            <h4>Calibration Mode (Button pressed)</h4>
            <ul>
              <li>Press physical button on device to enter calibration</li>
              <li>Device stays awake for 5 minutes and sends reading every 5-10 seconds</li>
              <li>Same MQTT telemetry topic — dashboard auto-receives via WebSocket</li>
              <li>Trigger field will be <code>manual</code> — table shows "Calibration" badge</li>
              <li>No dashboard action needed — it just works</li>
            </ul>
          </div>
        </div>
      </div>

      {/* ── API Keys — greyed out (reserved) ────────────────────────────── */}
      <div className="settings-section" style={{ opacity:0.5, pointerEvents:'none', userSelect:'none' }}>
        <div className="section-header">
          <div>
            <h3 style={{ margin:0 }}>API Keys <span style={{ fontSize:'0.72rem', background:'#f4f4f5', color:'#71717a', padding:'2px 8px', borderRadius:4, marginLeft:8, fontWeight:400 }}>Reserved</span></h3>
            <p className="section-description">Reserved for future integrations.</p>
          </div>
          <button className="create-key-btn" disabled>Create API Key</button>
        </div>
        <div className="empty-state">
          <p>Not in use in the current architecture.</p>
        </div>
      </div>

      {/* ── Create key modal ────────────────────────────────────────────── */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            {!createdKey ? (
              <>
                <h3>Create API Key</h3>
                <div className="form-group">
                  <label>Key Name</label>
                  <input value={newKeyName} onChange={e => setNewKeyName(e.target.value)} placeholder="e.g., Integration Key" />
                </div>
                <div className="form-group">
                  <label>Expiration</label>
                  <select value={newKeyExpiration} onChange={e => setNewKeyExpiration(e.target.value)}>
                    <option value="never">Never</option>
                    <option value="30d">30 Days</option>
                    <option value="90d">90 Days</option>
                    <option value="1y">1 Year</option>
                  </select>
                </div>
                <div className="modal-actions">
                  <button className="cancel-btn" onClick={() => setShowCreateModal(false)}>Cancel</button>
                  <button className="create-btn" onClick={createApiKey} disabled={!newKeyName.trim()}>Create</button>
                </div>
              </>
            ) : (
              <>
                <h3>API Key Created</h3>
                <div className="warning-box">Copy this key now — it will not be shown again.</div>
                <div className="key-display">
                  <code>{createdKey.api_key}</code>
                  <button className="copy-btn" onClick={() => copyToClipboard(createdKey.api_key)}>
                    {copied ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <div className="modal-actions">
                  <button className="done-btn" onClick={() => { setShowCreateModal(false); setCreatedKey(null); }}>
                    Done
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default Settings;
