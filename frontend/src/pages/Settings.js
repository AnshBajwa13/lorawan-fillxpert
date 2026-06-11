import React from 'react';
import './Settings.css';

function Settings() {
  // ─────────────────────────────────────────────────────────────────────
  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Settings</h1>
        <p>System configuration and integration reference</p>
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

    </div>
  );
}

export default Settings;
