/** Theme preference: an explicit light or dark, or "system" (no attribute; tokens.css follows the OS). */
export const THEMES = ["system", "light", "dark"] as const;
export type ThemePreference = (typeof THEMES)[number];
export const THEME_STORAGE_KEY = "aia.theme";

export function isThemePreference(v: unknown): v is ThemePreference {
  return typeof v === "string" && (THEMES as readonly string[]).includes(v);
}

/** Applies a preference to <html>. "system" removes the attribute. */
export function applyTheme(pref: ThemePreference, root: HTMLElement = document.documentElement) {
  if (pref === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", pref);
}

/**
 * Runs before first paint so a stored dark preference never flashes light.
 * Storage may be unavailable (private window); then the OS preference applies.
 */
export const THEME_BOOT_SCRIPT = `(function(){try{var v=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});if(v==="light"||v==="dark")document.documentElement.setAttribute("data-theme",v);}catch(e){}})();`;
