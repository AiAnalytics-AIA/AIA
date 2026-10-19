"use client";

// "Ověřeno, přidat zdroj" (plan inline-decisions chunk 1): beside a source Deep Research captured,
// the person who opened and checked it adds it to the client's knowledge with one click. The click is
// the person's write; the server takes the URL, title and quote from the run's sealed bundle, never
// from here, and adds each URL once (a second click says it is already there and links to it).

import Link from "next/link";
import { useState } from "react";

import { ApiError, deepResearch, type VerifiedSourceAdded } from "@/lib/api";
import { VERIFY_LABEL, verifiedSourceWords } from "@/lib/verified-source";
import { Button } from "../ui";

export function VerifiedSourceButton({ studyId, clientId, runId, snapshotId, evidenceId }: {
  studyId: string; clientId: string; runId: string; snapshotId: string; evidenceId: string;
}) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<VerifiedSourceAdded | null>(null);
  const [error, setError] = useState<string | null>(null);

  const add = async () => {
    setBusy(true);
    setError(null);
    try {
      setDone(await deepResearch.addSourceToKnowledge(studyId, runId, snapshotId, evidenceId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    const w = verifiedSourceWords(clientId, done);
    return (
      <span className="inline-flex flex-wrap items-center gap-1.5 text-xs" role="status" data-verified-source={done.status}>
        <span className="font-medium text-ink">{w.label}</span>
        {w.href ? <Link href={w.href} className="underline">Otevřít ve znalostech</Link> : null}
      </span>
    );
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Button small variant="quiet" disabled={busy} onClick={() => void add()}
        title="Zdroj jste otevřeli a zkontrolovali: přidá se do znalostí klienta s citací a odkazem.">
        {busy ? "Přidávám…" : VERIFY_LABEL}
      </Button>
      {error ? <span role="alert" className="text-xs text-status-fault">{error}</span> : null}
    </span>
  );
}
