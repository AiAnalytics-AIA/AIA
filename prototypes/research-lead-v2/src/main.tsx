import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/app.css';
import { App } from './app/App';
import { initStore, setFast, getState } from './app/store';
import { seedDesign } from './app/seed';
import { loadScenario, SCENARIOS } from './app/scenarios';

// ?s=<scenario>&fast=1&auto=0 — used by the browser checks and screenshots.
const q = new URLSearchParams(location.search);
initStore(seedDesign());
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
// A bare #B (scenario id) also works, for the published single-file page.
const hash = location.hash.replace('#', '');
const id = q.get('s') ?? (hash || 'A');
setFast(q.get('fast') === '1');
loadScenario(SCENARIOS.some((x) => x.id === id) ? id : 'A', { autorun: q.get('auto') !== '0' });
if (q.get('fast') === '1') setFast(true);
// Read-only handle for the browser checks (scripts/verify.mjs).
(window as unknown as { __aia: unknown }).__aia = { getState };
window.addEventListener('hashchange', () => {
  const h = location.hash.replace('#', '');
  if (SCENARIOS.some((x) => x.id === h)) loadScenario(h);
});
