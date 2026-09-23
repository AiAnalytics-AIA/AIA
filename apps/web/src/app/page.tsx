import Link from "next/link";
import { t } from "@/i18n/t";

export default function Home() {
  return (
    <div className="min-h-screen bg-surface p-10">
      <div className="mx-auto max-w-2xl space-y-4">
        <h1 className="text-2xl font-semibold">{t("home.title")}</h1>
        <p className="text-sm text-ink-muted">{t("home.intro")}</p>
        <div className="rounded-md border border-border bg-surface-raised p-4">
          <Link className="font-medium text-signal hover:underline" href="/org/aia-dev/dashboard">
            {t("home.goToPortfolio")}
          </Link>
        </div>
      </div>
    </div>
  );
}
