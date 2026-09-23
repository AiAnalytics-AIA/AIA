"use client";

// AIA's own front page. On the develop host `/` is the NPC Panel 18.6.6
// interface, served by the unit behind the gate (ADR 0012), so this page is
// what a local `make dev` shows; the sign-in the gate uses is /login.

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { login, useSession } from "@/lib/auth";
import { localPath } from "@/lib/panel";
import { t } from "@/i18n/t";

function Home() {
  const params = useSearchParams();
  const requested = params.get("next");
  const next = requested ? localPath(requested) : "/studies";
  const signedIn = useSession() !== null;

  return (
    <div className="min-h-screen bg-zinc-50 p-10">
      <div className="mx-auto max-w-2xl space-y-4">
        <h1 className="text-2xl font-semibold">AIA</h1>

        <div className="rounded-xl border border-emerald-200 bg-white p-4">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-emerald-700">
            {t("live.badge")}
          </div>
          <p className="text-sm text-zinc-600">{t("home.liveIntro")}</p>
          <div className="mt-3">
            {signedIn ? (
              <Link className="font-medium text-blue-700 hover:underline" href="/studies">
                {t("home.openStudies")}
              </Link>
            ) : (
              <button
                className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-semibold text-white hover:bg-zinc-800"
                onClick={() => void login(next)}
              >
                {t("home.signInGoogle")}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={null}>
      <Home />
    </Suspense>
  );
}
