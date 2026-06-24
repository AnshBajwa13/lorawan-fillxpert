/**
 * time.js — Centralised timestamp utilities for FillXpert frontend.
 *
 * WHY THIS EXISTS:
 * The backend stores all timestamps in UTC (PostgreSQL default).
 * When serialised to JSON they come as "2026-06-24T06:02:43" — WITHOUT a
 * timezone designator. ECMAScript treats such strings as *local time*, not UTC,
 * so new Date("2026-06-24T06:02:43") in a browser set to IST (UTC+5:30) gives
 * 06:02 IST instead of the correct 11:32 IST.
 *
 * The fix: append "Z" when the string lacks any timezone info. That forces
 * JavaScript to interpret the value as UTC and then convert to local (IST)
 * for display — exactly what we want.
 *
 * Usage:
 *   import { parseUTC, toLocalStr, toLocalTimeStr } from '../utils/time';
 *   new Date(reading.timestamp)       // ❌ wrong: treated as local
 *   parseUTC(reading.timestamp)       // ✅ correct: treated as UTC → IST
 *   toLocalStr(reading.timestamp)     // ✅ "6/24/2026, 11:32:43 AM"
 */

/**
 * Normalise a backend timestamp string and return a JS Date in local time.
 * @param {string|null} ts  ISO 8601 string from backend
 * @returns {Date|null}
 */
export function parseUTC(ts) {
  if (!ts) return null;
  // If the string already carries timezone info (Z or ±HH:MM) leave it alone.
  // Otherwise append Z so JS knows it is UTC.
  const normalized = /Z|[+-]\d{2}:\d{2}$/.test(ts) ? ts : ts + 'Z';
  const d = new Date(normalized);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Format a backend timestamp string as a full local date+time string.
 * e.g. "2026-06-24T06:02:43"  →  "6/24/2026, 11:32:43 AM"  (IST browser)
 * @param {string|null} ts
 * @returns {string}
 */
export function toLocalStr(ts) {
  const d = parseUTC(ts);
  return d ? d.toLocaleString() : '—';
}

/**
 * Format as time only (no date) — used in headers / sparklines.
 * e.g. "2026-06-24T06:02:43"  →  "11:32:43 AM"
 * @param {string|null} ts
 * @returns {string}
 */
export function toLocalTimeStr(ts) {
  const d = parseUTC(ts);
  return d ? d.toLocaleTimeString() : '—';
}

/**
 * Format for the chart X-axis label (compact: "24 Jun, 11:32").
 * @param {string|null} ts
 * @returns {string}
 */
export function toChartLabel(ts) {
  const d = parseUTC(ts);
  if (!d) return '—';
  return d.toLocaleString('en-IN', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
}
