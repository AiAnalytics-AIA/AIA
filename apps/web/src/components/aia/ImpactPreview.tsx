import type { ImpactResponse } from "@/lib/api/types";
import type { ApiResult } from "@/lib/api/client";
import { IMPACT_FIELDS, stageLabel, type ProjectType } from "@/design/lifecycle";
import { t } from "@/i18n/t";
import { Panel, Value } from "@/components/ui";
import { ApiErrorPanel } from "./ApiErrorPanel";

/**
 * What an edit to one content field would preserve and invalidate — rendered
 * exactly as `GET …/impact` returns it. Nothing is computed here: the server
 * owns the invalidation rule. Cost and duration are shown as missing because the
 * domain `ImpactPreview` carries neither (OI-10), not as zero.
 *
 * A plain GET form, so it works without client JavaScript and the preview is a
 * shareable URL.
 */
export function ImpactPreview({
  projectType,
  field,
  result,
}: {
  projectType: ProjectType | null;
  field: string | null;
  result: ApiResult<ImpactResponse> | null;
}) {
  const label = (id: string) => (projectType ? stageLabel(projectType, id) : null) ?? id;
  return (
    <Panel title={t("impact.title")}>
      <p className="text-xs text-ink-muted">{t("impact.help")}</p>
      <form method="get" className="mt-3 flex flex-wrap items-end gap-2">
        <label className="text-xs text-ink-muted">
          {t("impact.field")}
          <select name="field" defaultValue={field ?? ""} className="mt-1 block h-9 rounded-md border border-border bg-surface-raised px-2 font-mono text-sm text-ink">
            {IMPACT_FIELDS.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </label>
        <button type="submit" className="h-9 rounded-md border border-border-strong bg-surface-raised px-3 text-sm font-semibold text-ink hover:bg-surface-sunken">
          {t("impact.preview")}
        </button>
      </form>

      {result && !result.ok ? <div className="mt-3"><ApiErrorPanel error={result.error} /></div> : null}
      {result && result.ok ? (
        <div className="mt-3 space-y-3 text-sm" data-impact-field={field ?? ""}>
          <div>
            {t("impact.root")}: {result.data.root_stage ? <span className="font-semibold">{label(result.data.root_stage)}</span> : <span className="text-ink-muted">{t("impact.none")}</span>}
          </div>
          {result.data.presentation_only ? <p role="note" className="text-ink-muted">{t("impact.presentationOnly")}</p> : null}
          <div className="grid gap-3 sm:grid-cols-2">
            <StageList title={t("impact.invalidated")} ids={result.data.invalidate} label={label} kind="invalidated" />
            <StageList title={t("impact.preserved")} ids={result.data.preserve} label={label} kind="preserved" />
          </div>
          <dl data-unavailable="impact-estimate" className="grid grid-cols-[max-content_minmax(0,1fr)] items-center gap-x-3 gap-y-1">
            <dt className="text-ink-muted">{t("impact.cost")}</dt>
            <dd><Value value={null} /> <span className="text-xs text-ink-muted">{t("impact.estimateMissing")}</span></dd>
            <dt className="text-ink-muted">{t("impact.duration")}</dt>
            <dd><Value value={null} /> <span className="text-xs text-ink-muted">{t("impact.estimateMissing")}</span></dd>
          </dl>
        </div>
      ) : null}
    </Panel>
  );
}

function StageList({ title, ids, label, kind }: { title: string; ids: string[]; label: (id: string) => string; kind: "invalidated" | "preserved" }) {
  return (
    <div data-impact={kind}>
      <div className="text-xs font-semibold text-ink-muted">{title} ({ids.length})</div>
      {ids.length === 0 ? <div className="text-ink-muted">—</div> : (
        <ul className="mt-1 space-y-0.5">
          {ids.map((id) => (
            <li key={id} className="flex items-center gap-2">
              <span aria-hidden="true" className={kind === "invalidated" ? "inline-block h-2 w-2 rotate-45 border border-ink" : "inline-block h-2 w-2 rounded-full bg-ink-muted"} />
              {label(id)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
