import React from 'react';
import DataTable from '../components/DataTable';
import Stats from '../components/Stats';
import SensorChart from '../components/SensorChart';

function Dashboard({
  data,
  filteredData,
  locations,
  deviceIds,
  selectedLocation,
  setSelectedLocation,
  selectedDevice,
  setSelectedDevice,
  searchTerm,
  setSearchTerm,
  timeRange,
  setTimeRange,
  loading,
  error,
  setError,
  stats,
  mqttStatus,
  isRefreshing,
  fetchData,
  resetFilters,
  exportToCSV,
  historicalData
}) {
  return (
    <>
      {error && (
        <div className="alert alert-error">
          <strong>Error:</strong> {error}
          <button onClick={() => setError(null)} className="alert-close">×</button>
        </div>
      )}

      {stats && <Stats stats={stats} />}

      <div className="controls-panel">
        <div className="controls-row">

          <div className="control-group">
            <label>Time Range</label>
            <select value={timeRange} onChange={e => setTimeRange(e.target.value)}>
              <option value="1">Last 1 Hour</option>
              <option value="6">Last 6 Hours</option>
              <option value="24">Last 24 Hours</option>
              <option value="168">Last 7 Days</option>
              <option value="720">Last 30 Days</option>
              <option value="2160">Last 90 Days</option>
              <option value="4380">Last 180 Days</option>
              <option value="8760">Last 1 Year</option>
              <option value="26280">Last 3 Years</option>
              <option value="43800">Last 5 Years</option>
            </select>
          </div>

          <div className="control-group">
            <label>Location</label>
            <select
              value={selectedLocation}
              onChange={e => { setSelectedLocation(e.target.value); setSelectedDevice(''); }}
            >
              <option value="">All Locations</option>
              {locations.map(loc => <option key={loc} value={loc}>{loc}</option>)}
            </select>
          </div>

          <div className="control-group">
            <label>Device</label>
            <select
              value={selectedDevice}
              onChange={e => setSelectedDevice(e.target.value)}
              disabled={deviceIds.length === 0}
            >
              <option value="">All Devices</option>
              {deviceIds.map(id => <option key={id} value={id}>{id}</option>)}
            </select>
          </div>

          <div className="control-group">
            <label>Search</label>
            <input
              type="text"
              placeholder="Filter by location or device ID..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>
        </div>

        <div className="controls-row">
          <div className="control-actions">
            <button onClick={fetchData} className="btn btn-primary" disabled={loading}>
              {loading ? 'Loading...' : 'Refresh'}
            </button>
            <button onClick={resetFilters} className="btn btn-secondary">
              Reset Filters
            </button>
            <button onClick={exportToCSV} className="btn btn-secondary" disabled={filteredData.length === 0}>
              Export CSV
            </button>
          </div>

          <div className="control-toggles">
            {/* Live MQTT indicator — replaces the old auto-refresh checkbox */}
            <span style={{
              fontSize: '0.8rem',
              padding: '4px 12px',
              borderRadius: '999px',
              background: mqttStatus === 'connected' ? '#f0fdf4' : '#fafafa',
              border: `1px solid ${mqttStatus === 'connected' ? '#bbf7d0' : '#e4e4e7'}`,
              color: mqttStatus === 'connected' ? '#15803d' : '#a1a1aa',
              fontWeight: 500,
            }}>
              {mqttStatus === 'connected' ? '● Live (MQTT active)' : '○ Live (reconnecting...)'}
            </span>
          </div>
        </div>
      </div>

      {/* Sensor Trend Chart — reads filteredData, no API call, renders above table */}
      <SensorChart
        filteredData={filteredData}
        selectedDevice={selectedDevice}
        selectedLocation={selectedLocation}
      />

      <DataTable
        data={filteredData}
        loading={loading}
        totalCount={data.length}
        filteredCount={filteredData.length}
        historicalData={historicalData}
      />
    </>
  );
}

export default Dashboard;
