"use client";

// Profil → Pravidla (D-17, settings-backends SB7, #853): the client's data posture and the ceiling on
// its studies' wallets. Any member reads them; an organization OWNER or ADMIN sets them where they
// are shown (input standard I3/I4). An unset posture reads CLASSIFIED, never open: absence is not
// consent. No ceiling reads "bez stropu", never 0. Opening the client to public research is a
// consequential act and asks first (I7); back to CLASSIFIED is the safe direction and is at once.
// Until the route is deployed (http_404) it says "V AIA zatím není".

import { useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { ApiError, type ClientRulesOf, clientRules } from "@/lib/api";
import { relative } from "@/lib/format";
import { ChoiceChips } from "../../ui/ChoiceChips";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { Stepper } from "../../ui/Stepper";
import { Button } from "../../rehome/ui";
import { said } from "./KnowledgeLibrary";

const R = "aia.profile.clientRules";
type Posture = "OPEN" | "CLASSIFIED";
const POSTURES: readonly Posture[] = ["OPEN", "CLASSIFIED"];
const MAX_CEILING_USD = 1_000_000;
const usd = (n: number) => `${n.toLocaleString("cs-CZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;

type Read = { state: "loading" } | { state: "not_yet" } | { state: "refused"; message: string } | { state: "ready"; rules: ClientRulesOf };
const wellFormed = (r: unknown): r is ClientRulesOf =>
  !!r && typeof r === "object" && ((r as ClientRulesOf).effective_posture === "OPEN" || (r as ClientRulesOf).effective_posture === "CLASSIFIED");

export function ClientRulesEditor({ clientId, clientName, mayAdminister }: { clientId: string; clientName?: string; mayAdminister: boolean }) {
  const [read, setRead] = useState<Read>({ state: "loading" });
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    clientRules.get(clientId).then(
      (r) => { if (live) setRead(wellFormed(r) ? { state: "ready", rules: r } : { state: "refused", message: t(`${R}.malformed`) }); },
      (e: unknown) => { if (live) setRead(e instanceof ApiError && e.status === 404 && e.code === "http_404" ? { state: "not_yet" } : { state: "refused", message: said(e) }); },
    );
    return () => { live = false; };
  }, [clientId]);

  if (read.state === "loading") return null;
  if (read.state === "not_yet") return <p data-not-yet className="mt-3 inline-flex rounded-sm border border-dashed border-border-strong px-2 py-0.5 text-xs text-ink-muted">{t("aia.settings.panel.notYet")}</p>;
  if (read.state === "refused") return <p role="alert" className="mt-3 text-sm text-status-fault">{read.message}</p>;
  const rules = read.rules;

  /** One change sent; the answer is what is now in force. A refusal is said at the rules, and thrown for the stepper. */
  const send = async (changes: Parameters<typeof clientRules.set>[1]) => {
    setError(null); setBusy(true);
    try { setRead({ state: "ready", rules: await clientRules.set(clientId, changes) }); }
    catch (e) { setError(said(e)); throw e; }
    finally { setBusy(false); }
  };
  const choose = (p: Posture) => {
    if (p === rules.effective_posture && rules.data_posture !== null) return;
    if (p === "OPEN") setAsking(true); else void send({ data_posture: "CLASSIFIED" }).catch(() => {});
  };
  return (
    <div data-client-rules-editor className="mt-4 flex flex-col gap-4 border-t border-border pt-4">
      <div>
        <p id="client-posture-label" className="text-sm font-medium">{t(`${R}.posture`)}</p>
        <p className="text-xs leading-5 text-ink-muted">{t(`${R}.postureHelp`)}</p>
        <ChoiceChips className="mt-2" label={t(`${R}.posture`)} value={rules.effective_posture} disabled={!mayAdminister || busy}
          options={POSTURES.map((p) => ({ key: p, label: p }))} onChange={choose} />
        {rules.data_posture === null ? <p data-posture-unset className="mt-1 text-xs text-ink-muted">{t(`${R}.unset`)}</p> : null}
      </div>
      <div>
        <p className="text-sm font-medium">{t(`${R}.ceiling`)}</p>
        <p className="text-xs leading-5 text-ink-muted">{t(`${R}.ceilingHelp`)}</p>
        {mayAdminister ? (
          <div className="mt-2 flex flex-wrap items-start gap-2">
            <Stepper label={t(`${R}.ceiling`)} value={rules.wallet_ceiling_usd} min={0} max={MAX_CEILING_USD} step={10} decimals={2} unit="USD"
              onCommit={(v) => send({ wallet_ceiling_usd: v })} />
            {rules.wallet_ceiling_usd !== null ? <Button small disabled={busy} onClick={() => void send({ wallet_ceiling_usd: null }).catch(() => {})}>{t(`${R}.clear`)}</Button> : null}
          </div>
        ) : rules.wallet_ceiling_usd !== null ? <p className="mt-1 font-mono text-sm">{usd(rules.wallet_ceiling_usd)}</p> : null}
        {rules.wallet_ceiling_usd === null ? <p data-no-ceiling className="mt-1 text-xs text-ink-muted">{t(`${R}.noCeiling`)}</p> : null}
      </div>
      {rules.set_at ? <p className="text-xs text-ink-faint">{tv(`${R}.changed`, { when: relative(rules.set_at) ?? rules.set_at })}</p> : null}
      {!mayAdminister ? <p className="text-xs text-ink-faint">{t(`${R}.adminOnly`)}</p> : null}
      {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
      <ConfirmDialog open={asking} marker="posture-open-dialog" busy={busy} error={asking ? error : null}
        title={tv(`${R}.openTitle`, { client: clientName ?? clientId })} text={t(`${R}.openText`)}
        confirmLabel={t(`${R}.openConfirm`)}
        onConfirm={() => void send({ data_posture: "OPEN" }).then(() => setAsking(false), () => {})}
        onCancel={() => { setAsking(false); setError(null); }} />
    </div>
  );
}
