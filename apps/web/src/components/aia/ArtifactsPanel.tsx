"use client";

import { useMemo, useState } from "react";
import { fixtureArtifacts, type ArtifactType, type FixtureArtifact as Artifact } from "@/fixtures/artifacts";
import { lsGet, lsSet } from "@/lib/storage";
import { Panel } from "@/components/ui";
import { t } from "@/i18n/t";

function key(projectId: string) {
  return `aia.artifacts.${projectId}`;
}

function typeLabel(tt: ArtifactType) {
  return t(`artifacts.types.${tt}`);
}

export function ArtifactsPanel({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<ArtifactType>("input_docx");
  const [filename, setFilename] = useState("");
  const [versionLabel, setVersionLabel] = useState("v1");

  const artifacts = useMemo(() => {
    const seeded = fixtureArtifacts.filter((a) => a.projectId === projectId);
    const stored = lsGet<Artifact[]>(key(projectId), []);
    const merged = [...seeded, ...stored];
    merged.sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
    return merged;
  }, [projectId]);

  function addArtifact() {
    if (!filename.trim()) return;
    const stored = lsGet<Artifact[]>(key(projectId), []);
    const a: Artifact = {
      id: `art-${Math.random().toString(16).slice(2)}`,
      projectId,
      type,
      filename: filename.trim(),
      versionLabel: versionLabel.trim() || "v1",
      createdAt: new Date().toISOString(),
      note: t("artifacts.note"),
    };
    lsSet(key(projectId), [a, ...stored]);
    setFilename("");
    setVersionLabel("v1");
    setOpen(false);
    // quick refresh: simplest for demo
    window.location.reload();
  }

  return (
    <Panel title={t("artifacts.title")}>
      <div className="flex items-center justify-between">
        <div className="text-xs text-ink-muted">{t("artifacts.helper")}</div>
        <button
          className="rounded-md border border-border px-2.5 py-1.5 text-xs font-semibold hover:bg-surface-sunken"
          onClick={() => setOpen(true)}
        >
          {t("artifacts.upload")}
        </button>
      </div>

      <div className="mt-3 space-y-2">
        {artifacts.length === 0 ? (
          <div className="text-xs text-ink-muted">{t("artifacts.noArtifacts")}</div>
        ) : (
          artifacts.map((a) => (
            <div key={a.id} className="rounded-md border border-border p-2">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-xs font-semibold text-ink">{a.filename}</div>
                  <div className="mt-0.5 text-[11px] text-ink-muted">{new Date(a.createdAt).toLocaleString()}</div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className="inline-flex items-center rounded-sm border border-border px-1.5 text-xs text-ink-muted">{typeLabel(a.type)}</span>
                  <span className="inline-flex items-center rounded-sm border border-border px-1.5 text-xs text-ink-muted">{a.versionLabel}</span>
                </div>
              </div>
              {a.note ? <div className="mt-1 text-[11px] text-ink-muted">{a.note}</div> : null}
            </div>
          ))
        )}
      </div>

      {open ? (
        <div className="mt-4 rounded-md border border-border bg-surface-sunken p-3">
          <div className="text-xs font-semibold text-ink">{t("artifacts.mockUpload")}</div>
          <div className="mt-2 grid gap-2">
            <label className="text-xs text-ink-muted">
              {t("artifacts.type")}
              <select
                className="mt-1 h-9 w-full rounded-md border border-border bg-surface-raised px-3 text-sm"
                value={type}
                onChange={(e) => setType(e.target.value as ArtifactType)}
              >
                <option value="input_docx">{t("artifacts.types.input_docx")}</option>
                <option value="input_xlsx">{t("artifacts.types.input_xlsx")}</option>
                <option value="dataset">{t("artifacts.types.dataset")}</option>
                <option value="import_pack">{t("artifacts.types.import_pack")}</option>
                <option value="sociomap">{t("artifacts.types.sociomap")}</option>
                <option value="final_docx">{t("artifacts.types.final_docx")}</option>
                <option value="final_pdf">{t("artifacts.types.final_pdf")}</option>
              </select>
            </label>

            <label className="text-xs text-ink-muted">
              {t("artifacts.filename")}
              <input
                className="mt-1 h-9 w-full rounded-md border border-border bg-surface-raised px-3 text-sm"
                placeholder="např. vstupy.xlsx"
                value={filename}
                onChange={(e) => setFilename(e.target.value)}
              />
            </label>

            <label className="text-xs text-ink-muted">
              {t("artifacts.versionLabel")}
              <input
                className="mt-1 h-9 w-full rounded-md border border-border bg-surface-raised px-3 text-sm"
                placeholder="v1"
                value={versionLabel}
                onChange={(e) => setVersionLabel(e.target.value)}
              />
            </label>
          </div>

          <div className="mt-3 flex gap-2">
            <button
              className="rounded-md bg-signal px-3 py-2 text-xs font-semibold text-on-signal hover:brightness-110"
              onClick={addArtifact}
            >
              {t("artifacts.save")}
            </button>
            <button
              className="rounded-md border border-border px-3 py-2 text-xs font-semibold hover:bg-surface-raised"
              onClick={() => setOpen(false)}
            >
              {t("artifacts.cancel")}
            </button>
          </div>
          <div className="mt-2 text-[11px] text-ink-muted">
            {t("artifacts.localOnly")}
          </div>
        </div>
      ) : null}
    </Panel>
  );
}
