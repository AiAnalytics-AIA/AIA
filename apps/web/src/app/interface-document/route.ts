import { buildIdentity } from "@/lib/build";
import { applySkin, skinEnabledFrom, type SkinOutcome } from "@/lib/interface-skin";

// The 18.6.6 interface document, with the AIA skin when it applies (ADR 0013).
//
// Reachable only through Caddy's rewrite of `/`, after the same forward_auth gate
// that fronts every unit path; a direct request for this path is answered 404 at
// the edge. The document is fetched from the unit on every navigation and never
// cached here, exactly as the unit serves it (`no-store`).
export const dynamic = "force-dynamic";

const NO_STORE = {
  "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
  Pragma: "no-cache",
} as const;

function unitUrl(): string {
  const base = process.env.AIA_LEGACY_PANEL_URL?.trim() || "http://legacy-panel:8765";
  return `${base.replace(/\/+$/, "")}/`;
}

/** The build SHA versions the stylesheet URL; a malformed value must not take `/` down. */
function buildVersion(): string | null {
  try {
    return buildIdentity().sha;
  } catch {
    return null;
  }
}

function log(outcome: SkinOutcome | "bypassed-upstream-status", detail: Record<string, unknown>): void {
  console.warn(JSON.stringify({ event: "interface_skin_bypassed", outcome, ...detail }));
}

export async function GET(): Promise<Response> {
  let upstream: Response;
  try {
    upstream = await fetch(unitUrl(), { cache: "no-store", redirect: "manual" });
  } catch {
    return new Response("Rozhraní 18.6.6 není dostupné.", {
      status: 502,
      headers: { ...NO_STORE, "Content-Type": "text/plain; charset=utf-8", "X-AIA-Skin": "bypassed-unreachable" },
    });
  }

  const bytes = Buffer.from(await upstream.arrayBuffer());
  const contentType = upstream.headers.get("content-type") ?? "text/html; charset=utf-8";

  if (upstream.status !== 200) {
    log("bypassed-upstream-status", { status: upstream.status });
    return new Response(new Uint8Array(bytes), {
      status: upstream.status,
      headers: { ...NO_STORE, "Content-Type": contentType, "X-AIA-Skin": "bypassed-upstream-status" },
    });
  }

  const decision = applySkin(bytes, {
    enabled: skinEnabledFrom(process.env.AIA_INTERFACE_SKIN_ENABLED),
    version: buildVersion(),
  });
  if (decision.outcome !== "applied" && decision.outcome !== "bypassed-disabled") {
    log(decision.outcome, { received_sha256: decision.receivedSha256 });
  }
  return new Response(new Uint8Array(decision.body), {
    status: 200,
    headers: { ...NO_STORE, "Content-Type": contentType, "X-AIA-Skin": decision.outcome },
  });
}
