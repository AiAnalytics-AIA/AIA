"use client";

// The Deep Research tab: every policy value Deep Research runs by, what is in force
// and who approved it (ADR 0022, GET /api/v1/deep-research/settings). Until someone
// approves a value, the code's proposed default is in force and is labelled so. An
// administrator proposes a value -- a new version, not yet in force -- and approves a
// version or withdraws to the default; each change takes effect for runs enqueued
// after it. The redesign's board (prototype v51, fidelity F8): where research reaches
// (Dosah) with the client's data posture pointed to where it is set, one flat table of
// the rules with a proposal made in their Návrh cell and approved through a modal (I7),
// and the code's fixed protections, which no rule turns off. What is allowed is the API's to say: its
// refusal is shown as it gave it.

import { type FormEvent, type ReactNode, useCallback, useEffect, useState } from "react";

import { useRouter } from "next/navigation";
import { InlineConfirm } from "../../rehome/step";
import { researchPolicyHelp } from "./settings-guide";
import { cs } from "@/i18n/cs";
import { t, tv } from "@/i18n/t";
import {
  type DrSetting,
  type DrSettingDetail,
  type DrSettingValue,
  type DrSettingVersion,
  type DrSettingsOverview,
  type ReachRoute,
  deepResearchSettings,
} from "@/lib/api";
import { STATUS_VALUES, groupsInOrder, inputKind, parseInput, toInput } from "@/lib/deep-research-settings";
import { plural, relative } from "@/lib/format";
import Link from "next/link";
import { Button, Field, Select, TextArea, TextInput } from "../../rehome/ui";
import { ChoiceChips } from "../../ui/ChoiceChips";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { Stepper } from "../../ui/Stepper";
import { FOCUS } from "../../ui/parts";
import { Technical } from "./technical";
import { Loaded } from "../states";
import { useResource } from "../useResource";
import { describeError } from "./errors";
import { waitingChanged } from "./sections";

const D = "aia.settings.deepResearch";
const LABELS: Record<string, string> = cs.aia.settings.deepResearch.labels;
const UNITS: Record<string, string> = cs.aia.settings.deepResearch.units;

type People = (id: string | null) => string;

const when = (iso: string | null) => (iso ? (relative(iso) ?? iso) : "—");
const number = new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 6 });

/** A setting's name in Czech; the catalogue's own label when the page has none for it. */
const labelOf = (s: Pick<DrSetting, "key" | "label">) => LABELS[s.key] ?? s.label;

/** A value as a reader sees it. Null is unknown -- the code holds nothing -- never zero. */
export function showValue(type: string, value: DrSettingValue): string {
  if (value === null) return t(`${D}.unknown`);
  if (typeof value === "boolean") return t(`${D}.${value ? "yes" : "no"}`);
  if (Array.isArray(value)) return value.length ? value.join(", ") : t(`${D}.emptyList`);
  if (typeof value === "number") return number.format(value);
  if (inputKind(type) === "status") return t(`${D}.status.${value}`);
  return value;
}

function unitOf(s: DrSetting): string {
  return s.unit ? (UNITS[s.unit] ?? s.unit) : "";
}

function bounds(s: DrSetting): string | null {
  const min = s.minimum === null ? null : number.format(s.minimum);
  const max = s.maximum === null ? null : number.format(s.maximum);
  if (min !== null && max !== null) return tv(`${D}.bounds`, { min, max });
  if (min !== null) return tv(`${D}.boundsMin`, { min });
  if (max !== null) return tv(`${D}.boundsMax`, { max });
  return null;
}

async function load(): Promise<DrSettingsOverview> {
  const body: unknown = await deepResearchSettings.list();
  // A body without a list is not "no settings": say so rather than draw an empty tab.
  if (!body || typeof body !== "object" || !Array.isArray((body as DrSettingsOverview).settings)) {
    throw new Error(t(`${D}.malformed`));
  }
  return body as DrSettingsOverview;
}

export function DeepResearchSettingsPanel({ people }: { people: People }) {
  const [res, retry] = useResource(load, []);
  return <Loaded res={res} retry={retry}>{(overview) => <Overview overview={overview} people={people} reload={retry} />}</Loaded>;
}

const TH = "px-2 py-1.5 text-left text-xs font-normal text-ink-faint";
const TD = "border-t border-border px-2 py-2.5 align-top text-sm";
const FLAGS = ["required_for_live", "lower_only", "method"] as const;
const CARD = "rounded-md border border-border bg-surface-raised px-5 py-4";

// The prototype's board (v51, fidelity F8): Dosah with the client's data posture inside it, then one
// card of the rules -- readiness in its head, one flat table of every rule with its group, what is
// in force, the proposal made in its Návrh cell and Schválit / Stáhnout beside it -- and the code's
// fixed protections at its foot. A rule's history and a written proposal open beneath its row.
// A search or the live filter hides rows; a draft survives both, because no row unmounts.
function Overview({ overview, people, reload }: { overview: DrSettingsOverview; people: People; reload: () => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [liveOnly, setLiveOnly] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState<{ key: string | null } | null>(null);
  const rules = groupsInOrder(overview.settings).flatMap(({ settings }) => settings);
  const toggle = (key: string) => {
    const next = open === key ? null : key;
    if (dirty) setPending({ key: next }); else { setOpen(next); setDirty(false); }
  };
  const missing = new Set(overview.missing_for_live);
  const q = query.trim().toLocaleLowerCase("cs");
  // The live filter holds only while something waits: once the last rule is approved its toggle
  // goes, and so does the filter, never leaving every row hidden with nothing to restore them.
  const live = liveOnly && missing.size > 0;
  const matches = (s: DrSetting) => (s.key === open && dirty) ||
    (`${labelOf(s)} ${t(`${D}.groups.${s.group}`)} ${s.key} ${researchPolicyHelp(s.key, s.group)}`.toLocaleLowerCase("cs").includes(q) && (!live || missing.has(s.key)));
  const anyVisible = rules.some(matches);
  return (
    <div className="flex flex-col gap-4">
      <Reach mayAdminister={overview.may_administer} missing={overview.missing_for_live} />
      <section data-dr-rules aria-labelledby="dr-rules-h" className={CARD}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h3 id="dr-rules-h" className="text-base font-semibold">{t(`${D}.board.rules`)}</h3>
          <Readiness count={missing.size} yours={overview.may_administer} />
        </div>
        <p className="mt-1 max-w-3xl text-xs leading-5 text-ink-muted">
          {t(`${D}.board.rulesHelp`)}{missing.size ? <> {t(`${D}.live.note`)}</> : null}
        </p>
        <Technical><p data-technical className="mt-1 text-xs text-ink-faint">{tv(`${D}.catalogue`, { version: overview.catalogue_version })}</p></Technical>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <TextInput type="search" className="w-full sm:w-72" aria-label={t(`${D}.search`)} placeholder={t(`${D}.searchPlaceholder`)} value={query} onChange={(e) => setQuery(e.target.value)} />
          {missing.size ? <Button aria-pressed={live} onClick={() => setLiveOnly((v) => !v)}>{t(`${D}.live.${live ? "showAll" : "showWaiting"}`)}</Button> : null}
        </div>
        {pending ? <div className="mt-2"><InlineConfirm message={t(`${D}.draftGuard`)} action={t(`${D}.discardDraft`)} onCancel={() => setPending(null)} onConfirm={() => { setOpen(pending.key); setDirty(false); setPending(null); }} /></div> : null}
        {!anyVisible ? <p role="status" className="mt-2 text-sm text-ink-muted">{t(`${D}.noMatch`)}</p> : null}
        <div className="relative mt-2 overflow-x-auto"><table className="w-full min-w-[54rem]">
          <caption className="sr-only">{t(`${D}.board.rules`)}</caption>
          <thead><tr>
            <th scope="col" className={`${TH} w-32`}>{t(`${D}.col.group`)}</th><th scope="col" className={TH}>{t(`${D}.col.setting`)}</th>
            <th scope="col" className={`${TH} w-44`}>{t(`${D}.col.value`)}</th><th scope="col" className={`${TH} w-56`}>{t(`${D}.col.proposal`)}</th>
            <th scope="col" className={`${TH} w-28`}>{t(`${D}.col.approval`)}</th>
          </tr></thead>
          <tbody>
            {rules.map((s) => (
              <Row
                key={s.key}
                setting={s}
                shown={matches(s)}
                missing={missing.has(s.key)}
                people={people}
                open={open === s.key}
                onToggle={() => toggle(s.key)}
                onDirty={setDirty}
                mayAdminister={overview.may_administer}
                onChanged={reload}
              />
            ))}
          </tbody>
        </table></div>
        {overview.may_administer ? null : <p className="mt-2 text-xs text-ink-muted">{t(`${D}.adminNote`)}</p>}
        <Protections />
      </section>
    </div>
  );
}

const ROUTE_NAMES: Record<string, string> = {
  "wikipedia-public-web_search": "Wikipedie (vyhledávání)",
  "wikipedia-public-web_fetch": "Wikipedie (stránky)",
  "brave-web-search": "Brave Search",
  "public-web-fetch": "Veřejné webové stránky",
  "common-crawl-athena-index": "Common Crawl (index)",
  "common-crawl-archive": "Common Crawl (archiv)",
};
const routeName = (id: string) => ROUTE_NAMES[id] ?? (id.startsWith("connector-") ? tv(`${D}.reach.connector`, { name: id.slice("connector-".length) }) : id);
const REASONS = new Set(["settings_unapproved", "class", "deep_research_off", "search_route_other", "public_fetch_off", "connector_not_listed", "common_crawl_off", "agent_directed_off", "unavailable"]);

/**
 * What the organization's approval means for a route, from what the worker recorded and nothing
 * else: a priced route waits for the rules live needs or runs on them; a composed route without a
 * price needs none. A route the deployment did not compose recorded no price, so its approval is
 * not known ("—"), never "not needed".
 */
function reachApproval(r: ReachRoute, missingForLive: number): string {
  if (r.state === "waiting") {
    const n = r.missing_settings.length || missingForLive;
    const R = `${D}.reach.approval.rules`;
    return tv(`${D}.reach.approval.waiting`, { n, rules: plural(n, t(`${R}.one`), t(`${R}.few`), t(`${R}.many`)) });
  }
  const composed = r.state === "active" || r.classes.length > 0;
  if (!composed) return "—";
  if (r.priced) return t(`${D}.reach.approval.${missingForLive ? "missing" : "approved"}`);
  return t(`${D}.reach.approval.free`);
}

/** The state's dot: filled while it runs or waits, hollow when it is off. Coral only for someone who can approve. */
function StateDot({ state, yours }: { state: ReachRoute["state"]; yours: boolean }) {
  const look = state === "waiting" ? (yours ? "bg-status-you border-status-you" : "bg-ink-muted border-ink-muted")
    : state === "active" ? "bg-ink border-ink" : "border-ink-muted";
  return <span aria-hidden="true" className={`mt-1.5 inline-block size-2.5 shrink-0 rounded-full border ${look}`} />;
}

/** Dosah: where Deep Research reaches, from the newest worker's record of its composition (#844). The
 *  table is drawn whatever the record holds; an empty one says why in its one row, never a route. */
function Reach({ mayAdminister, missing }: { mayAdminister: boolean; missing: readonly string[] }) {
  // Read again whenever what live needs changes (an approval, a withdrawal, a return to the
  // default): a priced route's "schváleno" or "čeká" is the organization's, read with the record.
  const needs = [...missing].sort().join("\n");
  const [res, retry] = useResource(() => deepResearchSettings.reach(), [needs]);
  const head = (summary?: ReactNode, source?: ReactNode) => (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <h3 id="dr-reach-h" className="text-base font-semibold">{t(`${D}.reach.title`)}</h3>
      {summary}
      {source ? <span className="text-xs text-ink-muted sm:ml-auto">{source}</span> : null}
    </div>
  );
  // An empty table keeps no width of its own: its one row's sentence wraps on a phone, not scrolls.
  const table = (body: ReactNode, empty = false) => (
    <div className="relative mt-2 overflow-x-auto"><table className={`w-full ${empty ? "" : "min-w-[48rem]"}`}>
      <caption className="sr-only">{t(`${D}.reach.title`)}</caption>
      <thead><tr>
        <th scope="col" className={TH}>{t(`${D}.reach.col.route`)}</th><th scope="col" className={TH}>{t(`${D}.reach.col.kind`)}</th>
        <th scope="col" className={TH}>{t(`${D}.reach.col.approval`)}</th><th scope="col" className={`${TH} w-20`}>{t(`${D}.reach.col.classes`)}</th>
        <th scope="col" className={`${TH} w-[34%]`}>{t(`${D}.reach.col.state`)}</th>
      </tr></thead>
      <tbody>{body}</tbody>
    </table></div>
  );
  const empty = (marker: "data-not-yet" | "data-reach-unrecorded", text: string) => (
    <tr><td colSpan={5} className={`${TD} text-ink-muted`} {...{ [marker]: "" }}>{text}</td></tr>
  );
  return (
    <section data-dr-reach aria-labelledby="dr-reach-h" className={CARD}>
      {/* Until the route is deployed (a 404), the panel says it is not in AIA yet, as before. */}
      {res.state === "not-found" ? <>
        {head(<span className="inline-flex min-h-[22px] items-center rounded-pill border border-dashed border-border-strong px-2 text-xs text-ink-muted">{t("aia.settings.panel.notYet")}</span>)}
        {table(empty("data-not-yet", t(`${D}.reach.notYet`)), true)}
      </> : (
        <Loaded res={res} retry={retry}>{(reach) => {
          if (!reach.recorded) return <>
            {head()}
            <p className="mt-0.5 max-w-3xl text-xs leading-5 text-ink-muted">{t(`${D}.reach.help`)}</p>
            {table(empty("data-reach-unrecorded", t(`${D}.reach.unrecorded`)), true)}
          </>;
          const active = reach.routes.filter((r) => r.state === "active").length;
          return <>
            {head(
              <span data-reach-summary className="inline-flex min-h-[22px] items-center rounded-pill border border-border px-2 text-xs">{tv(`${D}.reach.summary`, { active, n: reach.routes.length })}</span>,
              <>
                {tv(`${D}.reach.source`, { when: when(reach.composed_at) })}
                {reach.build_sha ? <> · {tv(`${D}.reach.build`, { sha: reach.build_sha.slice(0, 7) })}</> : null}
                {reach.class_gates === "advisory" ? <> · {t(`${D}.reach.advisory`)}</> : null}
              </>,
            )}
            <p className="mt-0.5 max-w-3xl text-xs leading-5 text-ink-muted">{t(`${D}.reach.help`)}</p>
            {table(reach.routes.map((r) => {
              const yours = r.state === "waiting" && mayAdminister;
              return (
                <tr key={r.route} data-reach-route={r.route} data-reach-state={r.state} className={yours ? "bg-status-you-wash" : r.state === "active" || r.state === "waiting" ? "" : "text-ink-muted"}>
                  <th scope="row" className={`${TD} text-left font-normal`}>
                    <span className={`font-medium ${r.state === "active" || r.state === "waiting" ? "text-ink" : ""}`}>{routeName(r.route)}</span>
                    <Technical><code data-technical className="block break-all text-xs text-ink-faint">{r.route}</code></Technical>
                  </th>
                  <td className={TD}>
                    {t(`${D}.reach.kind.${r.kind}`)}
                    {r.priced ? <> · {t(`${D}.reach.priced`)}</> : null}
                    {r.zone && r.zone !== "EU" ? <>, {t(`${D}.reach.zone.${r.zone === "NON_EU" ? "nonEu" : "unknown"}`)}</> : null}
                  </td>
                  <td data-reach-approval className={TD}>{reachApproval(r, reach.missing_for_live.length)}</td>
                  <td className={`${TD} font-mono text-xs`}>{r.classes.length ? r.classes.join(", ") : "—"}</td>
                  <td className={TD}>
                    <span className="flex items-start gap-2">
                      <StateDot state={r.state} yours={yours} />
                      <span className="min-w-0">
                        <span className={`font-medium ${r.state === "active" || r.state === "waiting" ? "text-ink" : ""}`}>{t(`${D}.reach.state.${r.state}`)}</span>
                        {r.reason ? <span data-reach-reason className="block max-w-prose text-xs leading-5">
                          {REASONS.has(r.reason) ? t(`${D}.reach.reason.${r.reason}`) : r.reason}
                          {r.reason === "settings_unapproved" && r.missing_settings.length ? ` ${tv(`${D}.reach.missing`, { n: r.missing_settings.length })}` : ""}
                        </span> : null}
                        {r.class_advisory ? <span className="block text-xs">{t(`${D}.reach.classAdvisory`)}</span> : null}
                        {r.detail ? <Technical><span data-technical className="block break-words font-mono text-[11px] text-ink-faint">{r.detail}</span></Technical> : null}
                      </span>
                    </span>
                  </td>
                </tr>
              );
            }))}
          </>;
        }}</Loaded>
      )}
      <Posture />
    </section>
  );
}

/** The client's data posture: set at the client, read here so a person knows where it lives. */
function Posture() {
  return (
    <div data-dr-posture className="mt-4 border-t border-border pt-4">
      <h4 className="text-sm font-semibold">{t(`${D}.posture.title`)}</h4>
      <p className="mt-1 max-w-3xl text-sm leading-6">
        {t(`${D}.posture.text`)}{" "}
        <Link href="/app/clients" className={`text-signal hover:underline ${FOCUS}`}>{t(`${D}.posture.profile`)}</Link>
        {t(`${D}.posture.between`)}{" "}
        <a href="#access" className={`text-signal hover:underline ${FOCUS}`}>{t(`${D}.posture.access`)}</a>
        {t(`${D}.posture.end`)}
      </p>
    </div>
  );
}

const PROTECTIONS = ["robots", "noLogin", "noPersonal", "publicOnly", "cited"] as const;
/** "Pevné ochrany v kódu": what holds for every run, whatever a rule says; at the rules' foot. */
function Protections() {
  return (
    <div data-dr-protections className="mt-4 border-t border-border pt-4">
      <h4 className="text-sm font-semibold">{t(`${D}.protections.title`)}</h4>
      <p className="mt-0.5 text-xs text-ink-muted">{t(`${D}.protections.note`)}</p>
      <ul className="mt-2 flex flex-wrap gap-1.5">
        {PROTECTIONS.map((k) => <li key={k} className="inline-flex min-h-[22px] items-center rounded-pill border border-border px-2 text-xs">{t(`${D}.protections.${k}`)}</li>)}
      </ul>
    </div>
  );
}

/** What live still needs, as the rules card's chip: coral for someone who can approve, neutral otherwise. */
function Readiness({ count, yours }: { count: number; yours: boolean }) {
  const look = count && yours ? "border-status-you/50 bg-status-you-wash text-status-you-ink" : "border-border text-ink";
  return (
    <p data-live-readiness role="status" className={`inline-flex min-h-[26px] items-center rounded-pill border px-2.5 text-xs ${look}`}>
      {count ? tv(`${D}.live.chip`, { count }) : t(`${D}.live.ready`)}
    </p>
  );
}

function Row({ setting: s, shown, missing, people, open, onToggle, mayAdminister, onChanged, onDirty }: {
  setting: DrSetting; shown: boolean; missing: boolean; people: People; open: boolean; onToggle: () => void; mayAdminister: boolean; onChanged: () => void; onDirty: (value: boolean) => void;
}) {
  const approved = s.origin === "approved";
  const pending = usePending(s);
  const waiting = pending?.version_number ?? null;
  // Coral and Schválit only for someone the server will let approve it (#897): never for a proposer
  // whose own proposal waits on independent review.
  const approver = mayAdminister && (pending?.may_approve ?? true);
  const help = researchPolicyHelp(s.key, s.group);
  const [explained, setExplained] = useState(false);
  return (
    <>
      <tr data-dr-setting={s.key} data-dr-group={s.group} data-missing={missing ? s.key : undefined} data-pending={waiting !== null ? waiting : undefined} hidden={!shown}
        className={open ? "bg-signal-wash/50" : waiting !== null ? (approver ? "bg-status-you-wash" : "bg-surface-sunken") : undefined}>
        <td className={`${TD} text-ink-muted`}>{t(`${D}.groups.${s.group}`)}</td>
        <th scope="row" className={`${TD} text-left font-normal`}>
          <span className="font-medium text-ink">{labelOf(s)}</span>
          {/* A real disclosure, as on Studie a rozpočty: keyboard and touch open what it explains. */}
          <button type="button" data-dense aria-expanded={explained} aria-controls={`dr-help-${s.key}`} aria-label={tv(`${D}.helpOf`, { rule: labelOf(s) })}
            title={help} onClick={() => setExplained((v) => !v)}
            className={`ml-1 inline-flex size-11 items-center justify-center rounded-full align-middle text-ink-faint hover:text-ink sm:size-6 ${FOCUS}`}>ⓘ</button>
          <span id={`dr-help-${s.key}`} hidden={!explained} className="mt-0.5 block max-w-prose text-xs leading-5 text-ink-muted">{help}</span>
          {/* The rule's marks and the way into its history, one line: 52 rows read at a glance. */}
          <span className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-ink-muted">
            {FLAGS.filter((f) => s[f]).map((f) => <span key={f} title={t(`${D}.flagHelp.${f}`)}>{t(`${D}.flag.${f}`)}</span>)}
            {/* Dense beside the rule on a desktop (24 px); a 44 px target on a phone (I11). */}
            <button type="button" onClick={onToggle} aria-expanded={open} aria-controls={`dr-detail-${s.key}`} data-dense
              className={`inline-flex min-h-11 items-center text-signal hover:underline sm:min-h-6 ${FOCUS}`}>
              {t(`${D}.${open ? "close" : mayAdminister ? "open" : "view"}`)}
            </button>
          </span>
          <Technical><code data-technical className="mt-1 block break-all text-xs text-ink-faint">{s.key}</code></Technical>
        </th>
        <td className={TD}>
          <span data-value className="break-words font-mono">{showValue(s.type, s.value)}</span>
          {s.value !== null && unitOf(s) ? <span className="text-ink-muted"> {unitOf(s)}</span> : null}
          <span className="mt-0.5 block text-xs text-ink-muted">
            <span data-origin={s.origin}>{t(`${D}.origin.${s.origin}`)}</span>
            {approved && s.version !== null ? <> · {tv(`${D}.origin.approvedBy`, { version: s.version, who: people(s.approved_by), when: when(s.approved_at) })}</> : null}
          </span>
        </td>
        <td className={TD}>
          {pending ? <PendingValue setting={s} version={pending} yours={approver} />
            : mayAdminister ? <ProposeInPlace setting={s} onChanged={onChanged} onOpen={onToggle} />
            : <span className="text-xs text-ink-faint">{t(`${D}.noProposal`)}</span>}
        </td>
        <td className={TD}>
          <div className="flex flex-col items-start gap-1.5">
            {waiting !== null && approver ? <ApproveButton setting={s} version={waiting} onDone={onChanged} /> : null}
            {pending && mayAdminister ? <WithdrawButton setting={s} version={pending} onDone={onChanged} /> : null}
          </div>
        </td>
      </tr>
      {open ? (
        <tr hidden={!shown}><td colSpan={5} id={`dr-detail-${s.key}`} className="border-t border-border bg-surface-sunken px-3 py-4">
          <p className="mb-3 max-w-3xl text-sm leading-6 text-ink-muted">{help}</p>
          <Detail settingKey={s.key} people={people} mayAdminister={mayAdminister} onChanged={onChanged} onDirty={onDirty} />
        </td></tr>
      ) : null}
    </>
  );
}

/**
 * The proposal waiting for approval, when there is one: the newest version saved after the rule's
 * last approval (or with none made). A number above the one in force is not enough -- a withdrawal
 * to the default leaves the version it withdrew from earlier, not waiting. The overview carries no
 * version's date or decline, so a rule with a newer number is read again whenever the overview is
 * (a withdrawal changes no field of it); until then nothing waits.
 */
function usePending(s: DrSetting): DrSettingVersion | null {
  const candidate = s.latest_number !== null && s.latest_number > (s.version ?? 0);
  const [res] = useResource(() => (candidate ? deepResearchSettings.get(s.key) : Promise.resolve(null)), [s, candidate]);
  if (!candidate || res.state !== "ready" || !res.data) return null;
  return pendingOf(res.data);
}

/** The one rule for what waits, read by the row and the detail's steps alike. Saved after the last
 *  approval, in both cases: a PENDING version from before it is one an approval passed over (review of
 *  #842). The server's state (#841), where sent, adds what the dates cannot say: a withdrawn or
 *  declined version waits for nothing. */
function pendingOf(detail: DrSettingDetail): DrSettingVersion | null {
  const last = detail.history.map((h) => h.approved_at).sort().at(-1);
  const waiting = detail.versions.filter((v) => (v.state !== undefined ? v.state === "PENDING" : v.version_number !== detail.version)
    && (last === undefined || v.created_at > last));
  return waiting.sort((a, b) => b.version_number - a.version_number)[0] ?? null;
}

function bound(s: DrSetting): { min: number; max: number } {
  // A cap may be lowered and never raised (lower_only): its default is the field's top.
  const top = s.lower_only && typeof s.default === "number" ? s.default : null;
  const max = s.maximum ?? top ?? 1e9;
  return { min: s.minimum ?? 0, max: top !== null ? Math.min(max, top) : max };
}

/** A proposal made where the rule is read (I1): a stepper for a number, a choice for yes/no or a status.
 *  Any other type opens its form below the row, where a list, a date or an address is written. */
function ProposeInPlace({ setting: s, onChanged, onOpen }: { setting: DrSetting; onChanged: () => void; onOpen: () => void }) {
  const kind = inputKind(s.type);
  const [error, setError] = useState<string | null>(null);
  const propose = (value: DrSettingValue) => {
    setError(null);
    return deepResearchSettings.propose(s.key, { value, source_url: "", note: "" }).then(onChanged, (e: unknown) => { setError(describeError(e)); throw e; });
  };
  const label = tv(`${D}.proposeOf`, { rule: labelOf(s) });
  const shown = error ? <p role="alert" className="mt-1 text-xs text-status-fault">{error}</p> : null;
  if (kind === "whole" || kind === "decimal") {
    const { min, max } = bound(s);
    return <>
      <Stepper label={label} value={typeof s.value === "number" ? s.value : null} min={min} max={max} decimals={kind === "whole" ? 0 : 4} step={kind === "whole" ? 1 : 0.5}
        unit={unitOf(s) || undefined} showBounds={false} note={bounds(s)} onCommit={(v) => propose(v)} />
      {shown}
    </>;
  }
  if (kind === "decision" || kind === "status") {
    const options = kind === "decision"
      ? [{ key: "true", label: t(`${D}.yes`) }, { key: "false", label: t(`${D}.no`) }]
      : STATUS_VALUES.map((v) => ({ key: v, label: t(`${D}.status.${v}`) }));
    const value = s.value === null ? null : String(s.value);
    return <>
      <ChoiceChips look="segmented" small label={label} value={value} options={options} onChange={(k) => { if (k !== value) void propose(kind === "decision" ? k === "true" : k).catch(() => {}); }} />
      {shown}
    </>;
  }
  return <Button small onClick={onOpen}>{t(`${D}.proposeHere`)}</Button>;
}

/** The waiting proposal's value. */
/** Coral means "needs you": only for someone who can approve it; a member reads it neutral. */
function PendingValue({ setting: s, version: v, yours }: { setting: DrSetting; version: DrSettingVersion; yours: boolean }) {
  return (
    <span data-pending-value className="text-sm">
      <span className="font-mono">{showValue(s.type, v.value)}</span>{v.value !== null && unitOf(s) ? <span className="text-ink-muted"> {unitOf(s)}</span> : null}
      <span className={`block text-xs ${yours ? "text-status-you-ink" : "text-ink-muted"}`}>{tv(`${D}.waitingVersion`, { version: v.version_number })}</span>
    </span>
  );
}

/** Stáhnout návrh: an I7 modal with a reason (required); the version stays, never approved after. */
function WithdrawButton({ setting: s, version: v, onDone }: { setting: DrSetting; version: DrSettingVersion; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fmt = (value: DrSettingValue) => `${showValue(s.type, value)}${value !== null && unitOf(s) ? ` ${unitOf(s)}` : ""}`;
  const go = async () => {
    if (!reason.trim()) { setError(t(`${D}.withdraw.reasonNeeded`)); return; }
    setBusy(true); setError(null);
    try { await deepResearchSettings.withdraw(s.key, v.version_number, reason.trim()); setOpen(false); setReason(""); onDone(); }
    catch (e) { setError(describeError(e)); }
    finally { setBusy(false); }
  };
  return <>
    <Button small className="max-sm:min-h-11" onClick={() => { setError(null); setOpen(true); }}>{t(`${D}.withdrawProposal`)}</Button>
    {open ? (
      <ConfirmDialog open marker="dr-withdraw" busy={busy} error={error} title={t(`${D}.withdraw.title`)}
        rows={[{ label: t(`${D}.approve.rule`), value: labelOf(s) }, { label: t(`${D}.approve.from`), value: fmt(s.value) }, { label: t(`${D}.withdraw.taking`), value: fmt(v.value) }]}
        text={t(`${D}.withdraw.consequence`)} confirmLabel={t(`${D}.withdraw.confirm`)} cancelLabel={t(`${D}.approve.cancel`)}
        onConfirm={() => void go()} onCancel={() => setOpen(false)}>
        <Field label={t(`${D}.withdraw.reason`)}>
          <TextInput value={reason} maxLength={255} required onChange={(e) => setReason(e.target.value)} />
        </Field>
      </ConfirmDialog>
    ) : null}
  </>;
}

/** Schválit: an I7 modal with the rule, what holds and what is approved, and what follows. */
function ApproveButton({ setting: s, version, onDone }: { setting: DrSetting; version: number; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  return <>
    <Button small variant="primary" className="max-sm:min-h-11" onClick={() => setOpen(true)}>{t(`${D}.approve.short`)}</Button>
    {open ? <Approve settingKey={s.key} version={version} onCancel={() => setOpen(false)} onDone={() => { setOpen(false); onDone(); }} /> : null}
  </>;
}

function Detail({ settingKey, people, mayAdminister, onChanged, onDirty }: { settingKey: string; people: People; mayAdminister: boolean; onChanged: () => void; onDirty: (value: boolean) => void }) {
  const [res, retry] = useResource(() => deepResearchSettings.get(settingKey), [settingKey]);
  const changed = () => {
    retry();
    onChanged();
  };
  return (
    <Loaded res={res} retry={retry}>
      {(detail) => <DetailBody detail={detail} people={people} mayAdminister={mayAdminister} onChanged={changed} onDirty={onDirty} />}
    </Loaded>
  );
}

type Approving = { version: number | null } | null;

/** Where a rule's change stands: propose, approve, in force for new runs. */
function Flow({ detail }: { detail: DrSettingDetail }) {
  const inForce = detail.origin === "approved" ? detail.version : null;
  // What waits is the row's rule: a declined, withdrawn or passed-over newest version waits for nothing.
  const waiting = pendingOf(detail) !== null;
  const state = (step: 1 | 2 | 3) =>
    step === 1 ? (waiting || inForce !== null ? "done" : "now")
    : step === 2 ? (waiting ? "now" : inForce !== null ? "done" : "")
    : inForce !== null && !waiting ? "done" : "";
  return (
    <ol data-dr-flow aria-label={t(`${D}.flow.label`)} className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
      {([1, 2, 3] as const).map((n) => {
        const st = state(n);
        return (
          <li key={n} data-state={st || "later"} className={`flex items-center gap-2 ${st === "now" ? "font-semibold text-signal" : st === "done" ? "text-ink" : "text-ink-faint"}`}>
            <span aria-hidden="true" className={`inline-flex size-5 items-center justify-center rounded-full border font-mono text-[11px] ${st === "done" ? "border-ink bg-ink text-surface-raised" : st === "now" ? "border-signal" : "border-border-strong"}`}>{n}</span>
            {t(`${D}.flow.step${n}`)}
          </li>
        );
      })}
    </ol>
  );
}

function DetailBody({ detail, people, mayAdminister, onChanged, onDirty }: { detail: DrSettingDetail; people: People; mayAdminister: boolean; onChanged: () => void; onDirty: (value: boolean) => void }) {
  const [approving, setApproving] = useState<Approving>(null);
  const [done, setDone] = useState<string | null>(null);
  const [draftDirty, setDraftDirty] = useState(false);
  const dirtyChanged = useCallback((value: boolean) => { setDraftDirty(value); onDirty(value); }, [onDirty]);
  const inForce = detail.origin === "approved" ? detail.version : null;
  return (
    <div data-dr-detail={detail.key} className="flex flex-col gap-4">
      {mayAdminister ? <Flow detail={detail} /> : null}
      {done ? <p role="status" className="text-sm font-medium text-ink">{done}</p> : null}
      <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-3">
          {approving ? (
            <Approve
              settingKey={detail.key}
              version={approving.version}
              onCancel={() => setApproving(null)}
              onDone={() => { setApproving(null); setDone(t(`${D}.approve.done`)); onChanged(); }}
            />
          ) : null}
          {mayAdminister ? <Propose key={`${detail.origin}:${detail.version}`} detail={detail} onDirty={dirtyChanged} onSaved={(n) => { setDone(tv(`${D}.propose.saved`, { version: n })); onChanged(); }} /> : null}
          {!mayAdminister ? <p className="text-sm text-ink-muted">{t(`${D}.adminNote`)}</p> : null}
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <div>
            <h4 className="text-sm font-semibold">{t(`${D}.detail.versions`)}</h4>
            {detail.versions.length ? (
              <ul className="mt-1 flex flex-col divide-y divide-border text-sm">
                {detail.versions.map((v) => (
                  <li key={v.version_number} data-dr-version={v.version_number} className="flex flex-wrap items-center gap-x-2 gap-y-1 py-2">
                    <strong>{tv(`${D}.detail.version`, { version: v.version_number })}</strong>
                    <span className="break-words font-mono">{showValue(detail.type, v.value)}</span>
                    {inForce === v.version_number ? <span className="text-xs font-semibold text-signal">{t(`${D}.detail.inForce`)}</span> : null}
                    {v.decline ? <span data-declined={v.decline.kind} className="text-xs text-ink-muted">{t(`${D}.detail.${v.decline.kind === "WITHDRAWN" ? "withdrawnProposal" : "declinedProposal"}`)} · {people(v.decline.by)} · {when(v.decline.at)} — {v.decline.reason}</span> : null}
                    <span className="basis-full text-xs text-ink-muted">{people(v.created_by)} · {when(v.created_at)}{v.note ? ` · ${v.note}` : ""}</span>
                    {v.source_url ? <a className="text-xs underline" href={v.source_url} target="_blank" rel="noreferrer noopener">{t(`${D}.detail.source`)}</a> : null}
                    {mayAdminister && inForce !== v.version_number && !v.decline && (v.may_approve ?? true) ? (
                      <Button small disabled={draftDirty} onClick={() => { setDone(null); setApproving({ version: v.version_number }); }}>{tv(`${D}.detail.approve`, { version: v.version_number })}</Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : <p className="mt-1 text-sm text-ink-muted">{t(`${D}.detail.noVersions`)}</p>}
            {mayAdminister && inForce !== null ? (
              <div className="mt-2"><Button small disabled={draftDirty} onClick={() => { setDone(null); setApproving({ version: null }); }}>{t(`${D}.approve.withdraw`)}</Button></div>
            ) : null}
          </div>
          <div>
            <h4 className="text-sm font-semibold">{t(`${D}.detail.history`)}</h4>
            {detail.history.length ? (
              <ul className="mt-1 flex flex-col gap-1 text-sm">
                {detail.history.map((h) => (
                  <li key={h.approval_id} data-dr-approval={h.approval_id}>
                    <strong>{h.version_number === null ? t(`${D}.detail.withdrawn`) : tv(`${D}.detail.version`, { version: h.version_number })}</strong> · {people(h.approved_by)} · {when(h.approved_at)}
                    {h.reason ? <span className="text-ink-muted"> — {h.reason}</span> : null}
                  </li>
                ))}
              </ul>
            ) : <p className="mt-1 text-sm text-ink-muted">{t(`${D}.detail.noHistory`)}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Approve({ settingKey, version, onCancel, onDone }: { settingKey: string; version: number | null; onCancel: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // What holds and what the approval makes of it, read from the rule's own versions.
  const [res] = useResource(() => deepResearchSettings.get(settingKey), [settingKey]);
  const detail = res.state === "ready" ? res.data : null;
  const fmt = (value: DrSettingValue) => (detail ? `${showValue(detail.type, value)}${value !== null && unitOf(detail) ? ` ${unitOf(detail)}` : ""}` : "…");
  const to = version === null ? detail?.default ?? null : detail?.versions.find((v) => v.version_number === version)?.value ?? null;
  const go = async () => {
    setBusy(true);
    setError(null);
    try {
      await deepResearchSettings.approve(settingKey, version, reason.trim());
      waitingChanged();
      onDone();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    // Nothing is approved before the person has seen what it changes: the comparison read, or its failure said.
    <ConfirmDialog open marker="dr-approve" busy={busy} error={error ?? (res.state === "failed" || res.state === "not-found" ? (res.state === "failed" ? res.message : t(`${D}.approve.unread`)) : null)}
      confirmDisabled={res.state !== "ready"}
      title={version === null ? t(`${D}.approve.withdrawTitle`) : tv(`${D}.approve.title`, { version })}
      rows={[
        { label: t(`${D}.approve.rule`), value: detail ? labelOf(detail) : settingKey },
        { label: t(`${D}.approve.from`), value: detail ? fmt(detail.value) : "…" },
        { label: version === null ? t(`${D}.approve.toDefault`) : t(`${D}.approve.to`), value: detail ? fmt(to) : "…" },
      ]}
      text={t(`${D}.approve.consequence`)}
      confirmLabel={t(`${D}.approve.${version === null ? "confirmWithdraw" : "confirm"}`)} cancelLabel={t(`${D}.approve.cancel`)}
      onConfirm={() => void go()} onCancel={onCancel}>
      <Field label={t(`${D}.approve.reason`)}>
        <TextInput value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} />
      </Field>
    </ConfirmDialog>
  );
}

function Propose({ detail, onSaved, onDirty }: { detail: DrSettingDetail; onSaved: (version: number) => void; onDirty: (value: boolean) => void }) {
  const kind = inputKind(detail.type);
  const [raw, setRaw] = useState(() => toInput(detail.type, detail.value));
  const [source, setSource] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const [leaveHref, setLeaveHref] = useState<string | null>(null);
  const dirty = raw !== toInput(detail.type, detail.value) || !!source.trim() || !!note.trim();
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  useEffect(() => {
    if (!dirty) return;
    const unload = (e: BeforeUnloadEvent) => e.preventDefault();
    const leave = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const link = (e.target as Element).closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || link.target || link.download || link.origin !== location.origin || link.pathname === location.pathname) return;
      e.preventDefault(); setLeaveHref(link.pathname + link.search + link.hash);
    };
    window.addEventListener("beforeunload", unload); document.addEventListener("click", leave, true);
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", leave, true); };
  }, [dirty]);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const parsed = parseInput(detail.type, raw);
    if (!parsed.ok) {
      setError(t(`${D}.propose.invalid.${parsed.reason}`));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await deepResearchSettings.propose(detail.key, { value: parsed.value, source_url: source.trim(), note: note.trim() });
      onSaved(saved.version_number); setRaw(toInput(detail.type, detail.value)); setSource(""); setNote("");
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  };
  const valueLabel = kind === "lines" ? `${t(`${D}.propose.value`)} · ${t(`${D}.propose.lines`)}` : t(`${D}.propose.value`);
  return (
    <form data-dr-propose onSubmit={(e) => void submit(e)} className="flex min-w-0 flex-col gap-3">
      {leaveHref ? <InlineConfirm message={t(`${D}.draftGuard`)} action={t(`${D}.discardDraft`)} onCancel={() => setLeaveHref(null)} onConfirm={() => router.push(leaveHref)} /> : null}
      <h4 className="text-sm font-semibold">{t(`${D}.propose.title`)}</h4>
      <Field label={valueLabel}>
        {kind === "decision" ? (
          <Select disabled={busy} value={raw} onChange={(e) => setRaw(e.target.value)}>
            <option value="true">{t(`${D}.yes`)}</option>
            <option value="false">{t(`${D}.no`)}</option>
          </Select>
        ) : kind === "status" ? (
          <Select disabled={busy} value={raw} onChange={(e) => setRaw(e.target.value)}>
            {STATUS_VALUES.map((v) => <option key={v} value={v}>{t(`${D}.status.${v}`)}</option>)}
          </Select>
        ) : kind === "lines" ? (
          <TextArea disabled={busy} aria-label={t(`${D}.propose.value`)} value={raw} onChange={(e) => setRaw(e.target.value)} />
        ) : (
          <TextInput
            disabled={busy} value={raw}
            onChange={(e) => setRaw(e.target.value)}
            inputMode={kind === "whole" ? "numeric" : kind === "decimal" ? "decimal" : undefined}
            type={kind === "date" ? "date" : kind === "url" ? "url" : "text"}
          />
        )}
      </Field>
      <div className="flex flex-wrap gap-2">
        <Field label={t(`${D}.propose.source`)} className="w-full min-w-0 sm:min-w-64 sm:flex-1">
          <TextInput disabled={busy} type="url" value={source} maxLength={500} onChange={(e) => setSource(e.target.value)} />
        </Field>
        <Field label={t(`${D}.propose.note`)} className="w-full min-w-0 sm:min-w-64 sm:flex-1">
          <TextInput disabled={busy} value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} />
        </Field>
      </div>
      {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
      <div className="flex flex-wrap gap-2"><Button type="submit" variant="primary" disabled={busy}>{t(`${D}.propose.submit`)}</Button><Button disabled={busy || !dirty} onClick={() => { setRaw(toInput(detail.type, detail.value)); setNote(""); setSource(""); setError(null); }}>{t(`${D}.revertDraft`)}</Button></div>
    </form>
  );
}
