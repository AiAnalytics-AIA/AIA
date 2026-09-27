"use client";

// Sign out of the NPC Panel session and of Cognito, then back to the front door.
// Reachable by URL from inside the 18.6.6 interface, which has no AIA sign-out
// of its own.

import { useEffect } from "react";

import { signOut } from "@/lib/panel";
import { t } from "@/i18n/t";

export default function LogoutPage() {
  useEffect(() => {
    void signOut();
  }, []);

  return (
    <div className="min-h-screen bg-zinc-50 p-10">
      <div className="mx-auto max-w-md rounded-xl border border-zinc-200 bg-white p-6 text-sm text-zinc-600">
        {t("panel.signingOut")}
      </div>
    </div>
  );
}
