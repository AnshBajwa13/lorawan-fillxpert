import React from 'react';
import './DataTable.css';
import Sparkline from './Sparkline';

function DataTable({ data, loading, totalCount, filteredCount, historicalData = {} }) {
  // Get all unique measurement keys from data
  const getMeasurementKeys = () => {
    const keys = new Set();
    data.forEach(reading => {
      if (reading.measurements) {
        Object.keys(reading.measurements).forEach(key => keys.add(key));
      }
    });
    return Array.from(keys);
  };

  const measurementKeys = data.length > 0 ? getMeasurementKeys() : [];

  if (loading) {
    return (
      <div className="table-container">
        <div className="table-header">
          <h2 className="table-title">Sensor Readings</h2>
          <span className="table-info">Loading...</span>
        </div>
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Gateway</th>
                <th>Node</th>
                <th>Timestamp</th>
                <th>Humidity (%)</th>
                <th>Moisture (%)</th>
                <th>Temperature (°C)</th>
                <th>Battery (V)</th>
              </tr>
            </thead>
            <tbody>
              {[...Array(5)].map((_, i) => (
                <tr key={i} className="skeleton-row">
                  <td><div className="skeleton"></div></td>
                  <td><div className="skeleton skeleton-badge"></div></td>
                  <td><div className="skeleton skeleton-badge"></div></td>
                  <td><div className="skeleton skeleton-timestamp"></div></td>
                  <td><div className="skeleton skeleton-value"></div></td>
                  <td><div className="skeleton skeleton-value"></div></td>
                  <td><div className="skeleton skeleton-value"></div></td>
                  <td><div className="skeleton skeleton-value"></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="table-container">
        <div className="table-header">
          <h2 className="table-title">Sensor Readings</h2>
          <span className="table-info">No data</span>
        </div>
        <div className="empty-state">
          <svg className="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
          <h3>No sensor readings found</h3>
          <p>Waiting for data from gateways. Make sure sensors are transmitting and gateways are connected.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="table-container">
      <div className="table-header">
        <h2 className="table-title">Sensor Readings</h2>
        <span className="table-info">
          Showing {filteredCount} of {totalCount} readings
        </span>
      </div>
      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Gateway</th>
              <th>Node</th>
              <th>Timestamp</th>
              <th>Humidity (%)</th>
              <th>Moisture (%)</th>
              <th>Temperature (°C)</th>
              <th>Battery (V)</th>
              {measurementKeys.map(key => (
                <th key={key}>{key.toUpperCase().replace('_', ' ')}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((reading) => {
              const historyKey = `${reading.gateway_id}-${reading.node_id}`;
              const nodeHistory = historicalData[historyKey] || {};
              
              return (
              <tr key={reading.id}>
                <td>{reading.id}</td>
                <td>
                  <span className="badge gateway">{reading.gateway_id}</span>
                </td>
                <td>
                  <span className="badge node">{reading.node_id}</span>
                </td>
                <td className="timestamp">
                  {new Date(reading.timestamp).toLocaleString()}
                </td>
                <td className="value">
                  <div className="value-with-sparkline">
                    <span>{reading.humidity !== null ? reading.humidity.toFixed(1) : '-'}</span>
                    {nodeHistory.humidity && nodeHistory.humidity.length > 2 && (
                      <Sparkline data={nodeHistory.humidity} color="#3b82f6" width={50} height={20} />
                    )}
                  </div>
                </td>
                <td className="value">
                  <div className="value-with-sparkline">
                    <span>{reading.moisture !== null ? reading.moisture.toFixed(1) : '-'}</span>
                    {nodeHistory.moisture && nodeHistory.moisture.length > 2 && (
                      <Sparkline data={nodeHistory.moisture} color="#8b5cf6" width={50} height={20} />
                    )}
                  </div>
                </td>
                <td className="value">
                  <div className="value-with-sparkline">
                    <span>{reading.temperature !== null ? reading.temperature.toFixed(1) : '-'}</span>
                    {nodeHistory.temperature && nodeHistory.temperature.length > 2 && (
                      <Sparkline data={nodeHistory.temperature} color="#f59e0b" width={50} height={20} />
                    )}
                  </div>
                </td>
                <td className="value">
                  {reading.battery_voltage !== null && reading.battery_voltage !== undefined ? (
                    <div className="value-with-sparkline">
                      <span className={`battery ${reading.battery_voltage < 3.3 ? 'battery-low' : ''}`}>
                        {reading.battery_voltage.toFixed(2)}
                      </span>
                      {nodeHistory.battery_voltage && nodeHistory.battery_voltage.length > 2 && (
                        <Sparkline 
                          data={nodeHistory.battery_voltage} 
                          color={reading.battery_voltage < 3.3 ? '#dc2626' : '#16a34a'} 
                          width={50} 
                          height={20} 
                        />
                      )}
                    </div>
                  ) : '-'}
                </td>
                {measurementKeys.map(key => (
                  <td key={key} className="value">
                    {reading.measurements && reading.measurements[key] !== null && reading.measurements[key] !== undefined
                      ? typeof reading.measurements[key] === 'number'
                        ? reading.measurements[key].toFixed(2)
                        : reading.measurements[key]
                      : '-'}
                  </td>
                ))}
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default DataTable;
