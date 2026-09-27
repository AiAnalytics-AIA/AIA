/**
 * The identity's motif (docs/design/aia-design-system-brief.md §3): a field of
 * individual points. Inline and in currentColor so it follows the theme; the
 * same pitch and point size as public/skin/brand/lattice-field.svg. Decoration
 * only -- never behind data.
 */
const PITCH = 8;

export function LatticeField({ className = "" }: { className?: string }) {
  return (
    <svg className={className} aria-hidden="true" focusable="false" preserveAspectRatio="xMidYMid slice" viewBox="0 0 480 480">
      <defs>
        <pattern id="aia-lattice-field" width={PITCH} height={PITCH} patternUnits="userSpaceOnUse">
          <circle cx={PITCH / 2} cy={PITCH / 2} r={0.7} fill="currentColor" fillOpacity={0.3} />
        </pattern>
      </defs>
      <rect width="480" height="480" fill="url(#aia-lattice-field)" />
    </svg>
  );
}
