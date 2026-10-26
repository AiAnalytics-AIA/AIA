"use client";

// The sample size, set in one place per layout: Vzorek in the workbench, Dimenze in the classic layout,
// which has no Vzorek (artifact-sample SMP7, artifact-dimensions DIM3b; Nigel, 26 Oct 2026). One Stepper
// bounded by the server's valid n (RQC9), a value outside it refused at the field and never clamped, and
// the recommendation offered only within it. The caller marks it sample:n, once on its page.

import { Stepper } from "@/components/ui/Stepper";
import { TOUCH } from "@/components/ui/parts";
import { t, tv } from "@/i18n/t";
import { rangeWords } from "@/lib/number-input";
import { type Change, type SampleRefusal, applyRecommendedSample, isSampleRefusal, recommendedSample, sampleRefusalMessage, setSampleSize } from "@/research/persona";
import { useResearch } from "./context";
import { readyLimits, useSampleLimits } from "./useSampleLimits";

const PRESET = `inline-flex items-center ${TOUCH} rounded-pill border border-border bg-surface px-2.5 font-mono text-xs leading-6 text-ink hover:border-signal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring`;

export function SampleSize() {
  const { store, state, frame } = useResearch();
  const sampleLimits = useSampleLimits(frame.studyId);
  const limits = readyLimits(sampleLimits);
  const p = state.project;
  const r = recommendedSample(p);
  const storedN = Number(p.n) > 0 ? Number(p.n) : null;
  const n = storedN ?? r.n;
  const allowed = (x: number) => limits !== null && x >= limits.min && x <= limits.max;
  const apply = (c: Change) => store.update(() => ({ project: c.project }), { reason: c.reason });
  /** A sample size the Stepper already checked; a refusal still throws, and the Stepper says Neuloženo. */
  const applySample = (c: Change | SampleRefusal) => {
    if (isSampleRefusal(c)) throw new Error(c.message);
    apply(c);
  };
  return (
    <>
      <div>
        {limits ? (
          <Stepper
            key={n}
            label={t("research.persona.sampleLabel")}
            value={n}
            min={limits.min}
            max={limits.max}
            step={50}
            disabled={!frame.canEdit}
            onCommit={(v) => applySample(setSampleSize(store.get().project, String(v), limits))}
          />
        ) : sampleLimits.state === "failed" ? (
          <p role="alert" className="text-xs text-status-fault">
            {tv("research.persona.sampleStored", { n })} {sampleRefusalMessage("limits_unknown", null)}
          </p>
        ) : (
          <p className="text-xs text-ink-muted">{t("research.persona.sampleLoading")}</p>
        )}
      </div>
      {limits && storedN !== null && !allowed(storedN) ? (
        <p role="alert" className="mt-1 text-xs text-status-fault">{tv("research.persona.sampleStoredOutside", { n: storedN, range: rangeWords(limits) })}</p>
      ) : null}
      <div className="mt-3">
        <button
          type="button"
          disabled={!frame.canEdit || !allowed(r.n) || storedN === r.n}
          // Offered only within the valid n (disabled otherwise), so it is stored as it is.
          onClick={() => apply(applyRecommendedSample(store.get().project))}
          className={PRESET}
        >
          {tv("research.persona.sampleUse", { n: r.n })}
        </button>
      </div>
      <p className={`mt-3 text-xs leading-[18px] ${n < r.n ? "text-status-you-ink" : "text-ink-muted"}`}>
        {n < r.n ? tv("research.persona.sampleBelow", { n: r.n }) : r.why}
      </p>
    </>
  );
}
