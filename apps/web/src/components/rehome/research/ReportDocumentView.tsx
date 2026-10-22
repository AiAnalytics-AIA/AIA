"use client";

// Zpráva's document first (artifact-report RPT2): the run's internal draft rendered in the pane from
// its stored document model (report-delivery RD5a), in the report's print order -- sections,
// paragraphs, tables and figures, each number a chip that opens its claim in the item inspector.
// The DOCX stays the deliverable; this reads the document beside it and prints only what it holds:
// a number is the text the DOCX prints, a suppressed one is never shown, an unknown ref is "?".

import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { ApiError, research, type ResearchRun } from "@/lib/api";
import {
  type Block, type Cell, claimLines, claimTarget, gradeWords, type Inline, type LedgerEntry, type ListItem,
  approvalWords, readDocument, type ReportDocumentModel, reviewWords, type Section, sectionTarget, blockTarget,
  type StoredReportDocument, unresolvedRefs, valueWords,
} from "@/lib/artifacts/report";
import { backEntry, closeStack, emptyStack, openEntry, type InspectorStack } from "@/lib/inspector-stack";
import { isModelled, stepOf } from "@/lib/research-execution";
import { useFrame } from "./frame-hook";
import { ItemInspector } from "./ItemInspector";
import { canReview } from "./frame";
import { Button } from "../ui";
import { coverageRecord, type CoverageLine } from "@/lib/artifacts/report-coverage";

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

type Loaded =
  | { state: "loading" }
  | { state: "none" }
  | { state: "not_stored" }
  | { state: "unprepared" }
  | { state: "refused" }
  | { state: "failed"; message: string }
  | { state: "ready"; stored: StoredReportDocument; doc: ReportDocumentModel };

/** Fired each time the pane shows a client report: the run, the version shown and its review. The
 *  report card approves exactly the version the person reads here (RD3), never one it read itself. */
export const CLIENT_SHOWN = "aia:client-report-shown";
export type ClientShown = { runId: string; artifactId: string; reviewState: string; approvedOn: string | null; stamped: boolean };
/** Fired when the report card approves a version of the run's report, naming it, so the pane
 *  showing that version reads its review again. */
export const REPORT_APPROVED = "aia:report-approved";
export type ReportApproved = { runId: string; artifactId: string };

/** Which document the pane reads: the internal draft, or the client report (RD3). */
type Kind = "internal" | "client";

/** The run's stored draft of `kind`, read once per state of its report step. A client report not
 *  yet prepared is `unprepared`: `prepare` composes and stores it, and answers its document. */
function useReportDocument(studyId: string, run: ResearchRun, kind: Kind): { loaded: Loaded; prepare: () => void } {
  const step = stepOf(run, "report");
  const ready = step?.status === "SUCCEEDED";
  // The client version this pane shows, by run: every later read names it, so a read again (after
  // an approval) never shows a newer draft than the one the person read.
  const pin = useRef<{ runId: string; artifactId: string } | null>(null);
  const shown = useRef<string | null>(null);
  // Read again when the card approves the version shown: the doc bar says what was approved.
  const [approvals, setApprovals] = useState(0);
  useEffect(() => {
    const on = (e: Event) => {
      const got = (e as CustomEvent<ReportApproved>).detail;
      if (got?.runId === run.run_id && got.artifactId === shown.current) setApprovals((n) => n + 1);
    };
    window.addEventListener(REPORT_APPROVED, on);
    return () => window.removeEventListener(REPORT_APPROVED, on);
  }, [run.run_id]);
  const key = `${studyId}:${run.run_id}:${step?.status ?? ""}:${step?.artifact_id ?? ""}:${kind}:${approvals}`;
  const [answer, setAnswer] = useState<{ key: string; loaded: Loaded } | null>(null);
  // The document asked for now: an answer for another (a prepare that returns after a switch) is dropped.
  const current = useRef(key);
  useEffect(() => { current.current = key; }, [key]);
  const settle = useCallback((read: Promise<StoredReportDocument>, at: string, live: () => boolean) => {
    read.then(
      (stored) => {
        const doc = readDocument(stored.document);
        if (!live()) return;
        setAnswer({ key: at, loaded: doc ? { state: "ready", stored, doc } : { state: "refused" } });
        shown.current = doc ? stored.report_artifact_id : null;
        if (doc && kind === "client") {
          pin.current = { runId: run.run_id, artifactId: stored.report_artifact_id };
          const detail: ClientShown = {
            runId: run.run_id, artifactId: stored.report_artifact_id, reviewState: stored.review_state,
            approvedOn: stored.approved_on, stamped: stored.stamped,
          };
          window.dispatchEvent(new CustomEvent<ClientShown>(CLIENT_SHOWN, { detail }));
        }
      },
      (error: unknown) => {
        if (!live()) return;
        const code = error instanceof ApiError ? error.code : "";
        const status = error instanceof ApiError ? error.status : 0;
        const loaded: Loaded =
          // 404: none stored yet, which for the client report means not prepared; 403: a reader
          // who may not see this draft sees nothing of it.
          status === 404 ? (kind === "client" ? { state: "unprepared" } : { state: "none" })
            // The switch stays when the client report is refused: the internal draft is one click back.
            : status === 403 ? (kind === "client" ? { state: "failed", message: "Klientskou zprávu číst nemůžete." } : { state: "none" })
              : code === "report_document_not_stored" ? { state: "not_stored" }
                : code === "report_artifact_invalid" ? { state: "refused" }
                  : { state: "failed", message: message(error) };
        setAnswer({ key: at, loaded });
      },
    );
  }, [kind, run.run_id]);
  useEffect(() => {
    if (!ready) return;
    let live = true;
    const pinned = pin.current?.runId === run.run_id ? pin.current.artifactId : undefined;
    const read = kind === "client" ? research.clientReportDocument(studyId, run.run_id, pinned) : research.reportDocument(studyId, run.run_id);
    settle(read, key, () => live);
    return () => { live = false; };
  }, [studyId, run.run_id, key, ready, kind, settle]);
  const prepare = useCallback(() => {
    setAnswer({ key, loaded: { state: "loading" } });
    settle(research.prepareClientReport(studyId, run.run_id), key, () => current.current === key);
  }, [key, settle, studyId, run.run_id]);
  if (!ready) return { loaded: { state: "none" }, prepare };
  return { loaded: answer?.key === key ? answer.loaded : { state: "loading" }, prepare };
}

export function ReportDocumentView({ run }: { run: ResearchRun }) {
  const frame = useFrame();
  // The client report exists only for a run whose respondents were modelled from the population;
  // the pane shows one document at a time, so the Lead's report: ids name exactly one.
  const offersClient = isModelled(run);
  const [chosen, setChosen] = useState<Kind>("internal");
  const kind: Kind = offersClient ? chosen : "internal";
  const { loaded, prepare } = useReportDocument(frame.studyId, run, kind);
  const [stack, setStack] = useState<InspectorStack>(() => emptyStack("report"));
  // A claim belongs to one document's ledger: switching closes it.
  const setKind = (k: Kind) => { setChosen(k); setStack(closeStack); };
  const open = useCallback((ref: string) => setStack((s) => openEntry(s, { id: ref, title: `Tvrzení ${ref}`, sub: "Číslo ve zprávě a jeho evidence" })), []);
  const back = useCallback(() => setStack(backEntry), []);
  const close = useCallback(() => setStack(closeStack), []);

  // One document at a time, chosen in the doc bar; the client report is read here, never downloaded
  // to be read (RD3, F17: approval comes before a deliverable leaves).
  const choose = offersClient ? (
    <div role="group" aria-label="Dokument" className="mb-2 flex flex-wrap gap-2" data-report-kind>
      {(["internal", "client"] as const).map((k) => (
        <Button key={k} variant={kind === k ? "primary" : "quiet"} className="!min-h-11" aria-pressed={kind === k} onClick={() => setKind(k)}>
          {k === "internal" ? "Interní zpráva" : "Klientská zpráva"}
        </Button>
      ))}
    </div>
  ) : null;
  const notice = noticeOf(loaded, kind, prepare, canReview(frame));
  if (notice === undefined) return null;
  if (notice !== null || loaded.state !== "ready") return <div>{choose}{notice}</div>;

  const { stored, doc } = loaded;
  const missing = unresolvedRefs(doc);
  const entry = (ref: string): LedgerEntry | undefined => doc.ledger.refs[ref];
  return (
    // The pane's own width decides the layout, not the window's: the workbench's split can leave the
    // artifact narrow on a wide screen.
    <div className="@container" data-report-document="ready"><div className="flex min-w-0 flex-col gap-3 @3xl:flex-row @3xl:items-start">
      <div className="min-w-0 flex-1">
        {choose}
        <div className="mb-2.5 flex flex-wrap items-center gap-2 text-xs text-ink-muted" data-report-docbar>
          <span className="font-semibold text-ink">{kind === "client" ? "Klientská zpráva" : "Interní zpráva"}</span>
          <span>· {reviewWords(stored)}</span>
          {stored.approval ? <span data-approval>· {approvalWords(stored.approval, stored.approved_on)}</span> : null}
          <span className="font-mono">· {stored.report_artifact_id}</span>
        </div>
        {missing.length ? (
          <p role="alert" className="mb-2 text-sm text-status-fault">Dokument cituje čísla, která jeho evidence nemá ({missing.join(", ")}); zobrazují se jako „?“.</p>
        ) : null}
        <article aria-label="Koncept zprávy" className="rounded-card border border-border bg-surface-raised px-4 py-5 font-serif shadow-sm sm:px-8 lg:px-14 lg:py-10">
          <header className="mb-4 border-b border-border pb-4">
            <p className="font-sans text-xs text-ink-muted">{doc.meta.client_name} · {doc.meta.study_name}</p>
            <h1 className="mt-1 text-2xl font-semibold leading-tight sm:text-[28px]">{doc.meta.title}</h1>
            <p className="mt-1 font-sans text-sm text-ink-muted">{doc.meta.subtitle}</p>
          </header>
          {doc.sections.map((section) => (
            <DocSection key={section.id} section={section} entry={entry} onClaim={open} refs={Object.keys(doc.ledger.refs)} />
          ))}
          <footer className="mt-6 border-t border-border pt-2 font-sans text-[11px] text-ink-muted" data-report-foot>
            {stored.review_state === "APPROVED_INTERNAL" ? "Schváleno" : "Koncept"} · {stored.review_state} · {run.run_id} · revize {doc.meta.revision} · dokument {stored.artifact_id}
          </footer>
        </article>
        <Coverage lines={coverageRecord(run, doc.unread)} />
      </div>
      {/* Beside the document in a wide pane, a column only while a claim is open; in a narrow one, a sheet
          over the page's foot, so the claim opens where it was asked. */}
      <div className={`fixed inset-x-3 bottom-3 z-30 flex max-h-[60vh] flex-col @3xl:sticky @3xl:top-3 @3xl:max-h-none @3xl:shrink-0 ${stack.entries.length ? "@3xl:w-80" : "@3xl:w-0"}`}>
        <ItemInspector stack={stack} onBack={back} onClose={close}>
          {(top) => <ul className="flex flex-col gap-1">{claimLines(entry(top.id)).map((line) => <li key={line}>{line}</li>)}</ul>}
        </ItemInspector>
      </div>
    </div></div>
  );
}

/** What the draft does not hold and why (RPT4): beside the document, never part of its text. */
function Coverage({ lines }: { lines: CoverageLine[] }) {
  return (
    <section aria-labelledby="report-coverage" data-report-coverage className="mt-3 rounded-card border border-border bg-surface px-4 py-3 text-sm">
      <h2 id="report-coverage" className="font-semibold">Záznam pokrytí <span className="font-normal text-ink-muted">(mimo text zprávy)</span></h2>
      <ul className="mt-1.5 flex flex-col gap-1">
        {lines.map((line, i) => (
          <li key={i} data-coverage={line.kind} className="min-w-0 break-words">
            <span className="font-medium">{line.label}</span>: {line.state}
            {line.why ? <span className="text-ink-muted"> — {line.why}</span> : null}
            {line.ref ? <span className="font-mono text-xs text-ink-muted"> · {line.ref}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** What the pane says instead of a document: undefined, nothing at all; null, the document. */
function noticeOf(loaded: Loaded, kind: Kind, prepare: () => void, mayPrepare: boolean): ReactNode | undefined {
  switch (loaded.state) {
    case "none": return undefined;
    case "ready": return null;
    case "loading": return <p className="text-sm text-ink-muted" data-report-document="loading">Načítám koncept zprávy…</p>;
    case "failed": return <p role="alert" className="text-sm text-status-fault" data-report-document="failed">{loaded.message}</p>;
    case "unprepared": return (
      <div role="note" className="flex flex-wrap items-center gap-3 text-sm text-ink-muted" data-report-document="unprepared">
        <span>Klientská zpráva k tomuto běhu ještě není připravená. Připravíte ji ke čtení zde; žádný soubor přitom neodchází.</span>
        {mayPrepare ? <Button className="!min-h-11" onClick={prepare}>Připravit klientskou zprávu</Button> : null}
      </div>
    );
    case "not_stored": return (
      <p role="note" className="text-sm text-ink-muted" data-report-document="not_stored">
        Tuto zprávu AIA složila dřív, než začala ukládat její dokument; v panelu ji proto zobrazit nelze.{kind === "internal" ? " Koncept DOCX stáhnete níže." : ""}
      </p>
    );
    case "refused": return (
      <p role="alert" className="text-sm text-status-fault" data-report-document="refused">
        Uložený dokument zprávy neodpovídá jejímu souboru DOCX nebo je v jiném formátu; AIA ho nezobrazí.{kind === "internal" ? " Koncept DOCX stáhnete níže." : ""}
      </p>
    );
  }
}

type Read = {
  entry: (ref: string) => LedgerEntry | undefined;
  onClaim: (ref: string) => void;
  /** Every ref the ledger holds, in its order: what the evidence appendix lists. */
  refs: string[];
};

function DocSection({ section, ...read }: { section: Section } & Read) {
  return (
    <section data-aia={sectionTarget(section)} className="mb-2">
      <h2 className="mb-1.5 mt-5 font-sans text-base font-semibold">{section.appendix ? `Příloha · ${section.title}` : section.title}</h2>
      {section.blocks.map((block) => (
        <div key={block.id} data-aia={blockTarget(block)} className="mb-2.5">
          <DocBlock block={block} {...read} point={pointer(block)} />
        </div>
      ))}
    </section>
  );
}

/** A number as a chip: the DOCX's text for it; a click opens its claim. Suppressed: never a number. */
type Chip = Pick<Read, "entry" | "onClaim"> & {
  /** The chip's `data-aia` in its block: the first chip of a ref only, so no two elements share an id. */
  point: (ref: string) => string | undefined;
};

/** A block's pointer: `report:<block id>:<ref>` for a ref's first chip in the block, none after. */
function pointer(block: Block): (ref: string) => string | undefined {
  const seen = new Set<string>();
  return (ref) => {
    if (seen.has(ref)) return undefined;
    seen.add(ref);
    return claimTarget(block, ref) ?? undefined;
  };
}

function Claim({ ref_, withInterval, entry, onClaim, point }: { ref_: string; withInterval: boolean } & Chip) {
  const target = point(ref_);
  return (
    <button type="button" onClick={() => onClaim(ref_)} data-aia={target} data-claim={ref_}
      className="mx-px inline rounded-sm bg-surface-sunken px-1 font-mono text-[0.92em] text-ink hover:bg-signal-wash focus-visible:outline-2 focus-visible:outline-focus-ring">
      {valueWords(entry(ref_), withInterval)}
    </button>
  );
}

/** A block's own refs (a callout's or a finding's marks) as chips after its text. */
function Marks({ refs, ...chip }: { refs: string[] } & Chip) {
  if (!refs.length) return null;
  return <span className="ml-1 font-sans">{refs.map((ref) => <Claim key={ref} ref_={ref} withInterval={false} {...chip} />)}</span>;
}

function Inlines({ content, ...chip }: { content: Inline[] } & Chip): ReactNode {
  return content.map((inline, i) => {
    switch (inline.type) {
      case "text":
        return inline.emphasis === "strong" ? <strong key={i}>{inline.text}</strong> : inline.emphasis === "em" ? <em key={i}>{inline.text}</em> : <span key={i}>{inline.text}</span>;
      case "value":
        return <Claim key={i} ref_={inline.ref} withInterval={inline.with_interval} {...chip} />;
      case "footnote":
        return <sup key={i} title={inline.text} className="font-sans text-ink-muted">*</sup>;
      case "cross_ref":
        return <span key={i} className="font-sans text-ink-muted">(viz {inline.target})</span>;
      case "link":
        return <span key={i}>{inline.text} <span className="font-sans text-xs text-ink-muted">({inline.url})</span></span>;
      default:
        return null;
    }
  });
}

function Items({ items, ordered, ...chip }: { items: ListItem[]; ordered: boolean } & Chip) {
  const List = ordered ? "ol" : "ul";
  return <List className={`${ordered ? "list-decimal" : "list-disc"} ml-6 text-[15px] leading-6`}>
    {items.map((item, i) => <li key={i}><Inlines content={item.content} {...chip} />
      {item.children.length ? <Items items={item.children} ordered={ordered} {...chip} /> : null}</li>)}
  </List>;
}

function TableCell({ cell, ...chip }: { cell: Cell } & Chip) {
  if (cell.type === "text") return <>{cell.text}</>;
  if (cell.type === "empty") return <span className="text-ink-muted">{cell.reason}</span>;
  return <Claim ref_={cell.ref} withInterval={cell.with_interval} {...chip} />;
}

function DocBlock({ block, entry, onClaim, refs, point }: { block: Block; point: Chip["point"] } & Read) {
  const read = { entry, onClaim, point };
  switch (block.type) {
    case "heading":
      return block.level === 2 ? <h3 className="mt-3 font-sans text-[15px] font-semibold">{block.text}</h3> : <h4 className="mt-2 font-sans text-sm font-semibold">{block.text}</h4>;
    case "paragraph":
      return <p className={block.role === "lede" ? "text-[17px] leading-7" : block.role === "lead_in" ? "font-sans text-sm font-semibold" : "text-[15px] leading-6"}>
        <Inlines content={block.content} {...read} /><Marks refs={block.marks} {...read} />
      </p>;
    case "list":
      return <Items items={block.items} ordered={block.ordered} {...read} />;
    case "quote":
      return <blockquote className="border-l-2 border-border pl-3 text-[15px] italic leading-6">„{block.text}“ <span className="font-sans text-xs not-italic text-ink-muted">— {block.attribution}{block.synthetic ? " (smyšlený respondent)" : ""}</span></blockquote>;
    case "callout":
      return <div className="rounded-control border border-border bg-surface-sunken px-3 py-2 font-sans text-sm leading-6" data-callout={block.kind}>
        {block.title ? <p className="font-semibold">{block.title}<Marks refs={block.marks} {...read} /></p> : null}
        <p><Inlines content={block.content} {...read} />{block.title ? null : <Marks refs={block.marks} {...read} />}</p>
      </div>;
    case "key_finding":
      return <div className="border-l-2 border-signal pl-3 text-[15px] leading-6">
        <p className="font-sans font-semibold">{block.headline}<Marks refs={block.marks} {...read} /></p>
        <p>{block.finding}</p>
        <p className="font-sans text-sm text-ink-muted">Evidence: {block.evidence} · Význam: {block.meaning} · Jistota: {block.confidence}</p>
      </div>;
    case "recommendation":
      return <div className="text-[15px] leading-6"><p className="font-sans font-semibold">{block.action}<Marks refs={block.marks} {...read} /></p><p>{block.why}</p><p className="font-sans text-xs text-ink-muted">Priorita: {block.priority}</p></div>;
    case "kpi_row":
      return <div className="flex flex-wrap gap-3 font-sans">{block.items.map((kpi) => (
        <div key={kpi.ref} className="min-w-32 rounded-control border border-border px-3 py-2">
          <Claim ref_={kpi.ref} withInterval {...read} />
          <p className="text-xs text-ink-muted">{kpi.label}</p>
        </div>))}</div>;
    case "table":
      return <figure className="font-sans">
        <figcaption className="mb-1 text-xs text-ink-muted">Tabulka · {block.title}</figcaption>
        <div className="overflow-x-auto"><table className="w-full border-collapse text-sm">
          <thead><tr>{block.columns.map((c, i) => <th key={i} scope="col" className={`border-b border-border px-2 py-1 font-semibold ${c.align === "right" ? "text-right" : "text-left"}`}>{c.label}{c.unit ? ` (${c.unit})` : ""}</th>)}</tr></thead>
          <tbody>{block.rows.map((row, r) => <tr key={r} className={row.emphasis ? "font-semibold" : undefined}>
            {row.cells.map((cell, i) => <td key={i} className={`border-b border-border px-2 py-1 ${block.columns[i]?.align === "right" ? "text-right" : ""}`}><TableCell cell={cell} {...read} /></td>)}
          </tr>)}</tbody>
        </table></div>
        <p className="mt-1 text-xs text-ink-muted">Zdroj: {block.source}{block.suppressed_rows ? ` · odstraněno řádků pro nedostatečnou podporu: ${block.suppressed_rows}` : ""}</p>
        {block.notes.map((note) => <p key={note} className="text-xs text-ink-muted">{note}</p>)}
      </figure>;
    case "figure":
      // The chart's numbers as a table: the DOCX draws the chart, the pane lists what it plots.
      return <figure className="rounded-control border border-border px-3 py-2 font-sans">
        <figcaption className="mb-1 text-xs text-ink-muted">Graf · {block.title} <span className="sr-only">({block.alt})</span></figcaption>
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead><tr><th scope="col" className="text-left font-semibold">{block.chart.value_label}</th>{block.chart.series.map((s) => <th key={s.name} scope="col" className="text-right font-semibold">{s.name}{s.modelled ? " (modelováno)" : ""}</th>)}</tr></thead>
          <tbody>{block.chart.categories.map((category, c) => <tr key={category}><th scope="row" className="text-left font-normal">{category}</th>
            {block.chart.series.map((s) => { const ref = s.refs[c]; return <td key={s.name} className="text-right">{ref ? <Claim ref_={ref} withInterval={false} {...read} /> : <span className="text-ink-muted">—</span>}</td>; })}
          </tr>)}</tbody>
        </table></div>
        <p className="mt-1 text-xs text-ink-muted">Zdroj: {block.source}</p>
      </figure>;
    case "sociomap_figure":
      return <figure className="rounded-control border border-border px-3 py-2 font-sans text-sm" data-map-figure={block.anchor}>
        <figcaption className="text-xs text-ink-muted">Mapa · {block.title} · {block.methodology_status}{block.fit_caption ? ` · ${block.fit_caption}` : block.stress_1 != null ? ` · Stress-1 ${block.stress_1}` : ""}</figcaption>
        <p className="mt-1">Obrázek mapy je v souboru DOCX; v AIA ji otevřete na stupni Sociomapa.</p>
      </figure>;
    case "evidence_key":
      return <p className="font-sans text-xs text-ink-muted">U každého čísla je uveden stupeň jeho evidence; otevřete číslo pro podrobnosti.</p>;
    case "evidence_appendix":
      return <EvidenceAppendix {...read} refs={refs} />;
    case "audit":
      return <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 font-sans text-xs">{block.entries.map(([k, v]) => <div key={k} className="contents"><dt className="text-ink-muted">{k}</dt><dd className="break-all font-mono">{v}</dd></div>)}</dl>;
    case "page_break":
      return null;
    default:
      return <p className="font-sans text-xs text-ink-muted" data-unrendered>Tento blok zprávy AIA v panelu zatím nezobrazuje; je v souboru DOCX.</p>;
  }
}

/** One row per ref the document cites, admitted or suppressed, as the DOCX's evidence appendix. */
function EvidenceAppendix({ refs, ...chip }: Pick<Read, "refs"> & Chip) {
  const { entry } = chip;
  return <div className="overflow-x-auto font-sans"><table className="w-full text-sm" data-evidence-appendix>
    <thead><tr>{["Tvrzení", "Hodnota", "Základ", "Stupeň"].map((h) => <th key={h} scope="col" className="border-b border-border px-2 py-1 text-left font-semibold">{h}</th>)}</tr></thead>
    <tbody>{refs.map((ref) => { const e = entry(ref); return <tr key={ref}>
      <td className="border-b border-border px-2 py-1 font-mono text-xs">{ref}</td>
      <td className="border-b border-border px-2 py-1"><Claim ref_={ref} withInterval {...chip} /></td>
      <td className="border-b border-border px-2 py-1">{e && !e.suppressed ? e.base_text ?? "n = ?" : "—"}</td>
      <td className="border-b border-border px-2 py-1">{e && !e.suppressed ? gradeWords(e.grade) : e ? "potlačeno" : "?"}</td>
    </tr>; })}</tbody>
  </table></div>;
}
