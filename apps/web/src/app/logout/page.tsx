"use client";

// Sign out of AIA's session and of Cognito, then back to the front door.
// Reachable by URL too.

import { useEffect } from "react";

import { FrontDoor } from "@/components/aia/FrontDoor";
import { signOut } from "@/lib/session";
import { t } from "@/i18n/t";

export default function LogoutPage() {
  useEffect(() => {
    void signOut();
  }, []);

  return (
    <FrontDoor>
      <p className="text-ink-muted" role="status">
        {t("session.signingOut")}
      </p>
    </FrontDoor>
  );
}
