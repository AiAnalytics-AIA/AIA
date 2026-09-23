import { FIXTURE_CAPABILITIES } from "@/fixtures/registry";
import { t } from "@/i18n/t";

/** Marks a surface rendered from development fixtures, so it never passes for production data. */
export function FixtureNotice({ capability }: { capability: string }) {
  if (!FIXTURE_CAPABILITIES.some((c) => c.id === capability)) {
    throw new Error(`Fixture capability "${capability}" is not in FIXTURE_CAPABILITIES`);
  }
  return (
    <div role="note" data-fixture={capability} className="rounded-md border border-dashed border-border-strong bg-surface-sunken px-3 py-2 text-xs text-ink-muted">
      {t("app.fixtureBanner")} <span className="font-mono">[{capability}]</span>
    </div>
  );
}
