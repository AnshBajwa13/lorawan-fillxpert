import React, { useState, useEffect, useCallback } from 'react';
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

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [data, setData] = useState([]);
  const [filteredData, setFilteredData] = useState([]);
  const [gateways, setGateways] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [selectedGateway, setSelectedGateway] = useState('');
  const [selectedNode, setSelectedNode] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [timeRange, setTimeRange] = useState('24');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [apiStatus, setApiStatus] = useState('checking');
  const [lastUpdate, setLastUpdate] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [historicalData, setHistoricalData] = useState({});

  // Setup axios interceptor for authentication
  useEffect(() => {
    const requestInterceptor = axios.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token && !config.url?.includes('/auth/login') && !config.url?.includes('/auth/register')) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    return () => {
      axios.interceptors.request.eject(requestInterceptor);
    };
  }, []);

  // Check authentication on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const response = await axios.get(`${API_URL}/api/auth/me`);
          setIsAuthenticated(true);
          setCurrentUser(response.data);
        } catch (error) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          setIsAuthenticated(false);
        }
      }
      setAuthLoading(false);
    };
    checkAuth();
  }, []);

  // Build historical data for sparklines
  const buildHistoricalData = useCallback((readings) => {
    const history = {};
    
    // Group readings by gateway-node combination
    readings.forEach(reading => {
      const key = `${reading.gateway_id}-${reading.node_id}`;
      if (!history[key]) {
        history[key] = {
          humidity: [],
          moisture: [],
          temperature: [],
          battery_voltage: []
        };
      }
      
      // Keep only last 10 readings
      if (reading.humidity !== null && reading.humidity !== undefined) {
        history[key].humidity.push(reading.humidity);
        if (history[key].humidity.length > 10) history[key].humidity.shift();
      }
      if (reading.moisture !== null && reading.moisture !== undefined) {
        history[key].moisture.push(reading.moisture);
        if (history[key].moisture.length > 10) history[key].moisture.shift();
      }
      if (reading.temperature !== null && reading.temperature !== undefined) {
        history[key].temperature.push(reading.temperature);
        if (history[key].temperature.length > 10) history[key].temperature.shift();
      }
      if (reading.battery_voltage !== null && reading.battery_voltage !== undefined) {
        history[key].battery_voltage.push(reading.battery_voltage);
        if (history[key].battery_voltage.length > 10) history[key].battery_voltage.shift();
      }
    });
    
    return history;
  }, []);

  // Fetch data from API
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setIsRefreshing(true);
      setError(null);

      const [readingsRes, statsRes] = await Promise.all([
        axios.get(`${API_URL}/api/sensor-data`),
        axios.get(`${API_URL}/api/stats`)
      ]);

      const readings = readingsRes.data;
      setData(readings);
      setStats(statsRes.data);
      
      // Build historical data for sparklines
      const history = buildHistoricalData(readings);
      setHistoricalData(history);

      // Extract unique gateways and nodes
      const uniqueGateways = [...new Set(readings.map(r => r.gateway_id))];
      const uniqueNodes = [...new Set(readings.map(r => r.node_id))];
      setGateways(uniqueGateways);
      setNodes(uniqueNodes);

      setApiStatus('connected');
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Failed to fetch sensor data. Please check if the backend is running.');
      setApiStatus('disconnected');
    } finally {
      setLoading(false);
      setTimeout(() => setIsRefreshing(false), 500);
    }
  }, [buildHistoricalData]);

  // Filter data based on selections
  useEffect(() => {
    let filtered = [...data];

    // Time range filter
    if (timeRange !== 'all') {
      const now = new Date();
      const hoursAgo = parseInt(timeRange);
      const cutoff = new Date(now.getTime() - (hoursAgo * 60 * 60 * 1000));
      filtered = filtered.filter(r => new Date(r.timestamp) >= cutoff);
    }

    // Gateway filter
    if (selectedGateway) {
      filtered = filtered.filter(r => r.gateway_id === selectedGateway);
    }

    // Node filter
    if (selectedNode) {
      filtered = filtered.filter(r => r.node_id === selectedNode);
    }

    // Search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(r => 
        r.gateway_id.toLowerCase().includes(term) ||
        r.node_id.toLowerCase().includes(term)
      );
    }

    setFilteredData(filtered);
  }, [data, timeRange, selectedGateway, selectedNode, searchTerm]);

  // Auto-refresh
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchData, 10000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, fetchData]);

  // Check API availability and fetch initial data
  useEffect(() => {
    if (isAuthenticated) {
      fetchData();
    }
  }, [isAuthenticated, fetchData]);

  // Export to CSV
  const exportToCSV = () => {
    if (filteredData.length === 0) return;

    // Get all measurement keys
    const allKeys = new Set();
    filteredData.forEach(item => {
      if (item.measurements) {
        Object.keys(item.measurements).forEach(key => allKeys.add(key));
      }
    });

    // Build headers
    const headers = [
      'ID', 'Gateway ID', 'Node ID', 'Timestamp', 
      'Humidity', 'Moisture', 'Temperature', 'Battery Voltage',
      ...Array.from(allKeys).map(k => `measurements_${k}`)
    ];

    // Build rows
    const rows = filteredData.map(item => [
      item.id,
      item.gateway_id,
      item.node_id,
      item.timestamp,
      item.humidity || '',
      item.moisture || '',
      item.temperature || '',
      item.battery_voltage || '',
      ...Array.from(allKeys).map(k => item.measurements?.[k] || '')
    ]);

    // Create CSV content
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    // Download
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lorawan-data-${new Date().toISOString()}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const resetFilters = () => {
    setSelectedGateway('');
    setSelectedNode('');
    setSearchTerm('');
    setTimeRange('24');
  };

  return (
    <Router>
      {authLoading ? (
        <div className="auth-loading-screen">
          <div className="spinner-large"></div>
          <p>Loading...</p>
        </div>
      ) : !isAuthenticated ? (
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      ) : (
        <div className={`app ${isRefreshing ? 'refreshing' : ''}`}>
          <Sidebar 
            isOpen={sidebarOpen} 
            onClose={() => setSidebarOpen(false)}
            currentUser={currentUser}
          />
          
          <div className={`main-content ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
          <header className="app-header">
            <div className="header-left">
              <button 
                className="sidebar-toggle"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
              >
                ☰
              </button>
              <h1 className="app-title">LoRaWAN Data Collection System</h1>
              <div className="api-status">
                <span className={`status-indicator status-${apiStatus}`}></span>
                <span className="status-text">
                  {apiStatus === 'connected' ? 'Connected' : 
                   apiStatus === 'disconnected' ? 'Disconnected' : 'Checking...'}
                </span>
              </div>
            </div>
            <div className="header-right">
              {lastUpdate && (
                <span className="last-update">
                  Last updated: {lastUpdate.toLocaleTimeString()}
                </span>
              )}
            </div>
          </header>

          <main className="app-main">
            <div className="content-wrapper">
              <Routes>
                <Route path="/" element={
                  <Dashboard
                    data={data}
                    filteredData={filteredData}
                    gateways={gateways}
                    nodes={nodes}
                    selectedGateway={selectedGateway}
                    setSelectedGateway={setSelectedGateway}
                    selectedNode={selectedNode}
                    setSelectedNode={setSelectedNode}
                    searchTerm={searchTerm}
                    setSearchTerm={setSearchTerm}
                    timeRange={timeRange}
                    setTimeRange={setTimeRange}
                    loading={loading}
                    error={error}
                    setError={setError}
                    stats={stats}
                    autoRefresh={autoRefresh}
                    setAutoRefresh={setAutoRefresh}
                    apiStatus={apiStatus}
                    lastUpdate={lastUpdate}
                    isRefreshing={isRefreshing}
                    fetchData={fetchData}
                    resetFilters={resetFilters}
                    exportToCSV={exportToCSV}
                    historicalData={historicalData}
                  />
                } />
                <Route path="/manual-entry" element={<ManualEntry />} />
                <Route path="/data-export" element={<DataExport />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </div>
          </main>

          <footer className="app-footer">
            <p>LoRaWAN Data Collection System v1.0.0 | Total Readings: {stats?.total_readings || 0}</p>
          </footer>
          </div>
        </div>
      )}
    </Router>
  );
}

export default App;
