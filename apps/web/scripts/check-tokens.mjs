#!/usr/bin/env node
// Token lint: the Modernist token sheet is the only place raw colors and radii may live.
// Fails if any .ts/.tsx/.css under app/, components/ or styles/ (except styles/modernist.css)
// contains a raw hex color, or a border-radius that isn't 0 / var(--radius-*).
// Escape hatch for a deliberate exception: put `tokens-ignore` in a comment on that line.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const DIRS = ["app", "components", "styles"];
const EXCLUDE = new Set([join("styles", "modernist.css")]);
const EXT = /\.(ts|tsx|css)$/;

const HEX = /(^|[^&\w])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_-])/g;
const RADIUS_CSS = /border(?:-(?:top|bottom)-(?:left|right))?-radius\s*:\s*([^;}]+)/gi;
const RADIUS_JS = /border(?:Top|Bottom)?(?:Left|Right)?Radius\s*:\s*([^,}\n]+)/g;
const OK_RADIUS = /^\s*(?:["'`]?\s*(?:0(?:px)?|var\(--radius-(?:sm|md|lg)\))\s*["'`]?\s*)+(?:!important)?\s*$/;

function walk(dir, out = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of entries) {
    if (name === "node_modules" || name === ".next") continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (EXT.test(name)) out.push(p);
  }
  return out;
}

const problems = [];
for (const d of DIRS) {
  for (const file of walk(join(root, d))) {
    const rel = relative(root, file);
    if (EXCLUDE.has(rel)) continue;
    const lines = readFileSync(file, "utf8").split(/\r?\n/);
    lines.forEach((line, i) => {
      if (line.includes("tokens-ignore")) return;
      for (const m of line.matchAll(HEX)) {
        problems.push(`${rel.split(sep).join("/")}:${i + 1}  raw hex color "#${m[0].split("#")[1]}" — use a --color-* token`);
      }
      const radiusRe = file.endsWith(".css") ? RADIUS_CSS : RADIUS_JS;
      for (const m of line.matchAll(radiusRe)) {
        const value = (m[1] ?? "").trim();
        if (!OK_RADIUS.test(value)) {
          problems.push(`${rel.split(sep).join("/")}:${i + 1}  border-radius "${value}" — Modernist radii are 0 (or var(--radius-*))`);
        }
      }
    });
  }
}

if (problems.length) {
  console.error(`check:tokens — ${problems.length} problem(s):\n  ${problems.join("\n  ")}`);
  process.exit(1);
}
console.log("check:tokens — OK (no raw hex colors or non-zero radii outside styles/modernist.css)");
