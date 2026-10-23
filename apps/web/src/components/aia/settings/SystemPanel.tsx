"use client";

// Stav systému (settings-redesign chunk 11, System board): the deployment's latest smoke run, its
// checks not ready first, and error reporting from GlitchTip (settings-backends SB4, #839). Read
// only, OWNER or ADMIN. A route not deployed yet (404) reads "V AIA zatím není"; a deployment that
// holds several organizations (409 deployment_shared) says the server's words; GlitchTip without a
// token says so, never as an error; a monitor GlitchTip did not report on is unknown, never up.

import { useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { ApiError, type ErrorTracking, settingsStatus } from "@/lib/api";
import { relative } from "@/lib/format";
import { FOCUS } from "../../ui/parts";
import { describeError } from "./errors";
import { Technical } from "./technical";

const S = "aia.settings.panel.system";
const CARD = "rounded-md border border-border bg-surface-raised px-6 py-5";
const HEAD = "px-2 py-1.5 text-left text-xs font-normal text-ink-faint";
const CELL = "border-t border-border px-2 py-2 align-top text-sm";
const when = (iso: string | null) => (iso ? (relative(iso) ?? iso) : "—");

/** A read of one route: its data, or why there is none, in words. */
type Read<T> = { state: "loading" } | { state: "ready"; data: T } | { state: "not_yet" } | { state: "admin_only" } | { state: "refused"; message: string };

function useRead<T>(load: () => Promise<T>): Read<T> {
  const [read, setRead] = useState<Read<T>>({ state: "loading" });
  useEffect(() => {
    let live = true;
    load().then(
      // A body that is not an object of the route's shape is not "all is well": said so.
      (data) => { if (live) setRead(data && typeof data === "object" && !Array.isArray(data) ? { state: "ready", data } : { state: "refused", message: t(`${S}.malformed`) }); },
      (e: unknown) => {
        if (!live) return;
        // Not deployed: no route answered (http_404).
        if (e instanceof ApiError && e.status === 404 && e.code === "http_404") setRead({ state: "not_yet" });
        else if (e instanceof ApiError && e.status === 403) setRead({ state: "admin_only" });
        // 409 deployment_shared carries the server's Czech sentence: said as given.
        else if (e instanceof ApiError && e.code === "deployment_shared") setRead({ state: "refused", message: e.message });
        else setRead({ state: "refused", message: describeError(e) });
      },
    );
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- read once per mount
  }, []);
  return read;
}

function Unread({ read }: { read: Exclude<Read<unknown>, { state: "ready" }> }) {
  if (read.state === "loading") return <p className="mt-2 text-sm text-ink-muted">{t(`${S}.loading`)}</p>;
  if (read.state === "not_yet") return <p data-not-yet className="mt-3 inline-flex rounded-sm border border-dashed border-border-strong px-2 py-0.5 text-xs text-ink-muted">{t("aia.settings.panel.notYet")}</p>;
  if (read.state === "admin_only") return <p className="mt-2 text-sm text-ink-muted">{t(`${S}.adminOnly`)}</p>;
  return <p role="alert" className="mt-2 text-sm text-status-fault">{read.message}</p>;
}

function Readiness() {
  const read = useRead(() => settingsStatus.system());
  return (
    <section data-system-readiness aria-labelledby="sys-ready-h" className={CARD}>
      <h3 id="sys-ready-h" className="text-base font-semibold">{t(`${S}.readiness`)}</h3>
      {read.state !== "ready" ? <><p className="mt-1 text-sm leading-6 text-ink-muted">{t(`${S}.readinessHolds`)}</p><Unread read={read} /></> : !read.data.latest || !Array.isArray(read.data.latest.checks) ? (
        <p data-smoke-none className="mt-1 text-sm leading-6 text-ink-muted">{t(`${S}.noRun`)}</p>
      ) : (() => {
        const run = read.data.latest;
        const ready = run.checks.filter((c) => c.status === "ok").length;
        return <>
          <p className="mt-0.5 text-xs text-ink-muted">
            <span className="font-medium text-ink">{tv(`${S}.readyCount`, { ready, total: run.checks.length })}</span>
            {" · "}{tv(`${S}.smokeAt`, { when: when(run.ran_at) })}{" · "}{tv(`${S}.build`, { sha: run.build_sha.slice(0, 7) })}
          </p>
          <p className="mt-1 text-xs text-ink-muted">{t(`${S}.readinessHelp`)}</p>
          <ul className="mt-3 divide-y divide-border border-y border-border">
            {run.checks.map((c, i) => {
              // A failed check is a failure (fault), one that could not run is unknown (neutral): neither
              // is coral, which says a person is awaited. Passed checks are muted, below.
              return (
                <li key={`${i}-${c.check}`} data-smoke-check={c.status} className={`flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-2 py-2 text-sm ${c.status === "ok" ? "text-ink-muted" : "font-medium"}`}>
                  <span className="min-w-0 break-words">{c.check}</span>
                  <span className={`shrink-0 text-xs ${c.status === "FAIL" ? "text-status-fault" : ""}`}>{t(`${S}.check.${c.status}`)}</span>
                </li>
              );
            })}
          </ul>
        </>;
      })()}
    </section>
  );
}

const NOTHING_READ: ErrorTracking = { configured: false, dashboard_url: null, project: null, project_url: null, alerts: [], uptime: [], uptime_enabled: null, issues_7d: [], error: null };

function Errors() {
  const read = useRead(() => settingsStatus.errorTracking());
  if (read.state !== "ready") return (
    <section data-system-errors aria-labelledby="sys-err-h" className={CARD}>
      <h3 id="sys-err-h" className="text-base font-semibold">{t(`${S}.errors`)}</h3>
      <p className="mt-1 text-sm leading-6 text-ink-muted">{t(`${S}.errorsHolds`)}</p>
      <Unread read={read} />
    </section>
  );
  // A field the answer lacks is unknown: no token, no rules, no monitors, nothing claimed.
  const e: ErrorTracking = { ...NOTHING_READ, ...(read.data as Partial<ErrorTracking>) };
  return (
    <section data-system-errors aria-labelledby="sys-err-h" className={CARD}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="sys-err-h" className="text-base font-semibold">{t(`${S}.errors`)}</h3>
        {e.dashboard_url ? <a href={e.dashboard_url} target="_blank" rel="noreferrer noopener" className={`inline-flex min-h-9 items-center rounded-sm border border-border-strong px-3 text-sm ${FOCUS}`}>{t(`${S}.openGlitchtip`)} ↗</a> : null}
      </div>
      <p className="mt-1 text-xs leading-5 text-ink-muted">{t(`${S}.errorsReadOnly`)}</p>
      {!e.configured ? <p data-glitchtip-unconfigured className="mt-3 text-sm text-ink-muted">{t(`${S}.unconfigured`)}</p> : <>
        {e.error ? <p role="alert" className="mt-3 text-sm text-status-fault">{t(`${S}.readError`)} <Technical><code className="text-xs">{e.error}</code></Technical></p> : null}
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div>
            <h4 className="text-sm font-semibold">{t(`${S}.alerts`)}</h4>
            {e.alerts.length ? <ul className="mt-1 flex flex-col gap-1 text-sm">{e.alerts.map((a) => (
              <li key={a.name} data-alert>{a.name}<span className="block text-xs text-ink-muted">
                {a.quantity !== null && a.timespan_minutes !== null ? tv(`${S}.alertRule`, { n: a.quantity, minutes: a.timespan_minutes }) : t(`${S}.alertRuleUnknown`)} · {tv(`${S}.recipients`, { n: a.recipients })}
              </span></li>
            ))}</ul> : <p className="mt-1 text-sm text-ink-muted">{e.error ? t(`${S}.alertsUnread`) : t(`${S}.noAlerts`)}</p>}
          </div>
          <div>
            <h4 className="text-sm font-semibold">{t(`${S}.uptime`)}</h4>
            {e.uptime_enabled === false ? <p data-uptime-off className="mt-1 text-sm text-ink-muted">{t(`${S}.uptimeOff`)}</p>
              : !e.uptime.length ? <p className="mt-1 text-sm text-ink-muted">{e.error ? t(`${S}.uptimeUnread`) : e.uptime_enabled ? t(`${S}.uptimeNone`) : t(`${S}.uptimeUnknown`)}</p>
              : <ul className="mt-1 flex flex-col gap-1 text-sm">{e.uptime.map((m) => (
                <li key={m.name} data-monitor={m.is_up === null ? "unknown" : m.is_up ? "up" : "down"}>
                  {m.name} · <span className={m.is_up === false ? "font-medium text-status-fault" : ""}>{t(`${S}.monitor.${m.is_up === null ? "unknown" : m.is_up ? "up" : "down"}`)}</span>
                  {m.last_change ? <span className="block text-xs text-ink-muted">{tv(`${S}.since`, { when: when(m.last_change) })}</span> : null}
                </li>
              ))}</ul>}
          </div>
        </div>
        <div className="mt-4">
          <h4 className="text-sm font-semibold">{t(`${S}.issues`)}</h4>
          {e.issues_7d.length ? (
            <div className="mt-1 overflow-x-auto"><table className="w-full min-w-[32rem] border-collapse">
              <thead><tr><th scope="col" className={HEAD}>{t(`${S}.col.issue`)}</th><th scope="col" className={HEAD}>{t(`${S}.col.where`)}</th><th scope="col" className={HEAD}>{t(`${S}.col.count`)}</th><th scope="col" className={HEAD}>{t(`${S}.col.last`)}</th></tr></thead>
              <tbody>{e.issues_7d.map((i, n) => (
                <tr key={`${n}-${i.title}`} data-issue>
                  <td className={`${CELL} break-words`}>{i.url ? <a href={i.url} target="_blank" rel="noreferrer noopener" className={`text-signal hover:underline ${FOCUS}`}>{i.title} ↗</a> : i.title}</td>
                  <td className={`${CELL} break-words text-ink-muted`}>{i.culprit ?? "—"}</td>
                  <td className={`${CELL} font-mono tabular-nums`}>{i.count ?? "?"}</td>
                  <td className={`${CELL} whitespace-nowrap text-ink-muted`}>{when(i.last_seen)}</td>
                </tr>
              ))}</tbody>
            </table></div>
          ) : <p className="mt-1 text-sm text-ink-muted">{e.error ? t(`${S}.issuesUnread`) : t(`${S}.noIssues`)}</p>}
        </div>
        <p className="mt-4 text-xs leading-5 text-ink-muted">{t(`${S}.neverSent`)}</p>
      </>}
    </section>
  );
}

export function SystemPanel({ mayAdminister }: { mayAdminister: boolean }) {
  if (!mayAdminister) return <section className={CARD}><p className="text-sm text-ink-muted">{t(`${S}.adminOnly`)}</p></section>;
  return <div className="flex flex-col gap-4"><Readiness /><Errors /></div>;
}
