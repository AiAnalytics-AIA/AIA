#!/usr/bin/env node
/**
 * Design evidence, re-measured from src/design/tokens.json on every run:
 *   1. WCAG 2 contrast for every text and non-text pair the system relies on, both themes.
 *   2. The categorical chart palette: lightness band, chroma floor, colour-blind
 *      separation (Machado–Oliveira–Fernandes 2009, severity 1.0; OKLab ΔE × 100),
 *      normal-vision floor, contrast vs surface.
 *   3. Family separation: client accents vs status/UI/chart colours, and each other.
 * Exits 1 on any hard failure. `--json` prints the full report.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const tokens = JSON.parse(readFileSync(join(root, "src/design/tokens.json"), "utf8"));
const byName = new Map(tokens.color.tokens.map((t) => [t.name, t]));
function hex(name, theme, d = 0) {
  const t = byName.get(name); if (!t) throw new Error(`no token ${name}`);
  const v = typeof t.value === "string" ? t.value : t.value[theme] ?? t.value.light;
  return v.startsWith("{") ? hex(v.slice(1, -1), theme, d + 1) : v;
}

// ---------- colour maths ----------
const dec = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const enc = (x) => { x = Math.min(Math.max(x, 0), 1); return x <= 0.0031308 ? 12.92 * x : 1.055 * x ** (1 / 2.4) - 0.055; };
const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
const lin = (h) => rgb(h).map(dec);
const lum = (h) => { const [r, g, b] = lin(h); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
function oklab(h) {
  const [r, g, b] = lin(h);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}
const dE = (a, b) => 100 * Math.hypot(...oklab(a).map((v, i) => v - oklab(b)[i]));
const oklch = (h) => { const [L, a, b] = oklab(h); return { L, C: Math.hypot(a, b) }; };
const CVD = {
  protan: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
  deutan: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.01182, 0.04294, 0.968881]],
};
const simulate = (h, kind) => { const v = lin(h); const M = CVD[kind]; return "#" + M.map((row) => Math.round(enc(row[0] * v[0] + row[1] * v[1] + row[2] * v[2]) * 255).toString(16).padStart(2, "0")).join(""); };

// ---------- 1. contrast ----------
const surfaces = ["surface", "surface-raised", "surface-sunken", "surface-overlay"];
const TEXT = [
  ...[...surfaces, "signal-wash", "status-running-wash", "status-world-wash", "status-you-wash", "status-fault-wash"].map((bg) => ["ink", bg, 7, "numeric/body text"]),
  ...["ink-muted", "ink-faint"].flatMap((fg) => surfaces.map((bg) => [fg, bg, 4.5, "secondary text"])),
  ["ink-muted", "signal-wash", 4.5, "secondary on selection"],
  ...["surface", "surface-raised", "surface-sunken", "signal-wash"].map((bg) => ["signal", bg, 4.5, "link / running label"]),
  ["on-signal", "signal", 4.5, "text on signal fill"],
  ...["surface", "surface-raised", "surface-sunken"].map((bg) => ["status-you-ink", bg, 4.5, "waiting-on-person text"]),
  ["on-status-you", "status-you", 7, "label on parked-on-you fill"],
  ...["surface", "surface-raised", "surface-sunken", "status-world-wash"].map((bg) => ["status-world", bg, 4.5, "waiting-on-world text"]),
  ...["surface", "surface-raised", "surface-sunken", "status-fault-wash"].map((bg) => ["status-fault", bg, 4.5, "failed text"]),
  ["on-status-fault", "status-fault", 4.5, "label on failed fill"],
  ["on-status-recovery", "status-recovery", 7, "label on recovery fill"],
  ["ink-inverse", "surface-inverse", 7, "inverse text"],
  ...[1, 2, 3, 4, 5, 6].map((i) => ["on-client", `client-${i}`, 4.5, "monogram on client accent"]),
  ["doc-ink", "doc-paper", 7, "report prose"], ["doc-muted", "doc-paper", 4.5, "captions"], ["doc-accent", "doc-paper", 4.5, "report headings accent"],
];
const NONTEXT = [
  ...["surface", "surface-raised", "surface-sunken"].map((bg) => ["border-strong", bg, 3, "control border"]),
  ...[...surfaces, "signal-wash", "status-you-wash", "status-fault-wash"].map((bg) => ["focus-ring", bg, 3, "focus ring"]),
  ["status-you", "surface", 1, "parked fill (shape carries it)"],
  ["status-recovery-hatch", "status-recovery", 3, "recovery hatch"],
  ...[1, 2, 3, 4, 5, 6].flatMap((i) => ["surface", "surface-raised"].map((bg) => [`client-${i}`, bg, 3, "client band on surface"])),
  ...["surface", "surface-raised"].map((bg) => ["viz-axis", bg, 4.5, "axis labels"]),
];
const contrastRows = [...TEXT, ...NONTEXT].flatMap(([fg, bg, min, use]) =>
  ["light", "dark"].map((theme) => { const r = contrast(hex(fg, theme), hex(bg, theme)); return { theme, fg, bg, min, use, ratio: +r.toFixed(2), pass: r >= min }; }));

// ---------- 2. chart palette ----------
const cats = [1, 2, 3, 4, 5, 6].map((i) => `viz-cat-${i}`);
const BAND = { light: [0.43, 0.77], dark: [0.48, 0.67] };
function palette(theme, n = cats.length, allPairs = false) {
  const cs = cats.slice(0, n).map((c) => hex(c, theme)); const surf = hex("surface", theme);
  const pairs = allPairs ? cs.flatMap((a, i) => cs.slice(i + 1).map((b) => [a, b])) : cs.slice(1).map((b, i) => [cs[i], b]);
  const cvd = Math.min(...pairs.flatMap(([a, b]) => ["protan", "deutan"].map((k) => dE(simulate(a, k), simulate(b, k)))));
  const normal = Math.min(...pairs.map(([a, b]) => dE(a, b)));
  const band = cs.filter((c) => { const { L } = oklch(c); return L < BAND[theme][0] || L > BAND[theme][1]; });
  const chroma = cs.filter((c) => oklch(c).C < 0.1);
  const lowContrast = cs.filter((c) => contrast(c, surf) < 3);
  return { theme, n, pairs: allPairs ? "all" : "adjacent", cvd: +cvd.toFixed(1), normal: +normal.toFixed(1), outOfBand: band, belowChroma: chroma, belowContrast3: lowContrast,
    pass: cvd >= 6 && normal >= 15 && band.length === 0 && chroma.length === 0 };
}
const paletteRows = [palette("light"), palette("dark"), palette("light", 3, true), palette("dark", 3, true)];

// ---------- 3. family separation ----------
const clientTokens = [1, 2, 3, 4, 5, 6].map((i) => `client-${i}`);
const others = tokens.color.tokens.map((t) => t.name).filter((n) => /^(status-|viz-cat-)/.test(n) || ["signal", "focus-ring", "ink", "ink-muted", "ink-faint", "border-strong"].includes(n));
const separation = ["light", "dark"].map((theme) => {
  let near = [Infinity]; let self = [Infinity];
  for (const c of clientTokens) {
    for (const o of others) { const d = dE(hex(c, theme), hex(o, theme)); if (d < near[0]) near = [d, c, o]; }
    for (const c2 of clientTokens) if (c < c2) { const d = dE(hex(c, theme), hex(c2, theme)); if (d < self[0]) self = [d, c, c2]; }
  }
  return { theme, nearestOther: +near[0].toFixed(1), pair: near.slice(1), nearestAccent: +self[0].toFixed(1), accentPair: self.slice(1), pass: near[0] >= 7 && self[0] >= 12 };
});

// ---------- report ----------
const failures = [...contrastRows.filter((r) => !r.pass), ...paletteRows.filter((r) => !r.pass), ...separation.filter((r) => !r.pass)];
if (process.argv.includes("--json")) {
  console.log(JSON.stringify({ contrast: contrastRows, palette: paletteRows, separation, failures: failures.length }, null, 2));
} else {
  const pairs = contrastRows.length / 2;
  console.log(`contrast: ${pairs} pairs × 2 themes = ${contrastRows.length} checks, ${contrastRows.filter((r) => !r.pass).length} failures`);
  for (const r of paletteRows) console.log(`palette ${r.theme} ${r.pairs} (${r.n}): CVD ΔE ${r.cvd}, normal ΔE ${r.normal}, band ${r.outOfBand.length ? "FAIL" : "ok"}, chroma ${r.belowChroma.length ? "FAIL" : "ok"}, <3:1 relief needed for ${r.belowContrast3.length} → ${r.pass ? "PASS" : "FAIL"}`);
  for (const s of separation) console.log(`client accents ${s.theme}: nearest status/UI/chart ΔE ${s.nearestOther} (${s.pair.join(" vs ")}), nearest accent ΔE ${s.nearestAccent} → ${s.pass ? "PASS" : "FAIL"}`);
  for (const f of failures) console.error("FAIL", JSON.stringify(f));
}
process.exit(failures.length ? 1 : 0);
