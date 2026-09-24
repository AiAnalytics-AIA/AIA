import { t } from "@/i18n/t";

// The rebuilt interface's entry (ADR 0014). The shell and the first area
// replace this page in the re-home plan's chunks 3 and 4.
export default function RehomeHome() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-2xl font-semibold text-ink">{t("rehome.title")}</h1>
      <p className="mt-3 text-ink-muted">{t("rehome.intro")}</p>
      {/* A full document load, not <Link>: `/` is the classic interface the unit
          serves behind the gate, not a page of this app. */}
      {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
      <a className="mt-6 inline-block text-signal underline-offset-4 hover:underline" href="/">
        {t("rehome.openClassic")}
      </a>
    </main>
  );
}
