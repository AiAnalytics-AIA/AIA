"use client";

// Můj Vedoucí výzkumu (ADR 0026, Accepted with 6): the signed-in researcher's own Research Lead,
// read only. Its files -- SOUL (its manner) and USER (what it knows of how you work) -- and its
// memory, personal or bound to one client. Nothing here edits them: the researcher shapes the
// Lead by talking to it in a study, and the Lead changes its own files, saying so in the reply.
// One choice is made here (plan inline-decisions chunk 2): whether the Lead's text edits are
// accepted without a click. Off by default; structure always waits for the researcher.

import { useState } from "react";

import { ApiError, researcherLead, type ResearcherLeadView } from "@/lib/api";
import type { LeadMemory } from "@/lib/lead";
import { Button } from "../rehome/ui";
import { AppShell } from "./AppShell";
import { CARD, Empty, Loaded } from "./states";
import { announceHatched } from "@/lib/rail-lead";

import { useResource } from "./useResource";

const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("cs-CZ", { dateStyle: "medium", timeStyle: "short" });
};

function File({ name, title, text, empty }: { name: string; title: string; text: string; empty: string }) {
  return (
    <section className={CARD} aria-labelledby={`lead-file-${name}`}>
      <div className="flex items-baseline justify-between gap-3">
        <h2 id={`lead-file-${name}`} className="text-base font-semibold">{title}</h2>
        <span className="font-mono text-xs text-ink-faint">{name}.md · jen ke čtení</span>
      </div>
      {text.trim() ? <pre className="mt-2 whitespace-pre-wrap font-sans text-sm leading-6 text-ink">{text}</pre> : <p className="mt-2 text-sm text-ink-muted">{empty}</p>}
    </section>
  );
}

export const AUTO_ACCEPT_LABEL = "Automaticky přijímat textové úpravy Vedoucího (formulace, ne strukturu)";

/** The researcher's standing choice: the Lead's wording edits are accepted when its turn finishes. */
export function AutoAcceptToggle({ on, onChanged }: { on: boolean; onChanged: (me: ResearcherLeadView) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The box shows the click at once; while the server answers it holds the asked value, and a
  // refusal puts it back to what the server holds (`on`).
  const [asked, setAsked] = useState<boolean | null>(null);
  const set = async (next: boolean) => {
    setBusy(true);
    setError(null);
    setAsked(next);
    try {
      onChanged(await researcherLead.setPreferences({ auto_accept_text_edits: next }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setAsked(null);
      setBusy(false);
    }
  };
  return (
    <section className={CARD} aria-labelledby="lead-preferences">
      <h2 id="lead-preferences" className="text-base font-semibold">Nastavení</h2>
      <label className="mt-2 flex items-start gap-2 text-sm leading-6">
        <input type="checkbox" className="mt-1.5" checked={asked ?? on} disabled={busy} onChange={(e) => void set(e.target.checked)} />
        <span>{AUTO_ACCEPT_LABEL}</span>
      </label>
      <p className="mt-1 text-xs text-ink-muted">Přijme se jen změna znění: textu zadání a plánu, položky seznamu, znění otázky. Nové a odebrané položky, možnosti otázek a velikost vzorku vždy čekají na vás. Každou automaticky přijatou úpravu uvidíte u artefaktu a můžete ji vrátit.</p>
      {error ? <p role="alert" className="mt-1 text-sm text-status-fault">{error}</p> : null}
    </section>
  );
}

function Memories({ items }: { items: LeadMemory[] }) {
  const personal = items.filter((m) => m.scope === "personal");
  const byClient = new Map<string, LeadMemory[]>();
  for (const m of items.filter((m) => m.scope === "client")) {
    const k = m.client_name || m.client_id || "?";
    byClient.set(k, [...(byClient.get(k) ?? []), m]);
  }
  const list = (xs: LeadMemory[]) => (
    <ul className="mt-1 flex flex-col gap-1.5">
      {xs.map((m) => <li key={m.memory_id} className="text-sm leading-6"><span>{m.text}</span> <span className="text-xs text-ink-faint">· {when(m.created_at)}</span></li>)}
    </ul>
  );
  return (
    <section className={CARD} aria-labelledby="lead-memory">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="lead-memory" className="text-base font-semibold">Paměť</h2>
        <span className="font-mono text-xs text-ink-faint">MEMORY.md · jen ke čtení</span>
      </div>
      <p className="mt-1 text-xs text-ink-muted">Osobní poznámky jdou s vámi do všech studií. Poznámky o klientovi se načtou jen ve studiích toho klienta.</p>
      <h3 className="mt-3 text-sm font-semibold">Osobní</h3>
      {personal.length ? list(personal) : <p className="text-sm text-ink-muted">Zatím nic.</p>}
      {[...byClient].map(([client, xs]) => (
        <div key={client}><h3 className="mt-3 text-sm font-semibold">Klient: {client}</h3>{list(xs)}</div>
      ))}
    </section>
  );
}

export function LeadProfilePage() {
  const [res, retry] = useResource(() => researcherLead.get(), []);
  // What the last change answered, until the page is read again.
  const [changed, setChanged] = useState<ResearcherLeadView | null>(null);
  return (
    <AppShell hero title="Můj Vedoucí výzkumu" sub="Váš vlastní Vedoucí, jeho soubory a paměť. Měníte je rozhovorem s ním, ne zde.">
      <Loaded res={res} retry={retry}>
        {(me: ResearcherLeadView) => {
          if (!me.hatched || !me.lead) {
            return (
              <Empty>
                <span className="flex flex-col items-start gap-3">
                  <span>Svého Vedoucího jste si zatím nevylíhli. Vylíhne se jednou a pak se učí s vámi ve všech vašich studiích.</span>
                  <Button variant="primary" onClick={() => void researcherLead.hatch().then(() => { announceHatched(); retry(); }, retry)}>Vylíhnout mého Vedoucího</Button>
                </span>
              </Empty>
            );
          }
          const l = changed?.lead ?? me.lead;
          return (
            <div className="flex max-w-3xl flex-col gap-4">
              <section className={CARD}>
                <h2 className="text-lg font-semibold">{l.name}</h2>
                <p className="text-sm text-ink-muted">Vylíhnut {when(l.hatched_at)} · naposledy změněn {when(l.updated_at)}</p>
                <p className="mt-2 text-sm leading-6">Chcete-li něco změnit, řekněte to Vedoucímu v kterékoli studii, například „buď stručnější“ nebo „zapomeň, že preferuji …“. Změnu provede sám a řekne vám, co upravil.</p>
              </section>
              <File name="SOUL" title="Povaha a styl práce" text={l.files.soul} empty="Zatím výchozí." />
              <File name="USER" title="Co ví o tom, jak pracujete" text={l.files.user} empty="Zatím nic: naučí se to při práci s vámi." />
              <AutoAcceptToggle on={!!l.preferences?.auto_accept_text_edits} onChanged={setChanged} />
              <Memories items={l.memories} />
            </div>
          );
        }}
      </Loaded>
    </AppShell>
  );
}
