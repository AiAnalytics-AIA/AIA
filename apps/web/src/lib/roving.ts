// Arrow keys within one group of controls (input-interactions I11): a segmented control, chips,
// swatches and a menu are one Tab stop, and the arrows move inside it (roving tabindex). Pure:
// which index the key moves to, skipping the disabled ones, wrapping at the ends.

const FORWARD = new Set(["ArrowRight", "ArrowDown"]);
const BACK = new Set(["ArrowLeft", "ArrowUp"]);

/**
 * The index `key` moves focus to from `from` among `count` controls, or null when the key is not
 * a moving key or nothing is enabled. `disabled(i)` skips a control; `axis` limits the arrows to
 * one direction (a vertical menu ignores left and right).
 */
export function rovingIndex(
  from: number,
  key: string,
  count: number,
  disabled: (i: number) => boolean = () => false,
  axis: "both" | "vertical" | "horizontal" = "both",
): number | null {
  if (count <= 0) return null;
  if (axis === "vertical" && (key === "ArrowLeft" || key === "ArrowRight")) return null;
  if (axis === "horizontal" && (key === "ArrowUp" || key === "ArrowDown")) return null;
  const enabled = (i: number) => !disabled(i);
  if (key === "Home") return first(count, enabled, 0, 1);
  if (key === "End") return first(count, enabled, count - 1, -1);
  const dir = FORWARD.has(key) ? 1 : BACK.has(key) ? -1 : 0;
  if (!dir) return null;
  for (let n = 1; n <= count; n++) {
    const i = (((from + dir * n) % count) + count) % count;
    if (enabled(i)) return i;
  }
  return null;
}

function first(count: number, enabled: (i: number) => boolean, start: number, dir: 1 | -1): number | null {
  for (let i = start; i >= 0 && i < count; i += dir) if (enabled(i)) return i;
  return null;
}

/** The one control of a group that takes Tab: the chosen one, else the first enabled. */
export function tabStop(count: number, chosen: number, disabled: (i: number) => boolean = () => false): number {
  if (chosen >= 0 && chosen < count && !disabled(chosen)) return chosen;
  for (let i = 0; i < count; i++) if (!disabled(i)) return i;
  return -1;
}
