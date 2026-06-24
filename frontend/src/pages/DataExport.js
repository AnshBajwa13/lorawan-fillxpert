import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './DataExport.css';
import { toLocalStr } from '../utils/time';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function DataExport() {
  const [exportConfig, setExportConfig] = useState({
    location: '',
    device_id: '',
    hours: 'all',   // 'all' = no time limit, or number string like '24', '720'
    format: 'csv',
  });

  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    fetchDevices();
    fetchStats();
  }, []);

  const fetchDevices = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/devices`);
      setDevices(res.data);
    } catch (err) {
      console.error('Failed to load devices:', err);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/stats`);
      setStats(res.data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setExportConfig(prev => ({ ...prev, [name]: value }));
  };

  // ── CSV export helper ─────────────────────────────────────────────────
  const exportToCSV = (data) => {
    if (data.length === 0) { setMessage({ type: 'error', text: 'No data to export' }); return; }
    const allKeys = new Set();
    data.forEach(item => {
      Object.keys(item).forEach(k => allKeys.add(k));
      if (item.measurements) Object.keys(item.measurements).forEach(k => allKeys.add(`meas_${k}`));
    });
    const headers = Array.from(allKeys).filter(k => k !== 'measurements');
    const csvContent = [
      headers.join(','),
      ...data.map(item =>
        headers.map(h => {
          if (h.startsWith('meas_')) {
            const k = h.replace('meas_', '');
            return item.measurements?.[k] ?? '';
          }
          // Format timestamp to human-readable IST
          if (h === 'timestamp') return `"${toLocalStr(item[h])}"`;
          const v = item[h];
          if (v === null || v === undefined) return '';
          if (typeof v === 'string' && v.includes(',')) return `"${v}"`;
          return v;
        }).join(',')
      )
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `sensorvault-export-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    setMessage({ type: 'success', text: `Exported ${data.length} readings as CSV.` });
  };

  const exportToJSON = (data) => {
    if (data.length === 0) { setMessage({ type: 'error', text: 'No data to export' }); return; }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `sensorvault-export-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    setMessage({ type: 'success', text: `Exported ${data.length} readings as JSON.` });
  };

  // ── Main export handler ───────────────────────────────────────────────
  const handleExport = async () => {
    setLoading(true);
    setMessage({ type: '', text: '' });
    try {
      // limit 50000 — enough for 45 years of 3 readings/day on 1 device
      const params = { limit: 50000 };
      // Only pass hours param if not "All Time"
      if (exportConfig.hours && exportConfig.hours !== 'all') {
        params.hours = parseInt(exportConfig.hours);
      }
      if (exportConfig.location)  params.gateway_id = exportConfig.location;
      if (exportConfig.device_id) params.node_id    = exportConfig.device_id;

      const res = await axios.get(`${API_URL}/api/sensor-data`, { params });
      exportConfig.format === 'csv' ? exportToCSV(res.data) : exportToJSON(res.data);
    } catch {
      setMessage({ type: 'error', text: 'Failed to fetch data for export.' });
    } finally {
      setLoading(false);
    }
  };

  // ── Derive unique locations from devices list ─────────────────────────
  const locations = [...new Set(devices.map(d => d.location).filter(Boolean))];
  const filteredDevices = exportConfig.location
    ? devices.filter(d => d.location === exportConfig.location)
    : devices;

  return (
    <div className="data-export-page">
      <div className="page-header">
        <h1>Data Export</h1>
        <p>Download sensor readings as CSV or JSON</p>
      </div>

      {message.text && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage({ type: '', text: '' })}>×</button>
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Total Readings</div>
            <div className="stat-value">{stats.total_readings.toLocaleString()}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Locations</div>
            <div className="stat-value">{stats.total_gateways}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Devices</div>
            <div className="stat-value">{stats.total_nodes}</div>
          </div>
        </div>
      )}

      {/* Export form */}
      <div className="export-form">
        <h3>Export Configuration</h3>

        <div className="form-row">
          <div className="form-group">
            <label>Time Range</label>
            <select name="hours" value={exportConfig.hours} onChange={handleInputChange}>
              <option value="all">All Time (every reading)</option>
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
            <select name="format" value={exportConfig.format} onChange={handleInputChange}>
              <option value="csv">CSV (Excel / Sheets)</option>
              <option value="json">JSON</option>
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Location (Optional)</label>
            <select name="location" value={exportConfig.location} onChange={handleInputChange}>
              <option value="">All Locations</option>
              {locations.map(loc => <option key={loc} value={loc}>{loc}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label>Device (Optional)</label>
            <select
              name="device_id"
              value={exportConfig.device_id}
              onChange={handleInputChange}
              disabled={filteredDevices.length === 0}
            >
              <option value="">All Devices</option>
              {filteredDevices.map(d => (
                <option key={d.device_id} value={d.device_id}>
                  {d.device_id}{d.name ? ` — ${d.name}` : ''}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-actions">
          <button onClick={handleExport} disabled={loading} className="btn-export">
            {loading ? 'Exporting...' : 'Download Export'}
          </button>
        </div>
      </div>

      {/* Info */}
      <div className="export-info">
        <h3>Export Notes</h3>
        <ul>
          <li><strong>CSV</strong> — Compatible with Excel, Google Sheets</li>
          <li><strong>JSON</strong> — Structured format for programmatic use</li>
          <li><strong>Custom fields</strong> — NPK, pH and other sensor-specific values are included</li>
          <li><strong>Limit</strong> — Up to 10,000 readings per export</li>
        </ul>
      </div>
    </div>
  );
}

export default DataExport;
