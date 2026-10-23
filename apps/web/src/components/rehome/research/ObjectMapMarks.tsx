"use client";

// The object map's pins, labels and links, shared by the top view and the 3D terrain
// (plan object-map-3d-redesign, V16, V17, V21). Screen-space annotation only: every position
// comes from the stored layout through the view's projection, every number printed is the
// stored one, and a label that moves to avoid another never moves its object.

import type { KeyboardEvent, ReactNode } from "react";
import { t, tv } from "@/i18n/t";
import {
  type LabelBox,
  type MapLink,
  type MapObject,
  type Rect,
  type ViewSize,
  TERRACE_BANDS,
  labelWidth,
  originalRating,
  placeLabels,
} from "@/lib/object-map-view";
import { num } from "@/lib/sociomapping-view";

export const TERRACE = (band: number) => `var(--viz-terrace-${band + 1})`;
const SIGN = { positive: "var(--viz-link-positive)", negative: "var(--viz-link-negative)" } as const;

export type MarkState = {
  selected: string | null;
  partner: string | null;
  hovered: string | null;
  dimmed: Set<string>;
  labelsOnly: boolean;
  /** The id of the SVG drop-shadow filter the labels use (unique per drawing). */
  shadow?: string;
};

const PILL = { font: 12, meta: 11, padX: 9, padY: 4, line: 15, metaLine: 14 };
const PLAIN = { font: 11, padX: 2, padY: 1, line: 14 };
const FACE = '"IBM Plex Sans", "Segoe UI", system-ui, sans-serif';

/** A number as the map prints it: Czech decimal comma and a true minus sign. */
export const fmt = (value: number | null | undefined, digits: number) => (value === null || value === undefined || !Number.isFinite(value) ? "—" : num(value, digits).replace("-", "−"));

let ruler: CanvasRenderingContext2D | null | undefined;

/** A label's width: its lines measured in the face they are drawn in, or estimated where the
 * page has no canvas to measure with (tests). */
function width(lines: string[], fonts: string[], padding: number, fallback: number): number {
  if (ruler === undefined) {
    try { ruler = typeof document === "undefined" ? null : document.createElement("canvas").getContext("2d"); } catch { ruler = null; }
  }
  if (!ruler || typeof ruler.measureText !== "function") return fallback;
  const r = ruler;
  return Math.ceil(Math.max(...lines.map((line, k) => { r.font = fonts[Math.min(k, fonts.length - 1)]; return r.measureText(line).width; }))) + 2 * padding + 2;
}

/** The label's lines: the name (marked as context for a SECONDARY object) and, when the object
 * is active and labels are not names-only, its stored height, original rating and display band. */
function labelLines(o: MapObject, active: boolean, labelsOnly: boolean, scale?: [number, number]): string[] {
  const name = o.primary ? o.label : tv("research.exec.objectMap.contextSuffix", { label: o.label });
  if (labelsOnly || !active || o.height === null || o.band === null) return [name];
  const band = o.band + 1;
  const rating = originalRating(o.height, scale);
  const meta = rating === null
    ? tv("research.exec.objectMap.labelMetaNoScale", { height: fmt(o.height, 2), band, bands: TERRACE_BANDS })
    : tv("research.exec.objectMap.labelMeta", { height: fmt(o.height, 2), rating: `${fmt(rating, 1)}/${num(scale![1], 0)}`, band, bands: TERRACE_BANDS });
  return [name, meta];
}

/** Lay every object's label out around its anchor; the selected and compared objects first. */
export function layoutLabels(
  objects: MapObject[], anchors: Map<string, { sx: number; sy: number }>, marks: MarkState,
  view: ViewSize, obstacles: Rect[], scale?: [number, number],
): Map<string, { rect: Rect; lines: string[]; anchor: { sx: number; sy: number } }> {
  const rank = (id: string) => (id === marks.selected ? 0 : id === marks.partner ? 1 : id === marks.hovered ? 2 : 3);
  const order = [...objects].sort((a, b) => rank(a.id) - rank(b.id) || anchors.get(a.id)!.sy - anchors.get(b.id)!.sy || a.id.localeCompare(b.id));
  const lines = new Map(order.map((o) => [o.id, labelLines(o, rank(o.id) < 3, marks.labelsOnly, scale)]));
  const boxes: LabelBox[] = order.map((o) => {
    const l = lines.get(o.id)!;
    const a = anchors.get(o.id)!;
    if (marks.labelsOnly) {
      const w = width(l, [`${o.id === marks.selected ? 700 : 500} ${PLAIN.font}px ${FACE}`], PLAIN.padX, labelWidth(l, PLAIN.font, PLAIN.padX));
      return { id: o.id, ax: a.sx, ay: a.sy, w, h: PLAIN.line + 2 * PLAIN.padY };
    }
    const w = width(l, [`600 ${PILL.font}px ${FACE}`, `400 ${PILL.meta}px ${FACE}`], PILL.padX, labelWidth(l, PILL.font, PILL.padX));
    return { id: o.id, ax: a.sx, ay: a.sy, w, h: PILL.line + (l.length - 1) * PILL.metaLine + 2 * PILL.padY };
  });
  const placed = placeLabels(boxes, obstacles, view);
  return new Map(order.map((o) => [o.id, { rect: placed.get(o.id)!, lines: lines.get(o.id)!, anchor: anchors.get(o.id)! }]));
}

/** The labels' soft drop shadow (the approved design's 0 6px 18px). */
export function LabelShadow({ id }: { id: string }) {
  return (
    <defs>
      <filter id={id} x="-30%" y="-40%" width="160%" height="220%">
        <feDropShadow dx="0" dy="6" stdDeviation="9" floodColor="#000" floodOpacity="0.35" />
      </filter>
    </defs>
  );
}

/** One object's label: a stage pill (yellow when selected, blue when compared, light when
 * hovered), or names-only text on a stage halo. */
export function MapLabel({ o, rect, lines, anchor, marks }: { o: MapObject; rect: Rect; lines: string[]; anchor?: { sx: number; sy: number }; marks: MarkState }) {
  const selected = o.id === marks.selected;
  const partner = o.id === marks.partner;
  const hovered = o.id === marks.hovered;
  const leader = anchor ? <Leader anchor={anchor} rect={rect} strong={selected || partner} /> : null;
  if (marks.labelsOnly) {
    return (
      <>{leader}<text x={rect.x + PLAIN.padX} y={rect.y + PLAIN.padY + PLAIN.font} fontSize={PLAIN.font} fontWeight={selected ? 700 : 500}
        fill={selected ? "var(--viz-map-select)" : partner ? "var(--viz-map-partner)" : "var(--viz-stage-ink)"}
        paintOrder="stroke" stroke="var(--viz-stage)" strokeWidth={3.5} strokeLinejoin="round">{lines[0]}</text></>
    );
  }
  const lit = selected || partner || hovered;
  const fill = selected ? "var(--viz-map-select)" : partner ? "var(--viz-map-partner)" : hovered ? "var(--viz-stage-ink)" : "var(--viz-stage)";
  const ink = lit ? "var(--viz-stage)" : "var(--viz-stage-ink)";
  return (
    <g>
      {leader}
      <rect x={rect.x} y={rect.y} width={rect.w} height={rect.h} rx={6} fill={fill} fillOpacity={lit ? 1 : 0.78}
        stroke="white" strokeOpacity={lit ? 0 : 0.14} filter={marks.shadow ? `url(#${marks.shadow})` : undefined} />
      <text x={rect.x + PILL.padX} y={rect.y + PILL.padY + PILL.font} fontSize={PILL.font} fontWeight={600} fill={ink}>{lines[0]}</text>
      {lines[1] ? <text x={rect.x + PILL.padX} y={rect.y + PILL.padY + PILL.line + PILL.meta} fontSize={PILL.meta} fill={ink} style={{ fontVariantNumeric: "tabular-nums" }}>{lines[1]}</text> : null}
    </g>
  );
}

/** The thin line from a pin to its label when collisions moved the label away from it, so
 * every label still visibly belongs to its object. Nothing when the label sits at the pin. */
function Leader({ anchor, rect, strong }: { anchor: { sx: number; sy: number }; rect: Rect; strong: boolean }) {
  const x = Math.max(rect.x, Math.min(rect.x + rect.w, anchor.sx));
  const y = Math.max(rect.y, Math.min(rect.y + rect.h, anchor.sy));
  if (Math.hypot(x - anchor.sx, y - anchor.sy) <= 12) return null;
  return <line data-leader x1={anchor.sx} y1={anchor.sy} x2={x} y2={y} stroke="var(--viz-stage-ink)" strokeOpacity={strong ? 0.85 : 0.5} strokeWidth={1.2} />;
}

/** One object's pin head: a lit sphere for a PRIMARY object, a diamond for a SECONDARY one;
 * yellow when selected, blue when compared. `pop` scales it in during the opening; `ring` is
 * the white ring where the pin meets the terrain (`flat` squashes it with the camera). */
export function MapPin({ o, x, y, marks, pop = 1, ring }: { o: MapObject; x: number; y: number; marks: MarkState; pop?: number; ring?: { x: number; y: number; flat: number } }) {
  const selected = o.id === marks.selected;
  const partner = o.id === marks.partner;
  const active = selected || o.id === marks.hovered;
  const size = (active ? 8.5 : 6) * pop;
  const fill = selected ? "var(--viz-map-select)" : partner ? "var(--viz-map-partner)" : o.primary ? "var(--viz-stage-ink)" : "var(--viz-map-context)";
  return (
    <>
      {ring ? <ellipse cx={ring.x} cy={ring.y} rx={(active ? 12 : 8) * pop} ry={(active ? 12 : 8) * pop * ring.flat} fill="none" stroke="white" strokeOpacity={0.85} strokeWidth={2.2} /> : null}
      {o.primary
        ? <circle cx={x} cy={y} r={size} fill={fill} stroke="var(--viz-stage)" strokeOpacity={0.6} strokeWidth={1} />
        : <rect x={x - size} y={y - size} width={2 * size} height={2 * size} transform={`rotate(45 ${x} ${y})`} fill={fill} stroke="var(--viz-stage)" strokeOpacity={0.6} strokeWidth={1} />}
      {o.primary && pop > 0 ? <circle cx={x - size * 0.3} cy={y - size * 0.35} r={size * 0.35} fill="white" fillOpacity={0.55} /> : null}
      <circle data-export="skip" className="opacity-0 group-focus-visible:opacity-100" cx={x} cy={y} r={size + 9} fill="none" stroke="var(--viz-stage-ink)" strokeWidth={2} strokeDasharray="3 3" />
    </>
  );
}

/** The button wrapping one object's pin and label: click, Enter or Space selects it. */
export function PinButton({ o, marks, onSelect, onHover, children }: {
  o: MapObject; marks: MarkState; onSelect: (id: string) => void; onHover: (id: string | null) => void; children: ReactNode;
}) {
  const onKeyDown = (e: KeyboardEvent<SVGGElement>) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(o.id); }
  };
  const dim = marks.dimmed.has(o.id) && o.id !== marks.hovered;
  return (
    <g role="button" tabIndex={0} aria-label={tv("research.exec.objectMap.selectObject", { label: o.label })} aria-pressed={o.id === marks.selected}
      onClick={() => onSelect(o.id)} onKeyDown={onKeyDown} onPointerEnter={() => onHover(o.id)} onPointerLeave={() => onHover(null)}
      className="group cursor-pointer outline-none" opacity={dim ? 0.45 : 1} data-testid={`object-map-point-${o.id}`}>
      <title>{o.label}</title>
      {children}
    </g>
  );
}

/** A drawn link's stroke: width and opacity from |r|, colour from its sign (dashed when
 * negative, so the sign survives greyscale); the one compared pair stands out. Every link
 * passed here is already one `mapLinks` draws. */
export function linkStyle(link: MapLink, partner: string | null) {
  const focus = partner !== null && (link.a === partner || link.b === partner);
  const fade = partner !== null && !focus ? 0.3 : 1;
  return {
    stroke: SIGN[link.sign],
    strokeWidth: (1.5 + 2.5 * link.strength) * (focus ? 1.6 : 1),
    strokeOpacity: (0.35 + 0.6 * link.strength) * fade,
    strokeDasharray: link.sign === "negative" ? "7 5" : undefined,
  };
}

export const casing = (width: number) => ({ stroke: "var(--viz-stage)", strokeWidth: width + 2, strokeOpacity: 0.45 });

/** The first `t` (0..1) of a quadratic curve from `a` through control `c` to `b`, as a path:
 * the arc draws itself in, as in the approved design. */
export function partialCurve(a: { sx: number; sy: number }, c: { sx: number; sy: number }, b: { sx: number; sy: number }, t: number): string {
  const k = Math.max(0, Math.min(1, t));
  const q = { sx: a.sx + k * (c.sx - a.sx), sy: a.sy + k * (c.sy - a.sy) };
  const r = { sx: c.sx + k * (b.sx - c.sx), sy: c.sy + k * (b.sy - c.sy) };
  const e = { sx: q.sx + k * (r.sx - q.sx), sy: q.sy + k * (r.sy - q.sy) };
  return `M${a.sx.toFixed(1)},${a.sy.toFixed(1)} Q${q.sx.toFixed(1)},${q.sy.toFixed(1)} ${e.sx.toFixed(1)},${e.sy.toFixed(1)}`;
}

export const legendLabel = (scale?: [number, number]) =>
  scale ? tv("research.exec.objectMap.legendOriginal", { low: num(scale[0], 0), high: num(scale[1], 0) }) : t("research.exec.objectMap.legendHeight");
