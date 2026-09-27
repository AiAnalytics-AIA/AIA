"use client";

// The front door on the develop host (ADR 0012, ADR 0015). The gate in front of
// /app and of the classic interface sends every navigation without a session
// here as /login?next=<where they were going>; with nowhere named, the client
// directory. This page opens the session and sends them back; signed out, it
// offers the Google Workspace sign-in and comes back here after it. It never
// starts the sign-in by itself: Cognito's sign-out lands on `/`, which leads
// here, and an automatic sign-in would undo the sign-out the user just asked for.

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { FrontDoor } from "@/components/aia/FrontDoor";
import { Button } from "@/components/rehome/ui";
import { login } from "@/lib/auth";
import { isAiaPage, localPath, openPanelSession, signOut } from "@/lib/panel";
import { t } from "@/i18n/t";

// Set just before returning to the panel. Seeing it again within this window
// means the cookie did not stick and the gate sent the browser straight back:
// stop and say so rather than bounce between the two forever.
const OPENED_KEY = "aia.panel.openedAt";
const LOOP_WINDOW_MS = 10_000;

const LINK =
  "font-medium text-signal underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

type View =
  | { kind: "working" }
  | { kind: "signed-out" }
  | { kind: "denied"; message: string }
  | { kind: "disabled" }
  | { kind: "loop" }
  | { kind: "error"; message: string };

function Login() {
  const params = useSearchParams();
  // With nowhere named, the application home (ADR 0015).
  const next = params.get("next") ? localPath(params.get("next")) : "/app/clients";
  const [view, setView] = useState<View>({ kind: "working" });
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    try {
      sessionStorage.removeItem(OPENED_KEY);
    } catch {
      // Storage unavailable: the loop guard simply does not apply.
    }
    setView({ kind: "working" });
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const go = (path: string) => {
      if (!cancelled) window.location.replace(path);
    };

    async function run() {
      let openedAt = 0;
      try {
        openedAt = Number(sessionStorage.getItem(OPENED_KEY) ?? 0);
      } catch {
        openedAt = 0;
      }
      if (Date.now() - openedAt < LOOP_WINDOW_MS) {
        setView({ kind: "loop" });
        return;
      }

      const outcome = await openPanelSession();
      if (cancelled) return;
      switch (outcome.kind) {
        case "signed-out":
          setView({ kind: "signed-out" });
          return;
        case "opened":
          try {
            sessionStorage.setItem(OPENED_KEY, String(Date.now()));
          } catch {
            // Without storage there is no loop guard; the redirect still works.
          }
          go(next);
          return;
        case "disabled":
          if (isAiaPage(next)) go(next);
          else setView({ kind: "disabled" });
          return;
        case "denied":
          // A member who is not an administrator still uses AIA's own pages.
          if (isAiaPage(next) && outcome.code === "legacy_panel_denied") go(next);
          else
            setView({
              kind: "denied",
              message:
                outcome.code === "legacy_panel_denied" ? t("panel.adminsOnly") : outcome.message,
            });
          return;
      }
    }

    run().catch((e: unknown) => {
      if (!cancelled) setView({ kind: "error", message: String(e) });
    });
    return () => {
      cancelled = true;
    };
  }, [next, attempt]);

  return (
    <FrontDoor title={t("home.signInTitle")}>
      {view.kind === "working" && (
        <p className="text-ink-muted" role="status">
          {t("panel.opening")}
        </p>
      )}
      {view.kind === "signed-out" && (
        <>
          <p className="leading-relaxed text-ink-muted">{t("home.liveIntro")}</p>
          <Button
            variant="primary"
            className="w-full justify-center"
            // Back here after Google, with the same destination.
            onClick={() => void login(`/login?next=${encodeURIComponent(next)}`)}
          >
            {t("home.signInGoogle")}
          </Button>
        </>
      )}
      {view.kind === "denied" && (
        <>
          <p className="text-ink">{view.message}</p>
          <div className="flex items-center gap-2">
            <Link className={`${LINK} min-h-9 inline-flex items-center`} href="/studies">
              {t("home.openStudies")}
            </Link>
            <Button variant="quiet" onClick={() => void signOut()}>
              {t("live.signOut")}
            </Button>
          </div>
        </>
      )}
      {view.kind === "disabled" && (
        <>
          <p className="text-ink">{t("panel.notEnabled")}</p>
          <Link className={LINK} href="/studies">
            {t("home.openStudies")}
          </Link>
        </>
      )}
      {(view.kind === "loop" || view.kind === "error") && (
        <>
          <p className="rounded-sm border border-status-fault/40 bg-status-fault-wash px-3 py-2 text-status-fault" role="alert">
            {view.kind === "loop" ? t("panel.loop") : `${t("panel.failed")}: ${view.message}`}
          </p>
          <Button variant="primary" onClick={retry}>
            {t("panel.retry")}
          </Button>
        </>
      )}
    </FrontDoor>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <Login />
    </Suspense>
  );
}
