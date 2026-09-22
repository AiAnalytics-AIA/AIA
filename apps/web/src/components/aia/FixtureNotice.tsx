import { t } from "@/i18n/t";

/** Marks a surface rendered from development fixtures, so it never passes for production data. */
export function FixtureNotice({ capability }: { capability: string }) {
  return (
    <div role="note" data-fixture={capability} className="rounded-md border border-dashed border-zinc-400 bg-zinc-100 px-3 py-2 text-xs text-zinc-700">
      {t("app.fixtureBanner")} <span className="font-mono">[{capability}]</span>
    </div>
  );
}
