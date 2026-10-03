"use client";

import { useMemo, useRef, useState } from "react";
import {
  INITIAL_CAMERA,
  elevation,
  project,
  surface,
  type MapWorkspace,
  type MapPoint,
} from "@/lib/sociomap-workspace";
import { Button } from "../ui";

const metrics: Record<string, string> = {
  density: "Hustota respondentů",
  relation_classic: "Celkové relační skóre",
  relation_norm: "Normativní relační skóre",
  mean_rating: "Průměrné hodnocení",
  support_n: "Počet odpovědí",
};
const reasons: Record<string, string> = {
  SCALE_NOT_1_10:
    "Tento pohled podporuje škálu 1–10. Studie používá jinou škálu.",
  WORKSPACE_SIZE_LIMIT:
    "Mapa překračuje limit 2 000 respondentů nebo 32 objektů. Data nebyla zkrácena.",
  INSUFFICIENT_PAIR_SUPPORT_OR_VARIANCE:
    "Objektová mapa potřebuje alespoň pět společných odpovědí a proměnlivá hodnocení pro každou dvojici. Chybějící vztahy nejsou nahrazeny odhadem.",
};
const number = (n: number | null | undefined) =>
  n == null ? "—" : n.toLocaleString("cs-CZ", { maximumFractionDigits: 2 });
const colour = (v: number) =>
  `var(--viz-seq-${Math.min(7, Math.max(1, 1 + Math.floor(v * 7)))})`;

export function SociomapWorkspace({
  workspace,
  labels,
  origin,
}: {
  workspace?: MapWorkspace | null;
  labels: { id: string; label: string }[];
  origin: string | null;
}) {
  if (!workspace)
    return (
      <p className="text-sm text-ink-muted">
        Tento běh neobsahuje 3D mapu. Nový běh ji vytvoří, pokud je její výpočet
        zapnutý.
      </p>
    );
  if (workspace.version !== "aia-native-workspace-1")
    return <p role="status">Tato verze mapy zatím není podporována.</p>;
  if (workspace.status !== "AVAILABLE")
    return (
      <p role="status">
        {reasons[workspace.reason ?? ""] ?? "Mapa není dostupná."}
      </p>
    );
  return (
    <WorkspaceView
      key={workspace.input_fingerprint}
      workspace={workspace}
      labels={labels}
      origin={origin}
    />
  );
}

function WorkspaceView({
  workspace: w,
  labels,
  origin,
}: {
  workspace: MapWorkspace;
  labels: { id: string; label: string }[];
  origin: string | null;
}) {
  const [mode, setMode] = useState<"respondents" | "objects">("respondents");
  const [metric, setMetric] = useState("relation_classic");
  const [camera, setCamera] = useState(INITIAL_CAMERA);
  const [selected, setSelected] = useState("");
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const terrain =
    mode === "respondents" ? w.respondent_terrain : w.object_terrains[metric];
  const triangles = useMemo(
    () => (terrain ? surface(terrain, camera) : []),
    [terrain, camera],
  );
  const points = mode === "respondents" ? w.people : w.objects;
  const chosen = points.find((p) => p.id === selected);
  const label = (id: string) => labels.find((o) => o.id === id)?.label ?? id;
  const name = mode === "respondents" ? metrics.density : metrics[metric];
  const show = (p: MapPoint) =>
    terrain
      ? project(p.x, p.y, elevation(p, terrain) + 1, camera)
      : { x: 0, y: 0, depth: 0 };
  const switchMode = (next: "respondents" | "objects") => {
    setMode(next);
    setSelected("");
  };
  return (
    <div className="flex flex-col gap-3" data-testid="sociomap-workspace">
      <p role="note" className="text-sm text-ink-muted">
        Interní výzkumný pohled ·{" "}
        {origin?.startsWith("SYNTHETIC")
          ? "Syntetická data, nikoli měření trhu"
          : origin
            ? "Data tohoto běhu"
            : "Původ dat není uveden"}{" "}
        · bez populačních vah
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <Button
          aria-pressed={mode === "respondents"}
          onClick={() => switchMode("respondents")}
        >
          Respondenti
        </Button>
        <Button
          aria-pressed={mode === "objects"}
          onClick={() => switchMode("objects")}
        >
          Objekty
        </Button>
        {mode === "objects" && w.objects.length > 0 && (
          <label className="text-sm">
            Výška a barva{" "}
            <select
              className="ml-2 rounded-sm border border-border bg-surface p-2"
              value={metric}
              onChange={(e) => setMetric(e.target.value)}
            >
              {Object.keys(w.object_terrains).map((key) => (
                <option key={key} value={key}>
                  {metrics[key] ?? key}
                </option>
              ))}
            </select>
          </label>
        )}
        <Button onClick={() => setCamera((c) => ({ ...c, pitch: 0.72 }))}>
          3D
        </Button>
        <Button onClick={() => setCamera((c) => ({ ...c, pitch: 0 }))}>
          Pohled shora
        </Button>
        <Button
          aria-label="Přiblížit mapu"
          onClick={() =>
            setCamera((c) => ({ ...c, zoom: Math.min(2, c.zoom * 1.15) }))
          }
        >
          +
        </Button>
        <Button
          aria-label="Oddálit mapu"
          onClick={() =>
            setCamera((c) => ({ ...c, zoom: Math.max(0.4, c.zoom / 1.15) }))
          }
        >
          −
        </Button>
        <Button onClick={() => setCamera(INITIAL_CAMERA)}>
          Výchozí pohled
        </Button>
      </div>
      {terrain ? (
        <>
          <p className="text-xs text-ink-muted">
            {mode === "respondents"
              ? "Poloha vychází z hodnocení objektů; výška ukazuje hustotu respondentů."
              : "Poloha vychází ze vztahů; změna metriky mění výšku a barvu, nikoli polohu."}{" "}
            Tažením otočíte mapu. Šipky na klávesnici mění natočení.
          </p>
          <svg
            viewBox="0 0 900 540"
            role="img"
            aria-label={`${mode === "respondents" ? "Respondentská" : "Objektová"} 3D sociomapa: ${name}`}
            tabIndex={0}
            className="w-full touch-none rounded-md border border-border bg-surface-sunken"
            onKeyDown={(e) => {
              if (
                !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(
                  e.key,
                )
              )
                return;
              e.preventDefault();
              setCamera((c) => ({
                ...c,
                yaw:
                  c.yaw +
                  (e.key === "ArrowLeft"
                    ? -0.1
                    : e.key === "ArrowRight"
                      ? 0.1
                      : 0),
                pitch: Math.max(
                  0,
                  Math.min(
                    1.4,
                    c.pitch +
                      (e.key === "ArrowUp"
                        ? 0.1
                        : e.key === "ArrowDown"
                          ? -0.1
                          : 0),
                  ),
                ),
              }));
            }}
            onPointerDown={(e) => {
              drag.current = { x: e.clientX, y: e.clientY, moved: false };
              e.currentTarget.setPointerCapture(e.pointerId);
            }}
            onPointerMove={(e) => {
              const d = drag.current;
              if (!d) return;
              const dx = e.clientX - d.x,
                dy = e.clientY - d.y;
              drag.current = {
                x: e.clientX,
                y: e.clientY,
                moved: d.moved || Math.abs(dx) + Math.abs(dy) > 0,
              };
              setCamera((c) => ({
                ...c,
                yaw: c.yaw + dx * 0.008,
                pitch: Math.max(0, Math.min(1.4, c.pitch + dy * 0.006)),
              }));
            }}
            onPointerUp={(e) => {
              if (drag.current && !drag.current.moved) {
                const rect = e.currentTarget.getBoundingClientRect();
                const x = ((e.clientX - rect.left) / rect.width) * 900,
                  y = ((e.clientY - rect.top) / rect.height) * 540;
                const nearest = points
                  .map((p) => ({
                    p,
                    d: Math.hypot(show(p).x - x, show(p).y - y),
                  }))
                  .sort((a, b) => a.d - b.d)[0];
                if (nearest && nearest.d < 12) setSelected(nearest.p.id);
              }
              drag.current = null;
            }}
            onPointerCancel={() => {
              drag.current = null;
            }}
          >
            <title>{name} — interní mapa uloženého běhu</title>
            {triangles.map((tr, i) => (
              <polygon
                key={i}
                points={tr.points}
                fill={colour(tr.level)}
                stroke={colour(tr.level)}
                strokeWidth=".3"
              />
            ))}
            {[...points]
              .sort((a, b) => show(a).depth - show(b).depth)
              .map((p) => {
                const q = show(p);
                return (
                  <g
                    key={p.id}
                    onClick={() => setSelected(p.id)}
                    className="cursor-pointer"
                  >
                    <circle
                      cx={q.x}
                      cy={q.y}
                      r={p.id === selected ? 6 : mode === "objects" ? 4 : 2.5}
                      fill={
                        p.status === "UNDETERMINED"
                          ? "var(--surface)"
                          : "var(--ink)"
                      }
                      stroke="var(--surface-raised)"
                      strokeWidth="1.2"
                    />
                    <title>
                      {label(p.id)}
                      {p.status === "UNDETERMINED" ? " · neurčená poloha" : ""}
                    </title>
                    {(mode === "objects" || p.id === selected) && (
                      <text
                        x={q.x}
                        y={q.y - 10}
                        textAnchor="middle"
                        fill="var(--ink)"
                        stroke="var(--surface)"
                        strokeWidth="3"
                        paintOrder="stroke"
                        fontSize="12"
                      >
                        {label(p.id)}
                      </text>
                    )}
                  </g>
                );
              })}
            {mode === "respondents" &&
              w.anchors.map((p) => {
                const q = show(p);
                return (
                  <g key={p.id}>
                    <path
                      d={`M${q.x},${q.y - 5}l5,5l-5,5l-5,-5z`}
                      fill="var(--surface)"
                      stroke="var(--ink)"
                    />
                    <text
                      x={q.x}
                      y={q.y - 10}
                      textAnchor="middle"
                      fill="var(--ink)"
                      stroke="var(--surface)"
                      strokeWidth="3"
                      paintOrder="stroke"
                      fontSize="12"
                    >
                      {label(p.id)}
                    </text>
                  </g>
                );
              })}
          </svg>
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <span>
              {name} · rozsah této mapy: {number(terrain.normalizer_lo)} až{" "}
              {number(terrain.normalizer_hi)}
            </span>
            <span className="flex" aria-hidden="true">
              {[0, 1, 2, 3, 4, 5, 6].map((i) => (
                <span
                  key={i}
                  className="h-3 w-7"
                  style={{ background: colour(i / 6) }}
                />
              ))}
            </span>
          </div>
        </>
      ) : (
        <p
          role="status"
          className="rounded-sm border border-border p-4 text-sm"
        >
          {reasons[w.object_reason ?? ""] ??
            "Pro tento pohled není vypočtená krajina."}
        </p>
      )}
      {mode === "respondents" && (
        <p className="text-xs text-ink-muted">
          {w.people.length} respondentů ·{" "}
          {w.people.filter((p) => p.status === "UNDETERMINED").length} s
          neurčenou polohou (obvod mapy; žádné hodnocení nad 5). Krajina
          zahrnuje celý vzorek.
        </p>
      )}
      <label className="text-sm">
        {mode === "respondents" ? "Detail respondenta" : "Detail objektu"}
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="ml-2 max-w-full rounded-sm border border-border bg-surface p-2"
        >
          <option value="">Vyberte bod</option>
          {points.map((p) => (
            <option key={p.id} value={p.id}>
              {label(p.id)}
            </option>
          ))}
        </select>
      </label>
      {chosen && (
        <div className="overflow-auto rounded-sm border border-border p-3 text-sm">
          <p className="font-semibold">
            {label(chosen.id)}
            {chosen.status === "UNDETERMINED" ? " · neurčená poloha" : ""}
          </p>
          {mode === "respondents" ? (
            <table>
              <caption className="text-left text-xs text-ink-muted">
                Odpovědi uložené ve vstupním datasetu
              </caption>
              <tbody>
                {labels.map((o, i) => (
                  <tr key={o.id}>
                    <th className="pr-6 text-left font-normal">{o.label}</th>
                    <td>{number(chosen.ratings[i])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <table>
              <caption className="text-left text-xs text-ink-muted">
                Vztah a počet společných odpovědí
              </caption>
              <thead>
                <tr>
                  <th>Objekt</th>
                  <th>Vztah</th>
                  <th>N</th>
                </tr>
              </thead>
              <tbody>
                {labels.map((o, j) => {
                  const i = w.objects.findIndex((p) => p.id === chosen.id);
                  return i === j ? null : (
                    <tr key={o.id}>
                      <th className="pr-6 text-left font-normal">{o.label}</th>
                      <td className="pr-6">{number(w.relations[i]?.[j])}</td>
                      <td>{number(w.pair_n[i]?.[j])}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
      <details className="text-xs text-ink-muted">
        <summary>Metoda a původ mapy</summary>
        <p>
          Respondenti: barycentrum hodnocení nad 5. Objekty: párové korelace a
          relační rozmístění. Obě mapy používají původní pořadí objektů a
          nevážené odpovědi. P-hodnoty se neodhadují. Barvy a výška sdílejí
          metriku. Rozsah je relativní k této mapě.
        </p>
        <p className="break-all">
          {w.version} · vstup {w.input_fingerprint}
        </p>
      </details>
    </div>
  );
}
