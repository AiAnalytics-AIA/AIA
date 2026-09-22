import { unavailable } from "@/fixtures/registry";
import { t } from "@/i18n/t";
import { Panel } from "@/components/ui";

/**
 * A capability the backend cannot serve yet, shown as exactly that: a titled,
 * dashed panel naming the owner and the register entry. It never renders a
 * placeholder that could pass for an empty result ("no approvals" ≠ "we cannot ask").
 */
export function Unavailable({ id, title }: { id: string; title: string }) {
  const cap = unavailable(id);
  if (!cap) throw new Error(`Unavailable capability "${id}" is not in UNAVAILABLE_CAPABILITIES`);
  return (
    <Panel title={title}>
      <div data-unavailable={cap.id} className="rounded-sm border border-dashed border-border-strong bg-surface-sunken px-3 py-2 text-sm">
        <div className="font-semibold text-ink">{t("unavailable.label")}</div>
        <p className="text-ink-muted">{t(`unavailable.reason.${cap.reason}`)}</p>
        <p className="mt-1 text-xs text-ink-muted">
          {t("unavailable.owner")}: <span className="font-mono">{cap.owner}</span>
          {cap.register ? <> · {t("unavailable.register")}: <span className="font-mono">{cap.register}</span></> : null}
        </p>
      </div>
    </Panel>
  );
}
