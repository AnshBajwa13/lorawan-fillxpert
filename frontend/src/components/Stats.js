import React from 'react';
import './Stats.css';

function Stats({ stats }) {
  return (
    <div className="stats-container">
      <div className="stat-card">
        <div className="stat-content">
          <h3>Total Readings</h3>
          <p className="stat-value">{stats.total_readings.toLocaleString()}</p>
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-content">
          <h3>Gateways</h3>
          <p className="stat-value">{stats.total_gateways}</p>
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-content">
          <h3>Sensor Nodes</h3>
          <p className="stat-value">{stats.total_nodes}</p>
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-content">
          <h3>Last Update</h3>
          <p className="stat-value small">
            {stats.latest_reading_time 
              ? new Date(stats.latest_reading_time).toLocaleString()
              : 'No data'}
          </p>
        </div>
      </div>
    </div>
  );
}

export default Stats;
