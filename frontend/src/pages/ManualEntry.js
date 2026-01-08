import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './ManualEntry.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function ManualEntry() {
  const [formData, setFormData] = useState({
    gateway_id: '',
    node_id: '',
    timestamp: new Date().toISOString().slice(0, 16),
    humidity: '',
    moisture: '',
    temperature: '',
    battery_voltage: '',
  });
  
  const [customMeasurements, setCustomMeasurements] = useState([]);
  const [gateways, setGateways] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    fetchGateways();
  }, []);

  const fetchGateways = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/gateways`);
      setGateways(response.data);
    } catch (err) {
      console.error('Error fetching gateways:', err);
    }
  };

  const fetchNodes = async (gatewayId) => {
    try {
      const response = await axios.get(`${API_URL}/api/nodes`, {
        params: { gateway_id: gatewayId }
      });
      setNodes(response.data);
    } catch (err) {
      console.error('Error fetching nodes:', err);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    
    if (name === 'gateway_id') {
      fetchNodes(value);
      setFormData(prev => ({ ...prev, node_id: '' }));
    }
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
    setLoading(true);
    setMessage({ type: '', text: '' });

    try {
      // Build payload
      const payload = {
        gateway_id: formData.gateway_id,
        node_id: formData.node_id,
        timestamp: new Date(formData.timestamp).toISOString(),
      };

      // Add standard measurements if provided
      if (formData.humidity) payload.humidity = parseFloat(formData.humidity);
      if (formData.moisture) payload.moisture = parseFloat(formData.moisture);
      if (formData.temperature) payload.temperature = parseFloat(formData.temperature);
      if (formData.battery_voltage) payload.battery_voltage = parseFloat(formData.battery_voltage);

      // Add custom measurements
      if (customMeasurements.length > 0) {
        payload.measurements = {};
        customMeasurements.forEach(m => {
          if (m.key && m.value) {
            payload.measurements[m.key] = isNaN(m.value) ? m.value : parseFloat(m.value);
          }
        });
      }

      await axios.post(`${API_URL}/api/sensor-data`, payload);
      
      setMessage({ type: 'success', text: 'Data submitted successfully!' });
      
      // Reset form
      setFormData({
        gateway_id: formData.gateway_id,
        node_id: formData.node_id,
        timestamp: new Date().toISOString().slice(0, 16),
        humidity: '',
        moisture: '',
        temperature: '',
        battery_voltage: '',
      });
      setCustomMeasurements([]);
      
    } catch (err) {
      setMessage({ 
        type: 'error', 
        text: err.response?.data?.detail || 'Failed to submit data' 
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="manual-entry-page">
      <div className="page-header">
        <h1>Manual Data Entry</h1>
        <p>Manually add sensor readings to the system</p>
      </div>

      {message.text && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage({ type: '', text: '' })}>×</button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="entry-form">
        <div className="form-section">
          <h3>Required Information</h3>
          
          <div className="form-row">
            <div className="form-group">
              <label>Gateway ID *</label>
              <select
                name="gateway_id"
                value={formData.gateway_id}
                onChange={handleInputChange}
                required
              >
                <option value="">Select Gateway</option>
                {gateways.map(gw => (
                  <option key={gw} value={gw}>{gw}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Node ID *</label>
              <select
                name="node_id"
                value={formData.node_id}
                onChange={handleInputChange}
                required
                disabled={!formData.gateway_id}
              >
                <option value="">Select Node</option>
                {nodes.map(node => (
                  <option key={node} value={node}>{node}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
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

        <div className="form-section">
          <h3>Standard Measurements (Optional)</h3>
          
          <div className="form-row">
            <div className="form-group">
              <label>Humidity (%)</label>
              <input
                type="number"
                name="humidity"
                value={formData.humidity}
                onChange={handleInputChange}
                placeholder="0-100"
                min="0"
                max="100"
                step="0.1"
              />
            </div>

            <div className="form-group">
              <label>Moisture (%)</label>
              <input
                type="number"
                name="moisture"
                value={formData.moisture}
                onChange={handleInputChange}
                placeholder="0-100"
                min="0"
                max="100"
                step="0.1"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Temperature (°C)</label>
              <input
                type="number"
                name="temperature"
                value={formData.temperature}
                onChange={handleInputChange}
                placeholder="e.g., 25.5"
                step="0.1"
              />
            </div>

            <div className="form-group">
              <label>Battery Voltage (V)</label>
              <input
                type="number"
                name="battery_voltage"
                value={formData.battery_voltage}
                onChange={handleInputChange}
                placeholder="0-5"
                min="0"
                max="5"
                step="0.01"
              />
            </div>
          </div>
        </div>

        <div className="form-section">
          <div className="section-header">
            <h3>Custom Measurements (Optional)</h3>
            <button
              type="button"
              onClick={addCustomMeasurement}
              className="btn-add"
            >
              + Add Measurement
            </button>
          </div>

          {customMeasurements.map((measurement, index) => (
            <div key={index} className="custom-measurement">
              <input
                type="text"
                placeholder="Parameter name (e.g., npk_n)"
                value={measurement.key}
                onChange={(e) => updateCustomMeasurement(index, 'key', e.target.value)}
              />
              <input
                type="text"
                placeholder="Value"
                value={measurement.value}
                onChange={(e) => updateCustomMeasurement(index, 'value', e.target.value)}
              />
              <button
                type="button"
                onClick={() => removeCustomMeasurement(index)}
                className="btn-remove"
              >
                ×
              </button>
            </div>
          ))}
        </div>

        <div className="form-actions">
          <button type="submit" disabled={loading} className="btn-submit">
            {loading ? 'Submitting...' : 'Submit Data'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default ManualEntry;
