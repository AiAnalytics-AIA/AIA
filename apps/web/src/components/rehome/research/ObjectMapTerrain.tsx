"use client";

// The object map's 3D terrain (plan object-map-3d-redesign): the stored envelope grid drawn as
// ten terraces on a graphite stage, pins standing on it, the selected object's drawn relations
// as arcs and labels that keep clear of each other and of the panels. Canvas surface plus
// accessible SVG object controls, all from one frozen map; mounted only while 3D is on.

import { useEffect, useMemo, useRef } from "react";
import { t } from "@/i18n/t";
import { easeOut, faceLight, plinthSides, projectTerrain, terrainMesh, type TerrainCamera } from "@/lib/object-map-3d";
import { type MapLink, type MapObject, type ObjectMapArtifact, type Rect, type ViewSize, TERRACE_BANDS, terraceLevel, terrainAt, viewSpan } from "@/lib/object-map-view";
import { type MarkState, MapLabel, MapPin, PinButton, casing, layoutLabels, linkStyle } from "./ObjectMapMarks";

/** How tall a pin's stem stands above the terrain, in display units of the 0-1 height. */
const STALK = 0.16;

export function ObjectMapTerrain({ map, objects, camera, view, rise = 1, links, marks, obstacles = [], ratingScale, onSelect, onHover = () => {} }: {
  map: ObjectMapArtifact; objects: MapObject[]; camera: TerrainCamera; view: ViewSize; rise?: number;
  links: MapLink[]; marks: MarkState; obstacles?: Rect[]; ratingScale?: [number, number];
  onSelect: (id: string) => void; onHover?: (id: string | null) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const faces = useMemo(() => terrainMesh(map), [map]);
  const span = viewSpan(map);
  // The opening rise scales the drawn relief only; the stored grid is never touched.
  const shown: TerrainCamera = { ...camera, relief: camera.relief * Math.max(0.001, easeOut(rise)) };
  const pins = objects.map((o) => {
    const ground = terrainAt(map, o.x, o.y);
    const base = ground === null ? 0 : terraceLevel(ground);
    return {
      object: o,
      base: projectTerrain({ x: o.x, y: o.y, height: base }, shown, span, view),
      head: projectTerrain({ x: o.x, y: o.y, height: base + STALK }, shown, span, view),
      top: base + STALK,
    };
  });
  const at = new Map(pins.map((p) => [p.object.id, p]));
  const labels = layoutLabels(objects, new Map(pins.map((p) => [p.object.id, p.head])), marks, view, obstacles, ratingScale);

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
      const polygon = (vertices: { sx: number; sy: number }[]) => {
        context.beginPath();
        vertices.forEach((v, i) => i ? context.lineTo(v.sx, v.sy) : context.moveTo(v.sx, v.sy));
        context.closePath();
      };
      // The plinth's walls, then the "bez dat" ground: where no stored sample is, nothing is drawn over it.
      context.fillStyle = token("viz-stage-raised");
      for (const side of plinthSides(span)) { polygon(side.map((v) => projectTerrain(v, shown, span, view))); context.fill(); }
      const ground = [[-span, -span], [span, -span], [span, span], [-span, span]].map(([x, y]) => projectTerrain({ x, y, height: 0 }, shown, span, view));
      polygon(ground);
      context.fillStyle = token("viz-ground");
      context.fill();
      const projected = faces.map((face) => {
        const vertices = face.vertices.map((v) => projectTerrain(v, shown, span, view));
        return { face, vertices, depth: vertices.reduce((sum, v) => sum + v.depth, 0) / 3 };
      }).sort((a, b) => b.depth - a.depth);
      for (const { face, vertices } of projected) {
        polygon(vertices);
        context.fillStyle = colours[face.band];
        context.strokeStyle = colours[face.band];
        context.lineWidth = 0.5;
        context.fill(); context.stroke();
        // Light reveals shape, while the unshaded legend retains the bands.
        context.globalAlpha = 1 - faceLight(face, shown, span);
        context.fillStyle = "black";
        context.fill();
        // The light edge of a terrace step.
        if (face.riser) { context.globalAlpha = 0.22; context.fillStyle = "white"; context.fill(); }
        context.globalAlpha = 1;
      }
    };
    draw();
    const observer = new MutationObserver(draw);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme", "style"], subtree: true });
    const scheme = window.matchMedia?.("(prefers-color-scheme: dark)");
    scheme?.addEventListener("change", draw);
    return () => { observer.disconnect(); scheme?.removeEventListener("change", draw); };
  }, [faces, shown.yaw, shown.elevation, shown.zoom, shown.relief, span, view]); // eslint-disable-line react-hooks/exhaustive-deps

  const arc = (link: MapLink) => {
    const a = at.get(link.a), b = at.get(link.b);
    if (!a || !b) return null;
    const lift = Math.max(a.top, b.top) + 0.12 + 0.22 * link.strength;
    const c = projectTerrain({ x: (a.object.x + b.object.x) / 2, y: (a.object.y + b.object.y) / 2, height: lift }, shown, span, view);
    return `M${a.head.sx.toFixed(1)},${a.head.sy.toFixed(1)} Q${c.sx.toFixed(1)},${c.sy.toFixed(1)} ${b.head.sx.toFixed(1)},${b.head.sy.toFixed(1)}`;
  };

  return (
    <div className="absolute inset-0" data-testid="object-map-3d" data-camera={JSON.stringify(camera)} data-triangles={faces.length}>
      <canvas ref={canvas} className="absolute inset-0 h-full w-full" aria-hidden="true" />
      <svg className="absolute inset-0 h-full w-full" viewBox={`0 0 ${view.width} ${view.height}`} role="group" aria-label={t("research.exec.objectMap.terrainLabel")}>
        <g aria-hidden="true">
          {links.map((link) => { const d = arc(link); return d ? <path key={link.a + link.b} d={d} fill="none" {...casing(linkStyle(link, marks.partner).strokeWidth)} /> : null; })}
        </g>
        <g data-testid="object-map-3d-links">
          {links.map((link) => { const d = arc(link); return d ? <path key={`${link.a}|${link.b}`} data-pair={`${link.a}|${link.b}`} d={d} fill="none" strokeLinecap="round" {...linkStyle(link, marks.partner)} /> : null; })}
        </g>
        {pins.map(({ object: o, base, head }) => (
          <PinButton key={o.id} o={o} marks={marks} onSelect={onSelect} onHover={onHover}>
            <ellipse cx={base.sx} cy={base.sy} rx={7} ry={3.5} fill="none" stroke="var(--viz-stage-ink)" strokeOpacity={0.8} />
            <line x1={base.sx} y1={base.sy} x2={head.sx} y2={head.sy} stroke="var(--viz-stage-ink)" strokeOpacity={0.75} strokeWidth={1.5} />
            <MapPin o={o} x={head.sx} y={head.sy} marks={marks} />
            <g opacity={rise >= 0.9 ? 1 : 0}><MapLabel o={o} {...labels.get(o.id)!} marks={marks} /></g>
          </PinButton>
        ))}
      </svg>
    </div>
  );
}
