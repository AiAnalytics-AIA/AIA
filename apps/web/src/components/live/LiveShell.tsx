"use client";

// The shell for the live pages: who is signed in, sign out, and the build that
// answered -- the browser's and the API's. Everything inside is real
// application state read from the API; the demo pages under /org/* are not and
// say so in their own header.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { api, type Health } from "@/lib/api";
import { loadConfig, logout, useSession } from "@/lib/auth";
import { t } from "@/i18n/t";

export function LiveShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const session = useSession();
  const [webSha, setWebSha] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    // Not signed in: back to the front door, remembering where to return.
    if (session === null && typeof window !== "undefined" && !sessionStorage.getItem("aia.session")) {
      router.replace(`/?next=${encodeURIComponent(window.location.pathname)}`);
    }
  }, [session, router]);

  useEffect(() => {
    if (!session) return;
    loadConfig().then((c) => setWebSha(c.build.sha)).catch(() => setWebSha(null));
    api.health().then(setHealth).catch(() => setHealth(null));
  }, [session]);

  if (!session) return null;

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-4">
            <Link href="/studies" className="text-sm font-semibold">
              AIA
            </Link>
            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs text-emerald-800">
              {t("live.badge")}
            </span>
          </div>
          <div className="flex items-center gap-3 text-sm text-zinc-600">
            <span title={session.subject ?? undefined}>{session.email ?? t("live.signedIn")}</span>
            <button
              className="rounded-md border border-zinc-200 px-3 py-1.5 text-xs font-semibold hover:bg-zinc-50"
              onClick={() => void logout()}
            >
              {t("live.signOut")}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-6">{children}</main>
      <footer className="mx-auto max-w-5xl px-6 py-6 text-xs text-zinc-500">
        <span data-testid="build-web">
          web {webSha ? webSha.slice(0, 12) : "—"}
        </span>
        {" · "}
        <span data-testid="build-api">
          api {health?.build.sha ? health.build.sha.slice(0, 12) : "—"}
          {health ? ` (${health.env})` : ""}
        </span>
      </footer>
    </div>
  );
}
