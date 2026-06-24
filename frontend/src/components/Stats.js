import React from 'react';
import './Stats.css';
import { toLocalStr } from '../utils/time';

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
          <h3>Locations</h3>
          <p className="stat-value">{stats.total_gateways}</p>
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-content">
          <h3>Devices</h3>
          <p className="stat-value">{stats.total_nodes}</p>
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-content">
          <h3>Last Reading</h3>
          <p className="stat-value small">
            {stats.latest_reading_time
              ? toLocalStr(stats.latest_reading_time)
              : 'No data'}
          </p>
        </div>
      </div>
    </div>
  );
}

export default Stats;
