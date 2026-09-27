"use client";

// AIA's own session (ADR 0018 decision 3). Caddy asks the API's gate before every
// request to /app, and the gate reads the HttpOnly cookie set here from the id
// token this tab already holds. Any active member of the organization is admitted;
// what they may see inside is decided per call by the API, client by client and
// study by study. Nothing here decides either: the page only asks.

import { currentIdToken, loadConfig, logout } from "@/lib/auth";
import { closePanelSession } from "@/lib/panel";

export type SessionOutcome =
  | { kind: "opened" }
  | { kind: "signed-out" }
  | { kind: "denied"; code: string; message: string };

/** `next` if it is a path on this origin, else `/`: /login must not be an open redirect. */
export function localPath(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return "/";
  return next;
}

/** Turn this tab's id token into AIA's session cookie. */
export async function openSession(): Promise<SessionOutcome> {
  const token = await currentIdToken();
  if (!token) return { kind: "signed-out" };
  const config = await loadConfig();
  const response = await fetch(`${config.apiBase}/api/v1/session`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (response.status === 204) return { kind: "opened" };
  if (response.status === 401) return { kind: "signed-out" };
  const payload = (await response.json().catch(() => ({}))) as { code?: string; message?: string };
  if (response.status === 403) return { kind: "denied", code: payload.code ?? "forbidden", message: payload.message ?? "" };
  throw new Error(`${response.status} ${payload.code ?? ""} ${payload.message ?? ""}`.trim());
}

/** Clear AIA's session cookie. Best effort: signing out must not stall on it. */
export async function closeSession(): Promise<void> {
  try {
    const config = await loadConfig();
    await fetch(`${config.apiBase}/api/v1/session`, { method: "DELETE", cache: "no-store" });
  } catch {
    // The cookie holds an id token that expires within the hour regardless.
  }
}

/** Where only the 18.6.6 interface's own session lets a person in (until it leaves). */
export function needsPanel(path: string): boolean {
  return path === "/classic" || /^\/classic[?#]/.test(path) || path.startsWith("/app/settings/classic-projects");
}

/** Sign out of everything: both cookies, then the Cognito session. */
export async function signOut(): Promise<void> {
  await Promise.all([closeSession(), closePanelSession()]);
  await logout();
}
