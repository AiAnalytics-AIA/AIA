"use client";

// The session that lets an AIA sign-in open what remains of NPC Panel 18.6.6 on
// the product hostname (ADR 0012): the /classic hand-off and the unit's own paths,
// which the classic projects screen still reads. Caddy asks the API's panel gate
// before each of those requests; the gate reads the HttpOnly cookie set here from
// the id token this tab already holds. Whether the caller may open the panel is
// the API's decision (organization owners and admins only). AIA's own pages need
// only AIA's session (lib/session.ts, ADR 0018); this one goes when the unit
// leaves the product.

import { currentIdToken, loadConfig } from "@/lib/auth";

export type PanelOutcome =
  | { kind: "opened" }
  | { kind: "signed-out" }
  | { kind: "denied"; code: string; message: string }
  | { kind: "disabled" };

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
