import Link from "next/link";

import { FrontDoor } from "@/components/aia/FrontDoor";
import { t } from "@/i18n/t";

// Where the 18.6.6 interface was handed off (ADR 0015) until ADR 0018 took it out
// of the product. An old bookmark or link lands here and is told so plainly, with
// the way into AIA, instead of a bare 404 or a redirect that would hide it. No
// data and no sign-in: nothing here reads anything.
export const metadata = { title: "NPC Panel 18.6.6 · AIA" };

export default function ClassicRetired() {
  return (
    <FrontDoor title={t("classic.title")}>
      <p className="leading-relaxed text-ink">{t("classic.text")}</p>
      <p className="leading-relaxed text-ink-muted">{t("classic.missing")}</p>
      <Link
        className="inline-flex min-h-9 items-center font-medium text-signal underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        href="/app/clients"
      >
        {t("classic.openAia")}
      </Link>
    </FrontDoor>
  );
}
