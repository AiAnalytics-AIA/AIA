"use client";
// Sociomapa's inspector body (artifact-sociomap SOC4; spec szz S3): an object or a relation of a map on the
// stage, opened in the workbench's drawer by a person or by the Lead's "Detail dvojice". The frame draws the
// drawer and passes the target alone; the maps it reads are the ones the stage shows, published by
// SociomapStage (setShownMaps), so the drawer can never open another run's map. From the stored map only:
// nothing is recomputed, and an undefined relation reads unknown, never 0.

import { type ReactNode, useSyncExternalStore } from "react";
import { t, tv } from "@/i18n/t";
import { readTarget } from "@/lib/artifacts/sociomap";
import { objectDetail, relationDetail } from "@/lib/object-map-signed-off";
import { type BatteryWithMaps, type ObjectMapArtifact, originalRating } from "@/lib/object-map-view";
import { num } from "@/lib/sociomapping-view";

type Shown = readonly { battery: BatteryWithMaps; map: ObjectMapArtifact }[];

let shown: Shown = [];
const listeners = new Set<() => void>();

/** The maps the stage shows now; SociomapStage sets them when it draws them and clears them when it leaves. */
export function setShownMaps(next: Shown): void {
  if (next === shown) return;
  shown = next;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

const P = "research.exec.objectMap.panel";
const signed = (v: number) => (v >= 0 ? "+" : "") + num(v, 2);

function Fact({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="font-semibold tabular-nums">{value}</dd>
      {note ? <dd className="text-xs text-ink-muted tabular-nums">{note}</dd> : null}
    </div>
  );
}

export function MapInspect({ target }: { target: string }): ReactNode {
  const maps = useSyncExternalStore(subscribe, () => shown, () => shown);
  const at = readTarget(target);
  const found = at ? maps.find((m) => m.battery.battery_id === at.battery) : undefined;
  const index = (id: string) => found?.map.object_ids.indexOf(id) ?? -1;
  const missing = <p className="muted">{t("research.exec.mapInspect.missing")}</p>;
  if (!at || !found) return missing;
  const frozen = <p className="mt-2 text-xs text-ink-muted">{t("research.exec.mapInspect.frozen")}</p>;

  if (at.kind === "pair") {
    const i = index(at.a), j = index(at.b);
    if (i < 0 || j < 0) return missing;
    const d = relationDetail(found.battery, found.map, i, j);
    const verdict = d.r === null ? tv(`${P}.${d.verdict === "noSpread" ? "relationNoSpread" : "relationFewRatings"}`, { n: d.n ?? 0 })
      : t(`${P}.${d.verdict === "reliable" ? "relationReliable" : "relationWeak"}`);
    return (
      <div data-testid="map-inspect-pair">
        <b>{d.a} – {d.b}</b>
        <dl className="mt-2 flex flex-col gap-1">
          <Fact label={t(`${P}.relationR`)} value={d.r === null ? t("research.exec.mapInspect.unknown") : signed(d.r)}
            note={d.r === null ? undefined : d.interval ? tv(`${P}.relationInterval`, { lo: signed(d.interval[0]), hi: signed(d.interval[1]) }) : t(`${P}.relationNoInterval`)} />
          <Fact label={t(`${P}.relationN`)} value={d.n === null ? "—" : String(d.n)} />
        </dl>
        <p className="mt-2 text-sm">{verdict}</p>
        {frozen}
      </div>
    );
  }

  const k = index(at.object);
  if (k < 0) return missing;
  const o = objectDetail(found.battery, found.map, k);
  const height = o.height === null ? "—" : num(originalRating(o.height, found.battery.rating_scale) ?? o.height, 2);
  return (
    <div data-testid="map-inspect-object">
      <b>{o.label}</b>
      <dl className="mt-2 flex flex-col gap-1">
        <Fact label={t(`${P}.detailHeight`)} value={height} />
        <Fact label={t(`${P}.detailConnectedness`)} value={o.connectedness === null ? "—" : num(o.connectedness, 2)} />
      </dl>
      <h3 className="mt-3 text-sm font-semibold">{t(`${P}.detailRelations`)}</h3>
      {o.relations.length ? (
        <ul className="mt-1 flex flex-col gap-0.5 text-sm">
          {o.relations.map((x) => <li key={x.id}>{x.label} <b className="tabular-nums">{signed(x.r)}</b></li>)}
        </ul>
      ) : <p className="text-sm text-ink-muted">{t(`${P}.detailNoRelation`)}</p>}
      {frozen}
    </div>
  );
}
