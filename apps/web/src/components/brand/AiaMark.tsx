/**
 * The AIA mark -- the population lattice resolving into A -- inline, so it
 * follows the theme: points in currentColor, the apex (the one calibrated
 * measurement) in --signal. public/skin/brand/aia-mark.svg is the source; the
 * geometry here is identical, and AiaMark.test.tsx fails if the two drift.
 * Minimum size 20px; below that use the favicon (public/skin/brand/README.md).
 */
const PITCH = 6;
const ORIGIN = 4;
const APEX = "2,0";
// The resolved points, as [column, row] on the 5 × 5 lattice.
const RESOLVED = new Set(["2,0", "1,1", "3,1", "1,2", "2,2", "3,2", "0,3", "4,3", "0,4", "4,4"]);

export const MARK_POINTS = Array.from({ length: 25 }, (_, i) => {
  const [c, r] = [i % 5, Math.floor(i / 5)];
  const key = `${c},${r}`;
  return {
    cx: ORIGIN + c * PITCH,
    cy: ORIGIN + r * PITCH,
    r: RESOLVED.has(key) ? 2.3 : 0.9,
    apex: key === APEX,
    faint: !RESOLVED.has(key),
  };
});

export function AiaMark({ size = 32, label, className = "" }: { size?: number; label?: string; className?: string }) {
  const a11y = label ? { role: "img", "aria-label": label } : { "aria-hidden": true as const, focusable: "false" as const };
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} {...a11y}>
      {MARK_POINTS.map((p) => (
        <circle
          key={`${p.cx}-${p.cy}`}
          cx={p.cx}
          cy={p.cy}
          r={p.r}
          fill={p.apex ? "var(--signal)" : "currentColor"}
          fillOpacity={p.faint ? 0.35 : undefined}
        />
      ))}
    </svg>
  );
}
