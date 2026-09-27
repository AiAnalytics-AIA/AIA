"use client";

// Správa projektů · Koš, rebuilt (renderTrash26 / pmRestore26).

import Link from "next/link";
import { useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { unit } from "@/unit/client";
import { type ProjectRow, parseProjectRows } from "@/unit/projects";
import { Button, Toast } from "../ui";
import { Icon } from "../icons";
import { AppShell } from "../../aia/AppShell";
import { appRoutes } from "@/lib/app-routes";

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function TrashScreen() {
  const [rows, setRows] = useState<ProjectRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [version, setVersion] = useState(0);
  useEffect(() => {
    let live = true;
    unit("projectsTrash")
      .then(parseProjectRows)
      .then(
        (r) => {
          if (!live) return;
          setRows(r);
          setError(null);
        },
        (e: unknown) => live && setError(message(e)),
      );
    return () => {
      live = false;
    };
  }, [version]);

  const restore = async (row: ProjectRow) => {
    try {
      await unit("projectAction", { body: { project_id: row.project_id, action: "restore-trash" }, timeoutMs: 30_000 });
      setToast(t("projects.restoreDone"));
      setVersion((v) => v + 1);
    } catch (e) {
      setToast(message(e));
    }
  };

  return (
    <AppShell
      crumbs={[
        { label: t("aia.navSettings"), href: appRoutes.settings() },
        { label: t("aia.settings.classicProjects"), href: appRoutes.classicProjects() },
        { label: t("projects.trash") },
      ]}
      title={t("projects.trashTitle")}
      sub={t("projects.trashSub")}
      action={
        <Link
          href={appRoutes.classicProjects()}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-sm border border-border-strong bg-surface-raised px-3 text-sm font-medium text-ink no-underline hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          <Icon name="back" />
          {t("projects.trashBack")}
        </Link>
      }
    >
      {error ? (
        <section role="alert" className="rounded-md border border-status-fault/40 bg-status-fault-wash p-5">
          <h2 className="font-semibold text-status-fault">{t("projects.trashLoadFailed")}</h2>
          <p className="mt-1 text-sm text-ink">{error}</p>
        </section>
      ) : !rows ? (
        <p className="py-10 text-sm text-ink-muted">{t("projects.trashLoading")}</p>
      ) : (
        <div className="flex flex-col gap-4">
          <span className="self-start rounded-sm border border-border bg-surface-sunken px-2 py-0.5 font-mono text-xs tabular-nums text-ink-muted">
            {tv("projects.trashCount", { n: rows.length })}
          </span>
          {rows.length ? (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
              {rows.map((x) => (
                <article key={x.project_id} className="flex flex-col gap-2 rounded-md border border-border bg-surface-raised p-4">
                  <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">
                    {t("projects.kindTrash")} · {x.project_type === "simulation" ? "SIMULACE" : "VÝZKUM"}
                  </div>
                  <h2 className="text-base font-semibold">{x.title}</h2>
                  <p className="text-xs text-ink-muted">
                    {tv("projects.trashDeleted", { at: String(x.deleted_at || "—").replace("T", " "), rev: x.revision ?? 0 })}
                  </p>
                  <div>
                    <Button small icon="restore" onClick={() => void restore(x)}>{t("projects.restore")}</Button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="rounded-md border border-dashed border-border-strong p-8 text-center text-sm text-ink-muted">{t("projects.trashEmpty")}</p>
          )}
        </div>
      )}
      <Toast message={toast} />
    </AppShell>
  );
}
