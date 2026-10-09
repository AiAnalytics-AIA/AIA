"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { t, tv } from "@/i18n/t";
import { faceLight, projectTerrain, terrainMesh, TERRAIN_VIEW, type TerrainCamera } from "@/lib/object-map-3d";
import { type MapObject, type ObjectMapArtifact, mapLinks, viewSpan } from "@/lib/object-map-view";
import { labelOffsets, num } from "@/lib/sociomapping-view";

/** Canvas surface plus accessible SVG object controls, all from one frozen map. */
export function ObjectMapTerrain({ map, objects, camera, selected, partner, showLinks, onSelect }: {
  map: ObjectMapArtifact; objects: MapObject[]; camera: TerrainCamera;
  selected: string | null; partner: string | null; showLinks: boolean;
  onSelect: (id: string) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [labelScale, setLabelScale] = useState(1);
  useEffect(() => {
    const node = canvas.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) setLabelScale(Math.max(1, Math.min(2.5, TERRAIN_VIEW.width / entry.contentRect.width)));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const faces = useMemo(() => terrainMesh(map), [map]);
  const span = viewSpan(map);
  const points = objects.map((o) => ({ object: o, ...projectTerrain({ ...o, height: o.height ?? 0 }, camera, span) }));
  const at = new Map(points.map((p) => [p.object.id, p]));
  const offsets = labelOffsets(points.map((p) => ({ id: p.object.id, sx: p.sx, sy: p.sy })), 40 * labelScale, 180 * labelScale);
  const links = showLinks ? mapLinks(map) : [];

  useEffect(() => {
    const node = canvas.current;
    if (!node) return;
    const context = node.getContext("2d");
    if (!context) return;
    const draw = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      if (node.width !== TERRAIN_VIEW.width * ratio) node.width = TERRAIN_VIEW.width * ratio;
      if (node.height !== TERRAIN_VIEW.height * ratio) node.height = TERRAIN_VIEW.height * ratio;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, TERRAIN_VIEW.width, TERRAIN_VIEW.height);
      const style = getComputedStyle(node);
      const colours = Array.from({ length: 7 }, (_, k) => style.getPropertyValue(`--viz-seq-${k + 1}`).trim());
      const polygon = (vertices: { sx: number; sy: number }[]) => {
        context.beginPath();
        vertices.forEach((v, i) => i ? context.lineTo(v.sx, v.sy) : context.moveTo(v.sx, v.sy));
        context.closePath();
      };
      const ground = [[-span, -span], [span, -span], [span, span], [-span, span]].map(([x, y]) => projectTerrain({ x, y, height: 0 }, camera, span));
      polygon(ground);
      context.fillStyle = style.getPropertyValue("--surface").trim();
      context.fill();
      context.strokeStyle = style.getPropertyValue("--border-strong").trim();
      context.lineWidth = 1;
      context.stroke();
      context.strokeStyle = style.getPropertyValue("--border").trim();
      for (let k = -3; k <= 3; k++) {
        const value = k * span / 4;
        for (const segment of [
          [{ x: value, y: -span, height: 0 }, { x: value, y: span, height: 0 }],
          [{ x: -span, y: value, height: 0 }, { x: span, y: value, height: 0 }],
        ]) {
          const [a, b] = segment.map((v) => projectTerrain(v, camera, span));
          context.beginPath(); context.moveTo(a.sx, a.sy); context.lineTo(b.sx, b.sy); context.stroke();
        }
      }
      const projected = faces.map((face) => {
        const vertices = face.vertices.map((v) => projectTerrain(v, camera, span));
        return { face, vertices, depth: vertices.reduce((sum, v) => sum + v.depth, 0) / 3 };
      }).sort((a, b) => b.depth - a.depth);
      for (const { face, vertices } of projected) {
        polygon(vertices);
        context.fillStyle = colours[face.band];
        context.strokeStyle = colours[face.band];
        context.lineWidth = 0.5;
        context.fill(); context.stroke();
        // Light reveals shape, while the unshaded legend retains the rating scale.
        context.globalAlpha = 1 - faceLight(face, camera, span);
        context.fillStyle = "black";
        context.fill();
        context.globalAlpha = 1;
      }
    };
    draw();
    const observer = new MutationObserver(draw);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme", "style"], subtree: true });
    const scheme = window.matchMedia?.("(prefers-color-scheme: dark)");
    scheme?.addEventListener("change", draw);
    return () => { observer.disconnect(); scheme?.removeEventListener("change", draw); };
  }, [faces, camera, span]);

  return (
    <div className="relative w-full" style={{ aspectRatio: `${TERRAIN_VIEW.width}/${TERRAIN_VIEW.height}` }} data-testid="object-map-3d" data-camera={JSON.stringify(camera)} data-triangles={faces.length}>
      <canvas ref={canvas} className="absolute inset-0 h-full w-full" aria-hidden="true" />
      <svg className="absolute inset-0 h-full w-full" viewBox={`0 0 ${TERRAIN_VIEW.width} ${TERRAIN_VIEW.height}`} role="group" aria-label={t("research.exec.objectMap.terrainLabel")}>
        <g data-testid="object-map-3d-links">
          {links.map((link) => {
            const a = at.get(link.a), b = at.get(link.b);
            if (!a || !b) return null;
            const focus = [selected, partner].includes(link.a) && [selected, partner].includes(link.b);
            return <line key={`${link.a}|${link.b}`} x1={a.sx} y1={a.sy} x2={b.sx} y2={b.sy}
              stroke={`var(--viz-div-${link.sign === "positive" ? 7 : 1})`} strokeWidth={focus ? 4 : 1.5}
              strokeOpacity={focus ? 1 : 0.25 + 0.65 * link.strength} strokeDasharray={link.sign === "negative" ? "7 5" : undefined} />;
          })}
        </g>
        {points.map(({ object: o, sx, sy }) => {
          const base = projectTerrain({ ...o, height: 0 }, camera, span);
          const on = o.id === selected;
          const showLabel = labelScale <= 1.8 && objects.length <= 12 || on || o.id === partner;
          const dy = offsets.get(o.id) ?? -22;
          const tx = Math.max(12, Math.min(TERRAIN_VIEW.width - 180 * labelScale, sx + 16 * labelScale));
          const ty = Math.max(30 * labelScale, Math.min(TERRAIN_VIEW.height - 55 * labelScale, sy + dy));
          const limit = labelScale > 1.8 ? 14 : 30;
          const label = o.label.length > limit ? `${o.label.slice(0, limit - 1)}…` : o.label;
          return (
            <g key={o.id} role="button" tabIndex={0} aria-label={tv("research.exec.objectMap.selectObject", { label: o.label })} aria-pressed={on}
              onClick={() => onSelect(o.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(o.id); } }}
              className="cursor-pointer" data-testid={`object-map-point-${o.id}`}>
              <line x1={base.sx} y1={base.sy} x2={sx} y2={sy} stroke="var(--ink-muted)" strokeDasharray="3 4" opacity={on ? 0.8 : 0.35} />
              <circle cx={sx} cy={sy} r={on ? 9 : 6} fill={o.band === null ? "var(--surface)" : `var(--viz-seq-${o.band + 1})`} stroke="var(--ink)" strokeWidth={on ? 3 : 1.5} />
              <title>{o.label}</title>
              {showLabel ? <>
              <line x1={sx} y1={sy} x2={tx - 2} y2={ty} stroke="var(--ink-muted)" />
              <text x={tx} y={ty} fontSize={15 * labelScale} fontWeight={on ? 700 : 500} fill="var(--ink)" paintOrder="stroke" stroke="var(--surface-raised)" strokeWidth={5} strokeLinejoin="round">{label}</text>
              <text x={tx} y={ty + 18 * labelScale} fontSize={13 * labelScale} fill="var(--ink-muted)" paintOrder="stroke" stroke="var(--surface-raised)" strokeWidth={4}>{num(o.height, 2)}</text>
              </> : null}
            </g>
          );
        })}

      </svg>
    </div>
  );
}
