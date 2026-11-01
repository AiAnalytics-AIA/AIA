// The Metodika module cards' drawings and accents (settings-redesign chunk 10; the product owner,
// 2026-10-21: "add some design elements to each card ... something that references it"). Each
// module has a wayfinding accent (never a status colour, never green: green is "in force") and a
// small inline drawing of what it computes. Decorative: aria-hidden; the card's title is the label.

// The runtime properties tokens.css defines, never Tailwind's --color-*, which it emits only for a class in use.
const v = (name: string) => `var(--${name})`;

/** A module's accent: the card's top border and its arrow. Unknown modules read neutral. */
const ACCENT: Record<string, string> = {
  sociomap: "hue-blue",
  support: "hue-teal",
  aggregation: "hue-blue",
  weighting: "hue-orange",
  response: "hue-violet",
  readiness: "hue-slate",
  field_origin: "hue-slate",
};
export const accentOf = (id: string) => ACCENT[id] ?? "border-strong";

export function ModuleArt({ id }: { id: string }) {
  const accent = v(accentOf(id));
  const ink = v("ink-muted");
  const common = { "aria-hidden": true, focusable: false, className: "block h-full w-full" } as const;
  switch (id) {
    case "sociomap":
      // A miniature object map: terraced hills on the map's stage, objects, links, one negative.
      return (
        <svg {...common} viewBox="0 0 320 96" preserveAspectRatio="xMidYMid slice">
          <rect width="320" height="96" fill={v("viz-stage")} />
          {[[90, 48, 46, 2], [90, 48, 30, 5], [90, 48, 15, 8], [220, 44, 52, 3], [220, 44, 34, 6], [220, 44, 18, 9]].map(([cx, cy, r, k], i) => (
            <ellipse key={i} cx={cx} cy={cy} rx={r * 1.4} ry={r} fill={v(`viz-terrace-${k}`)} opacity="0.9" />
          ))}
          <line x1="90" y1="48" x2="220" y2="44" stroke={v("viz-link-positive")} strokeWidth="2" />
          <line x1="150" y1="78" x2="220" y2="44" stroke={v("viz-link-negative")} strokeWidth="2" strokeDasharray="4 3" />
          {[[90, 48], [220, 44], [150, 78], [270, 70]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r="5" fill={v("viz-stage-ink")} />)}
        </svg>
      );
    case "support":
      // Bars, with the n = 30 line a cell must reach to be shown.
      return (
        <svg {...common} viewBox="0 0 160 72">
          {[22, 40, 58, 30, 48].map((h, i) => <rect key={i} x={14 + i * 28} y={64 - h} width="18" height={h} rx="2" fill={accent} opacity="0.8" />)}
          <line x1="6" y1="34" x2="154" y2="34" stroke={v("ink")} strokeWidth="1.5" strokeDasharray="3 3" />
          <text x="150" y="30" textAnchor="end" fontSize="9" fill={ink}>n = 30</text>
        </svg>
      );
    case "aggregation":
      // Estimates with their intervals.
      return (
        <svg {...common} viewBox="0 0 160 72">
          {[[30, 30, 10], [70, 42, 14], [110, 24, 8], [140, 36, 12]].map(([x, y, e], i) => (
            <g key={i}><line x1={x} y1={y - e} x2={x} y2={y + e} stroke={accent} strokeWidth="2" /><circle cx={x} cy={y} r="4" fill={accent} /></g>
          ))}
          <line x1="10" y1="64" x2="152" y2="64" stroke={ink} strokeWidth="1" />
        </svg>
      );
    case "weighting":
      // A balance scale.
      return (
        <svg {...common} viewBox="0 0 160 72" fill="none" stroke={accent} strokeWidth="2" strokeLinecap="round">
          <line x1="80" y1="12" x2="80" y2="62" /><line x1="60" y1="62" x2="100" y2="62" />
          <line x1="36" y1="22" x2="124" y2="18" />
          <path d="M36 22 L26 42 H46 Z" /><path d="M124 18 L114 38 H134 Z" />
        </svg>
      );
    case "response":
      // Probabilities, then the answer the code draws.
      return (
        <svg {...common} viewBox="0 0 160 72">
          {[0.15, 0.35, 0.3, 0.2].map((p, i) => <rect key={i} x={12} y={8 + i * 15} width={p * 160} height="10" rx="2" fill={accent} opacity={i === 1 ? 1 : 0.45} />)}
          <path d="M100 26 H128" stroke={ink} strokeWidth="1.5" markerEnd="none" />
          <circle cx="140" cy="26" r="9" fill="none" stroke={accent} strokeWidth="2" /><circle cx="140" cy="26" r="4" fill={accent} />
        </svg>
      );
    case "readiness":
      // A checklist and a progress ring.
      return (
        <svg {...common} viewBox="0 0 160 72" fill="none" strokeLinecap="round">
          {[16, 32, 48].map((y, i) => <g key={y}><rect x="14" y={y - 5} width="10" height="10" rx="2" stroke={accent} strokeWidth="1.5" />{i < 2 ? <path d={`M16 ${y} l3 3 l5 -6`} stroke={accent} strokeWidth="1.5" /> : null}<line x1="32" y1={y} x2="80" y2={y} stroke={ink} strokeWidth="1.5" /></g>)}
          <circle cx="124" cy="34" r="20" stroke={v("border")} strokeWidth="5" />
          <circle cx="124" cy="34" r="20" stroke={accent} strokeWidth="5" strokeDasharray="84 126" transform="rotate(-90 124 34)" />
        </svg>
      );
    default:
      // The population's field policy and any module without its own drawing: a neutral grid.
      return (
        <svg {...common} viewBox="0 0 160 72" fill="none" stroke={ink} strokeWidth="1">
          {[0, 1, 2, 3].map((r) => [0, 1, 2, 3, 4].map((c) => <rect key={`${r}-${c}`} x={14 + c * 28} y={8 + r * 15} width="22" height="10" rx="2" opacity={(r + c) % 3 ? 0.4 : 0.9} />))}
        </svg>
      );
  }
}
