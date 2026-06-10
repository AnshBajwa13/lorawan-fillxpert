// Validation script for SensorChart.js and Dashboard.js
const fs = require('fs');

let allPass = true;

function check(label, ok) {
  console.log((ok ? '[PASS]' : '[FAIL]') + ' ' + label);
  if (!ok) allPass = false;
}

// SensorChart.js checks
const src = fs.readFileSync('/app/src/components/SensorChart.js', 'utf8');
check('recharts import present',      src.includes("from 'recharts'"));
check('ResponsiveContainer used',     src.includes('ResponsiveContainer'));
check('LineChart used',               src.includes('LineChart'));
check('filteredData prop',            src.includes('filteredData'));
check('toggleMetric function',        src.includes('toggleMetric'));
check('METRICS config array',         src.includes('const METRICS'));
check('ChartTooltip component',       src.includes('ChartTooltip'));
check('CSS import',                   src.includes("SensorChart.css"));
check('export default SensorChart',   src.includes('export default SensorChart'));
check('useMemo for chartData',        src.includes('useMemo'));
check('ReferenceLine (30% moisture)', src.includes('ReferenceLine'));
check('connectNulls on Line',         src.includes('connectNulls'));

// CSS checks
const css = fs.readFileSync('/app/src/components/SensorChart.css', 'utf8');
check('CSS chart-panel class',        css.includes('.chart-panel'));
check('CSS chart-toggle class',       css.includes('.chart-toggle'));
check('CSS chart-empty class',        css.includes('.chart-empty'));
check('CSS chart-tooltip class',      css.includes('.chart-tooltip'));

// Dashboard.js checks
const dash = fs.readFileSync('/app/src/pages/Dashboard.js', 'utf8');
check('Dashboard imports SensorChart',          dash.includes("import SensorChart"));
check('Dashboard renders <SensorChart',         dash.includes('<SensorChart'));
check('Dashboard passes filteredData to chart', dash.includes('filteredData={filteredData}'));
check('Dashboard passes selectedDevice',        dash.includes('selectedDevice={selectedDevice}'));
check('Dashboard passes selectedLocation',      dash.includes('selectedLocation={selectedLocation}'));

console.log('\n--- RESULT ---');
if (allPass) {
  console.log('ALL CHECKS PASSED - SensorChart is ready');
} else {
  console.log('SOME CHECKS FAILED - see above');
  process.exit(1);
}
