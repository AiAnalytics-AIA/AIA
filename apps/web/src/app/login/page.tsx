"use client";

// The front door (ADR 0015, ADR 0018). The gate in front of /app sends every
// navigation without a session here as /login?next=<where they were going>; with
// nowhere named, the client directory. This page opens AIA's session -- any active
// member of the organization -- and sends them back; signed out, it offers the
// Google Workspace sign-in and comes back here after it. It never starts the
// sign-in by itself: Cognito's sign-out lands on `/`, which leads here, and an
// automatic sign-in would undo the sign-out the user just asked for.

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { FrontDoor } from "@/components/aia/FrontDoor";
import { Button } from "@/components/rehome/ui";
import { login } from "@/lib/auth";
import { localPath, openSession, signOut } from "@/lib/session";
import { t } from "@/i18n/t";

// Set just before returning to the page asked for. Seeing it again within this
// window means the cookie did not stick and the gate sent the browser straight
// back: stop and say so rather than bounce between the two forever.
const OPENED_KEY = "aia.session.openedAt";
const LOOP_WINDOW_MS = 10_000;

type View =
  | { kind: "working" }
  | { kind: "signed-out" }
  | { kind: "denied"; message: string }
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

      const outcome = await openSession();
      if (cancelled) return;
      if (outcome.kind === "signed-out") return setView({ kind: "signed-out" });
      if (outcome.kind === "denied") {
        const member = outcome.code === "not_a_member" || outcome.code === "not_provisioned";
        return setView({ kind: "denied", message: member ? t("session.notMember") : outcome.message });
      }
      try {
        sessionStorage.setItem(OPENED_KEY, String(Date.now()));
      } catch {
        // Without storage there is no loop guard; the redirect still works.
      }
      go(next);
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
          {t("session.opening")}
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
          <Button variant="quiet" onClick={() => void signOut()}>
            {t("live.signOut")}
          </Button>
        </>
      )}
      {(view.kind === "loop" || view.kind === "error") && (
        <>
          <p className="rounded-sm border border-status-fault/40 bg-status-fault-wash px-3 py-2 text-status-fault" role="alert">
            {view.kind === "loop" ? t("session.loop") : `${t("session.failed")}: ${view.message}`}
          </p>
          <Button variant="primary" onClick={retry}>
            {t("session.retry")}
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
