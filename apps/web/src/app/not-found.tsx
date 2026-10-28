import Link from "next/link";

import { FrontDoor } from "@/components/aia/FrontDoor";
import { t } from "@/i18n/t";

// Any address Next cannot route, an unknown stage slug included, lands here instead of
// Next's English default: one Czech sentence and the way back (UX research §5.3, P1 5).
export const metadata = { title: "Stránka nenalezena · AIA" };

export default function NotFoundPage() {
  return (
    <FrontDoor title={t("pageNotFound.title")}>
      <p className="leading-relaxed text-ink">{t("pageNotFound.text")}</p>
      <Link
        className="inline-flex min-h-9 items-center font-medium text-signal underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        href="/app/clients"
      >
        {t("pageNotFound.openClients")}
      </Link>
    </FrontDoor>
  );
}
