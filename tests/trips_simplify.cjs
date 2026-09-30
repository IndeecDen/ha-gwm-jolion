// Route simplification must remove the sawtooth without moving the road.
//
// The real route reaches the map decimated to about 13 m per point, and the median
// interior vertex of the field data is a 179 degree reversal: the parked receiver
// jittering a few metres back and forth. This checks that the drawn line drops
// that jitter, stays inside the tolerance, keeps both ends exactly on the measured
// positions, and is actually wired into the polylines the map draws.
//
// Run: node tests/trips_simplify.cjs
const fs = require("fs");
const path = require("path");

const CARD = path.join(__dirname, "..", "custom_components", "gwm_jolion", "frontend",
  "gwm-jolion-trips-card.js");
const source = fs.readFileSync(CARD, "utf8");

function grab(name) {
  const marker = `function ${name}(`;
  const start = source.indexOf(marker);
  if (start < 0) throw new Error(`not found in card source: ${name}`);
  const constant = source.split("\n").find(line => line.includes("const EARTH_M="));
  if (!constant) throw new Error("EARTH_M is not declared next to the card helpers");
  let depth = 0, i = source.indexOf("{", start);
  for (; i < source.length; i++) {
    if (source[i] === "{") depth++;
    else if (source[i] === "}") { depth--; if (depth === 0) break; }
  }
  return constant.trim() + "\n" + source.slice(start, i + 1);
}

const { simplifyPath } = new Function(grab("simplifyPath") + "\nreturn {simplifyPath};")();

const EARTH = 111320;
const toXy = (origin, point) => [
  (point[1] - origin[1]) * EARTH * Math.cos(origin[0] * Math.PI / 180),
  (point[0] - origin[0]) * EARTH];

function distanceTo(p, line) {
  let best = Infinity;
  for (let i = 0; i + 1 < line.length; i++) {
    const a = toXy(line[0], line[i]), b = toXy(line[0], line[i + 1]);
    const vx = b[0] - a[0], vy = b[1] - a[1], len2 = vx * vx + vy * vy;
    let t = len2 ? ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / len2 : 0;
    t = t < 0 ? 0 : (t > 1 ? 1 : t);
    best = Math.min(best, Math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy));
  }
  return best;
}

const fail = message => { console.error(message); process.exit(1); };
// The card calls simplifyPath with no tolerance, so the default is what ships and
// what has to be measured here. Passing a value in would hide a wrong default.
const DEFAULT_LIMIT = 10;

// A sawtooth of the real shape: the median step of the field data is 12.8 m and the
// median interior vertex is a 179 degree reversal - the receiver going back and
// forth, not a turn. On the real route a tolerance of 8 m drops 81% of the points,
// so the same has to happen here.
const sawtooth = [];
for (let i = 0; i < 40; i++) {
  sawtooth.push([55 + (i % 2 ? 4 : -4) / 111320, 37 + i * 12.8 / 111320]);
}
const smoothed = simplifyPath(sawtooth);
if (smoothed.length > sawtooth.length / 4) {
  fail(`the sawtooth survived: ${sawtooth.length} -> ${smoothed.length}`);
}
if (smoothed.length < 2) fail("the whole run was thrown away");

// Both ends stay exactly where the phone put them.
if (smoothed[0] !== sawtooth[0]) fail("the start moved");
if (smoothed[smoothed.length - 1] !== sawtooth[sawtooth.length - 1]) fail("the end moved");

// Nothing is invented: every drawn point is one the phone reported.
for (const point of smoothed) {
  if (!sawtooth.some(measured => measured === point)) fail("a point was invented");
}

// The line that gets drawn never leaves a measured point by more than the default.
let worst = 0;
for (const point of sawtooth) worst = Math.max(worst, distanceTo(toXy(sawtooth[0], point), smoothed));
if (worst > DEFAULT_LIMIT) fail(`the line strays ${worst.toFixed(1)} m from the route`);

// A genuine turn has to survive, or the route would be straightened into a ramp.
// Legs of 100 m north and 40 m east put the knee about 20 m off the chord, so only
// a default above 20 m would cut it - which is how a wrong default gets caught.
const corner = [
  [55, 37],
  [55 + 100 / 111320, 37],
  [55 + 100 / 111320, 37 + 40 / 63847],
  [55 + 200 / 111320, 37 + 40 / 63847],
];
const keptCorner = simplifyPath(corner);
if (keptCorner.length < 4) fail(`a real corner was straightened away: ${keptCorner.length} points`);
let cornerWorst = 0;
for (const point of corner) cornerWorst = Math.max(cornerWorst, distanceTo(toXy(corner[0], point), keptCorner));
if (cornerWorst > 20) fail(`the corner was cut by ${cornerWorst.toFixed(1)} m`);

// Short lines are left alone rather than reduced to two points for nothing.
if (simplifyPath([[55, 37], [55.0001, 37]]).length !== 2) fail("a two point line changed");
const straight = [[55, 37], [55.0005, 37], [55.001, 37], [55.0015, 37]];
if (simplifyPath(straight).length !== 2) fail("a straight line was not reduced");

// Wiring: without this the test above would still pass after the calls were
// removed, which is exactly the change that brings the sawtooth back. The
// stationary wander and the GPS gap lines are deliberately left raw - the first
// is part 1's verified behaviour, the second means "no data here".
// Wiring: without this the test above would still pass after the calls were
// removed, which is exactly the change that brings the sawtooth back. The route is
// handed to the map surface as `addLine(simplifyPath(...))`; the stationary wander
// and the GPS gap lines are deliberately left raw - the first is part 1's verified
// behaviour, the second means "no data here".
const simplifiedDraws = source.match(/addLine\(simplifyPath\(/g) || [];
if (simplifiedDraws.length < 2) {
  fail(`expected the speed bands and the plain route to be simplified, got ${simplifiedDraws.length}`);
}
if (/addLine\((run|segment)\b/.test(source)) {
  fail("a route polyline is handed to the surface without simplification");
}

console.log(`Sawtooth: ${sawtooth.length} -> ${smoothed.length} points, `
  + `line stays ${worst.toFixed(2)} m from the route: passed`);

