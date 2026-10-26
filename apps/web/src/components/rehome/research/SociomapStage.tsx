"use client";

// The Sociomapa stage of the workbench (artifact-sociomap SOC9): the map is the stage. No results tabs,
// no guide: each mapped set's map first, at the pane's full width, and under it what explains it
// (MapExplained). The run's notices stay above (its origin, a moved design), the experimental
// Sociomapping and its review below. A set stored under an older method says so and draws nothing; a
// map that is not the signed-off method's is drawn as the Results page draws it. Výsledky keeps its tabs.

import { type ReactNode, useEffect, useState } from "react";
import { t } from "@/i18n/t";
import { type Artifact, type ResearchRun, research } from "@/lib/api";
import { explainMap } from "@/lib/map-explained";
import { type BatteryWithMaps, mapApproval, olderMethodOnly, readObjectMap, type RecordedMethod, type RegisterEntry } from "@/lib/object-map-view";
import { isSignedOffMap } from "@/lib/object-map-signed-off";
import { stageOf } from "@/lib/workbench-stages";
import { useFrame } from "./frame-hook";
import { MapExplained } from "./MapExplained";
import { setShownMaps } from "./MapInspect";
import { ObjectMapPanel } from "./ObjectMapPanel";
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
  // The maps the item inspector may open an object or a relation of (MapInspect): the ones drawn here.
  useEffect(() => {
    const drawn = ((artifact?.payload ?? null) as Payload)?.sociomap?.batteries ?? [];
    setShownMaps(drawn.flatMap((battery) => {
      const read = readObjectMap(battery);
      return read.ok && read.map.outcome === "MAPPED" && isSignedOffMap(read.map) ? [{ battery, map: read.map }] : [];
    }));
    return () => setShownMaps([]);
  }, [artifact]);
  return (
    <div className="fx-stage flex min-w-0 flex-col gap-4" data-testid="sociomap-stage">
      {notice}
      {loading ? <p className="text-sm text-ink-muted">{t("research.loading")}</p> : null}
      {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
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
