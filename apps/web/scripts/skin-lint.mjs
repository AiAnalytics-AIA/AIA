/**
 * The rule the skin's hand-written layer lives by (ADR 0013, decision 5): colour,
 * radius, shadow and font come from the design system's tokens, never from a raw
 * value, so tokens.json stays the only place a visual decision is made.
 * Allowed without a token: `border-radius: 0 | 50%`, `box-shadow: none`,
 * `font-family: inherit`. Spacing may be literal: it is layout, not appearance.
 * Returns one message per offending line; empty means clean.
 */
export function lintComponents(css) {
  const body = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const problems = [];
  const lines = body.split("\n");
  lines.forEach((line, i) => {
    const at = `components.css:${i + 1}`;
    if (/#[0-9a-fA-F]{3,8}\b/.test(line)) problems.push(`${at} a hex colour; use a token`);
    if (/\b(rgba?|hsla?|oklch|oklab|lab|lch|hwb|color-mix)\(/.test(line)) problems.push(`${at} a colour function; use a token`);
    const decl = line.match(/^\s*(font-family|border-radius|box-shadow|font)\s*:\s*([^;]+)/);
    if (decl) {
      const [, prop, value] = decl;
      const ok =
        /var\(--/.test(value) ||
        (prop === "border-radius" && /^\s*(0|50%)\s*(!important)?\s*$/.test(value)) ||
        (prop === "box-shadow" && /^\s*none\s*(!important)?\s*$/.test(value)) ||
        (prop === "font-family" && /^\s*inherit\s*(!important)?\s*$/.test(value));
      if (!ok) problems.push(`${at} ${prop} must come from a token (var(--aia-…))`);
    }
  });
  return problems;
}
