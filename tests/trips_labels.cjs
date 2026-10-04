// Marker lettering: one letter per parking, not per appearance.
//
// A car left in the same place for several nights used to consume one letter per
// day, so the first stop of the next morning was labelled D. The check runs the
// card's own helper straight from the bundled source - the browser scenario cannot
// build the repeated-key case, but this can.
//
// Run: node tests/trips_labels.cjs
const fs = require("fs");
const path = require("path");

const CARD = path.join(__dirname, "..", "custom_components", "gwm_jolion", "frontend",
  "gwm-jolion-trips-card.js");
const source = fs.readFileSync(CARD, "utf8");

// These helpers are written as single lines in the bundle.
function grab(name) {
  const line = source.split("\n").find(entry => entry.includes(`function ${name}(`));
  if (!line) throw new Error(`not found in card source: ${name}`);
  return line.trim();
}

const helpers = ["dayInZone", "dateRange", "pointLabel", "parkingOccurrences"].map(grab).join("\n");
const { parkingOccurrences } = new Function(helpers + "\nreturn {parkingOccurrences};")();

const DAY = 86400;
const base = Date.parse("2026-09-18T00:00:00Z") / 1000;
const spots = [
  { latitude: 55.74, longitude: 37.59, start: base, end: null, observed_until: base + 3 * DAY, duration: 3 * DAY },
  { latitude: 55.90, longitude: 37.80, start: base + 4 * DAY, end: null, duration: 600 },
  { latitude: 56.10, longitude: 37.99, start: base + 5 * DAY, end: null, duration: 600 },
];

const labelled = parkingOccurrences(spots, "2026-09-18", "2026-09-24", "UTC", 0);
const labels = labelled.map(item => item.label);
const offsets = labelled.map(item => item.offset_index);

const expectedLabels = ["A", "B", "C", "D", "E", "F"];
const expectedOffsets = [0, 1, 2, 3, 0, 0];

if (JSON.stringify(labels) !== JSON.stringify(expectedLabels)) {
  console.error(`letters: ${labels.join(",")} - expected ${expectedLabels.join(",")}`);
  process.exit(1);
}
if (JSON.stringify(offsets) !== JSON.stringify(expectedOffsets)) {
  console.error(`repeats must be moved aside: ${offsets.join(",")}`);
  process.exit(1);
}
const afterRouteStart = parkingOccurrences(spots, "2026-09-18", "2026-09-24", "UTC", 1).map(item => item.label);
if (JSON.stringify(afterRouteStart) !== JSON.stringify(["B", "C", "D", "E", "F", "G"])) {
  console.error(`letters after route start: ${afterRouteStart.join(",")} - expected B,B,B,B,C,D`);
  process.exit(1);
}
console.log(`Markers: ${labels.length}, route-start offset labels ${afterRouteStart.join(",")} - passed`);
