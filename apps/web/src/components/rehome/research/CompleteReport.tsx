"use client";

// The study's end (research-lane-redesign chunk 8, complete-study-report B1-B5): one card at
// the top of Výsledky that says what the report holds, part by part. It reads the run as it is: a
// part is "ve zprávě" only when the report step composed it. The report is read, prepared,
// downloaded and approved in the pane's doc bar (RPT3c), never here.

import { useEffect, useState } from "react";

import { t } from "@/i18n/t";
import { ApiError, deepResearch, type DeepResearchRun, type ReportVariant, type ResearchReport, type ResearchRun, research } from "@/lib/api";
import { resultOriginKind, runOriginKinds, type OriginKind } from "@/lib/research-execution";
import { currentVariant, literatureState, reviewsFor } from "@/lib/report-variant";
import { Icon } from "../icons";
import { canReview } from "./frame";
import { useFrame } from "./frame-hook";

type Part = { label: string; detail: string; state: "in" | "pending" | "later" | "excluded" };

/**
 * What the report holds, from the run's own steps; nothing here is guessed from elsewhere.
 * The report is composed once every analysis module is done (its own step), so a part is
 * in it only when that step succeeded; the Sociomap only when the run computed one.
 * ``prepared``: the chosen variant's draft is stored. It is composed on its own, with the same
 * chapters, so its parts are in it whatever the run's own report step did (review 2).
 */
export function reportParts(
  run: { steps: readonly { kind?: string | null; node_key?: string; status: string }[] },
  literature: Part["state"] = "pending",
  prepared = false,
  origins: ReadonlySet<OriginKind> = new Set(),
): Part[] {
  const composed = prepared || run.steps.some((s) => s.kind === "research_report" && s.status === "SUCCEEDED");
  const map = run.steps.find((s) => s.node_key === "sociomap");
  const fromReport = (label: string, detail: string): Part => ({ label, detail, state: composed ? "in" : "pending" });
  return [
    fromReport("Shrnutí a dopady pro rozhodnutí", "Z AI analýzy, každé číslo z ověřené evidence"),
    fromReport("Výzkumné otázky, objekty, segmenty, hypotézy", "Osm modulů analýzy"),
    fromReport("Respondenti a výpočet", "Kdo odpovídal, populace běhu, verze metod"),
    { label: "Sociomapy", detail: "Mapy z uloženého výpočtu, se stavem metodiky", state: !map ? "later" : composed && map.status === "SUCCEEDED" ? "in" : "pending" },
    { label: "Literatura (Deep Research)", detail: literature === "excluded" ? "Jen ve variantě s vybranou rešerší" : "Vybraná rešerše, citace ze zachycených zdrojů", state: literature },
    fromReport("Tabulky všech otázek", "Podíly, průměry a intervaly ke každé otázce"),
    fromReport("Návrh studie a dotazník v příloze", "Revize návrhu, podle které běh proběhl"),
    fromReport("Omezení, původ dat a příloha evidence", `${originWords(origins)}, otisky artefaktů`),
  ];
}

/** The order a run's origin kinds are said in, so a mixed run always reads the same. */
const ORIGIN_ORDER: readonly OriginKind[] = ["SIMULATED", "MODELLED", "UNKNOWN"];

/**
 * The data's origin in words, from the kinds the run's steps and its report stated (CR-5): one
 * kind its own word, a mixed run every kind it holds, and nothing stated yet unknown -- never
 * presumed modelled.
 */
export function originWords(origins: ReadonlySet<OriginKind>): string {
  const kinds = ORIGIN_ORDER.filter((k) => origins.has(k));
  if (kinds.length === 0) return t("research.exec.originKind.UNKNOWN");
  return kinds.map((k) => t(`research.exec.originKind.${k}`)).join(" + ");
}

const MARK: Record<Part["state"], string> = {
  in: "bg-status-done text-surface-raised",
  pending: "border-[1.5px] border-border-strong",
  later: "border-[1.5px] border-dashed border-border-strong",
  excluded: "border-[1.5px] border-dashed border-border-strong",
};
const WORD: Record<Part["state"], string> = {
  in: "ve zprávě",
  pending: "čeká na přípravu zprávy",
  later: "běh ji nevytvořil",
  excluded: "není v této variantě",
};

/**
 * What the run's report holds, part by part (RPT3c): read, chosen, prepared, downloaded and approved
 * in the pane's doc bar below, never here. ``review`` is the literature review the results page
 * holds, so the literature part and the review panel never disagree; ``null`` is the run's own
 * report. A review that is not a completed review of this run goes back to ``null``.
 */
export function CompleteReport({ run, review = null, onReview }: { run: ResearchRun; review?: string | null; onReview?: (id: string | null) => void }) {
  const frame = useFrame();
  const mayReview = canReview(frame);
  // The completed reviews, and the choice they were read for: a choice is undone only against a
  // list read after it was made, never against one still loading, stale or unread.
  const [listed, setListed] = useState<{ asked: string | null; reviews: DeepResearchRun[] } | null>(null);
  const [variant, setVariant] = useState<ReportVariant | null>(null);
  const [status, setStatus] = useState<ResearchReport | null | "hidden">(null);
  const reportStep = run.steps.find((s) => s.kind === "research_report");
  useEffect(() => {
    if (!reportStep) return;
    let live = true;
    research.report(frame.studyId, run.run_id).then(
      (value) => live && setStatus(value),
      (e: unknown) => live && e instanceof ApiError && e.status === 403 && setStatus("hidden"),
    );
    return () => { live = false; };
  }, [frame.studyId, run.run_id, reportStep?.status, reportStep?.artifact_id, reportStep]);
  useEffect(() => {
    let live = true;
    const asked = review;
    deepResearch.runs(frame.studyId, 100).then(
      (all) => live && setListed({ asked, reviews: reviewsFor(all, run.run_id) }),
      // Unread is unknown, never "none": the list stays as it was.
      () => undefined,
    );
    return () => { live = false; };
  }, [frame.studyId, run.run_id, review]);
  useEffect(() => {
    if (review === null || listed === null || listed.asked !== review) return;
    if (!listed.reviews.some((r) => r.run_id === review)) onReview?.(null);
  }, [review, listed, onReview]);
  // Only the chosen review's draft is read as the variant.
  const current = currentVariant(variant, run.run_id, review);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- a review left or not permitted shows no variant
    if (review === null || !mayReview) { setVariant(null); return; }
    let live = true;
    deepResearch.contextReport(frame.studyId, run.run_id, review).then((v) => live && setVariant(v), () => undefined);
    return () => { live = false; };
  }, [frame.studyId, mayReview, run.run_id, review]);
  if (status === "hidden") return null;
  const report = status !== null && status.state === "READY" ? status : null;
  const modelled = report?.data_origin_kind === "MODELLED";
  const withReview = review !== null;
  const variantReady = withReview && current?.state === "READY";
  // The origin as the run's steps stamped it and as the stored report states it (CR-5).
  const origins = new Set(runOriginKinds(run));
  const reportKind = report ? resultOriginKind(report) : null;
  if (reportKind) origins.add(reportKind);
  const parts = reportParts(run, withReview ? literatureState(review, current) : "excluded", variantReady, origins);
  const limitation = report?.synthetic
    ? "Odpovídali syntetičtí respondenti: zpráva nepopisuje skutečné osoby."
    : modelled ? "Čísla jsou modelovaná AI respondenty, nejsou měřením." : null;

  return (
    <section aria-labelledby="complete-report-title" data-complete-report className="flex flex-col gap-3 rounded-card border border-ink bg-surface-raised p-4">
      <div className="flex items-center gap-2.5">
        {/* eslint-disable-next-line @next/next/no-img-element -- the identity's own SVG, served by this app */}
        <img src="/skin/brand/aia-mark.svg" alt="" width={28} height={28} />
        <div>
          <h2 id="complete-report-title" className="text-[17px] font-semibold leading-6">Kompletní zpráva studie</h2>
          <p className="text-xs text-ink-muted">{frame.studyName} · {frame.clientName} · se značkou AI Analytics</p>
        </div>
      </div>
      <ul className="grid gap-x-4 sm:grid-cols-2">
        {parts.map((p) => (
          <li key={p.label} className="grid grid-cols-[18px_1fr] items-start gap-2 border-b border-border py-1.5">
            <span aria-hidden="true" className={`mt-px inline-flex size-[18px] items-center justify-center rounded-full ${MARK[p.state]}`}>
              {p.state === "in" ? <Icon name="done" size={10} /> : null}
            </span>
            <span className="min-w-0">
              <span className="block text-[13px] font-medium leading-[18px]">{p.label}<span className="sr-only"> · {WORD[p.state]}</span></span>
              <span className={`block text-xs leading-4 ${p.state === "later" ? "text-ink-faint" : "text-ink-muted"}`}>{p.state === "later" ? `${p.detail} · ${WORD.later}` : p.detail}</span>
            </span>
          </li>
        ))}
      </ul>
      {limitation ? <p data-report-limitation className="text-xs leading-4 text-ink-muted">{limitation}</p> : null}
      {/* The report is read, prepared, downloaded and approved in the doc bar of Zpráva below (RPT3c). */}
      <p data-report-where className="text-xs leading-4 text-ink-muted">Zprávu čtete, stahujete a schvalujete v liště dokumentu níže.</p>
    </section>
  );
}
