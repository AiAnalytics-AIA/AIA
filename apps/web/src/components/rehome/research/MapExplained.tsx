"use client";

// What explains one signed-off map, under it on the Sociomapa stage (artifact-sociomap SOC10/SOC11):
// what the map shows, its strongest relations, the objects, the respondents and their taste segments,
// how reliable it is, and -- folded -- how it was computed, the technical ids last. Plain Czech, the
// map's own stored values only (lib/map-explained.ts); no id or method name outside "Technické údaje".

import "./map-explained.css";
import type { ReactNode } from "react";
import { t, tv } from "@/i18n/t";
import { type MapExplanation, plural } from "@/lib/map-explained";
import { SEGMENT_COLOURS } from "@/lib/object-map-panel";

const M = "research.exec.mapStage";
const pct = (x: number) => `${Math.round(100 * x)} %`;
const num = (x: number, d: number) => x.toLocaleString("cs-CZ", { minimumFractionDigits: d, maximumFractionDigits: d });
const signed = (x: number) => (x >= 0 ? "+" : "−") + num(Math.abs(x), 2);
const count = (n: number) => n.toLocaleString("cs-CZ");
const word = (key: string, n: number) => plural(n, t(`${key}.one`), t(`${key}.few`), t(`${key}.many`));

export type MapTech = { methodId: string; fingerprint: string; estimator: string | null; layout: string | null; terrain: string | null; run: string; revision: number; artifact: string; sha256: string };

function Section({ id, title, lead, children }: { id: string; title: string; lead?: ReactNode; children: ReactNode }) {
  return (
    <section className="fx-sec" aria-labelledby={`fx-${id}`} data-map-section={id}>
      <header className="fx-sec__head"><h2 id={`fx-${id}`}>{title}</h2>{lead ? <p>{lead}</p> : null}</header>
      {children}
    </section>
  );
}

function Tile({ label, value, sub, children }: { label: string; value: ReactNode; sub?: ReactNode; children?: ReactNode }) {
  return (
    <div className="fx-tile">
      <span className="fx-tile__label">{label}</span>
      <span className="fx-tile__value">{value}</span>
      {children}
      {sub ? <span className="fx-tile__sub">{sub}</span> : null}
    </div>
  );
}

/** A 0-1 meter with an optional threshold mark. */
function Meter({ value, mark, label }: { value: number; mark?: number; label: string }) {
  return (
    <span className="fx-meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(100 * value)} aria-label={label}>
      <i style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
      {mark !== undefined ? <b style={{ left: `${mark * 100}%` }} /> : null}
    </span>
  );
}

const Dot = ({ colour }: { colour: string }) => <span className="fx-dot" aria-hidden style={{ background: colour }} />;

export function MapExplained({ x, approved, tech, idPrefix = "" }: { x: MapExplanation; approved: boolean; tech: MapTech; idPrefix?: string }) {
  const [lo, hi] = x.scale;
  const top = x.objects[0], low = x.objects[x.objects.length - 1];
  const rMax = Math.max(0.01, ...x.relations.map((r) => Math.abs(r.r)));
  const p = x.placement;
  const people = p ? Math.max(1, p.placed + p.faded + p.notPlaced) : 1;
  const seg = x.segments;
  const id = (s: string) => `${idPrefix}${s}`;
  const halves = x.quality === null ? t(`${M}.relyHalvesNone`)
    : x.quality.value >= 0.9 ? t(`${M}.relyHalvesHigh`)
      : x.quality.value >= x.quality.threshold ? t(`${M}.relyHalvesOk`) : t(`${M}.relyHalvesLow`);
  return (
    <div className="fx-sections" data-testid="map-explained">
      <Section id={id("what")} title={t(`${M}.whatTitle`)}
        lead={<>{tv(`${M}.whatLead`, { objects: x.objects.length, objectsWord: word(`${M}.objectWord`, x.objects.length), respondents: count(x.respondents) })}{top && low && top !== low ? ` ${tv(`${M}.whatTop`, { top: top.label, low: low.label })}` : ""}</>}>
        <div className="fx-badges">
          <span className={`fx-badge${approved ? " is-ok" : ""}`}>{approved ? t(`${M}.approved`) : t(`${M}.internal`)}</span>
        </div>
        <div className="fx-tiles">
          <Tile label={t(`${M}.tileObjects`)} value={x.objects.length} sub={x.unplaced.length ? tv(`${M}.tileUnplaced`, { count: x.unplaced.length }) : t(`${M}.tileAllPlaced`)} />
          <Tile label={t(`${M}.tileRespondents`)} value={count(x.respondents)} sub={tv(`${M}.tileRespondentsSub`, { lo, hi })} />
          <Tile label={t(`${M}.tileQuality`)} value={x.quality ? pct(x.quality.value) : "—"} sub={x.quality ? tv(`${M}.tileQualitySub`, { threshold: pct(x.quality.threshold) }) : t(`${M}.tileQualityNone`)}>
            {x.quality ? <Meter value={x.quality.value} mark={x.quality.threshold} label={t(`${M}.tileQuality`)} /> : null}
          </Tile>
          <Tile label={t(`${M}.tilePairs`)} value={<>{x.pairs.reliable} <small>{t(`${M}.tilePairsReliable`)}</small></>}
            sub={x.pairs.unknown ? tv(`${M}.tilePairsSubUnknown`, { weak: x.pairs.weak, unknown: x.pairs.unknown, total: x.pairs.total }) : tv(`${M}.tilePairsSub`, { weak: x.pairs.weak, total: x.pairs.total })}>
            <span className="fx-split" aria-hidden>
              <i className="is-ok" style={{ flexGrow: x.pairs.reliable }} /><i className="is-weak" style={{ flexGrow: x.pairs.weak }} />{x.pairs.unknown ? <i className="is-none" style={{ flexGrow: x.pairs.unknown }} /> : null}
            </span>
          </Tile>
        </div>
      </Section>

      <Section id={id("rel")} title={t(`${M}.relTitle`)} lead={t(`${M}.relLead`)}>
        {x.relations.length ? (
          <ol className="fx-rels">
            {x.relations.map((r) => {
              const w = (Math.abs(r.r) / rMax) * 50;
              return (
                <li key={`${r.a.id}|${r.b.id}`} className="fx-rel">
                  <span className="fx-rel__pair"><Dot colour={r.a.colour} />{r.a.label}<span className="fx-rel__and">{t(`${M}.relAnd`)}</span><Dot colour={r.b.colour} />{r.b.label}</span>
                  <span className="fx-rel__bar" aria-hidden><i className={r.r >= 0 ? "is-pos" : "is-neg"} style={r.r >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }} /><b /></span>
                  <span className="fx-rel__value"><b>{signed(r.r)}</b><small>{t(`${M}.${r.clear ? "relClear" : "relMild"}`)}, {t(`${M}.${r.r >= 0 ? "relAlike" : "relOpposite"}`)}</small></span>
                </li>
              );
            })}
          </ol>
        ) : <p className="fx-note">{t(`${M}.relNone`)}</p>}
        {x.moreRelations ? <p className="fx-note">{tv(`${M}.relMore`, { count: x.moreRelations })}</p> : null}
      </Section>

      <Section id={id("obj")} title={t(`${M}.objTitle`)} lead={tv(`${M}.objLead`, { lo, hi })}>
        <div className="fx-objs" role="table" aria-label={t(`${M}.objTitle`)}>
          <div className="fx-obj fx-obj--head" role="row">
            <span role="columnheader">{t(`${M}.objName`)}</span><span role="columnheader">{t(`${M}.objRating`)}</span>
            <span role="columnheader">{t(`${M}.objConnected`)}</span><span role="columnheader">{t(`${M}.objOnMap`)}</span>
          </div>
          {x.objects.map((o) => (
            <div key={o.id} className="fx-obj" role="row">
              <span role="cell" className="fx-obj__name"><Dot colour={o.colour} />{o.label}</span>
              <span role="cell" className="fx-obj__bar"><span className="fx-bar"><i style={{ width: `${o.rating === null ? 0 : ((o.rating - lo) / (hi - lo || 1)) * 100}%`, background: o.colour }} /></span><b>{o.rating === null ? "—" : num(o.rating, 2)}</b></span>
              <span role="cell" className="fx-obj__bar"><span className="fx-bar"><i className="is-ink" style={{ width: `${o.connectedness ?? 0}%` }} /></span><b>{o.connectedness === null ? "—" : num(o.connectedness, 0)}</b></span>
              <span role="cell"><span className="fx-chip is-ok">{t(`${M}.objPlaced`)}</span></span>
            </div>
          ))}
          {x.unplaced.map((label) => (
            <div key={label} className="fx-obj" role="row">
              <span role="cell" className="fx-obj__name">{label}</span><span role="cell">—</span><span role="cell">—</span>
              <span role="cell"><span className="fx-chip">{t(`${M}.objNobody`)}</span></span>
            </div>
          ))}
        </div>
      </Section>

      {p ? (
        <Section id={id("resp")} title={t(`${M}.respTitle`)} lead={t(`${M}.respLead`)}>
          <div className="fx-stack" aria-label={t(`${M}.respPlacement`)}>
            <span className="fx-stack__bar" aria-hidden><i className="is-placed" style={{ flexGrow: p.placed }} /><i className="is-faded" style={{ flexGrow: p.faded }} />{p.notPlaced ? <i className="is-none" style={{ flexGrow: p.notPlaced }} /> : null}</span>
            <span className="fx-legend">
              <span><Dot colour="var(--ink)" />{t(`${M}.respPlaced`)}: <b>{count(p.placed)}</b> ({pct(p.placed / people)})</span>
              <span><Dot colour="var(--ink-faint)" />{t(`${M}.respFaded`)}: <b>{count(p.faded)}</b> ({pct(p.faded / people)})</span>
              {p.notPlaced ? <span><Dot colour="var(--border-strong)" />{t(`${M}.respNotPlaced`)}: <b>{count(p.notPlaced)}</b></span> : null}
            </span>
          </div>
          {seg && seg.decision === "SEGMENTS" ? (
            <>
              <h3 className="fx-h3">{tv(`${M}.segTitle`, { count: seg.segments.length, word: word(`${M}.segWord`, seg.segments.length) })}{t(`${M}.${seg.distinct ? "segDistinct" : "segOverlap"}`)}</h3>
              <span className="fx-stack__bar fx-stack__bar--seg" aria-hidden>{seg.segments.map((g, k) => <i key={k} style={{ flexGrow: g.share, background: SEGMENT_COLOURS[k % SEGMENT_COLOURS.length] }}>{pct(g.share)}</i>)}</span>
              <ul className="fx-segs">
                {seg.segments.map((g, k) => (
                  <li key={k}><Dot colour={SEGMENT_COLOURS[k % SEGMENT_COLOURS.length]} /><b>{tv(`${M}.segGroup`, { k: k + 1, share: pct(g.share) })}</b>
                    <span>{[g.likes.length ? tv(`${M}.segLikes`, { objects: g.likes.join(", ") }) : null, g.dislikes.length ? tv(`${M}.segDislikes`, { objects: g.dislikes.join(", ") }) : null].filter(Boolean).join("; ")}</span></li>
                ))}
              </ul>
              <p className="fx-note">{tv(`${M}.segColour`, { share: pct(x.colourMembership) })}</p>
            </>
          ) : seg ? <p className="fx-note">{t(`${M}.${seg.decision === "BORDERLINE" ? "segBorderline" : "segNone"}`)}</p> : null}
        </Section>
      ) : null}

      <Section id={id("rely")} title={t(`${M}.relyTitle`)}>
        <div className="fx-gauges">
          <div className="fx-gauge" data-gauge="halves">
            <span className="fx-gauge__label">{t(`${M}.relyHalves`)}</span>
            <span className="fx-gauge__value">{x.quality ? pct(x.quality.value) : "—"}</span>
            {x.quality ? <Meter value={x.quality.value} mark={x.quality.threshold} label={t(`${M}.relyHalves`)} /> : null}
            <p>{halves}</p>
          </div>
          <div className="fx-gauge" data-gauge="place">
            <span className="fx-gauge__label">{t(`${M}.relyPlace`)}</span>
            <span className="fx-gauge__value">{x.uncertainty === null ? "—" : `± ${pct(x.uncertainty)}`}</span>
            {x.uncertainty !== null ? <Meter value={Math.min(1, x.uncertainty / 0.5)} label={t(`${M}.relyPlace`)} /> : null}
            <p>{x.uncertainty === null ? t(`${M}.relyPlaceNone`) : tv(`${M}.${x.uncertainty < 0.1 ? "relyPlaceLow" : "relyPlaceHigh"}`, { share: pct(x.uncertainty) })}</p>
          </div>
          <div className="fx-gauge" data-gauge="pairs">
            <span className="fx-gauge__label">{t(`${M}.relyPairs`)}</span>
            <span className="fx-gauge__value">{tv(`${M}.relyPairsValue`, { reliable: x.pairs.reliable, total: x.pairs.total })}</span>
            <Meter value={x.pairs.total ? x.pairs.reliable / x.pairs.total : 0} label={t(`${M}.relyPairs`)} />
            <p>{tv(`${M}.relyPairsText`, { reliable: x.pairs.reliable, word: word(`${M}.relyPairsWord`, x.pairs.reliable) })}</p>
          </div>
        </div>
      </Section>

      <details className="fx-sec fx-how" data-map-section={id("how")}>
        <summary><h2>{t(`${M}.howTitle`)}</h2><span>{t(`${M}.howSub`)}</span></summary>
        <ol className="fx-steps">
          <li><b>{t(`${M}.howRatings`)}</b> {tv(`${M}.howRatingsText`, { lo, hi })}</li>
          <li><b>{t(`${M}.howRelations`)}</b> {tv(`${M}.howRelationsText`, { nMin: x.nMin })}</li>
          <li><b>{t(`${M}.howLayout`)}</b> {t(`${M}.${tech.layout?.startsWith("soft_rank") ? "howLayoutText" : "howLayoutOther"}`)}</li>
          <li><b>{t(`${M}.howTerrain`)}</b> {t(`${M}.howTerrainText`)}</li>
          <li><b>{t(`${M}.howGroups`)}</b> {t(`${M}.howGroupsText`)}</li>
          <li><b>{t(`${M}.howReliability`)}</b> {t(`${M}.howReliabilityText`)}</li>
        </ol>
        <details className="fx-tech" data-testid="map-tech">
          <summary>{t(`${M}.tech`)}</summary>
          <dl>
            <dt>{t(`${M}.techMethod`)}</dt><dd>{tech.methodId}</dd>
            <dt>{t(`${M}.techEstimator`)}</dt><dd>{tech.estimator ?? "—"}</dd>
            <dt>{t(`${M}.techLayout`)}</dt><dd>{tech.layout ?? "—"}</dd>
            <dt>{t(`${M}.techTerrain`)}</dt><dd>{tech.terrain ?? "—"}</dd>
            <dt>{t(`${M}.techRun`)}</dt><dd>{tv(`${M}.techRunValue`, { run: tech.run, revision: tech.revision })}</dd>
            <dt>{t(`${M}.techArtifact`)}</dt><dd>{tech.artifact}</dd>
            <dt>SHA256</dt><dd>{tech.sha256}</dd>
            <dt>{t(`${M}.techSpec`)}</dt><dd>{tech.fingerprint}</dd>
          </dl>
        </details>
      </details>
    </div>
  );
}
