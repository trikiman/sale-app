const fs = require("fs");
const path = ".planning/research/SUMMARY.md";
const lines = [];
const rl = require("readline").createInterface({input: process.stdin});
rl.on("line", l => lines.push(l));
rl.on("close", () => fs.writeFileSync(path, lines.join("
")));
