"use client";

// "Závislosti" (artifact-questionnaire QST8; V2 DesignStages.tsx:132-139): what reads each set and
// question downstream, from the working copy by the rules src/research/readers.ts cites. Sets and
// the questions that differ (a Sociomap rating item, an open question, one held back) get a row
// each; the ordinary closed questions share one. Display only: it edits nothing.

import Link from "next/link";

import { t, tv } from "@/i18n/t";
import { questionElementId, setElementId } from "@/lib/answerability";
import { STAGES, stageHref, type WorkbenchStage } from "@/lib/workbench-stages";
import { type ItemReaders, type Reader, questionnaireReaders } from "@/research/readers";
import { useResearch } from "./context";
import { useFrame } from "./frame-hook";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";
const LINK = `underline decoration-border-strong underline-offset-2 hover:decoration-ink ${FOCUS}`;

const STAGE_OF: Record<Reader, WorkbenchStage> = { fieldwork: "fieldwork", results: "results", sociomap: "sociomap", analysis: "analysis", report: "report" };

/** A plain closed question: everything but what makes a row of its own. */
const plain = (i: ItemReaders) => i.kind === "question" && !i.open && !i.rating && !i.held;

function Stages({ readers }: { readers: Reader[] }) {
  const frame = useFrame();
  return (
    <span className="inline-flex flex-wrap gap-x-1.5">
      {readers.map((r, k) => (
        <span key={r}>
          <Link className={LINK} href={stageHref(STAGE_OF[r], frame.stepHref)}>{STAGES[STAGE_OF[r]].label}</Link>
          {k < readers.length - 1 ? "," : ""}
        </span>
      ))}
    </span>
  );
}

function ItemName({ item }: { item: ItemReaders }) {
  const anchor = item.kind === "set" ? setElementId({ id: item.id ?? undefined }, item.section) : item.id ? questionElementId({ id: item.id }) : null;
  const name = item.text ? `${item.label} ${item.text}` : item.label;
  return anchor ? <a className={`font-medium ${LINK}`} href={`#${anchor}`}>{name}</a> : <span className="font-medium">{name}</span>;
}

function note(item: ItemReaders): string | null {
  if (item.held) return t(`research.questionnaire.dependencies.held.${item.held}`);
  if (item.open) return t("research.questionnaire.dependencies.open");
  if (item.rating && !item.readers.includes("sociomap")) return t("research.questionnaire.dependencies.ratingNoSet");
  if (item.rating) return t("research.questionnaire.dependencies.rating");
  if (item.context.length) return tv("research.questionnaire.dependencies.context", { objects: item.context.join(", ") });
  return null;
}

export function QuestionnaireDependencies() {
  const { state } = useResearch();
  const items = questionnaireReaders(state.project);
  if (!items.length) return null;
  const closed = items.filter(plain);
  const own = items.filter((i) => !plain(i));
  return (
    <section aria-labelledby="q-dependencies" className="flex flex-col gap-2 rounded-panel border border-border bg-surface-raised p-4">
      <h3 id="q-dependencies" className="text-sm font-semibold">{t("research.questionnaire.dependencies.title")}</h3>
      <ul className="flex flex-col gap-2 text-[13px] leading-5">
        {own.map((item) => {
          const why = note(item);
          return (
            <li key={`${item.kind}-${item.label}`}>
              <ItemName item={item} />
              {item.readers.length ? <> → <Stages readers={item.readers} /></> : null}
              {why ? <span className="block text-xs leading-4 text-ink-muted">{why}</span> : null}
            </li>
          );
        })}
        {closed.length ? (
          <li>
            <span className="font-medium">{tv(`research.questionnaire.dependencies.closed.${closed.length === 1 ? "one" : closed.length <= 4 ? "few" : "many"}`, { n: closed.length, items: closed.map((i) => i.label).join(", ") })}</span>
            {" → "}
            <Stages readers={closed[0].readers} />
          </li>
        ) : null}
      </ul>
      <p className="text-xs leading-4 text-ink-muted">{t("research.questionnaire.dependencies.rule")}</p>
    </section>
  );
}
