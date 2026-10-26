"use client";

// The settings section menu (prototype v54, settings-redesign F12b): the left column of sections
// gives way to "Nastavení › <sekce> ⌄" in the top bar. It opens on a click or on ⌘K / Ctrl+K from
// anywhere on the page; a search matches a section's name, its line and its keywords (práh, Brave,
// rozpočet); the sections stand in three columns, each with its icon and line; Enter opens the first
// match and Esc closes it, focus back on the button. The shortcut is the platform's (⌘ on Apple, Ctrl
// elsewhere) and never taken from a field being typed in. A section is its address (#deep_research):
// a link, so a deep link, the back button and a new tab all work as before; opening one from the page
// itself (the menu, an in-page link) pushes an entry that keeps the framework's history state
// (goToSection), so Back from another page lands on it. The coral
// counts say what waits on an administrator, read from the API (rules live needs approved, prompts
// saved and not yet switched on) when the page opens, the menu opens, the section changes and a
// section says it changed one; a count that could not be read is not drawn, never guessed.

import { type FocusEvent, type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { t, tv } from "@/i18n/t";
import { plural } from "@/lib/format";
import { type PromptSlotSummary, admin, deepResearchSettings } from "@/lib/api";
import { Icon, type IconName } from "../../rehome/icons";
import { waitingPrompts } from "./SystemPromptsPanel";
import { FOCUS, useDismiss } from "../../ui/parts";
import { SECTIONS, SECTION_GROUPS, type SectionId, WAITING_CHANGED, appleKeys, goToSection, sectionFromHash, sectionLinkClick } from "./sections";

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

/** The platform never changes under a page: nothing to subscribe to. */
const noChange = () => () => {};

/** Whether a modal dialog is open over the page: the menu would open beneath its top layer. */
function modalOpen(): boolean {
  try {
    return document.querySelector("dialog:modal") !== null;
  } catch {
    return false; // a browser without :modal has no modal dialog to sit beneath
  }
}

function Count({ n }: { n: number | undefined }) {
  if (!n) return null;
  return <span data-section-count className="inline-flex min-w-5 items-center justify-center rounded-pill bg-status-you px-1.5 text-[11px] font-semibold leading-5 text-on-status-you">{n}</span>;
}

export function SectionMenu({ mayAdminister }: { mayAdminister: boolean | null }) {
  const current = useSection();
  const [open, setOpen] = useState(false);
  // ⌘ on Apple platforms, Ctrl elsewhere: known only in the browser, so read after mount (the
  // server's page and the first render say nothing of the chord).
  const apple = useSyncExternalStore(noChange, appleKeys, () => null);
  // The counts are read when the page opens, each time the menu does, when the section changes and
  // when a section says it changed what waits (an approval, a prompt switched on): the coral total
  // on the button is never left counting what was already done.
  const [counts, setCounts] = useState<SectionCounts>({});
  const [opened, setOpened] = useState(0);
  const [changed, setChanged] = useState(0);
  useEffect(() => {
    const on = () => setChanged((n) => n + 1);
    window.addEventListener(WAITING_CHANGED, on);
    return () => window.removeEventListener(WAITING_CHANGED, on);
  }, []);
  useEffect(() => {
    if (mayAdminister === null) return;
    let live = true;
    readSectionCounts(mayAdminister).then((c) => { if (live) setCounts(c); }, () => {});
    return () => { live = false; };
  }, [mayAdminister, current, opened, changed]);
  const [query, setQuery] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, box, trigger);
  const show = useCallback(() => { setQuery(""); setOpened((n) => n + 1); setOpen(true); }, []);
  // Closed by the button or the shortcut, the focus goes back to the button: the search it was in
  // is gone, and a keyboard user keeps their place.
  const hide = useCallback(() => { setOpen(false); trigger.current?.focus(); }, []);
  const openRef = useRef(open);
  useEffect(() => { openRef.current = open; }, [open]);
  // The search takes focus once the menu is drawn (an effect, after the commit): typing is the
  // first thing it is opened for.
  const search = useRef<HTMLInputElement>(null);
  useEffect(() => { if (open) search.current?.focus(); }, [open]);

  // ⌘K (Apple) / Ctrl+K (elsewhere) from anywhere on the page opens it, and closes it again, as the
  // prototype does. Never from a field being typed in outside the menu (Ctrl+K deletes to the end
  // of the line on macOS, and moving the focus would commit a half-typed value on blur), never under
  // a modal dialog, never a key another handler took or one held down (ObjectMapPanel's guard).
  useEffect(() => {
    const key = (e: globalThis.KeyboardEvent) => {
      if (e.defaultPrevented || e.repeat || e.key.toLowerCase() !== "k" || e.altKey || e.shiftKey) return;
      if (!(appleKeys() ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey)) return;
      const target = e.target instanceof Element ? e.target : null;
      if (target?.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])") && !box.current?.contains(target)) return;
      if (modalOpen()) return;
      e.preventDefault();
      if (openRef.current) hide(); else show();
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [hide, show]);
  // Focus that leaves the menu for something outside it closes the menu (it is not modal, and an
  // open panel left over the page would cover what the focus went to).
  const onBlur = (e: FocusEvent<HTMLDivElement>) => {
    const next = e.relatedTarget;
    if (open && next instanceof Node && !box.current?.contains(next)) setOpen(false);
  };

  const chord = apple ? "⌘K" : "Ctrl K";
  const hits = useMemo(() => SECTIONS.filter((id) => sectionMatches(id, query)), [query]);
  const total = Object.values(counts).reduce((n, c) => n + (c ?? 0), 0);
  // Opened, the menu closes and the focus goes back to its button.
  const closeToButton = () => { setOpen(false); trigger.current?.focus(); };
  const go = (id: SectionId) => {
    // A new history entry with the framework's state kept, as every link to a section on the page
    // makes one (goToSection): Back returns to the section before; the page follows the event.
    goToSection(id);
    closeToButton();
  };
  const onSearchKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && hits[0]) { e.preventDefault(); go(hits[0]); }
  };

  return (
    <div ref={box} data-section-menu onBlur={onBlur} className="inline-flex items-center gap-2">
      <button ref={trigger} type="button" aria-haspopup="dialog" aria-expanded={open} aria-controls="settings-section-menu" aria-current="page"
        aria-keyshortcuts={apple === null ? undefined : apple ? "Meta+K" : "Control+K"}
        aria-label={`${tv(`${M}.button`, { section: t(`${P}.tabs.${current}`) })}${total ? `, ${tv(`${M}.waiting`, { n: total })}` : ""}`}
        onClick={() => (open ? hide() : show())}
        className={`inline-flex min-h-11 items-center gap-1.5 rounded-sm px-1.5 text-[13px] hover:bg-surface-sunken sm:min-h-8 ${FOCUS}`}>
        <Icon name={ICON[current]} size={14} className="text-ink-muted" />
        <span className="text-ink-muted">{t("aia.settings.title")}</span>
        <span aria-hidden="true" className="text-ink-faint">›</span>
        <b data-section-current className="font-medium text-ink">{t(`${P}.tabs.${current}`)}</b>
        <span aria-hidden="true"><Count n={total} /></span>
        <span aria-hidden="true" className="text-ink-faint">⌄</span>
      </button>
      {apple === null ? null : <kbd data-shortcut aria-hidden="true" className="hidden rounded-[4px] border border-border px-1 font-mono text-[11px] text-ink-faint sm:inline">{chord}</kbd>}
      {open ? (
        // Anchored to the header row, not the button (AppShell's topbar is the positioned box): the
        // button sits after the sidebar and the breadcrumb, and a panel from there ran past the
        // viewport from 768 to 1330 px. Inside the row's gutters it always fits.
        <div id="settings-section-menu" role="dialog" aria-label={t(`${M}.label`)}
          className="absolute inset-x-4 top-full z-[var(--z-overlay)] mt-1 rounded-md border border-border bg-surface-overlay shadow-[var(--shadow-overlay)] md:inset-x-6 lg:right-auto lg:w-[min(56rem,calc(100%-3rem))]">
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
                      onClick={(e) => sectionLinkClick(id, closeToButton)(e)}
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
          {/* Always in the page, so each change of what the search found is said, not only "none". */}
          <p role="status" className="sr-only">{hits.length ? plural(hits.length, t(`${M}.found.one`), t(`${M}.found.few`), t(`${M}.found.many`)) : tv(`${M}.none`, { q: query.trim() })}</p>
          {!hits.length ? <p aria-hidden="true" className="px-5 pb-3 text-sm text-ink-muted">{tv(`${M}.none`, { q: query.trim() })}</p> : null}
          <p aria-hidden="true" className="flex flex-wrap gap-x-4 gap-y-1 border-t border-border px-4 py-2 text-xs text-ink-faint">
            {apple === null ? null : <span><kbd className="font-mono">{chord}</kbd> {t(`${M}.hintAnywhere`)}</span>}
            <span><kbd className="font-mono">Enter</kbd> {t(`${M}.hintFirst`)}</span>
            <span><kbd className="font-mono">Esc</kbd> {t(`${M}.hintClose`)}</span>
          </p>
        </div>
      ) : null}
    </div>
  );
}
