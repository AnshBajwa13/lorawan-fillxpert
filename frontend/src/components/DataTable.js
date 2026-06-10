import React from 'react';
import './DataTable.css';
import Sparkline from './Sparkline';

function DataTable({ data, loading, totalCount, filteredCount, historicalData = {} }) {

  const getMeasurementKeys = () => {
    const keys = new Set();
    data.forEach(r => {
      if (r.measurements) {
        Object.keys(r.measurements)
          .filter(k => k !== 'sensor_type')   // hide internal flag
          .forEach(k => keys.add(k));
      }
    });
    return Array.from(keys);
  };

  const measurementKeys = data.length > 0 ? getMeasurementKeys() : [];

  // ── Loading skeleton ─────────────────────────────────────────────────
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
                <th>ID</th><th>Location</th><th>Device</th><th>Timestamp</th>
                <th>Humidity (%)</th><th>Moisture (%)</th><th>Temp (°C)</th><th>Battery (V)</th>
              </tr>
            </thead>
            <tbody>
              {[...Array(5)].map((_, i) => (
                <tr key={i} className="skeleton-row">
                  {[...Array(8)].map((_, j) => (
                    <td key={j}><div className="skeleton"></div></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // ── Empty state ──────────────────────────────────────────────────────
  if (data.length === 0) {
    return (
      <div className="table-container">
        <div className="table-header">
          <h2 className="table-title">Sensor Readings</h2>
          <span className="table-info">No data</span>
        </div>
        <div className="empty-state">
          <svg className="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
          <h3>No sensor readings found</h3>
          <p>Register a device and make sure it is transmitting via MQTT.</p>
        </div>
      </div>
    );
  }

  // ── Table ────────────────────────────────────────────────────────────
  return (
    <div className="table-container">
      <div className="table-header">
        <h2 className="table-title">Sensor Readings</h2>
        <span className="table-info">Showing {filteredCount} of {totalCount} readings</span>
      </div>

      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Location</th>
              <th>Device</th>
              <th>Trigger</th>
              <th>Timestamp</th>
              <th>Humidity (%)</th>
              <th>Moisture (%)</th>
              <th>Temp (°C)</th>
              <th>Battery (V)</th>
              {measurementKeys.map(k => (
                <th key={k}>{k.toUpperCase().replace(/_/g, ' ')}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((reading) => {
              const historyKey  = `${reading.gateway_id}-${reading.node_id}`;
              const nodeHistory = historicalData[historyKey] || {};
              const isLive      = reading._live;
              const isCalib     = reading._calibration;

              return (
                <tr key={reading.id} className={isLive ? 'row-live' : ''}>
                  <td>{reading.id}</td>
                  <td>
                    <span className="badge location">{reading.gateway_id}</span>
                  </td>
                  <td>
                    <span className="badge device">{reading.node_id}</span>
                  </td>
                  <td>
                    {isCalib
                      ? <span className="badge calibration">Calibration</span>
                      : <span className="badge trigger">{reading.measurements?.trigger || reading.trigger || 'schedule'}</span>
                    }
                  </td>
                  <td className="timestamp">
                    {new Date(reading.timestamp).toLocaleString()}
                    {isLive && <span className="live-dot" title="Just received via MQTT">●</span>}
                  </td>

                  <td className="value">
                    <div className="value-with-sparkline">
                      <span>{reading.humidity != null ? reading.humidity.toFixed(1) : '-'}</span>
                      {nodeHistory.humidity?.length > 2 && (
                        <Sparkline data={nodeHistory.humidity} color="#3b82f6" width={50} height={20} />
                      )}
                    </div>
                  </td>
                  <td className="value">
                    <div className="value-with-sparkline">
                      <span>{reading.moisture != null ? reading.moisture.toFixed(1) : '-'}</span>
                      {nodeHistory.moisture?.length > 2 && (
                        <Sparkline data={nodeHistory.moisture} color="#8b5cf6" width={50} height={20} />
                      )}
                    </div>
                  </td>
                  <td className="value">
                    <div className="value-with-sparkline">
                      <span>{reading.temperature != null ? reading.temperature.toFixed(1) : '-'}</span>
                      {nodeHistory.temperature?.length > 2 && (
                        <Sparkline data={nodeHistory.temperature} color="#f59e0b" width={50} height={20} />
                      )}
                    </div>
                  </td>
                  <td className="value">
                    {reading.battery_voltage != null ? (
                      <div className="value-with-sparkline">
                        <span className={reading.battery_voltage < 3.3 ? 'battery battery-low' : 'battery'}>
                          {reading.battery_voltage.toFixed(2)}
                        </span>
                        {nodeHistory.battery_voltage?.length > 2 && (
                          <Sparkline
                            data={nodeHistory.battery_voltage}
                            color={reading.battery_voltage < 3.3 ? '#dc2626' : '#16a34a'}
                            width={50} height={20}
                          />
                        )}
                      </div>
                    ) : '-'}
                  </td>

                  {measurementKeys.map(k => (
                    <td key={k} className="value">
                      {reading.measurements?.[k] != null
                        ? typeof reading.measurements[k] === 'number'
                          ? reading.measurements[k].toFixed(2)
                          : reading.measurements[k]
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
