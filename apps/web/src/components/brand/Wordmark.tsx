/**
 * The AIA wordmark, inline so it follows the theme: strokes and points in
 * currentColor, the first point of the I (the one calibrated measurement) in
 * --signal. Geometry is identical to public/brand/aia-wordmark.svg.
 */
export function Wordmark({ height = 20, label }: { height?: number; label: string }) {
  return (
    <svg height={height} viewBox="0 0 126 40" role="img" aria-label={label}>
      <path d="M1 40 20 1.5 39 40" fill="none" stroke="currentColor" strokeWidth={6} strokeMiterlimit={10} />
      {[13, 20, 27].map((x) => <circle key={`a${x}`} cx={x} cy={28} r={2.3} fill="currentColor" />)}
      {[0, 1, 2, 3, 4].map((i) => <circle key={`i${i}`} cx={63} cy={4 + i * 8} r={3.2} fill={i === 0 ? "var(--signal)" : "currentColor"} />)}
      <path d="M87 40 106 1.5 125 40" fill="none" stroke="currentColor" strokeWidth={6} strokeMiterlimit={10} />
      {[99, 106, 113].map((x) => <circle key={`b${x}`} cx={x} cy={28} r={2.3} fill="currentColor" />)}
    </svg>
  );
}
