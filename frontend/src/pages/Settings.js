import React from 'react';
import './Settings.css';

function Settings() {
  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Settings</h1>
        <p>Configure system settings and preferences</p>
      </div>

      <div className="settings-section">
        <h3>System Settings</h3>
        <p className="coming-soon">Settings page is under development...</p>
        
        <div className="settings-preview">
          <h4>Planned Features:</h4>
          <ul>
            <li>Gateway and node management</li>
            <li>User preferences</li>
            <li>System backup and restore</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default Settings;
