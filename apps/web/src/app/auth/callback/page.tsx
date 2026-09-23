"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { completeLogin } from "@/lib/auth";
import { t } from "@/i18n/t";

function Callback() {
  const params = useSearchParams();
  const router = useRouter();
  const [exchangeError, setExchangeError] = useState<string | null>(null);

  const code = params.get("code");
  const state = params.get("state");
  const denied = params.get("error");
  // Derived from the URL, not set in an effect: what Cognito sent back is known
  // before anything runs.
  const requestError = denied
    ? `${denied}: ${params.get("error_description") ?? ""}`
    : !code || !state
      ? t("live.callbackMissing")
      : null;
  const error = requestError ?? exchangeError;

  useEffect(() => {
    if (requestError || !code || !state) return;
    completeLogin(code, state)
      .then((next) => router.replace(next))
      .catch((e: unknown) => setExchangeError(String(e)));
  }, [requestError, code, state, router]);

  return (
    <div className="min-h-screen bg-zinc-50 p-10">
      <div className="mx-auto max-w-md rounded-xl border border-zinc-200 bg-white p-6 text-sm">
        {error ? (
          <div className="text-red-800">{error}</div>
        ) : (
          <div className="text-zinc-600">{t("live.completingLogin")}</div>
        )}
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={null}>
      <Callback />
    </Suspense>
  );
}
