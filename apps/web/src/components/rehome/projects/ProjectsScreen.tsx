"use client";

// Správa projektů, rebuilt (ADR 0014, area A2). The classic screen's controls,
// in its order: new research / simulation, the portfolio dashboard and the
// trash; the view tabs with the dashboard's counts; search and five filters;
// saved views; the cards. Its data comes from the unit through src/unit/, its
// rules from src/unit/projects.ts. Client-side because every control is.

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { classicHref } from "@/lib/interface-handoff";
import { t, tv } from "@/i18n/t";
import { unit } from "@/unit/client";
import {
  DEFAULT_FILTERS, type DashboardCounts, type DateWindow, type Filters, type ProjectRow, type Sort, VIEWS,
  filterOptions, filterProjects, parseDashboardCounts, parseProjectRows, providerLabel, stageLabel, statusLabel,
} from "@/unit/projects";
import { type Ask, AskDialog, Button, ClassicLink, Field, Select, TextInput, Toast } from "../ui";
import { Icon } from "../icons";
import { type CardAction, ProjectCard } from "./ProjectCard";
import { Shell } from "../Shell";

const FILTERS_KEY = "aia.projects.filters";
const VIEWS_KEY = "aia.projects.savedViews";

function stored<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? { ...fallback, ...(JSON.parse(raw) as T) } : fallback;
  } catch {
    return fallback;
  }
}
function store(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* a private window keeps the state for this page only */
  }
}

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function ProjectsScreen() {
  const [rows, setRows] = useState<ProjectRow[] | null>(null);
  const [counts, setCounts] = useState<DashboardCounts>({});
  const [error, setError] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState(0);
  const [filters, setFilters] = useState<Filters>(() => stored(FILTERS_KEY, DEFAULT_FILTERS));
  const [saved, setSaved] = useState<Record<string, Filters>>(() => stored(VIEWS_KEY, {}));
  const [ask, setAsk] = useState<Ask | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [version, setVersion] = useState(0);
  const load = () => setVersion((v) => v + 1);

  // renderProjects1785: the list and the dashboard, together.
  useEffect(() => {
    let live = true;
    Promise.all([unit("projects"), unit("projectsDashboard")])
      .then(([r, d]) => ({ rows: parseProjectRows(r), counts: parseDashboardCounts(d) }))
      .then(
        (x) => {
          if (!live) return;
          setRows(x.rows);
          setCounts(x.counts);
          setLoadedAt(Date.now());
          setError(null);
        },
        (e: unknown) => live && setError(message(e)),
      );
    return () => {
      live = false;
    };
  }, [version]);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(id);
  }, [toast]);

  const update = (patch: Partial<Filters>) => {
    setFilters((f) => {
      const next = { ...f, ...patch };
      store(FILTERS_KEY, next);
      return next;
    });
  };

  const confirm = (msg: string) => new Promise<boolean>((resolve) => setAsk({ kind: "confirm", message: msg, resolve }));
  const prompt = (msg: string, initial = "") =>
    new Promise<string | null>((resolve) => setAsk({ kind: "prompt", message: msg, initial, resolve }));

  const options = useMemo(() => filterOptions(rows ?? []), [rows]);
  const shown = useMemo(() => (rows ? filterProjects(rows, filters, loadedAt) : []), [rows, filters, loadedAt]);

  // pmAction1810 and pmTrash26: the same questions, the same bodies.
  const onAction = async (row: ProjectRow, action: CardAction) => {
    const body: Record<string, unknown> = { project_id: row.project_id, action };
    if (action === "duplicate") {
      const name = await prompt(t("projects.duplicatePrompt"));
      if (name === null) return;
      body.name = name || null;
    }
    if (action === "tags") {
      const tags = await prompt(t("projects.tagsPrompt"), (row.tags ?? []).join(", "));
      if (tags === null) return;
      body.tags = tags.split(",").map((x) => x.trim()).filter(Boolean);
    }
    if (action === "archive" && !(await confirm(t("projects.archiveConfirm")))) return;
    if (action === "trash" && !(await confirm(t("projects.toTrashConfirm")))) return;
    try {
      const r = (await unit("projectAction", { body, timeoutMs: 30_000 })) as { project_id?: unknown };
      if (action === "duplicate" && typeof r.project_id === "string") {
        setToast(t("projects.duplicateDone"));
        window.location.assign(classicHref({ open: r.project_id }));
        return;
      }
      setToast(action === "trash" ? t("projects.toTrashDone") : t("projects.updatedDone"));
      load();
    } catch (e) {
      setToast(message(e));
    }
  };

  // copyDemo1794
  const onCopyDemo = async (row: ProjectRow) => {
    if (!(await confirm(t("projects.copyDemoConfirm")))) return;
    try {
      const r = (await unit("demoCopy", { body: { project_id: row.project_id }, timeoutMs: 30_000 })) as { project_id?: unknown };
      setToast(t("projects.copyDemoDone"));
      if (typeof r.project_id === "string") window.location.assign(classicHref({ open: r.project_id }));
    } catch (e) {
      setToast(message(e));
    }
  };

  // pmSaveView1810 / pmApplySaved1810 / pmReset1810
  const saveView = async () => {
    const name = await prompt(t("projects.saveViewPrompt"), t("projects.saveViewDefault"));
    if (!name) return;
    const next = { ...saved, [name]: filters };
    setSaved(next);
    store(VIEWS_KEY, next);
  };

  const actions = (
    <>
      <ClassicLink href={classicHref({ start: "research" })} variant="primary" icon="plus">{t("projects.newResearch")}</ClassicLink>
      <ClassicLink href={classicHref({ start: "simulation" })} variant="secondary" icon="plus">{t("projects.newSimulation")}</ClassicLink>
      <ClassicLink href={classicHref({ go: "home" })}>{t("projects.portfolio")}</ClassicLink>
      <Link
        href="/app/projects/trash"
        className="inline-flex min-h-9 items-center gap-1.5 rounded-sm px-3 text-sm font-medium text-ink-muted no-underline hover:bg-surface-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
      >
        <Icon name="trash" />
        {t("projects.trash")}
      </Link>
    </>
  );

  return (
    <Shell title={t("projects.title")} sub={t("projects.sub")} actions={actions}>
      {error ? (
        <section role="alert" className="rounded-md border border-status-fault/40 bg-status-fault-wash p-5">
          <h2 className="font-semibold text-status-fault">{t("projects.loadFailed")}</h2>
          <p className="mt-1 text-sm text-ink">{error}</p>
          <Button className="mt-3" onClick={load}>{t("projects.retry")}</Button>
        </section>
      ) : !rows ? (
        <p className="py-10 text-sm text-ink-muted">{t("projects.loading")}</p>
      ) : (
        <div className="flex flex-col gap-5">
          <div role="group" aria-label={t("projects.views")} className="flex flex-wrap gap-0.5 border-b border-border">
            {VIEWS.map((v) => {
              const on = filters.view === v.id;
              return (
                <button
                  key={v.id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => update({ view: v.id })}
                  className={`-mb-px inline-flex min-h-9 shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-2 text-sm focus-visible:outline-2 focus-visible:outline-focus-ring ${on ? "border-signal font-semibold text-ink" : "border-transparent text-ink-muted hover:text-ink"}`}
                >
                  {v.label}
                  <span className={`rounded-sm px-1 font-mono text-[11px] tabular-nums ${on ? "bg-signal-wash text-signal" : "bg-surface-sunken text-ink-faint"}`}>
                    {v.count(counts)}
                  </span>
                </button>
              );
            })}
          </div>

          <section className="rounded-md border border-border bg-surface-raised p-4">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-[minmax(14rem,1.5fr)_repeat(4,minmax(8.5rem,1fr))_minmax(11.5rem,1.1fr)]">
              <Field label={t("projects.search")} className="md:col-span-3 xl:col-span-1">
                <TextInput
                  type="search"
                  value={filters.q}
                  placeholder={t("projects.searchPlaceholder")}
                  onChange={(e) => update({ q: e.target.value })}
                />
              </Field>
              <Field label={t("projects.status")}>
                <Select value={filters.status} onChange={(e) => update({ status: e.target.value })}>
                  <option value="all">{t("projects.all")}</option>
                  {options.statuses.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
                </Select>
              </Field>
              <Field label={t("projects.stage")}>
                <Select value={filters.stage} onChange={(e) => update({ stage: e.target.value })}>
                  <option value="all">{t("projects.all")}</option>
                  {options.stages.map((s) => <option key={s} value={s}>{stageLabel(s)}</option>)}
                </Select>
              </Field>
              <Field label={t("projects.provider")}>
                <Select value={filters.provider} onChange={(e) => update({ provider: e.target.value })}>
                  <option value="all">{t("projects.all")}</option>
                  {options.providers.map((p) => <option key={p} value={p}>{providerLabel(p)}</option>)}
                </Select>
              </Field>
              <Field label={t("projects.updated")}>
                <Select value={filters.date} onChange={(e) => update({ date: e.target.value as DateWindow })}>
                  <option value="all">{t("projects.anytime")}</option>
                  <option value="7">{t("projects.days7")}</option>
                  <option value="30">{t("projects.days30")}</option>
                  <option value="90">{t("projects.days90")}</option>
                </Select>
              </Field>
              <Field label={t("projects.sort")}>
                <Select value={filters.sort} onChange={(e) => update({ sort: e.target.value as Sort })}>
                  <option value="modified_desc">{t("projects.sortModified")}</option>
                  <option value="created_desc">{t("projects.sortCreated")}</option>
                  <option value="title">{t("projects.sortTitle")}</option>
                  <option value="progress_desc">{t("projects.sortProgress")}</option>
                </Select>
              </Field>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3">
              <Select
                className="w-auto min-w-48"
                value=""
                aria-label={t("projects.savedViews")}
                onChange={(e) => {
                  const v = saved[e.target.value];
                  if (v) update(v);
                }}
              >
                <option value="">{t("projects.savedViews")}</option>
                {Object.keys(saved).map((n) => <option key={n} value={n}>{n}</option>)}
              </Select>
              <Button variant="quiet" small onClick={() => void saveView()}>{t("projects.saveView")}</Button>
              <Button variant="quiet" small onClick={() => update(DEFAULT_FILTERS)}>{t("projects.reset")}</Button>
              <span className="ml-auto rounded-sm border border-border bg-surface-sunken px-2 py-0.5 font-mono text-xs tabular-nums text-ink-muted">
                {tv("projects.count", { n: shown.length })}
              </span>
            </div>
          </section>

          {shown.length ? (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3">
              {shown.map((row) => (
                <ProjectCard
                  key={row.project_id}
                  row={row}
                  now={loadedAt}
                  onAction={(r, a) => void onAction(r, a)}
                  onCopyDemo={(r) => void onCopyDemo(r)}
                />
              ))}
            </div>
          ) : (
            <p className="rounded-md border border-dashed border-border-strong p-8 text-center text-sm text-ink-muted">{t("projects.empty")}</p>
          )}
        </div>
      )}
      <AskDialog ask={ask} onDone={() => setAsk(null)} />
      <Toast message={toast} />
    </Shell>
  );
}
