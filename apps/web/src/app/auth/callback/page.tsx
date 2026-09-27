"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { FrontDoor } from "@/components/aia/FrontDoor";
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
    <FrontDoor>
      {error ? (
        <p className="rounded-sm border border-status-fault/40 bg-status-fault-wash px-3 py-2 text-status-fault" role="alert">
          {error}
        </p>
      ) : (
        <p className="text-ink-muted" role="status">
          {t("live.completingLogin")}
        </p>
      )}
    </FrontDoor>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={null}>
      <Callback />
    </Suspense>
  );
}
