"use client";

// The object map's 3D terrain (plan object-map-3d-redesign, V18, V19, V21): the stored
// envelope grid drawn as ten flat terraces on a framed plinth, risers shaded by the way they
// face, a light rim at each step, pins standing on the terraces, the selected object's drawn
// relations as arcs, and labels clear of each other and of the panels. Canvas surface plus
// accessible SVG object controls, all from one frozen map; mounted only while 3D is on.

import { useEffect, useId, useMemo, useRef } from "react";
import { t } from "@/i18n/t";
import { HEIGHT_SCALE, plinthSides, projectTerrain, terraceLayers, type TerrainCamera } from "@/lib/object-map-3d";
import { type Frame, type MapLink, type MapObject, type ObjectMapArtifact, type Rect, type ViewSize, TERRACE_BANDS, terraceLevel, terrainAt } from "@/lib/object-map-view";
import { type MarkState, LabelShadow, MapLabel, MapPin, PinButton, casing, layoutLabels, linkStyle, partialCurve } from "./ObjectMapMarks";

/** A pin's stem above the terrace it stands on: a quarter of the frame's half-width. */
const STALK = 0.24 / HEIGHT_SCALE;
/** Where the light comes from, in map directions (front left, as in the approved design). */
const LIGHT = { x: -0.776, y: -0.631 };

export function ObjectMapTerrain({ map, objects, camera, shown = camera, frame, view, rise = 1, pop = () => 1, labels: labelOpacity = 1, reveal = 1, links, marks, obstacles = [], ratingScale, onSelect, onHover = () => {} }: {
  map: ObjectMapArtifact; objects: MapObject[]; camera: TerrainCamera; shown?: TerrainCamera; frame: Frame; view: ViewSize;
  rise?: number; pop?: (index: number) => number; labels?: number; reveal?: number;
  links: MapLink[]; marks: MarkState; obstacles?: Rect[]; ratingScale?: [number, number];
  onSelect: (id: string) => void; onHover?: (id: string | null) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const shadow = `om3d${useId().replace(/:/g, "")}`;
  const layers = useMemo(() => terraceLayers(map), [map]);
  const pieces = layers.reduce((sum, l) => sum + l.pieces.length, 0);
  // The opening rise scales the drawn relief only; the stored grid is never touched.
  const lens: TerrainCamera = { ...shown, relief: shown.relief * Math.max(0.001, rise) };
  const project = (x: number, y: number, height: number) => projectTerrain({ x, y, height }, lens, frame, view);
  const pins = objects.map((o) => {
    const ground = terrainAt(map, o.x, o.y);
    const base = ground === null ? 0 : terraceLevel(ground);
    return { object: o, base: project(o.x, o.y, base), head: project(o.x, o.y, base + STALK), top: base + STALK };
  });
  const at = new Map(pins.map((p) => [p.object.id, p]));
  const marked = { ...marks, shadow };
  const placed = layoutLabels(objects, new Map(pins.map((p) => [p.object.id, p.head])), marked, view, obstacles, ratingScale);

  useEffect(() => {
    const node = canvas.current;
    if (!node) return;
    const context = node.getContext("2d");
    if (!context) return;
    const draw = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.round(view.width * ratio), height = Math.round(view.height * ratio);
      if (node.width !== width) node.width = width;
      if (node.height !== height) node.height = height;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, view.width, view.height);
      const style = getComputedStyle(node);
      const token = (name: string) => style.getPropertyValue(`--${name}`).trim();
      const colours = Array.from({ length: TERRACE_BANDS }, (_, k) => token(`viz-terrace-${k + 1}`));
      const p = (x: number, y: number, h: number) => projectTerrain({ x, y, height: h }, lens, frame, view);
      const polygon = (vertices: { sx: number; sy: number }[]) => {
        vertices.forEach((v, i) => (i ? context.lineTo(v.sx, v.sy) : context.moveTo(v.sx, v.sy)));
        context.closePath();
      };
      // The plinth: a slightly larger slab, its shadow on the stage, its walls, its edge.
      const slab = { ...frame, half: frame.half * 1.04 };
      const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([i, j]) => [slab.cx + i * slab.half, slab.cy + j * slab.half]);
      context.save();
      context.shadowColor = "rgba(0,0,0,0.55)"; context.shadowBlur = 36; context.shadowOffsetY = 18;
      context.beginPath(); polygon(corners.map(([x, y]) => p(x, y, 0))); context.fillStyle = token("viz-stage-raised"); context.fill();
      context.restore();
      context.fillStyle = token("viz-stage-raised");
      for (const side of plinthSides(slab)) { context.beginPath(); polygon(side.map((v) => p(v.x, v.y, v.height))); context.fill(); }
      context.beginPath(); polygon(corners.map(([x, y]) => p(x, y, 0)));
      context.strokeStyle = "rgba(255,255,255,0.16)"; context.lineWidth = 1; context.stroke();
      // The "bez dat" ground: where no stored sample is, nothing is drawn over it.
      const ground = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([i, j]) => p(frame.cx + i * frame.half, frame.cy + j * frame.half, 0));
      context.beginPath(); polygon(ground); context.fillStyle = token("viz-ground"); context.fill();
      // Terraces bottom to top: each one's risers (far first, only those facing the viewer),
      // then its flat top in one fill, then the light rim along its step.
      const sin = Math.sin(lens.yaw), cos = Math.cos(lens.yaw);
      for (const layer of layers) {
        const walls = layer.edges
          .filter((e) => e.nx * sin + e.ny * cos < 0)
          .map((e) => ({ e, quad: [p(e.a.x, e.a.y, layer.base), p(e.b.x, e.b.y, layer.base), p(e.b.x, e.b.y, layer.top), p(e.a.x, e.a.y, layer.top)] }))
          .sort((a, b) => b.quad[0].depth + b.quad[1].depth - a.quad[0].depth - a.quad[1].depth);
        for (const { e, quad } of walls) {
          context.beginPath(); polygon(quad);
          context.fillStyle = colours[layer.band]; context.fill();
          context.globalAlpha = 0.5 - 0.4 * Math.max(0, e.nx * LIGHT.x + e.ny * LIGHT.y);
          context.fillStyle = "black"; context.fill();
          context.globalAlpha = 1;
        }
        context.beginPath();
        for (const piece of layer.pieces) polygon(piece.map((v) => p(v.x, v.y, layer.top)));
        context.fillStyle = colours[layer.band];
        context.fill();
        // The light rim marks a step between terraces; the lowest terrace's outer edge is
        // where the stored grid ends, drawn without one.
        if (layer.band === 0) continue;
        context.beginPath();
        for (const e of layer.edges) { const a = p(e.a.x, e.a.y, layer.top), b = p(e.b.x, e.b.y, layer.top); context.moveTo(a.sx, a.sy); context.lineTo(b.sx, b.sy); }
        context.strokeStyle = "rgba(255,255,255,0.32)"; context.lineWidth = 1; context.stroke();
      }
    };
    draw();
    const observer = new MutationObserver(draw);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme", "style"], subtree: true });
    const scheme = window.matchMedia?.("(prefers-color-scheme: dark)");
    scheme?.addEventListener("change", draw);
    return () => { observer.disconnect(); scheme?.removeEventListener("change", draw); };
  }, [layers, lens.yaw, lens.elevation, lens.zoom, lens.relief, frame, view]); // eslint-disable-line react-hooks/exhaustive-deps

  const arc = (link: MapLink) => {
    const a = at.get(link.a), b = at.get(link.b);
    if (!a || !b) return null;
    const lift = Math.max(a.top, b.top) + (0.15 + 0.3 * link.strength) / HEIGHT_SCALE;
    const c = project((a.object.x + b.object.x) / 2, (a.object.y + b.object.y) / 2, lift);
    return partialCurve(a.head, c, b.head, reveal);
  };

  return (
    <div className="absolute inset-0" data-testid="object-map-3d" data-camera={JSON.stringify(camera)} data-triangles={pieces}>
      <canvas ref={canvas} className="absolute inset-0 h-full w-full" aria-hidden="true" />
      <svg className="absolute inset-0 h-full w-full" viewBox={`0 0 ${view.width} ${view.height}`} role="group" aria-label={t("research.exec.objectMap.terrainLabel")}>
        <LabelShadow id={shadow} />
        <g aria-hidden="true">
          {links.map((link) => { const d = arc(link); return d ? <path key={link.a + link.b} d={d} fill="none" {...casing(linkStyle(link, marks.partner).strokeWidth)} /> : null; })}
        </g>
        <g data-testid="object-map-3d-links">
          {links.map((link) => { const d = arc(link); return d ? <path key={`${link.a}|${link.b}`} data-pair={`${link.a}|${link.b}`} d={d} fill="none" strokeLinecap="round" {...linkStyle(link, marks.partner)} /> : null; })}
        </g>
        {pins.map(({ object: o, base, head }, k) => {
          const grow = pop(k);
          return (
            <PinButton key={o.id} o={o} marks={marked} onSelect={onSelect} onHover={onHover}>
              {o.id === marks.selected ? <line x1={base.sx} y1={base.sy} x2={head.sx} y2={head.sy} stroke="var(--viz-map-select)" strokeOpacity={0.16} strokeWidth={16} strokeLinecap="round" /> : null}
              <line x1={base.sx} y1={base.sy} x2={head.sx} y2={head.sy} stroke="var(--viz-stage-ink)" strokeOpacity={0.75 * grow} strokeWidth={1.4} />
              <MapPin o={o} x={head.sx} y={head.sy} marks={marked} pop={grow} ring={{ x: base.sx, y: base.sy, flat: Math.max(0.2, Math.sin(lens.elevation)) }} />
              <g opacity={labelOpacity}><MapLabel o={o} {...placed.get(o.id)!} marks={marked} /></g>
            </PinButton>
          );
        })}
      </svg>
    </div>
  );
}
