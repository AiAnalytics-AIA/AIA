// A small stroke icon set on a 24 grid (1.5 stroke, square caps), in the AIA icon
// grammar. Icons inherit currentColor. They never stand for a status: that is Glyph.
import type { ReactNode } from 'react';

const P: Record<string, ReactNode> = {
  worker: <><rect x="6" y="6" width="12" height="12" rx="1" /><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" /></>,
  research: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="M15.5 15.5L21 21M4 10.5h13M10.5 4c2 2 2 11 0 13M10.5 4c-2 2-2 11 0 13" /></>,
  compute: <><path d="M17 4H6l6 8-6 8h11" /></>,
  decision: <><path d="M4 21V5l8-2 8 2v16" /><path d="M9 21v-6h6v6" /></>,
  lookup: <><path d="M3 5h7a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H3zM21 5h-7a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h7z" /></>,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  back: <path d="M15 5l-7 7 7 7" />,
  next: <path d="M9 5l7 7-7 7" />,
  down: <path d="M5 9l7 7 7-7" />,
  up: <path d="M5 15l7-7 7 7" />,
  focusArtifact: <><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></>,
  focusChat: <><path d="M4 5h16v11H9l-5 4z" /></>,
  normal: <><rect x="3" y="4" width="18" height="16" rx="1" /><path d="M10 4v16" /></>,
  inspector: <><rect x="3" y="4" width="18" height="16" rx="1" /><path d="M15 4v16M17.5 8h1M17.5 11h1" /></>,
  attach: <path d="M20 11l-8 8a5 5 0 0 1-7-7l9-9a3.3 3.3 0 0 1 4.7 4.7l-9 9a1.7 1.7 0 0 1-2.4-2.4l8-8" />,
  at: <><circle cx="12" cy="12" r="4" /><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8" /></>,
  send: <path d="M12 20V5M6 11l6-6 6 6" />,
  stop: <rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor" stroke="none" />,
  copy: <><rect x="8" y="8" width="12" height="12" rx="1" /><path d="M16 8V4H4v12h4" /></>,
  why: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17v.5" /></>,
  open: <><path d="M14 4h6v6M20 4l-9 9" /><path d="M18 14v6H4V6h6" /></>,
  budget: <><rect x="3" y="6" width="18" height="13" rx="1" /><path d="M3 10h18M16 15h2" /></>,
  map: <><path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z" /><path d="M9 4v14M15 6v14" /></>,
  filter: <path d="M4 5h16l-6 8v6l-4 1v-7z" />,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  more: <><circle cx="5" cy="12" r="1" fill="currentColor" /><circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="19" cy="12" r="1" fill="currentColor" /></>,
  check: <path d="M5 12l5 5 9-10" />,
  lock: <><rect x="5" y="11" width="14" height="9" rx="1" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  pencil: <path d="M4 20l1-4L16 5l3 3L8 19zM14 7l3 3" />,
  plus: <path d="M12 5v14M5 12h14" />,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="M15.5 15.5L21 21" /></>,
  layers: <><path d="M12 3l9 5-9 5-9-5z" /><path d="M3 13l9 5 9-5" /></>,
  evidence: <><path d="M6 3h9l4 4v14H6z" /><path d="M14 3v5h5M9 13h7M9 17h5" /></>,
  client: <><circle cx="12" cy="8" r="4" /><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" /></>,
  population: <><circle cx="6" cy="8" r="2" /><circle cx="12" cy="6" r="2" /><circle cx="18" cy="8" r="2" /><path d="M2 20c1-3 2.5-5 4-5s3 2 4 5M8 18c1-3 2.5-5 4-5s3 2 4 5M14 20c1-3 2.5-5 4-5s3 2 4 5" /></>,
  memory: <><path d="M5 4h14v16H5z" /><path d="M9 8h6M9 12h6M9 16h3" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M5 21c1-4 4-6 7-6s6 2 7 6" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="1" /><path d="M3 10h18M8 3v4M16 3v4" /></>,
  flag: <path d="M5 21V4h11l-2 4 2 4H5" />,
  target: <><circle cx="12" cy="12" r="7" /><path d="M12 2v5M12 17v5M2 12h5M17 12h5" /></>,
  link: <><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  file: <><path d="M6 3h9l4 4v14H6z" /><path d="M14 3v5h5" /></>,
  grip: <><circle cx="9" cy="7" r=".8" fill="currentColor" /><circle cx="15" cy="7" r=".8" fill="currentColor" /><circle cx="9" cy="12" r=".8" fill="currentColor" /><circle cx="15" cy="12" r=".8" fill="currentColor" /><circle cx="9" cy="17" r=".8" fill="currentColor" /><circle cx="15" cy="17" r=".8" fill="currentColor" /></>,
};

export type IconName = keyof typeof P;

export function Icon({ name, size = 16, label }: { name: string; size?: number; label?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="square" strokeLinejoin="miter"
      role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true} className="icon">
      {P[name] ?? null}
    </svg>
  );
}

// The AIA mark: a 5 x 5 lattice where ten points form an A, the apex in signal.
export function Mark({ size = 20, onDark = false }: { size?: number; onDark?: boolean }) {
  const A = new Set(['2,0', '1,1', '3,1', '1,2', '2,2', '3,2', '0,3', '4,3', '0,4', '4,4']);
  const pts = [];
  for (let y = 0; y < 5; y++) for (let x = 0; x < 5; x++) pts.push({ x, y, on: A.has(x + ',' + y), apex: x === 2 && y === 0 });
  const ink = onDark ? 'var(--shell-ink)' : 'var(--ink)';
  return (
    <svg width={size} height={size} viewBox="0 0 50 50" aria-hidden className="mark">
      {pts.map((p) => (
        <circle key={p.x + '-' + p.y} cx={5 + p.x * 10} cy={5 + p.y * 10} r={p.on ? 3.6 : 1.4}
          fill={p.apex ? 'var(--brand-apex)' : ink} opacity={p.on ? 1 : 0.28} />
      ))}
    </svg>
  );
}
