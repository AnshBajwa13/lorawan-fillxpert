import React from 'react';
import DataTable from '../components/DataTable';
import Stats from '../components/Stats';

function Dashboard({ 
  data, 
  filteredData, 
  gateways, 
  nodes, 
  selectedGateway, 
  setSelectedGateway, 
  selectedNode, 
  setSelectedNode, 
  searchTerm, 
  setSearchTerm, 
  timeRange, 
  setTimeRange, 
  loading, 
  error, 
  setError, 
  stats, 
  autoRefresh, 
  setAutoRefresh, 
  apiStatus, 
  lastUpdate, 
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
            <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)}>
              <option value="1">Last 1 Hour</option>
              <option value="6">Last 6 Hours</option>
              <option value="24">Last 24 Hours</option>
              <option value="168">Last 7 Days</option>
              <option value="720">Last 30 Days</option>
            </select>
          </div>

          <div className="control-group">
            <label>Gateway</label>
            <select 
              value={selectedGateway} 
              onChange={(e) => {
                setSelectedGateway(e.target.value);
                setSelectedNode('');
              }}
            >
              <option value="">All Gateways</option>
              {gateways.map(gw => (
                <option key={gw} value={gw}>{gw}</option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <label>Node</label>
            <select 
              value={selectedNode} 
              onChange={(e) => setSelectedNode(e.target.value)}
              disabled={!selectedGateway && nodes.length === 0}
            >
              <option value="">All Nodes</option>
              {nodes.map(node => (
                <option key={node} value={node}>{node}</option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <label>Search</label>
            <input
              type="text"
              placeholder="Filter by gateway or node..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
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
            <label className="toggle-label">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
              <span>Auto-refresh (10s)</span>
            </label>
          </div>
        </div>
      </div>

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
