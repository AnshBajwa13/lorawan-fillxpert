import React, { useState, useEffect, useCallback, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import './App.css';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import ManualEntry from './pages/ManualEntry';
import DataExport from './pages/DataExport';
import Settings from './pages/Settings';
import Login from './pages/Login';
import Register from './pages/Register';
import Devices from './pages/Devices';
import DeviceConfig from './pages/DeviceConfig';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_URL  = (API_URL.replace('http', 'ws')) + '/ws/realtime';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser,     setCurrentUser]     = useState(null);
  const [authLoading,     setAuthLoading]     = useState(true);

  // Sensor data
  const [data,         setData]         = useState([]);
  const [filteredData, setFilteredData] = useState([]);

  // Filters — renamed from gateway/node → location/device
  const [locations,        setLocations]        = useState([]);
  const [deviceIds,        setDeviceIds]        = useState([]);
  const [selectedLocation, setSelectedLocation] = useState('');
  const [selectedDevice,   setSelectedDevice]   = useState('');
  const [searchTerm,       setSearchTerm]       = useState('');
  const [timeRange,        setTimeRange]        = useState('24');

  // UI state
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState(null);
  const [stats,         setStats]         = useState(null);
  const [apiStatus,     setApiStatus]     = useState('checking');
  const [mqttStatus,    setMqttStatus]    = useState('disconnected'); // WebSocket = MQTT bridge
  const [lastUpdate,    setLastUpdate]    = useState(null);
  const [isRefreshing,  setIsRefreshing]  = useState(false);
  const [sidebarOpen,   setSidebarOpen]   = useState(true);
  const [historicalData,setHistoricalData]= useState({});

  // WebSocket ref
  const wsRef     = useRef(null);
  const wsRetryRef= useRef(null);

  // ── Axios interceptor (auth token) ────────────────────────────────────
  useEffect(() => {
    const id = axios.interceptors.request.use(
      (cfg) => {
        const token = localStorage.getItem('access_token');
        if (token && !cfg.url?.includes('/auth/login') && !cfg.url?.includes('/auth/register')) {
          cfg.headers.Authorization = `Bearer ${token}`;
        }
        return cfg;
      },
      (err) => Promise.reject(err)
    );
    return () => axios.interceptors.request.eject(id);
  }, []);

  // ── Auth check ────────────────────────────────────────────────────────
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const res = await axios.get(`${API_URL}/api/auth/me`);
          setIsAuthenticated(true);
          setCurrentUser(res.data);
        } catch {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          setIsAuthenticated(false);
        }
      }
      setAuthLoading(false);
    };
    checkAuth();
  }, []);

  // ── Build sparkline history ──────────────────────────────────────────
  const buildHistoricalData = useCallback((readings) => {
    const history = {};
    readings.forEach(r => {
      const key = `${r.gateway_id}-${r.node_id}`;
      if (!history[key]) {
        history[key] = { humidity: [], moisture: [], temperature: [], battery_voltage: [] };
      }
      const push = (arr, val) => { if (val != null) { arr.push(val); if (arr.length > 10) arr.shift(); } };
      push(history[key].humidity,        r.humidity);
      push(history[key].moisture,        r.moisture);
      push(history[key].temperature,     r.temperature);
      push(history[key].battery_voltage, r.battery_voltage);
    });
    return history;
  }, []);

  // ── Initial data fetch (runs once on login) ───────────────────────────
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setIsRefreshing(true);
      setError(null);

      const [readingsRes, statsRes] = await Promise.all([
        axios.get(`${API_URL}/api/sensor-data`, { params: { limit: 200 } }),
        axios.get(`${API_URL}/api/stats`),
      ]);

      const readings = readingsRes.data;
      setData(readings);
      setStats(statsRes.data);
      setHistoricalData(buildHistoricalData(readings));

      // Extract unique location/device values (gateway_id = location, node_id = device)
      setLocations([...new Set(readings.map(r => r.gateway_id))]);
      setDeviceIds([...new Set(readings.map(r => r.node_id))]);

      setApiStatus('connected');
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Fetch error:', err);
      setError('Failed to fetch sensor data. Check that the backend is running.');
      setApiStatus('disconnected');
    } finally {
      setLoading(false);
      setTimeout(() => setIsRefreshing(false), 400);
    }
  }, [buildHistoricalData]);

  // ── WebSocket — live MQTT-to-browser bridge ───────────────────────────
  //
  //  Flow: Device → MQTT (Mosquitto) → Backend (mqtt_handler.py)
  //        → WebSocket (/ws/realtime) → This browser
  //
  //  Events we handle:
  //    new_reading  : prepend live reading to table, update sparkline
  //    device_status: (handled by Devices.js independently)
  //    config_acked : (handled by DeviceConfig.js independently)
  //
  const connectWebSocket = useCallback(() => {
    if (!isAuthenticated) return;

    const token = localStorage.getItem('access_token');
    const ws = new WebSocket(`${WS_URL}?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setMqttStatus('connected');
      console.log('[WS] Connected to backend MQTT bridge');
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);

        if (msg.event === 'new_reading') {
          const { device_id, location, timestamp, readings: vals, battery_mv, rssi_dbm } = msg;

          // Build a pseudo-reading row matching the REST API shape
          const newReading = {
            id:              Date.now(),        // temp id for key
            gateway_id:      location,          // location = gateway_id in DB
            node_id:         device_id,
            timestamp:       timestamp,
            humidity:        vals?.humidity    ?? null,
            moisture:        vals?.moisture    ?? null,
            temperature:     vals?.temperature ?? null,
            battery_voltage: battery_mv ? battery_mv / 1000 : null,
            measurements:    vals,
            _live:           true,              // flag for optional "LIVE" badge in table
            _calibration:    msg.trigger === 'manual', // calibration mode reading
          };

          // Prepend to data (newest first) — cap at 300 rows to avoid mem growth
          setData(prev => {
            const updated = [newReading, ...prev].slice(0, 300);
            return updated;
          });

          // Update sparkline history
          setHistoricalData(prev => {
            const key = `${location}-${device_id}`;
            const grp = prev[key] || { humidity:[], moisture:[], temperature:[], battery_voltage:[] };
            const push = (arr, val) => { if (val != null) { const a=[...arr,val]; if(a.length>10)a.shift(); return a; } return arr; };
            return {
              ...prev,
              [key]: {
                humidity:        push(grp.humidity,        newReading.humidity),
                moisture:        push(grp.moisture,        newReading.moisture),
                temperature:     push(grp.temperature,     newReading.temperature),
                battery_voltage: push(grp.battery_voltage, newReading.battery_voltage),
              }
            };
          });

          // Update location/device filter lists if new
          setLocations(prev => prev.includes(location)    ? prev : [...prev, location]);
          setDeviceIds( prev => prev.includes(device_id)  ? prev : [...prev, device_id]);
          setLastUpdate(new Date());

          // Refresh stats counter
          setStats(prev => prev ? { ...prev, total_readings: (prev.total_readings || 0) + 1 } : prev);
        }
      } catch (e) {
        console.warn('[WS] parse error', e);
      }
    };

    ws.onerror = () => { setMqttStatus('disconnected'); };

    ws.onclose = () => {
      setMqttStatus('disconnected');
      console.log('[WS] Disconnected — retrying in 4s');
      wsRetryRef.current = setTimeout(connectWebSocket, 4000);
    };
  }, [isAuthenticated]);

  // Connect WebSocket on login
  useEffect(() => {
    if (isAuthenticated) {
      fetchData();
      connectWebSocket();
    }
    return () => {
      wsRef.current?.close();
      clearTimeout(wsRetryRef.current);
    };
  }, [isAuthenticated, fetchData, connectWebSocket]);

  // ── Filter data ───────────────────────────────────────────────────────
  useEffect(() => {
    let filtered = [...data];

    if (timeRange !== 'all') {
      const cutoff = new Date(Date.now() - parseInt(timeRange) * 3_600_000);
      filtered = filtered.filter(r => new Date(r.timestamp) >= cutoff);
    }
    if (selectedLocation) filtered = filtered.filter(r => r.gateway_id === selectedLocation);
    if (selectedDevice)   filtered = filtered.filter(r => r.node_id   === selectedDevice);
    if (searchTerm) {
      const t = searchTerm.toLowerCase();
      filtered = filtered.filter(r =>
        r.gateway_id.toLowerCase().includes(t) ||
        r.node_id.toLowerCase().includes(t)
      );
    }

    setFilteredData(filtered);
  }, [data, timeRange, selectedLocation, selectedDevice, searchTerm]);

  // ── CSV export ────────────────────────────────────────────────────────
  const exportToCSV = () => {
    if (filteredData.length === 0) return;
    const allKeys = new Set();
    filteredData.forEach(item => {
      if (item.measurements) Object.keys(item.measurements).forEach(k => allKeys.add(k));
    });
    const headers = ['ID', 'Location', 'Device ID', 'Timestamp',
      'Humidity', 'Moisture', 'Temperature', 'Battery (V)',
      ...Array.from(allKeys).map(k => `custom_${k}`)];
    const rows = filteredData.map(item => [
      item.id, item.gateway_id, item.node_id, item.timestamp,
      item.humidity || '', item.moisture || '',
      item.temperature || '', item.battery_voltage || '',
      ...Array.from(allKeys).map(k => item.measurements?.[k] || '')
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `fillxpert-export-${new Date().toISOString().slice(0,10)}.csv`;
    a.click(); URL.revokeObjectURL(url);
  };

  const resetFilters = () => {
    setSelectedLocation(''); setSelectedDevice('');
    setSearchTerm(''); setTimeRange('24');
  };

  // ─────────────────────────────────────────────────────────────────────
  return (
    <Router>
      {authLoading ? (
        <div className="auth-loading-screen">
          <div className="spinner-large"></div>
          <p>Loading FillXpert...</p>
        </div>
      ) : !isAuthenticated ? (
        <Routes>
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="*"         element={<Navigate to="/login" />} />
        </Routes>
      ) : (
        <div className={`app ${isRefreshing ? 'refreshing' : ''}`}>
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} currentUser={currentUser} />

          <div className={`main-content ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
            <header className="app-header">
              <div className="header-left">
                <button
                  className="sidebar-toggle"
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                  title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
                >☰</button>
                <h1 className="app-title">FillXpert Data Collection System</h1>

                {/* REST API status */}
                <div className="api-status" title="Backend REST API">
                  <span className={`status-indicator status-${apiStatus}`}></span>
                  <span className="status-text">
                    {apiStatus === 'connected' ? 'API' : 'API ✗'}
                  </span>
                </div>

                {/* MQTT / WebSocket live status */}
                <div className="api-status" title="Live MQTT feed via WebSocket">
                  <span className={`status-indicator ${mqttStatus === 'connected' ? 'status-connected' : 'status-disconnected'}`}></span>
                  <span className="status-text">
                    {mqttStatus === 'connected' ? 'Live' : 'Live ✗'}
                  </span>
                </div>
              </div>

              <div className="header-right">
                {lastUpdate && (
                  <span className="last-update">
                    Last: {lastUpdate.toLocaleTimeString()}
                  </span>
                )}
                <button className="btn btn-secondary" onClick={fetchData} disabled={loading} style={{padding:'5px 12px',fontSize:'0.8rem'}}>
                  {loading ? '...' : 'Refresh'}
                </button>
              </div>
            </header>

            <main className="app-main">
              <div className="content-wrapper">
                <Routes>
                  <Route path="/" element={
                    <Dashboard
                      data={data}
                      filteredData={filteredData}
                      locations={locations}
                      deviceIds={deviceIds}
                      selectedLocation={selectedLocation}
                      setSelectedLocation={setSelectedLocation}
                      selectedDevice={selectedDevice}
                      setSelectedDevice={setSelectedDevice}
                      searchTerm={searchTerm}
                      setSearchTerm={setSearchTerm}
                      timeRange={timeRange}
                      setTimeRange={setTimeRange}
                      loading={loading}
                      error={error}
                      setError={setError}
                      stats={stats}
                      apiStatus={apiStatus}
                      mqttStatus={mqttStatus}
                      lastUpdate={lastUpdate}
                      isRefreshing={isRefreshing}
                      fetchData={fetchData}
                      resetFilters={resetFilters}
                      exportToCSV={exportToCSV}
                      historicalData={historicalData}
                    />
                  } />
                  <Route path="/manual-entry"               element={<ManualEntry />} />
                  <Route path="/data-export"                element={<DataExport />} />
                  <Route path="/settings"                   element={<Settings />} />
                  <Route path="/devices"                    element={<Devices />} />
                  <Route path="/devices/:deviceId/config"   element={<DeviceConfig />} />
                </Routes>
              </div>
            </main>

            <footer className="app-footer">
              <p>FillXpert Data Collection System v2.1.0 | Total Readings: {stats?.total_readings || 0}</p>
            </footer>
          </div>
        </div>
      )}
    </Router>
  );
}

export default App;
