import { notFound } from "next/navigation";
import { EvidenceMark, Money, Panel, StatusChip, Value } from "@/components/ui";
import { ThemeSwitch } from "@/components/theme/ThemeSwitch";
import { KNOWN_EVIDENCE_ROLES } from "@/design/evidence";
import { STAGE_STATUS, WORKFLOW_RUN_STATUS, RESERVATION_STATUS } from "@/design/enums";
import { formatPercent } from "@/design/format";

/**
 * Development-only state gallery: every primitive in every state, for review
 * screenshots. Off unless AIA_ENABLE_DEV_PAGES=1; production builds 404 it.
 * Copy is fixture copy (labels of the gallery itself), not product UI.
 */
export const dynamic = "force-dynamic";

export default function StatesGallery() {
  if (process.env.AIA_ENABLE_DEV_PAGES !== "1") notFound();
  return (
    <main className="space-y-4 p-6">
      <div className="flex items-center justify-between"><h1 className="text-xl font-semibold">Stavy (vývojová galerie)</h1><ThemeSwitch /></div>
      <Panel title="StageStatus">
        <div className="flex flex-wrap gap-2">{STAGE_STATUS.map((v) => <StatusChip key={v} kind="StageStatus" value={v} showAudience />)}</div>
      </Panel>
      <Panel title="WAITING_CREDITS: tým vs. vy (DS-3)">
        <div className="flex flex-wrap gap-2">
          <StatusChip kind="StageStatus" value="WAITING_CREDITS" showAudience />
          <StatusChip kind="StageStatus" value="WAITING_CREDITS" viewer={{ viewerCanResolve: true }} showAudience />
          <StatusChip kind="StageStatus" value="WAITING_CAPACITY" showAudience />
          <StatusChip kind="StageStatus" value="PAUSED_BY_ADMIN" />
        </div>
      </Panel>
      <Panel title="WorkflowRunStatus · ReservationStatus">
        <div className="flex flex-wrap gap-2">
          {WORKFLOW_RUN_STATUS.map((v) => <StatusChip key={v} kind="WorkflowRunStatus" value={v} />)}
          {RESERVATION_STATUS.map((v) => <StatusChip key={v} kind="ReservationStatus" value={v} />)}
        </div>
      </Panel>
      <Panel title="Hodnota · nula · chybí · potlačeno · načítá se">
        <div className="flex flex-wrap items-center gap-6">
          <Value value={1204} /><Value value={0} /><Value value={null} /><Value value={3} state="suppressed" reason="vzorek < 30" /><Value value={3} state="loading" />
          <Money value={12480.5} /><Money value={0} /><Money value={null} />
        </div>
      </Panel>
      <Panel title="Evidenční role">
        <div className="flex flex-wrap items-center gap-6">
          {[...KNOWN_EVIDENCE_ROLES, "NEZNÁMÁ_ROLE"].map((r) => (
            <span key={r} className="inline-flex items-center gap-2"><Value value={41.7} format={(v) => formatPercent(v)} role={r} /><span className="font-mono text-xs text-ink-muted">{r}</span><EvidenceMark role={r} size={16} /></span>
          ))}
        </div>
      </Panel>
    </main>
  );
}
