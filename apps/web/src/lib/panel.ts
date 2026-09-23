"use client";

// The session that lets an AIA sign-in open the NPC Panel 18.6.6 interface
// (ADR 0012). On the develop host Caddy serves the interface at `/`, straight
// from the vendored unit, and asks the API's gate before every request; the
// gate reads the HttpOnly cookie set here from the id token this tab already
// holds. Whether the caller may open the panel is the API's decision
// (organization owners and admins only); nothing here decides it.

import { currentIdToken, loadConfig, logout } from "@/lib/auth";

export type PanelOutcome =
  | { kind: "opened" }
  | { kind: "signed-out" }
  | { kind: "denied"; code: string; message: string }
  | { kind: "disabled" };

/** `next` if it is a path on this origin, else `/`: /login must not be an open redirect. */
export function localPath(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return "/";
  return next;
}

/** AIA's own live pages, which need a sign-in but not the panel session. */
export function isAiaPage(path: string): boolean {
  return path === "/studies" || path.startsWith("/studies/") || path.startsWith("/studies?");
}

/** Turn this tab's id token into the panel session cookie. */
export async function openPanelSession(): Promise<PanelOutcome> {
  const token = await currentIdToken();
  if (!token) return { kind: "signed-out" };
  const config = await loadConfig();
  const response = await fetch(`${config.apiBase}/api/v1/panel/session`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (response.status === 204) return { kind: "opened" };
  if (response.status === 401) return { kind: "signed-out" };
  if (response.status === 404) return { kind: "disabled" };
  const payload = (await response.json().catch(() => ({}))) as { code?: string; message?: string };
  if (response.status === 403) {
    return {
      kind: "denied",
      code: payload.code ?? "forbidden",
      message: payload.message ?? "",
    };
  }
  throw new Error(`${response.status} ${payload.code ?? ""} ${payload.message ?? ""}`.trim());
}

/** Clear the panel cookie. Best effort: signing out must not stall on it. */
export async function closePanelSession(): Promise<void> {
  try {
    const config = await loadConfig();
    await fetch(`${config.apiBase}/api/v1/panel/session`, { method: "DELETE", cache: "no-store" });
  } catch {
    // The cookie holds an id token that expires within the hour regardless.
  }
}

/** Sign out of both: the panel cookie first, then the Cognito session. */
export async function signOut(): Promise<void> {
  await closePanelSession();
  await logout();
}
