// Corner rounding must change the geometry, not just the stroke.
//
// A route drawn straight through GPS samples turns on a spike at every sample, and
// Leaflet's round joins only soften the paint where two layers meet. This checks
// that the polyline handed to the map actually carries a bend, that its endpoints
// stay on the measured positions, and that it never leaves the original line by
// more than the rounding steps allow.
//
// Run: node tests/trips_corners.cjs
const fs = require("fs");
const path = require("path");

const CARD = path.join(__dirname, "..", "custom_components", "gwm_jolion", "frontend",
  "gwm-jolion-trips-card.js");
const source = fs.readFileSync(CARD, "utf8");

function grab(name) {
  const marker = `function ${name}(`;
  const start = source.indexOf(marker);
  if (start < 0) throw new Error(`not found in card source: ${name}`);
  let depth = 0, i = source.indexOf("{", start);
  for (; i < source.length; i++) {
    if (source[i] === "{") depth++;
    else if (source[i] === "}") { depth--; if (depth === 0) break; }
  }
  return source.slice(start, i + 1);
}

const { roundCorners } = new Function(grab("roundCorners") + "\nreturn {roundCorners};")();

const meters = (a, b) => {
  const rad = Math.PI / 180;
  const dLat = (b[0] - a[0]) * rad;
  const dLon = (b[1] - a[1]) * rad;
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLon / 2) ** 2;
  return 12742 * Math.asin(Math.min(1, Math.sqrt(h))) * 1000;
};

// A right angle: north, then east.
const corner = [[55.0, 37.0], [55.001, 37.0], [55.001, 37.001]];
const rounded = roundCorners(corner, 2);

const fail = message => { console.error(message); process.exit(1); };

if (rounded.length !== 4) fail(`expected 4 points after rounding, got ${rounded.length}`);
if (rounded[0][0] !== corner[0][0] || rounded[0][1] !== corner[0][1]) fail("start moved");
if (rounded[rounded.length - 1][0] !== corner[2][0]
  || rounded[rounded.length - 1][1] !== corner[2][1]) fail("end moved");

const inserted = rounded[1];
const offCorner = meters(inserted, corner[1]);
if (offCorner < 1) fail(`the bend is still on the spike (${offCorner.toFixed(1)} m)`);
// Half a step of a ~157 m leg puts the bend well inside the corner.
if (offCorner > 120) fail(`the bend leaves the line too far (${offCorner.toFixed(1)} m)`);

// Nothing may appear far from the original line.
for (const point of rounded) {
  const near = Math.min(...corner.map(other => meters(point, other)));
  if (near > 120) fail(`a point sits ${near.toFixed(1)} m off the original route`);
}

// A straight leg is densified too, but the new points must land on the line
// itself - that is what makes rounding harmless where the car drove straight.
const straight = [[55.0, 37.0], [55.001, 37.0], [55.002, 37.0]];
for (const point of roundCorners(straight, 2)) {
  const drift = Math.min(...straight.map(other => meters(point, other)));
  if (drift > 1) fail(`a straight leg was bent by ${drift.toFixed(1)} m`);
}
// A two point line has no interior vertex and must come back untouched.
if (roundCorners([[55, 37], [55.001, 37]], 2).length !== 2) fail("a two point line was altered");

// The rounding only reaches the map if the drawn polylines go through it. Without
// this the test above would still pass after the calls were removed, which is
// exactly the change that makes the corners sharp again on screen.
const drawn = source.split("\n").filter(line => /L\.polyline\(/.test(line));
const roundedDraws = drawn.filter(line => /L\.polyline\(roundCorners\(/.test(line));
if (roundedDraws.length === 0) fail("no drawn polyline is passed through roundCorners");
const unsharpened = drawn.filter(line => /L\.polyline\((run|segment|points)\b/.test(line));
if (unsharpened.length) {
  fail(`drawn straight through the samples: ${unsharpened.map(line => line.trim().slice(0, 40)).join(" | ")}`);
}

console.log(`Corners: ${corner.length} points -> ${rounded.length}, bend ${offCorner.toFixed(1)} m off the spike: passed`);
