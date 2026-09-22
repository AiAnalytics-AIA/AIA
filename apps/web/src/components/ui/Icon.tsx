/**
 * The AIA icon set: 24-unit grid, 1.5 stroke, square caps, mitred joins,
 * currentColor. Same paths as public/brand (Icons group of the design source).
 * Never used to stand for a status — that is StatusGlyph.
 */
const ICONS = {
  stage: ["M2 12h5", "M17 12h5", "c:12,12,5"],
  revision: ["M8 3h11v15H8z", "M5 6v15h11"],
  fingerprint: ["M9.5 3.5 7.5 20.5", "M16.5 3.5l-2 17", "M4 8.5h16.5", "M3.5 15.5H20"],
  artifact: ["M6 3h8.5L19 7.5V21H6z", "M14 3v5h5"],
  gate: ["M5 3v18", "M19 3v18", "M5 8h14", "M5 12h14", "M3 21h4", "M17 21h4"],
  reservation: ["M6 5H3v14h3", "M18 5h3v14h-3", "c:12,12,4.5", "M12 9.5v5"],
  recovery: ["M12 2.5 21.5 12 12 21.5 2.5 12z", "M12 7.5v6", "M12 15.8v1.5"],
  ledger: ["M5 3h14v18H5z", "M8 7.5h8", "M8 11h8", "M8 14.5h8", "M8 18h5"],
  budget: ["M2.5 9.5h19v5h-19z", "M10 9.5v5", "M14 9.5v5", "M2.5 18h19"],
  provider: ["M4 4h16v6H4z", "M4 14h16v6H4z", "M7.5 7h1", "M7.5 17h1"],
  client: ["M4 21V7l8-4 8 4v14", "M2.5 21h19", "M10 21v-6h4v6"],
  study: ["M4 5h6l2 2h8v13H4z", "M4 10h16"],
  suppressed: ["M6 11h12v10H6z", "M8.5 11V7.5a3.5 3.5 0 0 1 7 0V11"],
  portfolio: ["M3 4h8v7H3z", "M13 4h8v7h-8z", "M3 13h8v7H3z", "M13 13h8v7h-8z"],
  export: ["M12 3v12", "M7.5 7.5 12 3l4.5 4.5", "M4 14v7h16v-7"],
  signoff: ["M3 17c2-4 4-6 5-3s2.5 5 4 1.5 3-4 4-1.5", "M14 21h7"],
  check: ["M4.5 12.5 9.5 17.5 19.5 6.5"],
  close: ["M5 5l14 14", "M19 5 5 19"],
  chevron: ["M9 5l7 7-7 7"],
  clock: ["c:12,12,8.5", "M12 7.5V12l3 2"],
} as const;
export type IconName = keyof typeof ICONS;

export function Icon({ name, size = 16, label }: { name: IconName; size?: number; label?: string }) {
  return (
    <svg
      className="inline-block shrink-0 align-[-3px]" width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={1.5} strokeLinecap="square" strokeLinejoin="miter"
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
    >
      {ICONS[name].map((d, i) => {
        if (d.startsWith("c:")) { const [cx, cy, r] = d.slice(2).split(","); return <circle key={i} cx={cx} cy={cy} r={r} />; }
        return <path key={i} d={d} />;
      })}
    </svg>
  );
}
