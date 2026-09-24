// Test support: run the classic interface's own functions under Node.
//
// Sources come from the vendored ui_app.html through tools/ui_functions.py
// (`effective`: the binding the browser runs, reassignments included), and are
// evaluated in a bare `vm` context -- no DOM, no network -- so a port can be
// compared with the original on the same inputs. Never imported by app code.

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import vm from "node:vm";

export const REPO = join(process.cwd(), "../..");
export const UI_APP = readFileSync(join(REPO, "legacy/npc-panel-18.6.6/app/ui_app.html"), "utf8");

/** The source of the binding of `name` that runs in the browser. */
export function effective(name: string): string {
  return execFileSync("python3", [join(REPO, "tools/ui_functions.py"), "effective", name], { encoding: "utf8" });
}

/** A statement of ui_app.html, from `start` to the first `end` after it, verbatim; the last occurrence with `last`. */
export function statement(start: string, end: string, { last = false }: { last?: boolean } = {}): string {
  const i = last ? UI_APP.lastIndexOf(start) : UI_APP.indexOf(start);
  if (i < 0) throw new Error(`not in ui_app.html: ${start}`);
  const j = UI_APP.indexOf(end, i);
  if (j < 0) throw new Error(`no ${JSON.stringify(end)} after ${start}`);
  return UI_APP.slice(i, j + end.length);
}

export type Legacy = {
  /** Evaluate `expr` with `globals` assigned first. */
  run: <T>(expr: string, globals?: Record<string, unknown>) => T;
};

/** A context holding `prelude` (verbatim statements) and the named functions. */
export function legacyContext(opts: { prelude?: string[]; functions: string[]; now?: number }): Legacy {
  const ctx = vm.createContext({});
  if (opts.now !== undefined) {
    vm.runInContext(`const __RealDate=Date;Date=class extends __RealDate{static now(){return ${opts.now}}};`, ctx);
  }
  for (const s of opts.prelude ?? []) vm.runInContext(s, ctx);
  for (const name of opts.functions) vm.runInContext(effective(name), ctx);
  return {
    run: <T,>(expr: string, globals: Record<string, unknown> = {}) => {
      for (const [k, v] of Object.entries(globals)) (ctx as Record<string, unknown>)[k] = structuredClone(v);
      return vm.runInContext(expr, ctx) as T;
    },
  };
}
