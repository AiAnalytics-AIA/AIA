"use client";
// Sociomapa's inspector body (artifact-sociomap SOC4; spec szz S3): an object or a relation of a map on the
// stage, opened in the workbench's drawer by a person or by the Lead's "Detail dvojice". The frame draws the
// drawer and passes the target alone; the maps it reads are the ones the stage draws, published by
// SociomapStage (setShownMaps), so the drawer can never open another run's map. The body is the panel's own
// card (RelationBlock, ObjectCard), from the stored map only: nothing is recomputed, and a relation that
// cannot be determined says why, never 0.

import { type ReactNode, useSyncExternalStore } from "react";
import { useItemInspector } from "@/components/workbench/item-inspector-context";
import { t } from "@/i18n/t";
import { pairTarget, readTarget } from "@/lib/artifacts/sociomap";
import { relationDetail } from "@/lib/object-map-signed-off";
import type { BatteryWithMaps, ObjectMapArtifact } from "@/lib/object-map-view";
import { ObjectCard, RelationBlock } from "./ObjectMapPanel";

type Shown = readonly { battery: BatteryWithMaps; map: ObjectMapArtifact }[];

// Null: no stage has read its artifact yet, so whether an item is on the map is not known.
let shown: Shown | null = null;
const listeners = new Set<() => void>();

/** The maps the stage draws now; SociomapStage sets them once it has read its artifact. */
export function setShownMaps(next: Shown | null): void {
  if (next === shown) return;
  shown = next;
  listeners.forEach((l) => l());
}

const NONE: Shown = [];

/** A stage that left: no map is drawn, so nothing is on it. Only its own maps (another stage may have come). */
export function clearShownMaps(mine: Shown | null): void {
  if (mine !== null && shown === mine) setShownMaps(NONE);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function MapInspect({ target }: { target: string }): ReactNode {
  const maps = useSyncExternalStore(subscribe, () => shown, () => shown);
  const inspector = useItemInspector();
  if (maps === null) return <p className="muted">{t("research.exec.mapInspect.loading")}</p>;
  const at = readTarget(target);
  const found = at ? maps.find((m) => m.battery.battery_id === at.battery) : undefined;
  const index = (id: string) => found?.map.object_ids.indexOf(id) ?? -1;
  const missing = <p className="muted">{t("research.exec.mapInspect.missing")}</p>;
  if (!at || !found) return missing;
  const frozen = <p className="mt-2 text-xs text-ink-muted">{t("research.exec.mapInspect.frozen")}</p>;
  if (at.kind === "pair") {
    const i = index(at.a), j = index(at.b);
    if (i < 0 || j < 0) return missing;
    return <div className="omw" data-testid="map-inspect-pair"><RelationBlock detail={relationDetail(found.battery, found.map, i, j)} />{frozen}</div>;
  }
  const k = index(at.object);
  if (k < 0) return missing;
  // A relation listed on the object's card opens that pair in the drawer, over the object.
  const openPair = (j: number) => {
    const id = pairTarget(found.battery.battery_id, found.map.object_ids[k], found.map.object_ids[j]);
    if (id) inspector?.open({ id, title: t("research.exec.objectMap.panel.relationTitle") });
  };
  return <div className="omw" data-testid="map-inspect-object"><ObjectCard battery={found.battery} map={found.map} selected={k} relation={null} onRelation={openPair} />{frozen}</div>;
}
