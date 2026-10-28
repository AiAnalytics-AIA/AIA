"use client";

// The command palette (design system v3, CommandPalette): Ctrl+K, or ⌘K on Apple, from any page
// of AIA, and the search button in the page header. It goes to the four global places, Můj
// Vedoucí, every client and its recent studies (the directory's own read, made when it first
// opens) and every settings section. Typed words match accent-folded. ↑ ↓ move, Enter opens,
// Esc closes, and focus goes back to where it was. On Settings, the section menu keeps its own
// ⌘K and this one leaves the key to it (it marks the key taken first).

import { useRouter } from "next/navigation";
import { type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { t, tv } from "@/i18n/t";
import { type ClientCard, workspace } from "@/lib/api";
import { type PaletteEntry, type PaletteGroup, clientEntries, matchEntries, moveSelection, staticEntries } from "@/lib/command-palette";
import { guardedNavigate } from "@/lib/guarded-navigation";
import { Icon, type IconName } from "../rehome/icons";
import { appleKeys } from "./settings/sections";

type Clients = { state: "idle" | "loading" | "failed" } | { state: "ready"; data: ClientCard[] };

const GROUP_ICON: Record<PaletteGroup, IconName> = { go: "next", clients: "client", studies: "research", settings: "settings" };
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";
const noChange = () => () => {};

function otherModalOpen(own: HTMLDialogElement | null): boolean {
  try {
    const m = document.querySelector("dialog:modal");
    return m !== null && m !== own;
  } catch {
    return false;
  }
}

/** The app router when it is mounted; outside it (a test's shell, a static page) none. */
function useOptionalRouter(): { push: (href: string) => void } | null {
  try {
    return useRouter();
  } catch {
    return null;
  }
}

export function CommandPalette() {
  const router = useOptionalRouter();
  const apple = useSyncExternalStore(noChange, appleKeys, () => null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [sel, setSel] = useState(0);
  const [clients, setClients] = useState<Clients>({ state: "idle" });
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const returnTo = useRef<HTMLElement | null>(null);
  const openRef = useRef(open);
  useEffect(() => { openRef.current = open; }, [open]);

  const show = useCallback(() => {
    returnTo.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setQuery("");
    setSel(0);
    setOpen(true);
    setClients((c) => {
      if (c.state === "ready" || c.state === "loading") return c;
      workspace.clients().then((data) => setClients({ state: "ready", data }), () => setClients({ state: "failed" }));
      return { state: "loading" };
    });
  }, []);
  const hide = useCallback(() => {
    setOpen(false);
    returnTo.current?.focus();
  }, []);

  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (open && !d.open) {
      if (typeof d.showModal === "function") d.showModal(); else d.setAttribute("open", "");
      input.current?.focus();
    } else if (!open && d.open) {
      if (typeof d.close === "function") d.close(); else d.removeAttribute("open");
    }
  }, [open]);

  // Ctrl+K / ⌘K: never a key another handler took (Settings' section menu), never one held
  // down, never from a field outside the palette, never under another modal.
  useEffect(() => {
    const key = (e: globalThis.KeyboardEvent) => {
      if (e.defaultPrevented || e.repeat || e.key.toLowerCase() !== "k" || e.altKey || e.shiftKey) return;
      if (!(appleKeys() ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey)) return;
      const target = e.target instanceof Element ? e.target : null;
      if (target?.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])") && !dialog.current?.contains(target)) return;
      if (otherModalOpen(dialog.current)) return;
      e.preventDefault();
      if (openRef.current) hide(); else show();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [show, hide]);

  const entries = useMemo(
    () => matchEntries([...staticEntries(), ...(clients.state === "ready" ? clientEntries(clients.data) : [])], query),
    [clients, query],
  );
  const active = entries.length ? Math.min(sel, entries.length - 1) : -1;

  // Through a link's click, so a stage's leave guard (Návrh's refused draft) can stop it.
  const go = (entry: PaletteEntry) => {
    setOpen(false);
    guardedNavigate(entry.href, (url) => (router ? router.push(url) : window.location.assign(url)));
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setSel(moveSelection(active, e.key === "ArrowDown" ? 1 : -1, entries.length));
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      go(entries[active]!);
    }
  };

  const chord = apple === null ? null : apple ? "⌘K" : "Ctrl K";
  return (
    <>
      <button
        type="button"
        onClick={show}
        aria-haspopup="dialog"
        aria-keyshortcuts="Control+K Meta+K"
        className={`inline-flex h-8 min-w-[200px] items-center gap-2 rounded-control border border-border bg-surface pl-2.5 pr-1.5 text-[13px] text-ink-faint hover:border-border-strong hover:text-ink-muted ${FOCUS}`}
      >
        <Icon name="search" size={14} />
        <span className="flex-1 text-left">{t("aia.palette.open")}…</span>
        {chord ? <kbd className="rounded-[4px] border border-border bg-surface-raised px-1 font-mono text-[11px] text-ink-muted">{chord}</kbd> : null}
      </button>
      <dialog
        ref={dialog}
        aria-label={t("aia.palette.title")}
        onCancel={(e) => { e.preventDefault(); hide(); }}
        onClick={(e) => { if (e.target === dialog.current) hide(); }}
        className="m-0 mx-auto mt-[12vh] w-[600px] max-w-[calc(100%-32px)] overflow-hidden rounded-panel border border-border bg-surface-overlay p-0 text-ink shadow-[var(--shadow-overlay)] backdrop:bg-ink/20"
      >
        {open ? (
          <div>
            <div className="flex items-center gap-2.5 border-b border-border px-3.5">
              <Icon name="search" size={16} />
              <input
                ref={input}
                type="text"
                role="combobox"
                aria-expanded="true"
                aria-controls="aia-palette-list"
                aria-activedescendant={active >= 0 ? `aia-palette-${active}` : undefined}
                aria-label={t("aia.palette.title")}
                placeholder={t("aia.palette.placeholder")}
                value={query}
                onChange={(e) => { setQuery(e.target.value); setSel(0); }}
                onKeyDown={onKey}
                className="h-12 flex-1 border-0 bg-transparent text-[15px] outline-none"
              />
            </div>
            <ul id="aia-palette-list" role="listbox" aria-label={t("aia.palette.title")} className="max-h-[380px] overflow-auto p-1.5">
              {entries.map((entry, i) => {
                const header = i === 0 || entries[i - 1]!.group !== entry.group ? t(`aia.palette.groups.${entry.group}`) : null;
                return (
                  <li key={entry.id} role="presentation">
                    {header ? <div role="presentation" className="px-2.5 pb-1 pt-2 text-[12px] font-medium text-ink-faint">{header}</div> : null}
                    <div
                      id={`aia-palette-${i}`}
                      role="option"
                      aria-selected={i === active}
                      onMouseMove={() => setSel(i)}
                      onClick={() => go(entry)}
                      className={`flex min-h-9 cursor-pointer items-center gap-2.5 rounded-card px-2.5 text-[13px] ${i === active ? "bg-signal-wash text-ink" : "text-ink"}`}
                    >
                      <span className={i === active ? "text-signal" : "text-ink-faint"}><Icon name={GROUP_ICON[entry.group]} size={16} /></span>
                      <span className="min-w-0 flex-1 truncate">
                        {entry.label}
                        {entry.sub ? <span className="ml-1.5 text-[12px] text-ink-faint">{entry.sub}</span> : null}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
            {entries.length === 0 ? <p role="status" className="px-4 pb-5 pt-1 text-center text-[13px] text-ink-faint">{tv("aia.palette.none", { query })}</p> : null}
            {clients.state === "loading" ? <p role="status" className="px-4 pb-2 text-[12px] text-ink-faint">{t("aia.palette.clientsLoading")}</p> : null}
            {clients.state === "failed" ? <p role="status" className="px-4 pb-2 text-[12px] text-ink-faint">{t("aia.palette.clientsUnread")}</p> : null}
            <div className="flex items-center gap-3.5 border-t border-border bg-surface px-3.5 py-2 text-[12px] text-ink-faint">
              <span><kbd className="font-mono">↑ ↓</kbd> {t("aia.palette.hintMove")}</span>
              <span><kbd className="font-mono">Enter</kbd> {t("aia.palette.hintOpen")}</span>
              <span><kbd className="font-mono">Esc</kbd> {t("aia.palette.hintClose")}</span>
            </div>
          </div>
        ) : null}
      </dialog>
    </>
  );
}
