#!/usr/bin/env node
// Execute functions extracted from the vendored ui_app.html under Node, on given inputs.
//
// The research functions of the 18.6.6 frontend (AIA-reference ui-capability-ledger.md:
// 88 of 737 carry methodology or compute numbers) are ported server-side from their
// JavaScript. Before a port, its fixture is captured by running the ORIGINAL function
// -- extracted verbatim by tools/ui_functions.py from the unit, which is byte-identical
// to the audited archive -- on authored inputs. This runner is that execution step,
// the same technique the reference used for fixtures F5-F9 (their
// runtime_environment.note: "Frontend math executed in Node from functions extracted
// verbatim from ui_app.html").
//
// It evaluates only the sources it is handed (the function under test, the helpers it
// calls, and any `globals` the case declares) inside a `vm` context with NO `document`,
// NO `window` and NO network, so a function that reaches for the DOM fails loudly
// instead of silently reading an empty page. Non-finite numbers are preserved as
// strings ("NaN", "Infinity") because JSON cannot carry them; functions returned inside
// results are recorded as "[function]".
//
// Protocol (stdin -> stdout, one JSON document each):
//   {
//     "sources": ["const clamp=(v,a,b)=>...;", "function normalizer66(values,mode,bounds){...}"],
//     "cases": [
//       {"id": "range_basic", "globals": {}, "call": "normalizer66", "args": [[1,2,3], "range", null],
//        "probe": "(r, c) => c.probe_points.map(r.t)", "extra": {"probe_points": [0, 1, 2]}}
//     ]
//   }
//   -> {"node": "v22.x", "results": [{"id": "range_basic", "ok": true, "value": ...} | {"id", "ok": false, "error"}]}
//
// `probe` is optional: an arrow-function source evaluated in the same context and
// applied to the return value and the case's `extra`, for functions that return
// closures (normalizer66 returns {t: x => ...}) or for picking part of a result.
// `globals` are assigned on the context before the call (e.g. a `PROJECT` object a
// function reads), and reset for every case.

import { readFileSync } from "node:fs";
import vm from "node:vm";

function sanitize(value, seen = new WeakSet()) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : String(value);
  }
  if (typeof value === "function") return "[function]";
  if (value === undefined) return null;
  if (value === null || typeof value !== "object") return value;
  if (seen.has(value)) return "[circular]";
  seen.add(value);
  if (Array.isArray(value)) return value.map((v) => sanitize(v, seen));
  const out = {};
  for (const key of Object.keys(value)) out[key] = sanitize(value[key], seen);
  return out;
}

function main() {
  const request = JSON.parse(readFileSync(0, "utf8"));
  const sources = request.sources || [];
  const results = [];
  for (const c of request.cases || []) {
    // A fresh context per case: nothing leaks between cases, and a case's globals
    // never outlive it.
    const context = vm.createContext({ Math, Number, String, Array, Object, JSON, Boolean, Date, Map, Set, structuredClone });
    try {
      for (const src of sources) vm.runInContext(src, context, { filename: "ui_app.extracted.js" });
      for (const [name, val] of Object.entries(c.globals || {})) context[name] = structuredClone(val);
      const fn = vm.runInContext(c.call, context);
      if (typeof fn !== "function") throw new TypeError(`${c.call} is not a function in the extracted sources`);
      const args = structuredClone(c.args || []);
      let value = fn(...args);
      if (c.probe) {
        const probe = vm.runInContext(`(${c.probe})`, context);
        value = probe(value, c.extra || {}, args);
      }
      results.push({ id: c.id, ok: true, value: sanitize(value) });
    } catch (err) {
      results.push({ id: c.id, ok: false, error: `${err && err.name}: ${err && err.message}` });
    }
  }
  process.stdout.write(JSON.stringify({ node: process.version, results }) + "\n");
}

main();
