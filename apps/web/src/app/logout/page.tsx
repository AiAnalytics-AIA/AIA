"use client";

// Sign out of the NPC Panel session and of Cognito, then back to the front door.
// Reachable by URL from inside the 18.6.6 interface, which has no AIA sign-out
// of its own.

import { useEffect } from "react";

import { FrontDoor } from "@/components/aia/FrontDoor";
import { signOut } from "@/lib/panel";
import { t } from "@/i18n/t";

export default function LogoutPage() {
  useEffect(() => {
    void signOut();
  }, []);

  return (
    <FrontDoor>
      <p className="text-ink-muted" role="status">
        {t("panel.signingOut")}
      </p>
    </FrontDoor>
  );
}
