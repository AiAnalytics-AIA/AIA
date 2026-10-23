"use client";

// The scale editor on Dotazník (input-interactions chunk 3b2; audit A9, A10). The range is chosen
// from the owner's presets, 1–5, 1–7, 0–10 and 1–10, or "Vlastní", which opens two steppers for
// the whole-number ends, each bounded by the other (I2, I3; Q32 a). The labels are the two ends or,
// on the owner's note ("word attributes to every number between 1-10"), one per point, each edited
// in place (I1; Tab moves from point to point). The rule the labels keep is the server's, in
// src/research/scale-labels.ts: labels it would leave out (readiness WARN scale_labels_ignored)
// are said here to be left out, and a repeated or over-long label is refused at its field.
//
// The range-change rule (plan § Scales): two ends stay two ends; labels per point stay only when
// the number of points is unchanged; otherwise the end labels stay, the inner ones are cleared and
// an undo toast counts them ("Odstraněno 8 popisků bodů – Vrátit"), restoring the range and the
// labels as they were. Nothing is redistributed by guess. The editor writes through its caller,
// the study's working copy, which autosaves.

import { createContext, type ReactNode, useContext, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { ChoiceChips } from "@/components/ui/ChoiceChips";
import { InlineText } from "@/components/ui/InlineText";
import { Stepper } from "@/components/ui/Stepper";
import { type UndoOffer, UndoToast, useUndo } from "@/components/ui/UndoToast";
import {
  DESCRIBED_POINTS_MAX,
  type LabelMode,
  SCALE_END_MAX,
  SCALE_END_MIN,
  SCALE_LABEL_MAX,
  SCALE_PRESETS,
  type Scale,
  clearedWords,
  describeEveryPoint,
  endBounds,
  endsOnly,
  labelMode,
  labelProblem,
  points,
  presetOf,
  rangeWords,
  readRange,
  repeatsAnother,
  rescaleLabels,
  shownEnds,
  withEnd,
  withPoint,
} from "@/research/scale-labels";

export type ScaleValue = { scale: Scale; labels: string[] };

type Undo = ReturnType<typeof useUndo>;
const ScaleUndo = createContext<Undo | null>(null);

/**
 * The editor's undo toast, shared by everything beneath ScaleUndoProvider: scale changes and
 * Dotazník's deletes (input-interactions chunk 3); null outside it.
 */
export const useEditorUndo = (): Undo | null => useContext(ScaleUndo);

/** One undo toast for every scale editor beneath it: one offer at a time (I6). */
export function ScaleUndoProvider({ children }: { children: ReactNode }) {
  const undo = useUndo();
  return (
    <ScaleUndo.Provider value={undo}>
      {children}
      <UndoToast offer={undo.current} onDone={undo.clear} />
    </ScaleUndo.Provider>
  );
}

const CUSTOM = "custom";
/** The most point boxes drawn; a wider range is written in words. */
const BOXES_MAX = 12;

export function ScaleEditor({
  scale: raw, labels, onChange, name, rangeFixed = false, perPoint = true, className = "",
}: {
  /** The range as stored; anything but two whole numbers in bounds, low < high, is said, never used. */
  scale: readonly unknown[] | undefined;
  /** The labels as stored (or the screen's default ends when none are). */
  labels: readonly string[];
  /** Writes the range and the labels together (the working copy autosaves). */
  onChange: (next: ScaleValue) => void;
  /** Whose scale it is ("Q3", "Sada 1"): in the controls' accessible names. */
  name: string;
  /** The range is shown, not edited (a tracked set's). */
  rangeFixed?: boolean;
  /** false: only the two ends are offered. */
  perPoint?: boolean;
  className?: string;
}) {
  const shared = useContext(ScaleUndo);
  const local = useUndo();
  const undo = shared ?? local;
  const stored = readRange(raw);
  const scale: Scale = stored ?? [1, 10];
  const [custom, setCustom] = useState(stored !== null && presetOf(stored) === null);
  const isCustom = custom || (stored !== null && presetOf(stored) === null);
  // The state an undo restores while its toast is still up: a second loss in a row (an arrow over
  // the presets) adds to the count and keeps the first state, so Vrátit gives back what was there.
  const pending = useRef<{ offer: UndoOffer; before: ScaleValue; cleared: number } | null>(null);

  const apply = (next: ScaleValue, cleared: number) => {
    if (cleared > 0) {
      const chain = pending.current && undo.current === pending.current.offer ? pending.current : null;
      const before = chain ? chain.before : { scale, labels: [...labels] };
      const total = (chain?.cleared ?? 0) + cleared;
      const offer: UndoOffer = {
        message: clearedWords(total),
        undo: () => {
          pending.current = null;
          setCustom(presetOf(before.scale) === null);
          onChange(before);
        },
      };
      pending.current = { offer, before, cleared: total };
      undo.offer(offer);
    }
    onChange(next);
  };

  const setRange = (to: Scale) => {
    if (stored && to[0] === stored[0] && to[1] === stored[1]) return;
    const r = stored ? rescaleLabels(labels, stored, to) : { labels: [...labels], cleared: 0 };
    apply({ scale: to, labels: r.labels }, r.cleared);
  };

  const mode: LabelMode = stored ? labelMode(labels, stored) : "ends";
  const setMode = (to: LabelMode) => {
    if (!stored || to === mode) return;
    if (to === "points") apply({ scale: stored, labels: describeEveryPoint(labels, stored) }, 0);
    else {
      const r = endsOnly(labels, stored);
      apply({ scale: stored, labels: r.labels }, r.cleared);
    }
  };
  const tooMany = points(scale) > DESCRIBED_POINTS_MAX;

  const rangeKey = stored === null ? (custom ? CUSTOM : null) : isCustom ? CUSTOM : rangeWords(stored);
  const bounds = endBounds(scale);
  const problem = stored ? labelProblem(labels, stored) : null;
  const disabledReason = stored ? undefined : t("research.questionnaire.scaleEditor.chooseFirst");

  const ends = shownEnds(labels);
  return (
    <div role="group" aria-label={tv("research.questionnaire.scaleEditor.group", { name })} className={`flex flex-col gap-3 ${className}`}>
      {rangeFixed ? (
        <p className="text-xs text-ink-muted">{tv("research.questionnaire.scaleEditor.fixed", { range: rangeWords(scale) })}</p>
      ) : (
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium text-ink-muted">{t("research.questionnaire.scaleEditor.range")}</span>
          <ChoiceChips
            label={tv("research.questionnaire.scaleEditor.rangeOf", { name })}
            value={rangeKey}
            options={[
              ...SCALE_PRESETS.map((preset) => ({ key: rangeWords(preset), label: rangeWords(preset) })),
              { key: CUSTOM, label: t("research.questionnaire.scaleEditor.custom") },
            ]}
            onChange={(key) => {
              if (key === CUSTOM) {
                setCustom(true);
                return;
              }
              const preset = SCALE_PRESETS.find((p) => rangeWords(p) === key);
              if (!preset) return;
              setCustom(false);
              setRange(preset);
            }}
          />
          {isCustom ? (
            <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
              <Stepper
                label={t("research.questionnaire.scaleMin")}
                value={stored ? stored[0] : null}
                min={bounds.low.min}
                max={bounds.low.max}
                onCommit={(v) => setRange([v, scale[1]])}
              />
              <Stepper
                label={t("research.questionnaire.scaleMax")}
                value={stored ? stored[1] : null}
                min={bounds.high.min}
                max={bounds.high.max}
                onCommit={(v) => setRange([stored ? stored[0] : scale[0], v])}
              />
            </div>
          ) : null}
          {stored === null ? (
            <p role="note" className="text-xs text-status-you-ink">
              {tv("research.questionnaire.scaleEditor.invalidStored", { raw: JSON.stringify(raw ?? null), min: SCALE_END_MIN, max: SCALE_END_MAX })}
            </p>
          ) : null}
        </div>
      )}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-medium text-ink-muted">{t("research.questionnaire.scaleEditor.labels")}</span>
        {perPoint && stored && points(stored) > 2 ? (
          <ChoiceChips
            label={tv("research.questionnaire.scaleEditor.labelsOf", { name })}
            value={mode}
            options={[
              { key: "ends", label: t("research.questionnaire.scaleEditor.ends") },
              { key: "points", label: t("research.questionnaire.scaleEditor.every"), disabled: tooMany && mode !== "points" },
            ]}
            onChange={setMode}
          />
        ) : null}
        {perPoint && tooMany && mode !== "points" ? (
          <p className="text-xs text-ink-muted">{tv("research.questionnaire.scaleEditor.tooMany", { max: DESCRIBED_POINTS_MAX })}</p>
        ) : null}
        {!perPoint ? <p className="text-xs text-ink-muted">{t("research.questionnaire.scaleEditor.endsOnlyHere")}</p> : null}
        {mode === "points" && stored ? (
          <ol className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
            {labels.map((_, i) => {
              const n = stored[0] + i;
              return (
                <li key={i} className="flex min-w-0 items-baseline gap-2">
                  <span aria-hidden="true" className="inline-flex h-6 min-w-7 shrink-0 items-center justify-center rounded-sm border border-border-strong bg-surface-raised font-mono text-[11px]">{n}</span>
                  <LabelField
                    list={labels}
                    index={i}
                    label={tv("research.questionnaire.scaleEditor.point", { n })}
                    placeholder={tv("research.questionnaire.scaleEditor.pointPlaceholder", { n })}
                    onCommit={(v) => apply({ scale: stored, labels: withPoint(labels, i, v) }, 0)}
                  />
                </li>
              );
            })}
          </ol>
        ) : (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <LabelField
              list={ends}
              index={0}
              label={t("research.questionnaire.scaleLow")}
              placeholder={t("research.questionnaire.scaleEditor.lowPlaceholder")}
              disabled={!stored}
              disabledReason={disabledReason}
              onCommit={(v) => apply({ scale, labels: withEnd(labels, 0, v) }, 0)}
            />
            {/* On a phone the boxes take the first row and each end's label sits under its end:
                beside them the right label wrapped to a row of its own, away from the end it names. */}
            <Boxes scale={scale} className="max-sm:order-first max-sm:basis-full" />
            <LabelField
              className="max-sm:ml-auto"
              list={ends}
              index={1}
              label={t("research.questionnaire.scaleHigh")}
              placeholder={t("research.questionnaire.scaleEditor.highPlaceholder")}
              disabled={!stored}
              onCommit={(v) => apply({ scale, labels: withEnd(labels, 1, v) }, 0)}
            />
          </div>
        )}
        {problem ? (
          <p role="note" data-scale-labels-left-out className="text-xs text-status-you-ink">
            {t("research.questionnaire.scaleEditor.leftOut")} {problem}
          </p>
        ) : null}
      </div>
      {shared ? null : <UndoToast offer={local.current} onDone={local.clear} />}
    </div>
  );
}

/**
 * One label field, edited in place: never refused for being empty (an end may be left blank, said
 * below as left out), at most SCALE_LABEL_MAX characters and never repeating another point's label,
 * both refused at the field (I9).
 */
function LabelField({ list, index, label, placeholder, disabled = false, disabledReason, className, onCommit }: {
  list: readonly string[];
  index: number;
  label: string;
  placeholder: string;
  disabled?: boolean;
  disabledReason?: string;
  className?: string;
  onCommit: (value: string) => void;
}) {
  return (
    <InlineText
      className={className}
      value={list[index] ?? ""}
      label={label}
      placeholder={placeholder}
      disabled={disabled}
      disabledReason={disabledReason}
      rules={{
        required: false,
        maxLength: SCALE_LABEL_MAX,
        validate: (v) => (repeatsAnother(list, index, v) ? t("research.questionnaire.scaleEditor.repeated") : null),
      }}
      onCommit={onCommit}
    />
  );
}

/** The scale's points as boxes, or in words when there are too many to draw. */
function Boxes({ scale, className = "" }: { scale: Scale; className?: string }) {
  const n = points(scale);
  if (n > BOXES_MAX) {
    return <span className={`text-xs text-ink-muted ${className}`}>{tv("research.questionnaire.scaleEditor.wide", { range: rangeWords(scale), n })}</span>;
  }
  return (
    <span aria-hidden="true" className={`flex min-w-40 flex-1 gap-0.5 ${className}`}>
      {Array.from({ length: n }, (_, i) => (
        <i key={i} className="flex h-6 flex-1 items-center justify-center rounded-sm border border-border-strong bg-surface-raised font-mono text-[10px] not-italic">
          {scale[0] + i}
        </i>
      ))}
    </span>
  );
}
