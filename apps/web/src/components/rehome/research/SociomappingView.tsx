"use client";

// The experimental Sociomapping on the Results page (plan sociomapping-engine I4).
//
// Renders the stored artifact only: positions, heights and fit come from the worker, and
// this view never computes or adjusts them. 3D and top view, rotation (drag, buttons,
// arrow keys), zoom, a height legend, each object's details, the fit diagnostics, the method
// and its provenance, the limitations, and the internal draft report. The method is AIA's
// experimental H-Model, and the page says so before anything else.

import { type KeyboardEvent, type PointerEvent, useEffect, useMemo, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { ApiError, type Artifact, type ResearchReport, type ResearchRun, research } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import {
  DEFAULT_3D,
  TOP_VIEW,
  VIEW,
  type Camera,
  type MapPoint,
  type SociomappingBattery,
  type SociomappingResult,
  clampCamera,
  limitationText,
  mapPoints,
  num,
  project,
  readResult,
  relationsOf,
} from "@/lib/sociomapping-view";
import { Button } from "../ui";

const SEQ = (band: number) => `var(--viz-seq-${band + 1})`;
const STEP = Math.PI / 12;

export function SociomappingView({ artifact, run, studyId, canEdit }: { artifact: Artifact; run: ResearchRun; studyId: string; canEdit: boolean }) {
  const read = readResult(artifact.payload);
  const [batteryId, setBatteryId] = useState<string | null>(null);
  if (!read.ok) {
    return <p role="alert" className="text-sm text-status-fault">{t(`research.exec.sociomapping.unreadable.${read.reason}`)}</p>;
  }
  const result = read.result;
  const battery = result.batteries.find((b) => b.battery_id === batteryId) ?? result.batteries[0];
  return (
    <div className="flex flex-col gap-4">
      <p role="note" className="text-sm font-semibold">{t("research.exec.sociomapping.experimental")}</p>
      {result.synthetic_data ? (
        <p className="text-sm text-status-fault">{tv("research.exec.sociomapping.synthetic", { origin: result.data_origin ?? "—" })}</p>
      ) : null}
      {result.batteries.length === 0 ? <p className="text-sm text-ink-muted">{result.note}</p> : null}
      {result.batteries.length > 1 ? (
        <label className="flex items-center gap-2 text-sm">
          {t("research.exec.sociomapping.set")}
          <select className="rounded border border-border bg-surface-raised px-2 py-1" value={battery?.battery_id} onChange={(e) => setBatteryId(e.target.value)}>
            {result.batteries.map((b) => <option key={b.battery_id} value={b.battery_id}>{b.title}</option>)}
          </select>
        </label>
      ) : null}
      {battery ? <BatteryMap key={battery.battery_id} battery={battery} /> : null}
      <MethodDetails result={result} battery={battery} artifact={artifact} run={run} />
      <SociomappingReport run={run} studyId={studyId} canEdit={canEdit} />
    </div>
  );
}

function BatteryMap({ battery }: { battery: SociomappingBattery }) {
  const points = useMemo(() => mapPoints(battery), [battery]);
  const [camera, setCamera] = useState<Camera>(DEFAULT_3D);
  const [selected, setSelected] = useState<string | null>(points[0]?.id ?? null);
  const drag = useRef<{ x: number; y: number; camera: Camera } | null>(null);

  if (battery.status !== "MAPPED" || !battery.layout) {
    return (
      <section aria-label={battery.title} className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold">{battery.title}</h3>
        <p role="alert" className="text-sm text-status-fault">{tv("research.exec.sociomapping.notMapped", { reason: battery.reason ?? "—" })}</p>
        <Limitations battery={battery} />
      </section>
    );
  }
  const layout = battery.layout;
  const move = (change: Partial<Camera>) => setCamera((c) => clampCamera({ ...c, ...change }));
  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    const keys: Record<string, Partial<Camera>> = {
      ArrowLeft: { yaw: camera.yaw - STEP },
      ArrowRight: { yaw: camera.yaw + STEP },
      ArrowUp: { pitch: camera.pitch + 0.1 },
      ArrowDown: { pitch: camera.pitch - 0.1 },
      "+": { zoom: camera.zoom * 1.2 },
      "-": { zoom: camera.zoom / 1.2 },
    };
    if (keys[e.key]) {
      e.preventDefault();
      move(keys[e.key]);
    }
  };
  const onDown = (e: PointerEvent<SVGSVGElement>) => {
    drag.current = { x: e.clientX, y: e.clientY, camera };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const start = drag.current;
    if (!start) return;
    move({ yaw: start.camera.yaw + (e.clientX - start.x) / 120, pitch: start.camera.pitch - (e.clientY - start.y) / 160 });
  };
  const onUp = () => {
    drag.current = null;
  };
  const ground = [[0, 0], [1, 0], [1, 1], [0, 1]].map(([x, y]) => project(x, y, 0, camera));
  const grid = [0.25, 0.5, 0.75];
  const drawn = points
    .map((p) => ({ p, top: project(p.x, p.y, p.share, camera), base: project(p.x, p.y, 0, camera) }))
    .sort((a, b) => b.top.depth - a.top.depth || a.p.id.localeCompare(b.p.id));
  const chosen = points.find((p) => p.id === selected) ?? null;
  const [low, high] = battery.rating_scale;
  return (
    <section aria-label={battery.title} className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold">{battery.title}</h3>
      <p className="text-xs text-ink-muted">
        {tv("research.exec.sociomapping.support", {
          complete: battery.support.respondents_complete,
          total: battery.support.respondents_total,
          objects: battery.objects.length,
        })}
      </p>
      <div className="flex flex-wrap gap-2" role="toolbar" aria-label={t("research.exec.sociomapping.controls")}>
        <Button small onClick={() => setCamera({ ...DEFAULT_3D, zoom: camera.zoom })} aria-pressed={camera.pitch > 0}>{t("research.exec.sociomapping.view3d")}</Button>
        <Button small onClick={() => setCamera({ ...TOP_VIEW, zoom: camera.zoom })} aria-pressed={camera.pitch === 0}>{t("research.exec.sociomapping.viewTop")}</Button>
        <Button small onClick={() => move({ yaw: camera.yaw - STEP })}>{t("research.exec.sociomapping.rotateLeft")}</Button>
        <Button small onClick={() => move({ yaw: camera.yaw + STEP })}>{t("research.exec.sociomapping.rotateRight")}</Button>
        <Button small onClick={() => move({ zoom: camera.zoom * 1.2 })}>{t("research.exec.sociomapping.zoomIn")}</Button>
        <Button small onClick={() => move({ zoom: camera.zoom / 1.2 })}>{t("research.exec.sociomapping.zoomOut")}</Button>
        <Button small onClick={() => setCamera(DEFAULT_3D)}>{t("research.exec.sociomapping.reset")}</Button>
      </div>
      <div className="grid gap-4 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div>
          <svg
            viewBox={`0 0 ${VIEW.width} ${VIEW.height}`}
            role="img"
            aria-label={tv("research.exec.sociomapping.mapLabel", { title: battery.title, n: points.length })}
            tabIndex={0}
            onKeyDown={onKey}
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerLeave={onUp}
            className="w-full touch-none rounded border border-border bg-surface-raised focus:outline focus:outline-2 focus:outline-[var(--focus-ring)]"
            data-testid="sociomapping-map"
          >
            <polygon points={ground.map((g) => `${g.sx},${g.sy}`).join(" ")} fill="var(--signal-wash)" stroke="var(--border-strong)" strokeWidth={1} />
            {grid.map((g) => {
              const a = project(g, 0, 0, camera);
              const b = project(g, 1, 0, camera);
              const c = project(0, g, 0, camera);
              const d = project(1, g, 0, camera);
              return (
                <g key={g} stroke="var(--border)" strokeWidth={0.6}>
                  <line x1={a.sx} y1={a.sy} x2={b.sx} y2={b.sy} />
                  <line x1={c.sx} y1={c.sy} x2={d.sx} y2={d.sy} />
                </g>
              );
            })}
            {drawn.map(({ p, top, base }) => (
              <g
                key={p.id}
                onClick={() => setSelected(p.id)}
                className="cursor-pointer"
                data-testid={`sociomapping-point-${p.id}`}
              >
                {camera.pitch > 0 ? <line x1={base.sx} y1={base.sy} x2={top.sx} y2={top.sy} stroke="var(--ink-muted)" strokeWidth={1} strokeDasharray="3 2" /> : null}
                <circle cx={top.sx} cy={top.sy} r={p.id === selected ? 11 : 8} fill={SEQ(p.band)} stroke={p.id === selected ? "var(--ink)" : "var(--ink-muted)"} strokeWidth={p.id === selected ? 2.5 : 1} />
                <text x={top.sx + 12} y={top.sy - 8} fontSize={13} fill="var(--ink)">{p.label}</text>
              </g>
            ))}
          </svg>
          <Legend low={low} high={high} labels={battery.scale_labels} />
          <p className="mt-1 text-xs text-ink-muted">{t("research.exec.sociomapping.howToRead")}</p>
        </div>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            {t("research.exec.sociomapping.object")}
            <select className="rounded border border-border bg-surface-raised px-2 py-1" value={selected ?? ""} onChange={(e) => setSelected(e.target.value)}>
              {points.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </label>
          {chosen ? <ObjectDetails battery={battery} point={chosen} /> : null}
          {layout.unplaced.length ? (
            <div className="text-sm">
              <p className="font-semibold">{t("research.exec.sociomapping.unplaced")}</p>
              <ul className="list-disc pl-5">
                {layout.unplaced.map((u) => (
                  <li key={u.element_id}>{battery.objects.find((o) => o.id === u.element_id)?.label ?? u.element_id}: {u.reason}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
      <FitDiagnostics battery={battery} />
      <Limitations battery={battery} />
    </section>
  );
}

function Legend({ low, high, labels }: { low: number; high: number; labels?: [string, string] }) {
  return (
    <div className="mt-2 flex items-center gap-2 text-xs" aria-label={t("research.exec.sociomapping.legend")}>
      <span>{t("research.exec.sociomapping.legend")}:</span>
      <span>{low}{labels ? ` ${labels[0]}` : ""}</span>
      <span className="flex" aria-hidden>
        {[0, 1, 2, 3, 4, 5, 6].map((k) => <span key={k} className="inline-block h-3 w-5" style={{ background: SEQ(k) }} />)}
      </span>
      <span>{high}{labels ? ` ${labels[1]}` : ""}</span>
    </div>
  );
}

function ObjectDetails({ battery, point }: { battery: SociomappingBattery; point: MapPoint }) {
  const relations = relationsOf(battery, point.id);
  return (
    <div className="rounded border border-border p-3 text-sm" data-testid="sociomapping-details">
      <p className="font-semibold">{point.label}</p>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        <dt className="text-ink-muted">{t("research.exec.sociomapping.height")}</dt>
        <dd className="tabular-nums">{num(point.height, 2)}</dd>
        <dt className="text-ink-muted">{t("research.exec.sociomapping.pointFit")}</dt>
        <dd className="tabular-nums">{num(point.fit)}</dd>
        <dt className="text-ink-muted">{t("research.exec.sociomapping.position")}</dt>
        <dd className="tabular-nums">{num(point.x)}, {num(point.y)}</dd>
      </dl>
      <p className="mt-2 text-xs font-semibold">{t("research.exec.sociomapping.relations")}</p>
      <table className="mt-1 w-full text-xs">
        <tbody>
          {relations.map((r) => (
            <tr key={r.id} className="border-t border-border">
              <td className="py-0.5 pr-2">{r.label}</td>
              <td className={`py-0.5 tabular-nums ${r.r !== null && r.r < 0 ? "text-status-fault" : ""}`}>{r.r === null ? t("research.exec.sociomapping.undefinedRelation") : num(r.r, 2)}</td>
              <td className="py-0.5 text-ink-muted">{r.why ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FitDiagnostics({ battery }: { battery: SociomappingBattery }) {
  const layout = battery.layout!;
  const a = layout.accuracy;
  return (
    <details className="text-sm" open>
      <summary className="cursor-pointer font-semibold">{t("research.exec.sociomapping.fit")}</summary>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        <dt className="text-ink-muted">{t("research.exec.sociomapping.overall")}</dt>
        <dd className="tabular-nums" data-testid="sociomapping-accuracy">{num(a.overall)}{a.overall_undefined ? ` (${a.overall_undefined})` : ""}</dd>
        <dt className="text-ink-muted">{t("research.exec.sociomapping.meanPerPoint")}</dt>
        <dd className="tabular-nums">{num(a.mean_per_point)}</dd>
        <dt className="text-ink-muted">{t("research.exec.sociomapping.pairs")}</dt>
        <dd className="tabular-nums">{tv("research.exec.sociomapping.pairsValue", { defined: a.ordered_pairs, undefined: a.undefined_pairs })}</dd>
        <dt className="text-ink-muted">{t("research.exec.sociomapping.baseline")}</dt>
        <dd className="tabular-nums">{num(layout.baseline_classical_mds)}</dd>
        <dt className="text-ink-muted">{t("research.exec.sociomapping.evaluator")}</dt>
        <dd>{a.evaluator}</dd>
      </dl>
      <table className="mt-2 w-full text-xs">
        <thead>
          <tr className="text-left text-ink-muted">
            <th className="py-1 font-medium">{t("research.exec.sociomapping.start")}</th>
            <th className="py-1 font-medium">{t("research.exec.sociomapping.branch")}</th>
            <th className="py-1 font-medium">{t("research.exec.sociomapping.startAccuracy")}</th>
          </tr>
        </thead>
        <tbody>
          {layout.starts.map((s, k) => (
            <tr key={s.label} className={`border-t border-border ${k === layout.chosen_start ? "font-semibold" : ""}`}>
              <td className="py-0.5">{s.label}{k === layout.chosen_start ? ` · ${t("research.exec.sociomapping.chosen")}` : ""}</td>
              <td className="py-0.5">{s.branch}</td>
              <td className="py-0.5 tabular-nums">{num(s.final_accuracy)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-xs text-ink-muted">{t("research.exec.sociomapping.fitNote")}</p>
    </details>
  );
}

function Limitations({ battery }: { battery: SociomappingBattery }) {
  return (
    <details className="text-sm" open>
      <summary className="cursor-pointer font-semibold">{t("research.exec.sociomapping.limitations")}</summary>
      <ul className="mt-2 list-disc pl-5">
        {battery.limitations.map((l) => <li key={l.code}>{limitationText(l)}</li>)}
      </ul>
    </details>
  );
}

function MethodDetails({ result, battery, artifact, run }: { result: SociomappingResult; battery?: SociomappingBattery; artifact: Artifact; run: ResearchRun }) {
  const rows: [string, string][] = [
    [t("research.exec.sociomapping.method"), `${result.method.name} (${result.method.status})`],
    [t("research.exec.sociomapping.evaluator"), result.method.evaluator],
    [t("research.exec.sociomapping.parameters"), Object.entries(result.method.parameters).map(([k, v]) => `${k}=${String(v)}`).join(", ")],
    [t("research.exec.sociomapping.origin"), result.data_origin ?? "—"],
    [t("research.exec.sociomapping.version"), result.sociomapping_version],
    [t("research.exec.sociomapping.artifact"), `${artifact.artifact_id} · SHA256 ${artifact.sha256.slice(0, 12)} · ${run.run_id}`],
  ];
  if (result.inputs?.dataset_sha256) rows.push([t("research.exec.sociomapping.dataset"), result.inputs.dataset_sha256.slice(0, 16)]);
  if (battery?.relations) rows.push([t("research.exec.sociomapping.relationsFingerprint"), battery.relations.fingerprint.slice(0, 16)]);
  if (battery?.rules) rows.push([t("research.exec.sociomapping.rules"), battery.rules.join(", ")]);
  if (battery?.coherences) {
    rows.push([
      t("research.exec.sociomapping.coherences"),
      battery.coherences.available ? battery.coherences.written ?? "" : battery.coherences.reason ?? "",
    ]);
  }
  return (
    <details className="text-sm">
      <summary className="cursor-pointer font-semibold">{t("research.exec.sociomapping.methodTitle")}</summary>
      <p className="mt-2 text-xs text-ink-muted">{t("research.exec.sociomapping.methodText")}</p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-muted">{k}</dt>
            <dd className="break-all">{v}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

type Loaded = { state: "loading" } | { state: "ready"; value: ResearchReport } | { state: "failed"; message: string } | { state: "hidden" };

function SociomappingReport({ run, studyId, canEdit }: { run: ResearchRun; studyId: string; canEdit: boolean }) {
  const [loaded, setLoaded] = useState<Loaded>({ state: "loading" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const step = run.steps.find((s) => s.node_key === "sociomapping_report");
  useEffect(() => {
    let live = true;
    research.sociomappingReport(studyId, run.run_id).then(
      (value) => live && setLoaded({ state: "ready", value }),
      (e: unknown) => live && setLoaded(e instanceof ApiError && e.status === 403 ? { state: "hidden" } : { state: "failed", message: e instanceof Error ? e.message : String(e) }),
    );
    return () => {
      live = false;
    };
  }, [studyId, run.run_id, step?.status, step?.artifact_id]);
  if (loaded.state === "hidden") return null;
  const status = loaded.state === "ready" ? loaded.value : null;
  const download = async () => {
    setBusy(true);
    setError(null);
    try {
      saveBlob(await research.downloadSociomappingReport(studyId, run.run_id), `AIA-${studyId}-sociomapping-experimental-draft.docx`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="rounded border border-border p-3 text-sm" data-testid="sociomapping-report">
      <p className="font-semibold">{t("research.exec.sociomapping.reportTitle")}</p>
      <p className="text-xs text-ink-muted">{t("research.exec.sociomapping.reportInternal")}</p>
      {loaded.state === "loading" ? <p className="text-ink-muted">{t("research.loading")}</p> : null}
      {loaded.state === "failed" ? <p role="alert" className="text-status-fault">{loaded.message}</p> : null}
      {status?.state === "READY" ? (
        <div className="mt-2 flex flex-col items-start gap-2">
          <p className="text-xs text-ink-muted">{tv("research.exec.results.reportProvenance", { id: status.artifact_id ?? "—", sha: status.sha256?.slice(0, 12) ?? "—", run: run.run_id })}</p>
          <Button onClick={download} disabled={busy || !canEdit}>{busy ? t("research.exec.results.reportDownloading") : t("research.exec.sociomapping.reportDownload")}</Button>
        </div>
      ) : null}
      {status && status.state !== "READY" ? <p className="text-ink-muted">{status.state === "FAILED" ? t("research.exec.results.reportFailed") : t("research.exec.sociomapping.reportWaiting")}</p> : null}
      {error ? <p role="alert" className="text-status-fault">{error}</p> : null}
    </div>
  );
}
