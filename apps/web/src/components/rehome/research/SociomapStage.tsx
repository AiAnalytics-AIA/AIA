"use client";

// The Sociomapa stage of the workbench (artifact-sociomap SOC9): the map is the stage. No results tabs,
// no guide: each mapped set's map first, at the pane's full width, and under it what explains it
// (MapExplained). The run's notices stay above (its origin, a moved design), the experimental
// Sociomapping and its review below. A set stored under an older method says so and draws nothing; a
// map that is not the signed-off method's is drawn as the Results page draws it. Výsledky keeps its tabs.

import { type ReactNode, useEffect, useMemo, useState } from "react";
import { t, tv } from "@/i18n/t";
import { type Artifact, type ResearchRun, research } from "@/lib/api";
import { isRefusal, readMapOp, readTarget } from "@/lib/artifacts/sociomap";
import { LEAD_MAP_VIEW, type LeadMapView, mapViewWords, sendLeadMapView, takeLeadMapView } from "@/lib/lead";
import { explainMap } from "@/lib/map-explained";
import { type BatteryWithMaps, mapApproval, olderMethodOnly, readObjectMap, type RecordedMethod, type RegisterEntry } from "@/lib/object-map-view";
import { densityGrid } from "@/lib/object-map-panel";
import { isSignedOffMap, storedFrame } from "@/lib/object-map-signed-off";
import { stageOf } from "@/lib/workbench-stages";
import { useFrame } from "./frame-hook";
import { MapExplained } from "./MapExplained";
import { clearShownMaps, setShownMaps } from "./MapInspect";
import { ObjectMapPanel, routeToMap } from "./ObjectMapPanel";
import { ObjectMapView } from "./ObjectMapView";

/**
 * Whether the address names the Sociomapa stage (lib/workbench-stages.ts: #maps and its old anchors),
 * as it was when the view opened and as navigation changes it (hashchange, popstate). A tab of
 * Výsledky rewrites the hash in place (ResultsWorkspace's replaceState, no event): that is a view
 * within Výsledky, so it never swaps the page for the Sociomapa stage under the person.
 */
export function useOnSociomapStage(): boolean {
  const [hash, setHash] = useState(() => (typeof window === "undefined" ? "" : window.location.hash));
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    window.addEventListener("popstate", on);
    return () => { window.removeEventListener("hashchange", on); window.removeEventListener("popstate", on); };
  }, []);
  return stageOf("results", hash) === "sociomap";
}

const P = "research.exec.objectMap.panel";

type Payload = { sociomap: { data_origin?: string | null; methods?: RecordedMethod[]; note?: string; batteries: BatteryWithMaps[] } } | null;

export function SociomapStage({ run, artifact, loading, error, notice, after }: {
  run: ResearchRun;
  artifact: Artifact | null;
  loading: boolean;
  error: string | null;
  /** The run's notices: its data's origin, a design moved since it ran. */
  notice: ReactNode;
  /** What else the run mapped, under the maps (the experimental Sociomapping and its review). */
  after?: ReactNode;
}) {
  const frame = useFrame();
  // The register a map's approval is read from (B4); not read, every map stays internal.
  const [register, setRegister] = useState<RegisterEntry[] | null>(null);
  useEffect(() => {
    let live = true;
    research.sociomapRegister(frame.studyId).then((value) => live && setRegister(value.entries ?? null), () => live && setRegister(null));
    return () => { live = false; };
  }, [frame.studyId]);
  const payload = (artifact?.payload ?? null) as Payload;
  const batteries = payload?.sociomap?.batteries ?? [];
  // The Lead's views (artifact-sociomap SOC2; research-lead-workbench 14), routed by the stage, which
  // knows every map it draws: each view checked with readMapOp against all of them and handed to the map
  // that owns it (every map for a stage-wide filter), or refused here once, in words, a view no map
  // here receives included (a stage that draws no signed-off map). Live views and the
  // one sent before the maps were drawn (the Workbench moves here, then sends) go the same way.
  // The maps drawn as the signed-off panel with its terrain (ObjectMapPanel's PanelView): what a Lead view
  // may name (each with the objects it places) and what the item inspector may open. Null until the
  // artifact is read.
  const panels = useMemo(() => {
    const sociomap = ((artifact?.payload ?? null) as Payload)?.sociomap;
    const read = sociomap?.batteries, methods = sociomap?.methods;
    if (!read) return null;
    return read.flatMap((battery) => {
      const o = olderMethodOnly(battery) ? null : readObjectMap(battery);
      if (!o?.ok || o.map.outcome !== "MAPPED" || !o.map.layout || !isSignedOffMap(o.map) || !storedFrame(o.map) || o.map.terrain.status !== "computed") return [];
      return [{ battery, map: o.map, approved: mapApproval(methods, register, o.methodId) !== null }];
    });
  }, [artifact, register]);
  const drawn = useMemo(() => panels?.map(({ battery: b, map }) => {
    const placed = new Set(map.object_ids);
    return { battery_id: b.battery_id, title: b.title, objects: b.objects.filter((x) => placed.has(x.id)), respondents: densityGrid(map) !== null };
  }) ?? null, [panels]);
  // The item inspector opens an object or a relation of these maps, and of no other (MapInspect).
  const unread = Boolean(error) && !artifact;
  useEffect(() => {
    const mine = unread ? "unread" : panels;
    setShownMaps(mine);
    return () => clearShownMaps(mine);
  }, [panels, unread]);
  const artifactId = artifact?.artifact_id ?? null;
  const [leadNote, setLeadNote] = useState({ artifact: artifactId, text: "" });
  useEffect(() => {
    if (!drawn) return;
    const all = drawn;
    const onView = (e: Event) => {
      const view = (e as CustomEvent<LeadMapView>).detail;
      takeLeadMapView();
      const op = readMapOp(view, all);
      const lacks = view.op === "filter" && (view.name === "labels" || view.name === "hide_weak");
      const owner = view.op === "select" ? readTarget(view.target)?.battery : view.name === "battery" ? view.value : null;
      // The respondent map goes only to the maps that store one; none here is said once, not once per map.
      const people = view.op === "filter" && view.name === "mode" && view.value === "respondents";
      const to = all.filter((b) => (!owner || owner === b.battery_id) && (!people || b.respondents));
      const note = isRefusal(op) ? tv(`${P}.leadRefused`, { words: op.words })
        : lacks ? tv(`${P}.leadNoControl`, { what: mapViewWords(view) })
        : to.length ? ""
        : people && all.length ? t(`${P}.leadNoRespondents`)
        : tv(`${P}.leadNoMap`, { what: mapViewWords(view) });
      setLeadNote({ artifact: artifactId, text: note });
      if (!note) for (const b of to) routeToMap(b.battery_id, view);
    };
    window.addEventListener(LEAD_MAP_VIEW, onView);
    const waiting = takeLeadMapView();
    if (waiting) sendLeadMapView(waiting);
    return () => window.removeEventListener(LEAD_MAP_VIEW, onView);
  }, [drawn, artifactId]);
  return (
    <div className="fx-stage flex min-w-0 flex-col gap-4" data-testid="sociomap-stage">
      {notice}
      {loading ? <p className="text-sm text-ink-muted">{t("research.loading")}</p> : null}
      {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
      {/* A Lead view no map here can apply, in words; read out, nothing drawn over the maps. */}
      <p role="status" className="sr-only" data-testid="sociomap-lead-note">{leadNote.artifact === artifactId ? leadNote.text : ""}</p>
      {artifact && payload && !batteries.length ? <p role="note" data-no-maps className="text-sm">{payload.sociomap?.note || t("research.exec.results.noMaps")}</p> : null}
      {batteries.map((b) => {
        if (olderMethodOnly(b)) {
          // An older method's map is not drawn (ADR 0038): the run keeps its data, the stage says why.
          return (
            <section key={b.battery_id} aria-label={b.title} className="flex flex-col gap-2">
              <h2 className="text-base font-semibold">{b.title}</h2>
              <p role="note" data-older-method className="text-sm">{t("research.exec.results.olderMethod")}</p>
            </section>
          );
        }
        const read = readObjectMap(b);
        const approvalOf = (methodId: string) => mapApproval(payload?.sociomap.methods, register, methodId);
        if (!read.ok || read.map.outcome !== "MAPPED" || !read.map.layout || !isSignedOffMap(read.map)) {
          // Not the signed-off method's map, or nothing mapped: as the Results page draws it.
          return <ObjectMapView key={b.battery_id} battery={b} dataOrigin={payload?.sociomap.data_origin ?? null} approvalOf={approvalOf} />;
        }
        const { map, methodId, fingerprint } = read;
        return (
          <section key={b.battery_id} aria-labelledby={`map-${b.battery_id}`} className="flex min-w-0 flex-col gap-3" data-testid={`sociomap-stage-${b.battery_id}`}>
            <h2 id={`map-${b.battery_id}`} className="text-lg font-semibold">{b.title}</h2>
            <ObjectMapPanel key={fingerprint} battery={b} map={map} facts={<p className="text-xs">{t("research.exec.mapStage.info")}</p>} />
            <MapExplained x={explainMap(b, map)} approved={approvalOf(methodId) !== null} idPrefix={`${b.battery_id}-`}
              tech={{ methodId, fingerprint, estimator: map.spec.relation.estimator ?? null, layout: map.layout?.method ?? null,
                terrain: map.terrain.status === "computed" ? map.terrain.method : null, run: run.run_id, revision: run.design_revision,
                artifact: artifact!.artifact_id, sha256: artifact!.sha256 }} />
          </section>
        );
      })}
      {after}
    </div>
  );
}
