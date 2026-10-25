"use client";

// The settings section menu (prototype v54, settings-redesign F12b): the left column of sections
// gives way to "Nastavení › <sekce> ⌄" in the top bar. It opens on a click or on ⌘K / Ctrl+K from
// anywhere on the page; a search matches a section's name, its line and its keywords (práh, Brave,
// rozpočet); the sections stand in three columns, each with its icon and line; Enter opens the first
// match and Esc closes it, focus back on the button. A section is its address (#deep_research): a
// link, so a deep link, the back button and a new tab all work as before. The coral counts say what
// waits on an administrator, read from the API (rules live needs approved, prompts saved and not yet
// switched on); a count that could not be read is not drawn, never guessed.

import { type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { t, tv } from "@/i18n/t";
import { type PromptSlotSummary, admin, deepResearchSettings } from "@/lib/api";
import { Icon, type IconName } from "../../rehome/icons";
import { waitingPrompts } from "./SystemPromptsPanel";
import { FOCUS, useDismiss } from "../../ui/parts";
import { SECTIONS, SECTION_GROUPS, type SectionId, sectionFromHash } from "./sections";

const P = "aia.settings.panel";
const M = `${P}.menu`;

/** Each section's icon, from the interface's one set. */
const ICON: Record<SectionId, IconName> = {
  methodology: "intelligence", prompts: "comment", deep_research: "world", ai: "assistant",
  access: "client", studies: "projects", audit: "library", system: "running", reference: "knowledge", data: "archive",
};

/** What waits on the person, per section, as the API said it; absent: not read, or nothing. */
export type SectionCounts = Partial<Record<SectionId, number>>;

const subscribe = (on: () => void) => {
  window.addEventListener("hashchange", on);
  window.addEventListener("popstate", on);
  return () => { window.removeEventListener("hashchange", on); window.removeEventListener("popstate", on); };
};

/** The section the address names; Metodika when it names none, as the page opens. */
export function useSection(): SectionId {
  return useSyncExternalStore(subscribe, () => sectionFromHash() ?? "methodology", () => "methodology");
}

/** Whether a section matches what is typed: its name, its line or its keywords, accents ignored. */
export function sectionMatches(id: SectionId, query: string): boolean {
  const fold = (s: string) => s.toLocaleLowerCase("cs").normalize("NFD").replace(/\p{M}/gu, "");
  const q = fold(query.trim());
  if (!q) return true;
  return fold(`${t(`${P}.tabs.${id}`)} ${t(`${P}.tabSubtitles.${id}`)} ${t(`${M}.keywords.${id}`)}`).includes(q);
}

/**
 * What waits on an administrator, read from the API: Deep Research's rules live still needs
 * approved, and prompts with a saved version not yet switched on. A member is shown no count, and a
 * read that fails leaves its count out: unknown is never a number.
 */
async function readSectionCounts(mayAdminister: boolean): Promise<SectionCounts> {
  if (!mayAdminister) return {};
  const [dr, prompts] = await Promise.allSettled([deepResearchSettings.list(), admin.prompts()]);
  const counts: SectionCounts = {};
  if (dr.status === "fulfilled" && Array.isArray(dr.value?.missing_for_live)) counts.deep_research = dr.value.missing_for_live.length;
  if (prompts.status === "fulfilled" && Array.isArray(prompts.value)) counts.prompts = waitingPrompts(prompts.value as PromptSlotSummary[]);
  return counts;
}

function Count({ n }: { n: number | undefined }) {
  if (!n) return null;
  return <span data-section-count className="inline-flex min-w-5 items-center justify-center rounded-pill bg-status-you px-1.5 text-[11px] font-semibold leading-5 text-on-status-you">{n}</span>;
}

export function SectionMenu({ mayAdminister }: { mayAdminister: boolean | null }) {
  const current = useSection();
  const [open, setOpen] = useState(false);
  // The counts are read when the page opens and again each time the menu does: an approval made on
  // a section is counted out the next time the person looks.
  const [counts, setCounts] = useState<SectionCounts>({});
  const read = useRef(false);
  useEffect(() => {
    if (mayAdminister === null || (read.current && !open)) return;
    read.current = true;
    let live = true;
    readSectionCounts(mayAdminister).then((c) => { if (live) setCounts(c); }, () => {});
    return () => { live = false; };
  }, [mayAdminister, open]);
  const [query, setQuery] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, box, trigger);
  const show = useCallback(() => { setQuery(""); setOpen(true); }, []);
  // The search takes focus once the menu is drawn (an effect, after the commit): typing is the
  // first thing it is opened for.
  const search = useRef<HTMLInputElement>(null);
  useEffect(() => { if (open) search.current?.focus(); }, [open]);

  // ⌘K / Ctrl+K from anywhere on the page opens it (and closes it again, as the prototype does).
  useEffect(() => {
    const key = (e: globalThis.KeyboardEvent) => {
      if (e.key.toLowerCase() !== "k" || !(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) return;
      e.preventDefault();
      setQuery("");
      setOpen((o) => !o);
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, []);

  const hits = useMemo(() => SECTIONS.filter((id) => sectionMatches(id, query)), [query]);
  const total = Object.values(counts).reduce((n, c) => n + (c ?? 0), 0);
  const go = (id: SectionId) => {
    setOpen(false);
    // The address is replaced, not pushed, keeping the history entry's own state: the framework's
    // router keeps what it stored there (as the tabs before did); the page follows the event.
    if (window.location.hash !== `#${id}`) {
      window.history.replaceState(window.history.state, "", `#${id}`);
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    }
    trigger.current?.focus();
  };
  const onSearchKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && hits[0]) { e.preventDefault(); go(hits[0]); }
  };

  return (
    <div ref={box} data-section-menu className="relative inline-flex items-center gap-2">
      <button ref={trigger} type="button" aria-haspopup="dialog" aria-expanded={open} aria-controls="settings-section-menu"
        aria-label={`${tv(`${M}.button`, { section: t(`${P}.tabs.${current}`) })}${total ? `, ${tv(`${M}.waiting`, { n: total })}` : ""}`}
        onClick={() => (open ? setOpen(false) : show())}
        className={`inline-flex min-h-11 items-center gap-1.5 rounded-sm px-1.5 text-[13px] hover:bg-surface-sunken sm:min-h-8 ${FOCUS}`}>
        <Icon name={ICON[current]} size={14} className="text-ink-muted" />
        <span className="text-ink-muted">{t("aia.settings.title")}</span>
        <span aria-hidden="true" className="text-ink-faint">›</span>
        <b data-section-current className="font-medium text-ink">{t(`${P}.tabs.${current}`)}</b>
        <span aria-hidden="true"><Count n={total} /></span>
        <span aria-hidden="true" className="text-ink-faint">⌄</span>
      </button>
      <kbd aria-hidden="true" className="hidden rounded-[4px] border border-border px-1 font-mono text-[11px] text-ink-faint sm:inline">⌘K</kbd>
      {open ? (
        <div id="settings-section-menu" role="dialog" aria-label={t(`${M}.label`)}
          className="absolute left-0 top-full z-[var(--z-overlay)] mt-1 w-[min(56rem,calc(100vw-2rem))] rounded-md border border-border bg-surface-overlay shadow-[var(--shadow-overlay)]">
          <div className="flex items-center gap-2 border-b border-border px-4 py-2">
            <Icon name="search" size={14} className="text-ink-faint" />
            <input ref={search} type="search" aria-label={t(`${M}.search`)} placeholder={t(`${M}.placeholder`)} value={query}
              onChange={(e) => setQuery(e.target.value)} onKeyDown={onSearchKey}
              className={`min-h-11 min-w-0 flex-1 bg-transparent text-sm outline-none ${FOCUS}`} />
            <kbd aria-hidden="true" className="rounded-[4px] border border-border px-1 font-mono text-[11px] text-ink-faint">Esc</kbd>
          </div>
          <div className="grid gap-x-4 gap-y-3 p-3 md:grid-cols-3">
            {SECTION_GROUPS.map((group) => {
              const items = group.sections.filter((id) => hits.includes(id));
              if (!items.length) return null;
              return (
                <div key={group.key} role="group" aria-label={t(`${M}.groups.${group.key}`)} className="flex min-w-0 flex-col gap-0.5">
                  <p className="px-2 pb-1 text-[11px] uppercase tracking-[0.06em] text-ink-faint">{t(`${M}.groups.${group.key}`)}</p>
                  {items.map((id) => (
                    <a key={id} href={`#${id}`} data-section-link={id} aria-current={id === current ? "true" : undefined}
                      onClick={(e) => { e.preventDefault(); go(id); }}
                      className={`flex min-h-11 items-start gap-2.5 rounded-sm px-2 py-1.5 no-underline ${id === current ? "bg-signal-wash" : "hover:bg-surface-sunken"} ${FOCUS}`}>
                      <Icon name={ICON[id]} size={16} className="mt-0.5 shrink-0 text-ink-muted" />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium text-ink">{t(`${P}.tabs.${id}`)}</span>
                        <span className="block text-xs leading-4 text-ink-muted">{t(`${P}.tabSubtitles.${id}`)}</span>
                      </span>
                      {counts[id] ? <span className="sr-only">{tv(`${M}.waiting`, { n: counts[id] })}</span> : null}
                      <span aria-hidden="true"><Count n={counts[id]} /></span>
                    </a>
                  ))}
                </div>
              );
            })}
          </div>
          {!hits.length ? <p role="status" className="px-5 pb-3 text-sm text-ink-muted">{tv(`${M}.none`, { q: query.trim() })}</p> : null}
          <p aria-hidden="true" className="flex flex-wrap gap-x-4 gap-y-1 border-t border-border px-4 py-2 text-xs text-ink-faint">
            <span><kbd className="font-mono">⌘K</kbd> {t(`${M}.hintAnywhere`)}</span>
            <span><kbd className="font-mono">Enter</kbd> {t(`${M}.hintFirst`)}</span>
            <span><kbd className="font-mono">Esc</kbd> {t(`${M}.hintClose`)}</span>
          </p>
        </div>
      ) : null}
    </div>
  );
}
