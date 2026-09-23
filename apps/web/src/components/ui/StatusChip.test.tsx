import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusChip } from "./StatusChip";
import { StatusGlyph, TONE_SHAPE } from "./StatusGlyph";
import { TONE_CHIP } from "./tone";
import {
  ATTEMPT_STATUS, CLIENT_STATUS, FAILURE_CLASS, PROJECT_STATUS, RESERVATION_STATUS, STAGE_STATUS,
  STEP_RUN_STATUS, STUDY_STATUS, WORKFLOW_RUN_STATUS,
} from "@/design/enums";
import type { StatusKind, Tone } from "@/design/status";

const ALL: [StatusKind, readonly string[]][] = [
  ["StageStatus", STAGE_STATUS], ["WorkflowRunStatus", WORKFLOW_RUN_STATUS], ["StepRunStatus", STEP_RUN_STATUS],
  ["AttemptStatus", ATTEMPT_STATUS], ["ReservationStatus", RESERVATION_STATUS], ["StudyStatus", STUDY_STATUS],
  ["ClientStatus", CLIENT_STATUS], ["ProjectStatus", PROJECT_STATUS], ["FailureClass", FAILURE_CLASS],
];

describe("StatusChip — every domain status has text and shape, not only colour", () => {
  for (const [kind, values] of ALL) {
    it.each(values)(`${kind}.%s renders a glyph and a label`, (value) => {
      const { container } = render(<StatusChip kind={kind} value={value} />);
      const chip = container.firstElementChild as HTMLElement;
      expect(chip.getAttribute("data-status")).toBe(value);
      const glyph = chip.querySelector("svg[data-shape]");
      expect(glyph).not.toBeNull();
      expect(chip.textContent?.trim().length).toBeGreaterThan(0);
      expect(chip.textContent).not.toContain("Neznámý stav");
      expect(chip.textContent).not.toContain(value); // a Czech label, not the raw enum
    });
  }

  it("renders an unknown value as a fault with the raw value visible", () => {
    const { container } = render(<StatusChip kind="StageStatus" value="PAUSED_BY_ADMIN" />);
    const chip = container.firstElementChild as HTMLElement;
    expect(chip).toHaveAttribute("data-tone", "fault");
    expect(chip).toHaveTextContent("Neznámý stav: PAUSED_BY_ADMIN");
  });

  it("uses Czech labels with correct diacritics", () => {
    render(<StatusChip kind="StageStatus" value="WAITING_CREDITS" />);
    expect(screen.getByText("Čeká na kredity")).toBeInTheDocument();
    render(<StatusChip kind="WorkflowRunStatus" value="RECOVERY_REQUIRED" />);
    expect(screen.getByText("Vyžaduje rozhodnutí")).toBeInTheDocument();
  });
});

describe("StatusChip — DS-3: a person must act, but only the API says it is you", () => {
  it("shows WAITING_CREDITS as waiting on the team when actionability is not stated", () => {
    const { container } = render(<StatusChip kind="StageStatus" value="WAITING_CREDITS" showAudience />);
    expect(container.firstElementChild).toHaveAttribute("data-tone", "person");
    expect(container).toHaveTextContent("čeká na tým / správce");
    expect(container).not.toHaveTextContent("čeká na vás");
  });
  it("shows it as waiting on you only when the viewer can resolve it", () => {
    const { container } = render(<StatusChip kind="StageStatus" value="WAITING_CREDITS" viewer={{ viewerCanResolve: true }} showAudience />);
    expect(container.firstElementChild).toHaveAttribute("data-tone", "you");
    expect(container).toHaveTextContent("čeká na vás");
  });
  it("keeps it as the team's when the viewer cannot resolve it", () => {
    const { container } = render(<StatusChip kind="WorkflowRunStatus" value="AWAITING_BUDGET" viewer={{ viewerCanResolve: false }} showAudience />);
    expect(container.firstElementChild).toHaveAttribute("data-tone", "person");
  });
  it("shows WAITING_CAPACITY as external capacity, whoever is looking", () => {
    const { container } = render(<StatusChip kind="StageStatus" value="WAITING_CAPACITY" viewer={{ viewerCanResolve: true }} showAudience />);
    expect(container.firstElementChild).toHaveAttribute("data-tone", "world");
    expect(container).toHaveTextContent("čeká na externí kapacitu");
  });
  it("cannot be made personal for a status that is not waiting on a person", () => {
    const { container } = render(<StatusChip kind="StageStatus" value="RUNNING" viewer={{ viewerCanResolve: true }} />);
    expect(container.firstElementChild).toHaveAttribute("data-tone", "running");
  });
});

describe("StatusGlyph — the five room-scale states differ by shape alone", () => {
  it("gives running, person, world, fault and recovery five different shapes", () => {
    const five: Tone[] = ["running", "person", "world", "fault", "recovery"];
    expect(new Set(five.map((t) => TONE_SHAPE[t])).size).toBe(5);
    const markup = five.map((t) => { const r = render(<StatusGlyph tone={t} />); const h = r.container.innerHTML.replace(/data-shape="[^"]*"/, ""); r.unmount(); return h; });
    expect(new Set(markup).size).toBe(5);
  });
});

describe("Theme — chips use token utilities only, so light and dark both follow tokens", () => {
  it("never hardcodes a palette colour or hex value", () => {
    for (const cls of Object.values(TONE_CHIP)) {
      expect(cls).not.toMatch(/(zinc|gray|slate|amber|red|green|blue)-\d|#[0-9a-f]{3,6}|\bbg-white\b|\btext-white\b/);
    }
  });
  it("reserves the solid amber fill for the viewer's own waits", () => {
    const solid = (Object.entries(TONE_CHIP) as [Tone, string][]).filter(([, c]) => /\bbg-status-you(?![-\w])/.test(c)).map(([t]) => t);
    expect(solid).toEqual(["you"]);
  });
});
