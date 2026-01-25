import React, { useState, useEffect, useCallback } from 'react';
import './Settings.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function Settings() {
  const [apiKeys, setApiKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyExpiration, setNewKeyExpiration] = useState('never');
  const [createdKey, setCreatedKey] = useState(null);
  const [copied, setCopied] = useState(false);

  const getToken = () => localStorage.getItem('access_token');

  // Fetch API keys
  const fetchApiKeys = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/auth/api-keys`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`
        }
      });
      
      if (!response.ok) throw new Error('Failed to fetch API keys');
      
      const data = await response.json();
      setApiKeys(data.keys || []);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApiKeys();
  }, [fetchApiKeys]);

  // Create new API key
  const createApiKey = async () => {
    if (!newKeyName.trim()) return;
    
    try {
      const response = await fetch(`${API_URL}/api/auth/api-keys`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          key_name: newKeyName,
          expiration: newKeyExpiration
        })
      });
      
      if (!response.ok) throw new Error('Failed to create API key');
      
      const data = await response.json();
      setCreatedKey(data);
      setNewKeyName('');
      fetchApiKeys();
    } catch (err) {
      setError(err.message);
    }
  };

  // Copy key to clipboard
  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  // Toggle key active status
  const toggleKeyStatus = async (keyId, currentlyActive) => {
    const endpoint = currentlyActive ? 'deactivate' : 'activate';
    try {
      const response = await fetch(`${API_URL}/api/auth/api-keys/${keyId}/${endpoint}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${getToken()}`
        }
      });
      
      if (!response.ok) throw new Error(`Failed to ${endpoint} key`);
      
      fetchApiKeys();
    } catch (err) {
      setError(err.message);
    }
  };

  // Delete API key
  const deleteApiKey = async (keyId, keyName) => {
    if (!window.confirm(`Are you sure you want to permanently delete "${keyName}"?`)) return;
    
    try {
      const response = await fetch(`${API_URL}/api/auth/api-keys/${keyId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${getToken()}`
        }
      });
      
      if (!response.ok) throw new Error('Failed to delete API key');
      
      fetchApiKeys();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Settings</h1>
        <p>Manage your API keys and system preferences</p>
      </div>

      {/* API Keys Section */}
      <div className="settings-section">
        <div className="section-header">
          <div>
            <h3> API Keys</h3>
            <p className="section-description">
              Use API keys for your IoT gateways. They don't expire (unless you set one).
            </p>
          </div>
          <button 
            className="create-key-btn"
            onClick={() => setShowCreateModal(true)}
          >
            + Create New Key
          </button>
        </div>

        {error && <div className="error-message">{error}</div>}

        {loading ? (
          <div className="loading">Loading API keys...</div>
        ) : apiKeys.length === 0 ? (
          <div className="empty-state">
            <p>No API keys yet. Create one to use with your gateway!</p>
            <div className="example-usage">
              <strong>Example usage:</strong>
              <code>
                curl -X POST https://your-api.com/api/sensor-data \<br/>
                &nbsp;&nbsp;-H "X-API-Key: lora_your_key_here" \<br/>
                &nbsp;&nbsp;-H "Content-Type: application/json" \<br/>
                &nbsp;&nbsp;-d '{"{"}...{"}"}'
              </code>
            </div>
          </div>
        ) : (
          <div className="api-keys-list">
            {apiKeys.map(key => (
              <div key={key.id} className={`api-key-item ${!key.is_active ? 'inactive' : ''}`}>
                <div className="key-info">
                  <div className="key-name">{key.key_name}</div>
                  <div className="key-preview">{key.key_preview}</div>
                  <div className="key-meta">
                    Created: {new Date(key.created_at).toLocaleDateString()}
                    {key.last_used_at && (
                      <> • Last used: {new Date(key.last_used_at).toLocaleDateString()}</>
                    )}
                    {key.expires_at && key.expires_at !== 'Never' && (
                      <> • Expires: {new Date(key.expires_at).toLocaleDateString()}</>
                    )}
                    {key.expires_at === 'Never' && <> • Never expires</>}
                  </div>
                </div>
                <div className="key-actions">
                  <span className={`status-badge ${key.is_active ? 'active' : 'inactive'}`}>
                    {key.is_active ? 'Active' : 'Inactive'}
                  </span>
                  <button 
                    className="action-btn toggle"
                    onClick={() => toggleKeyStatus(key.id, key.is_active)}
                  >
                    {key.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                  <button 
                    className="action-btn delete"
                    onClick={() => deleteApiKey(key.id, key.key_name)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Key Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => {
          setShowCreateModal(false);
          setCreatedKey(null);
        }}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            {!createdKey ? (
              <>
                <h3>Create New API Key</h3>
                <div className="form-group">
                  <label>Key Name</label>
                  <input
                    type="text"
                    placeholder="e.g., Gateway 1, Test Key"
                    value={newKeyName}
                    onChange={e => setNewKeyName(e.target.value)}
                    autoFocus
                  />
                </div>
                <div className="form-group">
                  <label>Expiration</label>
                  <select 
                    value={newKeyExpiration}
                    onChange={e => setNewKeyExpiration(e.target.value)}
                  >
                    <option value="never">Never (Recommended for gateways)</option>
                    <option value="1_year">1 Year</option>
                    <option value="30_days">30 Days</option>
                    <option value="7_days">7 Days (For testing)</option>
                  </select>
                </div>
                <div className="modal-actions">
                  <button 
                    className="cancel-btn"
                    onClick={() => setShowCreateModal(false)}
                  >
                    Cancel
                  </button>
                  <button 
                    className="create-btn"
                    onClick={createApiKey}
                    disabled={!newKeyName.trim()}
                  >
                    Create Key
                  </button>
                </div>
              </>
            ) : (
              <>
                <h3>✔️ API Key Created!</h3>
                <div className="warning-box">
                   Copy this key now! It won't be shown again.
                </div>
                <div className="key-display">
                  <code>{createdKey.key_value}</code>
                  <button 
                    className="copy-btn"
                    onClick={() => copyToClipboard(createdKey.key_value)}
                  >
                    {copied ? '✓ Copied!' : 'Copy'}
                  </button>
                </div>
                <div className="key-details">
                  <p><strong>Name:</strong> {createdKey.key_name}</p>
                  <p><strong>Expires:</strong> {createdKey.expires_at}</p>
                </div>
                <div className="modal-actions">
                  <button 
                    className="done-btn"
                    onClick={() => {
                      setShowCreateModal(false);
                      setCreatedKey(null);
                    }}
                  >
                    Done
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Other Settings Section */}
      <div className="settings-section">
        <h3> System Settings</h3>
        <p className="coming-soon">More settings coming soon...</p>
        <div className="settings-preview">
          <h4>Planned Features:</h4>
          <ul>
            <li>Gateway and node management</li>
            <li>Alert thresholds configuration</li>
            <li>Data retention settings</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default Settings;
