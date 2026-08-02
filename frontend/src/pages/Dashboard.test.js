/**
 * Tests for Dashboard.js filter cascade logic (Bug Fix 3b).
 *
 * When a location is selected, the device dropdown should only show
 * devices that have readings at that location.
 *
 * We test the filteredDeviceIds computation logic directly.
 *
 * Run:
 *   cd frontend && npm test -- --watchAll=false src/pages/Dashboard.test.js
 */


// ─────────────────────────────────────────────────────────────────────────────
// Pure logic test — no React rendering needed
// Mirrors the computation in Dashboard.js:
//   const filteredDeviceIds = selectedLocation
//     ? [...new Set(data.filter(r => r.gateway_id === selectedLocation).map(r => r.node_id))]
//     : deviceIds;
// ─────────────────────────────────────────────────────────────────────────────

function computeFilteredDeviceIds(data, selectedLocation, allDeviceIds) {
  return selectedLocation
    ? [...new Set(data.filter(r => r.gateway_id === selectedLocation).map(r => r.node_id))]
    : allDeviceIds;
}

const SAMPLE_DATA = [
  { gateway_id: 'chandigarh', node_id: 'D001', moisture: 45.0 },
  { gateway_id: 'chandigarh', node_id: 'D002', moisture: 38.0 },
  { gateway_id: 'chandigarh', node_id: 'D001', moisture: 42.0 }, // duplicate D001
  { gateway_id: 'sangrur',    node_id: 'D003', moisture: 55.0 },
  { gateway_id: 'sangrur',    node_id: 'D004', moisture: 60.0 },
];

const ALL_DEVICE_IDS = ['D001', 'D002', 'D003', 'D004'];


describe('Dashboard filteredDeviceIds (Bug Fix 3b — location cascade)', () => {
  test('returns all device IDs when no location selected', () => {
    const result = computeFilteredDeviceIds(SAMPLE_DATA, '', ALL_DEVICE_IDS);
    expect(result).toEqual(ALL_DEVICE_IDS);
  });

  test('returns only devices at chandigarh when chandigarh selected', () => {
    const result = computeFilteredDeviceIds(SAMPLE_DATA, 'chandigarh', ALL_DEVICE_IDS);
    expect(result).toContain('D001');
    expect(result).toContain('D002');
    expect(result).not.toContain('D003');
    expect(result).not.toContain('D004');
  });

  test('returns only devices at sangrur when sangrur selected', () => {
    const result = computeFilteredDeviceIds(SAMPLE_DATA, 'sangrur', ALL_DEVICE_IDS);
    expect(result).toContain('D003');
    expect(result).toContain('D004');
    expect(result).not.toContain('D001');
    expect(result).not.toContain('D002');
  });

  test('deduplicates device IDs (D001 appears twice in data but once in result)', () => {
    const result = computeFilteredDeviceIds(SAMPLE_DATA, 'chandigarh', ALL_DEVICE_IDS);
    const d001Count = result.filter(id => id === 'D001').length;
    expect(d001Count).toBe(1);
  });

  test('returns empty array for unknown location', () => {
    const result = computeFilteredDeviceIds(SAMPLE_DATA, 'nonexistent_site', ALL_DEVICE_IDS);
    expect(result).toHaveLength(0);
  });

  test('returns empty array when data is empty and location selected', () => {
    const result = computeFilteredDeviceIds([], 'chandigarh', ALL_DEVICE_IDS);
    expect(result).toHaveLength(0);
  });

  test('uses allDeviceIds (not data) when no location selected', () => {
    /**
     * This is the key: even if `data` is [] (e.g. after time filter with no results),
     * the dropdown still shows all registered device IDs (from /api/nodes).
     */
    const result = computeFilteredDeviceIds([], '', ALL_DEVICE_IDS);
    expect(result).toEqual(ALL_DEVICE_IDS);
    expect(result).toHaveLength(4);
  });
});


// ─────────────────────────────────────────────────────────────────────────────
// Refresh button — passes timeRange correctly (Bug Fix 3a)
// ─────────────────────────────────────────────────────────────────────────────

describe('Dashboard refresh button timeRange', () => {
  /**
   * Before fix: <button onClick={fetchData} ...>
   * After fix:  <button onClick={() => fetchData(timeRange)} ...>
   *
   * We simulate the two behaviors and verify the difference.
   */

  test('calling fetchData without argument loses timeRange (pre-fix behavior)', () => {
    let capturedTimeRange;
    function fetchData(tr) { capturedTimeRange = tr; }

    // Old broken: onClick={fetchData} — React passes the event object, not timeRange
    const syntheticEvent = { type: 'click' };
    fetchData(syntheticEvent);

    // capturedTimeRange is the event object, not '24' or '168'
    expect(capturedTimeRange).not.toBe('24');
    expect(typeof capturedTimeRange).toBe('object');
  });

  test('calling () => fetchData(timeRange) passes timeRange correctly (post-fix)', () => {
    let capturedTimeRange;
    function fetchData(tr) { capturedTimeRange = tr; }
    const timeRange = '24';

    // New fixed: onClick={() => fetchData(timeRange)}
    const clickHandler = () => fetchData(timeRange);
    clickHandler(); // simulate click

    expect(capturedTimeRange).toBe('24');
  });

  test('works with different timeRange values', () => {
    const testCases = ['1', '6', '24', '168', '720', 'all'];
    testCases.forEach(tr => {
      let captured;
      const fetchData = (timeRange) => { captured = timeRange; };
      const handler = () => fetchData(tr);
      handler();
      expect(captured).toBe(tr);
    });
  });
});
