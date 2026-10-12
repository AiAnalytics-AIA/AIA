// The lift-off film plays once, after a sign-in the person started: pressing the
// sign-in button arms it, and /login takes it when AIA's session opens. Anything
// else that lands on /login -- the gate bouncing a navigation, a reload, a session
// that was already open -- goes straight in. An armed film that is never taken
// (the person abandoned Google's page) expires rather than surprise them later.

const LIFTOFF_KEY = "aia.liftoff.armedAt";
export const LIFTOFF_WINDOW_MS = 10 * 60_000;

/** Called on the sign-in button: the next session opened in this tab plays the film. */
export function armLiftoff(now: number = Date.now()): void {
  try {
    sessionStorage.setItem(LIFTOFF_KEY, String(now));
  } catch {
    // Storage unavailable: no film, the sign-in itself is unaffected.
  }
}

/** Whether the film is armed, disarming it either way: it plays at most once. */
export function takeLiftoff(now: number = Date.now()): boolean {
  try {
    const armedAt = Number(sessionStorage.getItem(LIFTOFF_KEY) ?? NaN);
    sessionStorage.removeItem(LIFTOFF_KEY);
    return Number.isFinite(armedAt) && now - armedAt >= 0 && now - armedAt < LIFTOFF_WINDOW_MS;
  } catch {
    return false;
  }
}
