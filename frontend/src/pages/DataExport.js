import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './DataExport.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function DataExport() {
  const [exportConfig, setExportConfig] = useState({
    gateway_id: '',
    node_id: '',
    hours: '24',
    format: 'csv'
  });
  
  const [gateways, setGateways] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    fetchGateways();
    fetchStats();
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
        params: gatewayId ? { gateway_id: gatewayId } : {}
      });
      setNodes(response.data);
    } catch (err) {
      console.error('Error fetching nodes:', err);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/stats`);
      setStats(response.data);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setExportConfig(prev => ({
      ...prev,
      [name]: value
    }));
    
    if (name === 'gateway_id') {
      fetchNodes(value);
      setExportConfig(prev => ({ ...prev, node_id: '' }));
    }
  };

  const exportToCSV = (data) => {
    if (data.length === 0) {
      setMessage({ type: 'error', text: 'No data to export' });
      return;
    }

    // Get all unique keys from all records
    const allKeys = new Set();
    data.forEach(item => {
      Object.keys(item).forEach(key => allKeys.add(key));
      if (item.measurements) {
        Object.keys(item.measurements).forEach(key => allKeys.add(`measurements_${key}`));
      }
    });

    const headers = Array.from(allKeys).filter(k => k !== 'measurements');
    const csvContent = [
      headers.join(','),
      ...data.map(item => {
        return headers.map(header => {
          if (header.startsWith('measurements_')) {
            const key = header.replace('measurements_', '');
            return item.measurements?.[key] || '';
          }
          const value = item[header];
          if (value === null || value === undefined) return '';
          if (typeof value === 'string' && value.includes(',')) {
            return `"${value}"`;
          }
          return value;
        }).join(',');
      })
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `lorawan_export_${new Date().toISOString().slice(0,10)}.csv`;
    link.click();
    
    setMessage({ type: 'success', text: `Exported ${data.length} readings successfully!` });
  };

  const exportToJSON = (data) => {
    if (data.length === 0) {
      setMessage({ type: 'error', text: 'No data to export' });
      return;
    }

    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `lorawan_export_${new Date().toISOString().slice(0,10)}.json`;
    link.click();
    
    setMessage({ type: 'success', text: `Exported ${data.length} readings successfully!` });
  };

  const handleExport = async () => {
    setLoading(true);
    setMessage({ type: '', text: '' });

    try {
      const params = {
        limit: 10000,
        hours: parseInt(exportConfig.hours)
      };
      
      if (exportConfig.gateway_id) params.gateway_id = exportConfig.gateway_id;
      if (exportConfig.node_id) params.node_id = exportConfig.node_id;

      const response = await axios.get(`${API_URL}/api/sensor-data`, { params });
      
      if (exportConfig.format === 'csv') {
        exportToCSV(response.data);
      } else {
        exportToJSON(response.data);
      }
      
    } catch (err) {
      setMessage({ 
        type: 'error', 
        text: 'Failed to fetch data for export' 
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="data-export-page">
      <div className="page-header">
        <h1>Data Export</h1>
        <p>Download sensor readings in CSV or JSON format</p>
      </div>

      {message.text && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage({ type: '', text: '' })}>×</button>
        </div>
      )}

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Total Readings</div>
            <div className="stat-value">{stats.total_readings.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Gateways</div>
            <div className="stat-value">{stats.total_gateways}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Sensor Nodes</div>
            <div className="stat-value">{stats.total_nodes}</div>
          </div>
        </div>
      )}

      <div className="export-form">
        <h3>Export Configuration</h3>

        <div className="form-row">
          <div className="form-group">
            <label>Time Range</label>
            <select
              name="hours"
              value={exportConfig.hours}
              onChange={handleInputChange}
            >
              <option value="1">Last 1 Hour</option>
              <option value="6">Last 6 Hours</option>
              <option value="24">Last 24 Hours</option>
              <option value="168">Last 7 Days</option>
              <option value="720">Last 30 Days</option>
              <option value="8760">Last Year</option>
            </select>
          </div>

          <div className="form-group">
            <label>Format</label>
            <select
              name="format"
              value={exportConfig.format}
              onChange={handleInputChange}
            >
              <option value="csv">CSV (Excel)</option>
              <option value="json">JSON</option>
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Gateway (Optional)</label>
            <select
              name="gateway_id"
              value={exportConfig.gateway_id}
              onChange={handleInputChange}
            >
              <option value="">All Gateways</option>
              {gateways.map(gw => (
                <option key={gw} value={gw}>{gw}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Node (Optional)</label>
            <select
              name="node_id"
              value={exportConfig.node_id}
              onChange={handleInputChange}
              disabled={!exportConfig.gateway_id && nodes.length === 0}
            >
              <option value="">All Nodes</option>
              {nodes.map(node => (
                <option key={node} value={node}>{node}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-actions">
          <button 
            onClick={handleExport} 
            disabled={loading}
            className="btn-export"
          >
            {loading ? 'Exporting...' : 'Download Export'}
          </button>
        </div>
      </div>

      <div className="export-info">
        <h3>Export Information</h3>
        <ul>
          <li><strong>CSV Format:</strong> Compatible with Excel, Google Sheets, and other spreadsheet applications</li>
          <li><strong>JSON Format:</strong> Structured data format ideal for programmatic access and API integration</li>
          <li><strong>Data Included:</strong> All sensor readings including dynamic measurements (NPK, pH, CO2, etc.)</li>
          <li><strong>Maximum Records:</strong> Up to 10,000 readings per export</li>
        </ul>
      </div>
    </div>
  );
}

export default DataExport;
