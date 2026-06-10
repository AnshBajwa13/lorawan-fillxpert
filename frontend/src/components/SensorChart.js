/**
 * SensorChart — Time-series line chart for sensor readings.
 *
 * WHY THIS EXISTS:
 * The data table shows raw numbers per row. A chart shows TRENDS:
 * - Is soil moisture dropping below threshold? (irrigation needed)
 * - Is temperature spiking? (heat stress on crops)
 * - Is battery draining faster than expected?
 *
 * DESIGN DECISIONS:
 * - Uses recharts (already in package.json, React-native, no canvas issues)
 * - Reads from filteredData prop — ZERO new API calls
 * - Reverses the array so chart goes left=oldest, right=newest (chronological)
 * - Toggleable metric lines (click a pill to show/hide)
 * - Only shows lines that have at least one non-null data point
 * - Min 2 data points required to draw a meaningful line
 * - Graceful empty state with a hint message
 *
 * PROPS:
 *   filteredData    — array of sensor readings (from Dashboard → App.js)
 *   selectedDevice  — string device_id filter ('' = all devices)
 *   selectedLocation— string location filter  ('' = all locations)
 */

import React, { useMemo, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import './SensorChart.css';

// ─── Metric configuration ────────────────────────────────────────────────────
// Each metric: field name in the data row, display label, unit, chart colour
const METRICS = [
  { key: 'moisture',    label: 'Moisture',    unit: '%',  color: '#18181b' },
  { key: 'temperature', label: 'Temperature', unit: '°C', color: '#dc2626' },
  { key: 'humidity',    label: 'Humidity',    unit: '%',  color: '#2563eb' },
  { key: 'battery_voltage', label: 'Battery', unit: 'V',  color: '#16a34a' },
];

// ─── Custom dark tooltip ─────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-label">{label}</p>
      {payload.map(entry => (
        <div className="chart-tooltip-row" key={entry.dataKey}>
          <span className="chart-tooltip-dot" style={{ background: entry.color }} />
          <span>
            {entry.name}: <strong>{entry.value != null ? entry.value : '—'}</strong>
            {' '}{METRICS.find(m => m.key === entry.dataKey)?.unit ?? ''}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────
function SensorChart({ filteredData = [], selectedDevice = '', selectedLocation = '' }) {

  // Active metric toggles — all on by default
  const [active, setActive] = useState({
    moisture: true, temperature: true, humidity: true, battery_voltage: false,
  });

  const toggleMetric = (key) => setActive(prev => ({ ...prev, [key]: !prev[key] }));

  // ── Transform filteredData into chart-ready array ─────────────────────────
  //
  // filteredData is newest-first (prepended on each WS event / API load).
  // Chart reads left=oldest, right=newest → reverse.
  //
  // Each point: { time: "10:35", moisture: 43.5, temperature: 28.7, ... }
  // We show the 50 most recent points to keep the chart readable.
  //
  const chartData = useMemo(() => {
    if (!filteredData?.length) return [];

    // Take up to 50 points, reversed to chronological order
    const slice = [...filteredData].slice(0, 50).reverse();

    return slice.map(row => {
      // Format timestamp for X-axis label
      let timeLabel = '—';
      if (row.timestamp) {
        const d = new Date(row.timestamp);
        if (!isNaN(d)) {
          // "Jun 11 10:35" — short enough for axis
          timeLabel = d.toLocaleString('en-IN', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit', hour12: false,
          });
        }
      }

      return {
        time:            timeLabel,
        moisture:        row.moisture    != null ? +row.moisture.toFixed(1)    : null,
        temperature:     row.temperature != null ? +row.temperature.toFixed(1) : null,
        humidity:        row.humidity    != null ? +row.humidity.toFixed(1)    : null,
        battery_voltage: row.battery_voltage != null
                           ? +row.battery_voltage.toFixed(2)
                           : null,
        // Store node_id for tooltip context when "all devices" shown
        device: row.node_id || row.gateway_id || '',
      };
    });
  }, [filteredData]);

  // ── Figure out which metrics actually have data ───────────────────────────
  const availableMetrics = useMemo(() => {
    return METRICS.filter(m =>
      chartData.some(p => p[m.key] != null)
    );
  }, [chartData]);

  // ── Build device/location label for the panel header ─────────────────────
  const scopeLabel = useMemo(() => {
    const parts = [];
    if (selectedLocation) parts.push(selectedLocation);
    if (selectedDevice)   parts.push(selectedDevice);
    return parts.length ? parts.join(' / ') : 'All Devices';
  }, [selectedLocation, selectedDevice]);

  // ── Empty state ───────────────────────────────────────────────────────────
  const hasEnoughData = chartData.length >= 2;
  const hasAnyActive  = availableMetrics.some(m => active[m.key]);

  return (
    <div className="chart-panel">
      <div className="chart-header">
        <div>
          <p className="chart-title">Sensor Trend</p>
          <p className="chart-subtitle">
            {chartData.length} reading{chartData.length !== 1 ? 's' : ''}
            {' '}&nbsp;·&nbsp;{' '}
            <span className="chart-device-info">{scopeLabel}</span>
          </p>
        </div>

        {/* Metric toggle pills — only show pills for metrics with data */}
        <div className="chart-toggles">
          {availableMetrics.map(m => (
            <button
              key={m.key}
              className={`chart-toggle ${active[m.key] ? `active-${m.key}` : ''}`}
              onClick={() => toggleMetric(m.key)}
              title={active[m.key] ? `Hide ${m.label}` : `Show ${m.label}`}
            >
              {m.label} ({m.unit})
            </button>
          ))}
        </div>
      </div>

      {/* ── Chart or empty state ── */}
      {!hasEnoughData || !hasAnyActive ? (
        <div className="chart-empty">
          <span className="chart-empty-icon">—</span>
          <span>
            {!hasEnoughData
              ? 'Need at least 2 readings to draw a trend line.'
              : 'Select at least one metric above.'}
          </span>
          {!hasEnoughData && (
            <span style={{ fontSize: '0.72rem', color: '#d4d4d8' }}>
              {chartData.length === 0
                ? 'No readings match the current filter.'
                : `Only ${chartData.length} reading found.`}
            </span>
          )}
        </div>
      ) : (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart
              data={chartData}
              margin={{ top: 8, right: 16, left: -12, bottom: 4 }}
            >
              <CartesianGrid
                strokeDasharray="4 4"
                stroke="#f4f4f5"
                vertical={false}
              />

              <XAxis
                dataKey="time"
                tick={{ fontSize: 10, fill: '#a1a1aa' }}
                tickLine={false}
                axisLine={{ stroke: '#e4e4e7' }}
                interval="preserveStartEnd"
                minTickGap={40}
              />

              <YAxis
                tick={{ fontSize: 10, fill: '#a1a1aa' }}
                tickLine={false}
                axisLine={false}
                width={42}
              />

              <Tooltip
                content={<ChartTooltip />}
                cursor={{ stroke: '#e4e4e7', strokeWidth: 1 }}
              />

              {/* 
                Draw a line for each active metric that has data.
                connectNulls=false: gap in line where no reading exists.
                dot=false: cleaner for dense data; shows dot on hover.
                activeDot: black ring on hover (matches light theme).
              */}
              {METRICS.map(m =>
                active[m.key] && availableMetrics.find(am => am.key === m.key) ? (
                  <Line
                    key={m.key}
                    type="monotone"
                    dataKey={m.key}
                    name={m.label}
                    stroke={m.color}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{
                      r: 5,
                      fill: m.color,
                      stroke: '#fff',
                      strokeWidth: 2,
                    }}
                    connectNulls={false}
                  />
                ) : null
              )}

              {/* Reference line: 30% moisture is typically "low" alert threshold */}
              {active['moisture'] && availableMetrics.find(m => m.key === 'moisture') && (
                <ReferenceLine
                  y={30}
                  stroke="#fca5a5"
                  strokeDasharray="3 3"
                  strokeWidth={1}
                  label={{ value: 'Low', fill: '#fca5a5', fontSize: 10, position: 'insideTopRight' }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>

          {/* Colour legend */}
          <div className="chart-legend">
            {METRICS
              .filter(m => active[m.key] && availableMetrics.find(am => am.key === m.key))
              .map(m => (
                <span className="chart-legend-item" key={m.key}>
                  <span className="chart-legend-dot" style={{ background: m.color }} />
                  {m.label} ({m.unit})
                </span>
              ))
            }
          </div>
        </div>
      )}
    </div>
  );
}

export default SensorChart;
