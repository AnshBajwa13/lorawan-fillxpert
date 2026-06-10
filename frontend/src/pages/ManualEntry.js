import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './ManualEntry.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function ManualEntry() {
  const [devices, setDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);

  const [formData, setFormData] = useState({
    timestamp:       new Date().toISOString().slice(0, 16),
    humidity:        '',
    moisture:        '',
    temperature:     '',
    battery_voltage: '',
  });

  const [customMeasurements, setCustomMeasurements] = useState([]);
  const [loading, setLoading]   = useState(false);
  const [message, setMessage]   = useState({ type: '', text: '' });

  // ── Fetch registered devices (replaces old gateway/node calls) ──
  useEffect(() => {
    fetchDevices();
  }, []);

  const fetchDevices = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/devices`);
      setDevices(res.data);
    } catch (err) {
      console.error('Failed to load devices:', err);
    }
  };

  const handleDeviceChange = (e) => {
    const deviceId = e.target.value;
    const device   = devices.find(d => d.device_id === deviceId) || null;
    setSelectedDevice(device);
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const addCustomMeasurement = () => {
    setCustomMeasurements([...customMeasurements, { key: '', value: '' }]);
  };

  const removeCustomMeasurement = (index) => {
    setCustomMeasurements(customMeasurements.filter((_, i) => i !== index));
  };

  const updateCustomMeasurement = (index, field, value) => {
    const updated = [...customMeasurements];
    updated[index][field] = value;
    setCustomMeasurements(updated);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedDevice) {
      setMessage({ type: 'error', text: 'Please select a device.' });
      return;
    }

    setLoading(true);
    setMessage({ type: '', text: '' });

    try {
      // gateway_id = device location (matches MQTT topic), node_id = device_id
      const payload = {
        gateway_id: selectedDevice.location,
        node_id:    selectedDevice.device_id,
        timestamp:  new Date(formData.timestamp).toISOString(),
      };

      if (formData.humidity)        payload.humidity        = parseFloat(formData.humidity);
      if (formData.moisture)        payload.moisture        = parseFloat(formData.moisture);
      if (formData.temperature)     payload.temperature     = parseFloat(formData.temperature);
      if (formData.battery_voltage) payload.battery_voltage = parseFloat(formData.battery_voltage);

      if (customMeasurements.length > 0) {
        payload.measurements = {};
        customMeasurements.forEach(m => {
          if (m.key && m.value) {
            payload.measurements[m.key] = isNaN(m.value) ? m.value : parseFloat(m.value);
          }
        });
      }

      await axios.post(`${API_URL}/api/sensor-data`, payload);

      setMessage({ type: 'success', text: `Reading saved for device ${selectedDevice.device_id} (${selectedDevice.name || ''})` });

      // Reset measurement fields only; keep device selection for quick re-entry
      setFormData({
        timestamp:       new Date().toISOString().slice(0, 16),
        humidity:        '',
        moisture:        '',
        temperature:     '',
        battery_voltage: '',
      });
      setCustomMeasurements([]);

    } catch (err) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to submit data',
      });
    } finally {
      setLoading(false);
    }
  };

  const sensorLabel = selectedDevice?.sensor_type
    ? selectedDevice.sensor_type.charAt(0).toUpperCase() + selectedDevice.sensor_type.slice(1)
    : null;

  return (
    <div className="manual-entry-page">
      <div className="page-header">
        <h1>Manual Data Entry</h1>
        <p>Add a reading manually for a registered field device</p>
      </div>

      {message.text && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage({ type: '', text: '' })}>×</button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="entry-form">

        {/* ── Device selection ── */}
        <div className="form-section">
          <h3>Select Device</h3>

          <div className="form-group-full">
            <label>Registered Device *</label>
            <select
              value={selectedDevice?.device_id || ''}
              onChange={handleDeviceChange}
              required
            >
              <option value="">— Choose a device —</option>
              {devices.map(d => (
                <option key={d.device_id} value={d.device_id}>
                  {d.device_id}{d.name ? ` — ${d.name}` : ''} ({d.location})
                </option>
              ))}
            </select>
            {selectedDevice && (
              <p className="device-hint">
                Location: <strong>{selectedDevice.location}</strong>
                {sensorLabel && <> &nbsp;·&nbsp; Sensor: <strong>{sensorLabel}</strong></>}
                &nbsp;·&nbsp; Topic: <code>{selectedDevice.location}/{selectedDevice.device_id}/telemetry</code>
              </p>
            )}
            {devices.length === 0 && (
              <p className="device-hint">No devices registered yet. Go to Devices → Register a transmitter first.</p>
            )}
          </div>

          <div className="form-group-full">
            <label>Timestamp *</label>
            <input
              type="datetime-local"
              name="timestamp"
              value={formData.timestamp}
              onChange={handleInputChange}
              required
            />
          </div>
        </div>

        {/* ── Standard measurements ── */}
        <div className="form-section">
          <h3>Standard Measurements (Optional)</h3>

          <div className="form-row">
            <div className="form-group">
              <label>Humidity (%)</label>
              <input
                type="number" name="humidity"
                value={formData.humidity} onChange={handleInputChange}
                placeholder="0 – 100" min="0" max="100" step="0.1"
              />
            </div>
            <div className="form-group">
              <label>Moisture (%)</label>
              <input
                type="number" name="moisture"
                value={formData.moisture} onChange={handleInputChange}
                placeholder="0 – 100" min="0" max="100" step="0.1"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Temperature (°C)</label>
              <input
                type="number" name="temperature"
                value={formData.temperature} onChange={handleInputChange}
                placeholder="e.g., 25.5" step="0.1"
              />
            </div>
            <div className="form-group">
              <label>Battery Voltage (V)</label>
              <input
                type="number" name="battery_voltage"
                value={formData.battery_voltage} onChange={handleInputChange}
                placeholder="0 – 5" min="0" max="5" step="0.01"
              />
            </div>
          </div>
        </div>

        {/* ── Custom measurements ── */}
        <div className="form-section">
          <div className="section-header">
            <h3>Custom Measurements (Optional)</h3>
            <button type="button" onClick={addCustomMeasurement} className="btn-add">
              + Add Field
            </button>
          </div>

          {customMeasurements.map((m, index) => (
            <div key={index} className="custom-measurement">
              <input
                type="text"
                placeholder="Parameter (e.g. npk_n)"
                value={m.key}
                onChange={(e) => updateCustomMeasurement(index, 'key', e.target.value)}
              />
              <input
                type="text"
                placeholder="Value"
                value={m.value}
                onChange={(e) => updateCustomMeasurement(index, 'value', e.target.value)}
              />
              <button type="button" onClick={() => removeCustomMeasurement(index)} className="btn-remove">
                ×
              </button>
            </div>
          ))}

          {customMeasurements.length === 0 && (
            <p style={{ fontSize: '0.82rem', color: '#a1a1aa' }}>
              Add extra fields for NPK, pH, or any sensor-specific values.
            </p>
          )}
        </div>

        {/* ── Submit ── */}
        <div className="form-actions">
          <button type="submit" disabled={loading || !selectedDevice} className="btn-submit">
            {loading ? 'Saving...' : 'Save Reading'}
          </button>
        </div>

      </form>
    </div>
  );
}

export default ManualEntry;
