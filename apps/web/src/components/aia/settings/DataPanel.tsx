"use client";

// Správa dat (settings-redesign chunk 11, Data board): deleting a client, and the records AIA
// keeps after it (settings-backends SB5, #850). OWNER or ADMIN. The deletion is one I7 modal: what
// is deleted and what stays, with the server's counts, a one-time confirmation the server issued
// for this person, an acknowledgement switch, and the act named, "Smazat klienta". A count the
// server did not establish reads "nezjištěno", never 0. Until the routes are deployed (a 404 no
// route answers, http_404, or the 405 of the old GET preview), both parts read "V AIA zatím
// není"; a 404 not_found is a client that no longer exists.

import { useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type AdminClient, ApiError, type ClientDeletionPreview, type KeptRecord, clientDeletion } from "@/lib/api";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { Switch } from "../../ui/Switch";
import { Button, Select } from "../../rehome/ui";
import { ChoiceChips } from "../../ui/ChoiceChips";
import { describeError } from "./errors";
import { InfoButton } from "./InfoButton";
import { FOCUS } from "../../ui/parts";

const D = "aia.settings.panel.data";
const CARD = "rounded-md border border-border bg-surface-raised px-6 py-5";
type Part<T> = { ok: true; data: T } | { ok: false; message: string };

const count = (n: number | null | undefined) => (n === null || n === undefined ? t(`${D}.unknownCount`) : new Intl.NumberFormat("cs-CZ").format(n));
const DELETED = ["studies", "working_revisions", "knowledge_items", "sources", "files", "runs", "artifacts"] as const;
const KEPT = ["usage_rows", "approval_rows", "audit_rows"] as const;
const KNOWN_RECORDS = new Set(["usage_rows", "budget_holds", "approval_rows", "audit_rows", "deleted_clients"]);

/** The route is not deployed: no route answered (http_404), or the old GET preview's 405. */
/** The one destructive action on Settings, drawn as the prototype's danger button: fault-red, so it
 *  reads apart from every other action (F12). Local, not a shared variant: lane A owns the primitives. */
function DangerButton({ disabled, onClick, children }: { disabled?: boolean; onClick: () => void; children: string }) {
  return (
    <button type="button" data-danger disabled={disabled} onClick={onClick}
      className={`inline-flex min-h-9 items-center gap-1.5 rounded-sm border border-status-fault bg-surface-raised px-3 text-sm font-medium whitespace-nowrap text-status-fault transition-colors duration-[var(--duration-confirm)] hover:bg-status-fault-wash disabled:opacity-50 ${FOCUS}`}>
      <span aria-hidden="true">🗑</span>{children}
    </button>
  );
}

const notBuilt = (e: unknown) => e instanceof ApiError && ((e.status === 404 && e.code === "http_404") || e.status === 405);
const gone = (e: unknown) => e instanceof ApiError && e.status === 404 && e.code === "not_found";

function NotYetChip() {
  return <p data-not-yet className="mt-3 inline-flex rounded-sm border border-dashed border-border-strong px-2 py-0.5 text-xs text-ink-muted">{t("aia.settings.panel.notYet")}</p>;
}

function ClientDelete({ clients, reload }: { clients: Part<AdminClient[]>; reload: () => void }) {
  const [chosen, setChosen] = useState<string | null>(null);
  const [preview, setPreview] = useState<ClientDeletionPreview | null>(null);
  const [notYet, setNotYet] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ack, setAck] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const list = clients.ok ? clients.data : [];
  const open = async (clientId: string) => {
    setError(null); setDone(null); setAck(false); setBusy(true);
    try { setPreview(await clientDeletion.preview(clientId)); }
    catch (e) {
      if (notBuilt(e)) setNotYet(true);
      else if (gone(e)) { setChosen(null); setDone(t(`${D}.gone`)); reload(); }
      else setError(describeError(e));
    } finally { setBusy(false); }
  };
  // Files the store could not delete yet: the client has left the list, so the retry is kept here
  // with the token, and repeating the delete (already_deleted) retries only those files.
  const [waiting, setWaiting] = useState<{ client_id: string; name: string; token: string } | null>(null);
  const finish = (target: { client_id: string; name: string; token: string }, failed: number) => {
    setWaiting(failed > 0 ? target : null);
    setDone(failed > 0 ? tv(`${D}.deletedSomeWaiting`, { name: target.name, n: failed }) : tv(`${D}.deleted`, { name: target.name }));
  };
  const retryFiles = async () => {
    if (!waiting) return;
    setBusy(true); setError(null);
    try { finish(waiting, (await clientDeletion.remove(waiting.client_id, waiting.token)).objects_failed); reload(); }
    catch (e) { setError(describeError(e)); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    if (!preview) return;
    setBusy(true); setError(null);
    try {
      const target = { client_id: preview.client_id, name: preview.name, token: preview.confirm_token };
      const r = await clientDeletion.remove(target.client_id, target.token);
      setPreview(null); setChosen(null);
      finish(target, r.objects_failed);
      reload();
    } catch (e) {
      if (gone(e)) { setPreview(null); setChosen(null); setDone(t(`${D}.gone`)); reload(); return; }
      if (e instanceof ApiError && e.code === "client_has_active_work") {
        const runs = Array.isArray(e.details.run_ids) ? (e.details.run_ids as unknown[]).map(String) : [];
        setError(tv(`${D}.activeWork`, { runs: runs.join(", ") || "—" }));
      } else if (e instanceof ApiError && (e.code === "confirmation_invalid" || e.code === "confirmation_expired")) {
        setError(e.message);
      } else setError(describeError(e));
    } finally { setBusy(false); }
  };
  const [about, setAbout] = useState(false);
  return (
    <section data-client-delete aria-labelledby="data-del-h" className={CARD}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <h2 id="data-del-h" className="text-base font-semibold">{t(`${D}.clientDelete`)}</h2>
          <InfoButton label={t(`${D}.deleteInfo`)} controls="data-del-about" expanded={about} onToggle={() => setAbout((v) => !v)} title={t(`${D}.clientDeleteHelp`)} />
        </div>
        {/* Irreversible is the one fault-toned chip here (prototype v99's "chip bad"). */}
        <span data-irreversible className="inline-flex min-h-[22px] items-center gap-1 rounded-pill border border-status-fault/50 bg-status-fault-wash px-2 text-xs text-status-fault"><span aria-hidden="true">⚠</span>{t(`${D}.irreversible`)}</span>
      </div>
      <p id="data-del-about" hidden={!about} className="mt-1 text-sm leading-6 text-ink-muted">{t(`${D}.clientDeleteHelp`)}</p>
      {notYet ? <NotYetChip /> : <>
        {!clients.ok ? <p role="alert" className="mt-2 text-sm text-status-fault">{clients.message}</p> : !list.length ? <p className="mt-2 text-sm text-ink-muted">{t(`${D}.noClients`)}</p> : (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {/* A few clients as one segmented bar, as the prototype draws it; more as a select, since the
                list is unbounded and a bar of thirty is thirty rows on a phone (review of #870). */}
            <span className="text-xs text-ink-muted" aria-hidden="true">{t(`${D}.client`)}</span>
            {list.length <= SEGMENTED_MAX ? (
              <ChoiceChips look="segmented" label={t(`${D}.client`)} value={chosen} options={list.map((c) => ({ key: c.client_id, label: c.name }))} onChange={setChosen} />
            ) : (
              <Select aria-label={t(`${D}.client`)} value={chosen ?? ""} onChange={(e) => setChosen(e.target.value || null)} className="min-w-56">
                <option value="">{t(`${D}.chooseClient`)}</option>
                {list.map((c) => <option key={c.client_id} value={c.client_id}>{c.name}</option>)}
              </Select>
            )}
          </div>
        )}
        {/* What a deletion takes and what it keeps, in the open before the confirmation counts them
            (prototype v99's Smaže se / Zůstane); the counts are the confirmation's, from the server. */}
        {chosen ? (
          <div data-delete-inline className="mt-3 grid gap-3 sm:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold"><span aria-hidden="true">🗑 </span>{t(`${D}.willDelete`)}</h3>
              <ul className="mt-1 text-[13px] leading-6 text-ink-muted">{DELETED.map((k) => <li key={k}>{t(`${D}.deletedKind.${k}`)}</li>)}</ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold"><span aria-hidden="true">🛡 </span>{t(`${D}.willStay`)}</h3>
              <ul className="mt-1 text-[13px] leading-6 text-ink-muted">{KEPT.map((k) => <li key={k}>{t(`${D}.keptKind.${k}`)}</li>)}</ul>
            </div>
          </div>
        ) : null}
        {list.length ? (
          <div className="mt-3">
            <DangerButton disabled={!chosen || busy} onClick={() => { if (chosen) void open(chosen); }}>{(() => { const name = list.find((c) => c.client_id === chosen)?.name; return name ? tv(`${D}.deleteThis`, { name }) : t(`${D}.deleteNone`); })()}</DangerButton>
          </div>
        ) : null}
        {done ? <p role="status" data-deleted className="mt-3 text-sm">{done}</p> : null}
        {waiting ? <Button className="mt-2" disabled={busy} onClick={() => void retryFiles()}>{t(`${D}.retryFiles`)}</Button> : null}
        {error && !preview ? <p role="alert" className="mt-3 text-sm text-status-fault">{error}</p> : null}
      </>}
      {preview ? (
        <ConfirmDialog open marker="client-delete-dialog" busy={busy} error={error}
          title={tv(`${D}.dialogTitle`, { name: preview.name })}
          text={<>
            <h4 className="text-sm font-semibold">{t(`${D}.willDelete`)}</h4>
            <ul data-will-delete className="mt-1 grid grid-cols-[1fr_auto] gap-x-4 text-[13px] leading-6">
              {DELETED.map((k) => <li key={k} className="contents"><span>{t(`${D}.deletedKind.${k}`)}</span><span className="text-right font-mono tabular-nums">{count(preview.deleted[k])}</span></li>)}
            </ul>
            <h4 className="mt-3 text-sm font-semibold">{t(`${D}.willStay`)}</h4>
            <ul data-will-stay className="mt-1 grid grid-cols-[1fr_auto] gap-x-4 text-[13px] leading-6">
              {KEPT.map((k) => <li key={k} className="contents"><span>{t(`${D}.keptKind.${k}`)}</span><span className="text-right font-mono tabular-nums">{count(preview.kept[k])}</span></li>)}
            </ul>
            <h4 className="mt-3 text-sm font-semibold">{t(`${D}.untilSdl2`)}</h4>
            <ul data-until-sdl2 className="mt-1 grid grid-cols-[1fr_auto] gap-x-4 text-[13px] leading-6">
              <li className="contents"><span>{t(`${D}.sdl2.population_children`)}</span><span className="text-right font-mono tabular-nums">{count(preview.remains_until_sdl2.population_children)}</span></li>
              <li className="contents"><span>{t(`${D}.sdl2.replaced_source_readings`)}</span><span className="text-right font-mono tabular-nums">{count(preview.remains_until_sdl2.replaced_source_readings)}</span></li>
            </ul>
            <div className="mt-3 flex items-center gap-2"><Switch on={ack} onChange={setAck} label={t(`${D}.ack`)} showLabel /></div>
          </>}
          confirmLabel={t(`${D}.confirm`)} cancelLabel={t(`${D}.cancel`)}
          onConfirm={() => { if (ack) void remove(); else setError(t(`${D}.ackNeeded`)); }}
          onCancel={() => { setPreview(null); setError(null); }} />
      ) : null}
    </section>
  );
}

/** `version` moves after a deletion: the counts it changed (deleted clients, audit rows) are read again. */
function KeptRecords({ version }: { version: number }) {
  const [read, setRead] = useState<{ state: "loading" } | { state: "ready"; data: KeptRecord[] } | { state: "not_yet" } | { state: "refused"; message: string }>({ state: "loading" });
  useEffect(() => {
    let live = true;
    clientDeletion.kept().then(
      // A body that is not a list is not "nothing kept": said so, never drawn as an empty table.
      (data) => { if (live) setRead(Array.isArray(data) ? { state: "ready", data } : { state: "refused", message: t(`${D}.malformed`) }); },
      (e: unknown) => { if (live) setRead(notBuilt(e) ? { state: "not_yet" } : { state: "refused", message: describeError(e) }); },
    );
    return () => { live = false; };
  }, [version]);
  const head = "px-2 py-1.5 text-left text-xs font-normal text-ink-faint";
  const cell = "border-t border-border px-2 py-2 align-top text-sm";
  const [about, setAbout] = useState(false);
  return (
    <section data-kept-records aria-labelledby="data-kept-h" className={CARD}>
      <div className="flex items-center gap-1">
        <h2 id="data-kept-h" className="text-base font-semibold">{t(`${D}.keptRecords`)}</h2>
        <InfoButton label={t(`${D}.keptInfo`)} controls="data-kept-about" expanded={about} onToggle={() => setAbout((v) => !v)} title={t(`${D}.keptRecordsHelp`)} />
      </div>
      <p id="data-kept-about" hidden={!about} className="mt-1 text-sm leading-6 text-ink-muted">{t(`${D}.keptRecordsHelp`)}</p>
      {read.state === "loading" ? null : read.state === "not_yet" ? <NotYetChip /> : read.state === "refused" ? <p role="alert" className="mt-2 text-sm text-status-fault">{read.message}</p> : (
        <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[32rem] border-collapse">
          <thead><tr><th scope="col" className={head}>{t(`${D}.col.record`)}</th><th scope="col" className={head}>{t(`${D}.col.count`)}</th><th scope="col" className={head}>{t(`${D}.col.keptFor`)}</th><th scope="col" className={head}>{t(`${D}.col.why`)}</th></tr></thead>
          <tbody>{read.data.map((r) => (
            <tr key={r.record} data-kept={r.record}>
              <td className={`${cell} font-medium`}>{KNOWN_RECORDS.has(r.record) ? t(`${D}.record.${r.record}`) : r.record}</td>
              <td className={`${cell} font-mono tabular-nums`}>{count(r.count)}</td>
              <td className={cell}>{r.kept_for === "indefinite" ? t(`${D}.indefinite`) : r.kept_for}</td>
              <td className={`${cell} text-ink-muted`}>{KNOWN_RECORDS.has(r.record) ? t(`${D}.why.${r.record}`) : r.why}</td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
    </section>
  );
}


/** Up to this many clients the picker is the segmented bar; beyond it, a select. */
const SEGMENTED_MAX = 5;
export function DataPanel({ mayAdminister, clients, reload }: { mayAdminister: boolean; clients: Part<AdminClient[]>; reload: () => void }) {
  const [kept, setKept] = useState(0);
  if (!mayAdminister) return <section className={CARD}><p className="text-sm text-ink-muted">{t(`${D}.adminOnly`)}</p></section>;
  // A deletion reloads the clients and reads the kept records again.
  const afterDelete = () => { reload(); setKept((n) => n + 1); };
  return <div className="flex flex-col gap-4"><ClientDelete clients={clients} reload={afterDelete} /><KeptRecords version={kept} /></div>;
}
