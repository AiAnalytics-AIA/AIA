// @vitest-environment jsdom
// The experimental Sociomapping on the Results page: it says what it is first, draws the
// stored map, rotates and switches to a top view, shows an object's stored details and the
// fit, lists the limitations, and offers the internal draft. Fixture from the real builder.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { type Artifact, type ResearchRun, research } from "@/lib/api";
import fixture from "@/lib/fixtures/sociomapping.json";
import { SociomappingView } from "./SociomappingView";

const artifact = { artifact_id: "ART-9", sha256: "a".repeat(64), payload: fixture } as unknown as Artifact;
const run = { run_id: "RUN-1", steps: [{ node_key: "sociomapping_report", status: "SUCCEEDED", artifact_id: "ART-10" }] } as unknown as ResearchRun;

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SociomappingView", () => {
  it("says it is experimental, draws the stored points and explains what is missing", async () => {
    vi.spyOn(research, "sociomappingReport").mockResolvedValue({ run_id: "RUN-1", state: "READY", internal_only: true, artifact_id: "ART-10", sha256: "b".repeat(64), review_state: "DRAFT_UNAPPROVED" });
    render(<SociomappingView artifact={artifact} run={run} studyId="STU-1" canEdit />);
    expect(screen.getAllByRole("note")[0].textContent).toContain("nejde o ověřenou rekonstrukci SOMECS");
    expect(screen.getByText(/Fiktivní data/)).toBeTruthy();
    for (const id of ["altair", "borealis", "cirrus", "delta"]) expect(screen.getByTestId(`sociomapping-point-${id}`)).toBeTruthy();
    expect(screen.queryByTestId("sociomapping-point-echo")).toBeNull();
    expect(screen.getByText(/Mimo mapu/)).toBeTruthy();
    expect(screen.getByTestId("sociomapping-accuracy").textContent).toMatch(/^\d,\d{3}/);
    expect(screen.getByText(/Otevřená otázka M12/)).toBeTruthy();
    await waitFor(() => expect(screen.getByRole("button", { name: "Stáhnout zprávu (DOCX)" })).toBeTruthy());
  });

  it("rotates, tilts to a top view and shows a chosen object's stored relations", () => {
    vi.spyOn(research, "sociomappingReport").mockResolvedValue({ run_id: "RUN-1", state: "PENDING", internal_only: true });
    render(<SociomappingView artifact={artifact} run={run} studyId="STU-1" canEdit />);
    const point = () => screen.getByTestId("sociomapping-point-altair").querySelector("circle")!.getAttribute("cx");
    const before = point();
    fireEvent.click(screen.getByRole("button", { name: "Otočit vlevo" }));
    expect(point()).not.toBe(before);
    fireEvent.click(screen.getByRole("button", { name: "Pohled shora" }));
    expect(screen.getByTestId("sociomapping-point-altair").querySelector("line")).toBeNull(); // no stems from above
    fireEvent.keyDown(screen.getByTestId("sociomapping-map"), { key: "+" });
    fireEvent.click(screen.getByTestId("sociomapping-point-delta"));
    const details = screen.getByTestId("sociomapping-details");
    expect(within(details).getByText("Delta")).toBeTruthy();
    expect(within(details).getByText("nedefinováno")).toBeTruthy(); // Echo: no relation, kept
    expect(within(details).getByText("every answer equal for echo")).toBeTruthy();
    expect(details.querySelector(".text-status-fault")?.textContent).toMatch(/^-0,9/); // negative, signed
  });

  it("refuses a result that does not say it is experimental", () => {
    const upgraded = { ...artifact, payload: { sociomapping: { ...fixture.sociomapping, client_facing: true } } } as unknown as Artifact;
    render(<SociomappingView artifact={upgraded} run={run} studyId="STU-1" canEdit />);
    expect(screen.getByRole("alert").textContent).toContain("neříká, že je experimentální");
    expect(screen.queryByTestId("sociomapping-map")).toBeNull();
  });
});
