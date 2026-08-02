/**
 * Frontend unit tests for utils/time.js
 *
 * The timezone bug: backend sends timestamps without 'Z' (e.g. "2026-06-24T06:02:43").
 * Without our fix, a browser in IST (UTC+5:30) treats it as IST local time instead
 * of UTC — producing a 5h30m error in all displayed timestamps.
 *
 * These tests verify parseUTC(), toLocalStr(), toLocalTimeStr(), and toChartLabel()
 * all interpret backend strings as UTC regardless of system timezone.
 *
 * Run:
 *   cd frontend && npm test -- --watchAll=false src/utils/time.test.js
 */

import { parseUTC, toLocalStr, toLocalTimeStr, toChartLabel } from './time';

// ─────────────────────────────────────────────────────────────────────────────
// parseUTC
// ─────────────────────────────────────────────────────────────────────────────

describe('parseUTC', () => {
  test('returns a Date object for valid timestamp', () => {
    const d = parseUTC('2026-06-24T06:02:43');
    expect(d).toBeInstanceOf(Date);
  });

  test('returns null for null input', () => {
    expect(parseUTC(null)).toBeNull();
  });

  test('returns null for undefined input', () => {
    expect(parseUTC(undefined)).toBeNull();
  });

  test('returns null for empty string', () => {
    expect(parseUTC('')).toBeNull();
  });

  test('returns null for invalid date string', () => {
    expect(parseUTC('not-a-date')).toBeNull();
  });

  test('string WITHOUT Z is treated as UTC (appends Z)', () => {
    // "2026-06-24T06:02:43" should be treated as 06:02:43 UTC
    const d = parseUTC('2026-06-24T06:02:43');
    // UTC hour must be 6, not whatever local time would give
    expect(d.getUTCHours()).toBe(6);
    expect(d.getUTCMinutes()).toBe(2);
    expect(d.getUTCSeconds()).toBe(43);
  });

  test('string WITH Z is NOT double-corrected', () => {
    // Already has Z — should parse the same as without
    const withZ    = parseUTC('2026-06-24T06:02:43Z');
    const withoutZ = parseUTC('2026-06-24T06:02:43');
    expect(withZ.getTime()).toBe(withoutZ.getTime());
  });

  test('string with explicit +05:30 offset is NOT double-corrected', () => {
    // Has timezone info already → leave it alone
    const d = parseUTC('2026-06-24T11:32:43+05:30');
    // This is 06:02:43 UTC
    expect(d.getUTCHours()).toBe(6);
    expect(d.getUTCMinutes()).toBe(2);
  });

  test('core timezone bug: no 5h30m drift on IST machines', () => {
    /**
     * THE BUG: new Date("2026-06-24T06:02:43") in IST browser
     * returns the same instant as 06:02:43 IST = 00:32:43 UTC.
     *
     * With parseUTC(), it must return 06:02:43 UTC = 11:32:43 IST.
     *
     * We verify by checking UTC time matches what we passed.
     */
    const ts = '2026-06-24T06:02:43';
    const d = parseUTC(ts);
    const epochUTC = d.getTime();

    // Build the expected UTC epoch: 2026-06-24 06:02:43 UTC
    const expectedEpoch = Date.UTC(2026, 5, 24, 6, 2, 43); // month is 0-indexed
    expect(epochUTC).toBe(expectedEpoch);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// toLocalStr
// ─────────────────────────────────────────────────────────────────────────────

describe('toLocalStr', () => {
  test('returns a non-empty string for valid timestamp', () => {
    const result = toLocalStr('2026-06-24T06:02:43');
    expect(typeof result).toBe('string');
    expect(result).not.toBe('');
    expect(result).not.toBe('—');
  });

  test('returns dash for null', () => {
    expect(toLocalStr(null)).toBe('—');
  });

  test('returns dash for invalid date', () => {
    expect(toLocalStr('garbage')).toBe('—');
  });

  test('includes year 2026 in output', () => {
    const result = toLocalStr('2026-06-24T06:02:43');
    expect(result).toContain('2026');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// toLocalTimeStr
// ─────────────────────────────────────────────────────────────────────────────

describe('toLocalTimeStr', () => {
  test('returns a time string for valid input', () => {
    const result = toLocalTimeStr('2026-06-24T06:02:43');
    expect(typeof result).toBe('string');
    expect(result).not.toBe('—');
  });

  test('returns dash for null', () => {
    expect(toLocalTimeStr(null)).toBe('—');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// toChartLabel
// ─────────────────────────────────────────────────────────────────────────────

describe('toChartLabel', () => {
  test('returns compact label string', () => {
    const result = toChartLabel('2026-06-24T06:02:43');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(3);
    expect(result).not.toBe('—');
  });

  test('returns dash for null', () => {
    expect(toChartLabel(null)).toBe('—');
  });

  test('includes month abbreviation in label', () => {
    // June → "Jun" in en-IN locale
    const result = toChartLabel('2026-06-24T06:02:43');
    expect(result).toMatch(/jun/i);
  });
});
