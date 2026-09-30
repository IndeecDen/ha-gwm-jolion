// Before/after on the real runs, using the shipped function straight from the card.
const fs = require("fs");
const path = require("path");

const CARD = path.join(__dirname, "..", "custom_components", "gwm_jolion", "frontend",
  "gwm-jolion-trips-card.js");
const source = fs.readFileSync(CARD, "utf8");
const constant = source.split("\n").find(line => line.includes("const EARTH_M="));
const start = source.indexOf("function simplifyPath(");
let depth = 0, i = source.indexOf("{", start);
for (; i < source.length; i++) {
  if (source[i] === "{") depth++;
  else if (source[i] === "}") { depth--; if (depth === 0) break; }
}
const { simplifyPath } = new Function(constant.trim() + "\n" + source.slice(start, i + 1)
  + "\nreturn {simplifyPath};")();

const EARTH = 111320;
const runs = JSON.parse(fs.readFileSync(path.join(__dirname, "runs.json"), "utf8"));

const toXy = (origin, point) => [
  (point[1] - origin[1]) * EARTH * Math.cos(origin[0] * Math.PI / 180),
  (point[0] - origin[0]) * EARTH];

function worstStray(original, drawn) {
  let worst = 0;
  for (const point of original) {
    const p = toXy(drawn[0], point);
    let best = Infinity;
    for (let k = 0; k + 1 < drawn.length; k++) {
      const a = toXy(drawn[0], drawn[k]), b = toXy(drawn[0], drawn[k + 1]);
      const vx = b[0] - a[0], vy = b[1] - a[1], len2 = vx * vx + vy * vy;
      let t = len2 ? ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / len2 : 0;
      t = t < 0 ? 0 : (t > 1 ? 1 : t);
      best = Math.min(best, Math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy));
    }
    worst = Math.max(worst, best);
  }
  return worst;
}

let before = 0, after = 0, worst = 0, endsKept = 0, total = 0;
for (const dayRuns of Object.values(runs)) {
  for (const [, line] of dayRuns) {
    total++;
    const drawn = simplifyPath(line);
    before += line.length; after += drawn.length;
    worst = Math.max(worst, worstStray(line, drawn));
    if (drawn[0] === line[0] && drawn[drawn.length - 1] === line[line.length - 1]) endsKept++;
  }
}
console.log(`полос: ${total}`);
console.log(`точек на карте: ${before} -> ${after} (${(100 * after / before).toFixed(0)}% осталось)`);
console.log(`худший уход линии от измеренной точки: ${worst.toFixed(2)} м`);
console.log(`оба конца на измеренных местах: ${endsKept}/${total}`);
console.log(worst <= 8.05 && endsKept === total ? "OK" : "ПРОВАЛ");
process.exit(worst <= 8.05 && endsKept === total ? 0 : 1);
