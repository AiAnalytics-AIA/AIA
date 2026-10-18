// One store for the whole prototype. Components read it through useApp(); every
// change goes through update(), which clones, applies and notifies. Scenario
// scripts are plain async functions that call update() between sleeps, so the
// same transitions drive the interactive flows and the demo seeds.
import { useSyncExternalStore } from 'react';
import type { AppState } from '../model/types';

type Listener = () => void;

let state: AppState;
const listeners = new Set<Listener>();

export function initStore(s: AppState) { state = s; }
export function getState(): AppState { return state; }

export function update(fn: (draft: AppState) => void) {
  const next = structuredClone(state);
  fn(next);
  state = next;
  listeners.forEach((l) => l());
}

export function replaceState(next: AppState) {
  state = next;
  listeners.forEach((l) => l());
}

function subscribe(l: Listener) { listeners.add(l); return () => { listeners.delete(l); }; }

// Components subscribe to the whole state object (stable between updates) and
// select during render, so a selector may close over props safely. Every update
// re-renders subscribers; at prototype scale that is cheap.
export function useApp<T>(select: (s: AppState) => T): T {
  const s = useSyncExternalStore(subscribe, () => state);
  return select(s);
}

// ---- timing: scripted work runs on real timers; demo seeds run instantly ----
let fast = false;
let cancelToken = 0;
const timers = new Set<ReturnType<typeof setTimeout>>();

export function setFast(v: boolean) { fast = v; }
export function isFast() { return fast; }

export function sleep(ms: number): Promise<void> {
  // Fast mode still yields to the event loop, so the page stays responsive.
  if (fast) return new Promise((resolve) => setTimeout(resolve, 0));
  return new Promise((resolve) => {
    const t = setTimeout(() => { timers.delete(t); resolve(); }, ms);
    timers.add(t);
  });
}

export function clearTimers() { timers.forEach((t) => clearTimeout(t)); timers.clear(); }

export class Stopped extends Error { constructor() { super('stopped'); } }
export function token() { return cancelToken; }
export function cancelAll() { cancelToken++; }
export function check(t: number) { if (t !== cancelToken) throw new Stopped(); }

// ---- layout preferences persist per browser; never moved during a task ----
const KEY = 'aia-research-lead-v2';
export function loadPrefs(): { split?: number } {
  try { return JSON.parse(window.localStorage.getItem(KEY) || '{}'); } catch { return {}; }
}
export function savePrefs(p: { split: number }) {
  try { window.localStorage.setItem(KEY, JSON.stringify(p)); } catch { /* storage may be blocked */ }
}

let seq = 0;
export function nextId(prefix: string) { seq += 1; return prefix + '-' + seq.toString(36); }
export function resetIds(n = 0) { seq = n; }
