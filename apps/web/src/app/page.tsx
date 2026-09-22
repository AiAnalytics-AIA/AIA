import Link from "next/link";
import { t } from "@/i18n/t";

export default function Home() {
  return (
    <div className="min-h-screen bg-zinc-50 p-10">
      <div className="mx-auto max-w-2xl space-y-4">
        <h1 className="text-2xl font-semibold">{t("home.title")}</h1>
        <p className="text-sm text-zinc-600">{t("home.intro")}</p>
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <Link className="font-medium text-blue-700 hover:underline" href="/org/aia-dev/dashboard">
            {t("home.goToPortfolio")}
          </Link>
        </div>
      </div>
    </div>
  );
}
