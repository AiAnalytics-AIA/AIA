import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { ApiErrorPanel } from "./ApiErrorPanel";
import { ImpactPreview } from "./ImpactPreview";
import { ScopeHeader } from "./ScopeHeader";
import { StudyMoney } from "./StudyMoney";
import { Unavailable } from "./Unavailable";
import { FixtureNotice } from "./FixtureNotice";
import { cs } from "@/i18n/cs";
import type { ApiError } from "@/lib/api/client";

const error = (kind: ApiError["kind"]): ApiError => ({ kind, status: kind === "unreachable" ? null : 401, code: null, message: "m", requestId: "rq-1", path: "/studies" });

describe("ApiErrorPanel", () => {
  it.each(["unreachable", "unauthenticated", "not_provisioned", "organization_required", "not_found", "invalid_response", "error"] as const)(
    "%s is an alert with its own Czech title and recovery step",
    (kind) => {
      render(<ApiErrorPanel error={error(kind)} />);
      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent(cs.api.title[kind]);
      expect(alert).toHaveTextContent(cs.api.recovery[kind]);
      expect(alert).toHaveTextContent("/studies");
    },
  );
  it("shows the request id so a report can be traced", () => {
    render(<ApiErrorPanel error={error("error")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("rq-1");
  });
});

describe("Unavailable", () => {
  it("names the capability as unavailable, with owner and register — never as an empty result", () => {
    render(<Unavailable id="approvals" title="Schválení" />);
    const region = screen.getByRole("region", { name: "Schválení" });
    expect(region).toHaveTextContent(cs.unavailable.label);
    expect(region).toHaveTextContent("platform-runtime");
    expect(region).toHaveTextContent("OI-15");
  });
  it("refuses an id the registry does not list", () => {
    expect(() => render(<Unavailable id="nope" title="x" />)).toThrow(/UNAVAILABLE_CAPABILITIES/);
  });
  it("FixtureNotice refuses an unregistered fixture", () => {
    expect(() => render(<FixtureNotice capability="nope" />)).toThrow(/FIXTURE_CAPABILITIES/);
  });
});

describe("ScopeHeader", () => {
  it("writes the client's name beside the accent — colour is never the only cue", () => {
    render(<ScopeHeader client={{ client_id: "CLI-1", name: "Banka Horizont" }} crumbs={[{ label: "Studie A" }]} />);
    const nav = screen.getByRole("navigation", { name: cs.scope.client });
    expect(nav).toHaveTextContent("Banka Horizont");
    expect(nav).toHaveTextContent("Studie A");
    expect(nav.getAttribute("data-accent-slot")).toMatch(/^[1-6]$/);
  });
  it("marks the hash-derived accent as a temporary fallback until the slot is persisted", () => {
    const { container, rerender } = render(<ScopeHeader client={{ client_id: "CLI-1", name: "A" }} />);
    expect(container.querySelector('[data-unavailable="client-accent"]')).not.toBeNull();
    rerender(<ScopeHeader client={{ client_id: "CLI-1", name: "A", accent_slot: 3 }} />);
    expect(container.querySelector('[data-unavailable="client-accent"]')).toBeNull();
    expect(container.querySelector("[data-accent-slot]")?.getAttribute("data-accent-slot")).toBe("3");
  });
  it("a cross-client screen gets no client accent", () => {
    const { container } = render(<ScopeHeader client={null} />);
    expect(container.querySelector('[data-scope="above"]')).toHaveTextContent(cs.scope.aboveClients);
    expect(container.querySelector("[data-accent-slot]")).toBeNull();
  });
});

describe("StudyMoney", () => {
  it("renders a withheld cost as suppressed with its reason — not as missing, not as zero", () => {
    const { container } = render(<StudyMoney value={null} />);
    expect(container.querySelector('[data-state="suppressed"]')).toHaveTextContent(cs.study.costsWithheld);
    expect(container.textContent).not.toContain("0,00");
  });
  it("renders zero as a value", () => {
    const { container } = render(<StudyMoney value={0} />);
    expect(container.querySelector('[data-state="zero"]')?.textContent).toBe("0,00 USD");
  });
});

describe("ImpactPreview", () => {
  const ok = (data: { root_stage: string | null; invalidate: string[]; preserve: string[]; presentation_only: boolean }) => ({ ok: true as const, data, requestId: null });

  it("offers only the domain's impact fields", () => {
    render(<ImpactPreview projectType="research" field={null} result={null} />);
    const options = within(screen.getByLabelText(cs.impact.field)).getAllByRole("option");
    expect(options.map((o) => o.getAttribute("value"))).toContain("audience");
    expect(options.map((o) => o.getAttribute("value"))).not.toContain("");
  });

  it("renders the server's split as given, with Czech stage labels", () => {
    const { container } = render(
      <ImpactPreview projectType="research" field="audience" result={ok({ root_stage: "AUDIENCE", invalidate: ["AUDIENCE", "REPORT"], preserve: ["BRIEF"], presentation_only: false })} />,
    );
    expect(container.querySelector('[data-impact="invalidated"]')).toHaveTextContent("Cílová skupina");
    expect(container.querySelector('[data-impact="invalidated"]')).toHaveTextContent("(2)");
    expect(container.querySelector('[data-impact="preserved"]')).toHaveTextContent("(1)");
    expect(screen.queryByText(cs.impact.presentationOnly)).toBeNull();
  });

  it("says when a change is presentation-only", () => {
    render(<ImpactPreview projectType="research" field="report_style" result={ok({ root_stage: "REPORT", invalidate: ["REPORT", "DELIVERY"], preserve: [], presentation_only: true })} />);
    expect(screen.getByRole("note")).toHaveTextContent(cs.impact.presentationOnly);
  });

  it("shows cost and duration as missing (OI-10), never as zero", () => {
    const { container } = render(<ImpactPreview projectType="research" field="goal" result={ok({ root_stage: "BRIEF", invalidate: ["BRIEF"], preserve: [], presentation_only: false })} />);
    const estimate = container.querySelector('[data-unavailable="impact-estimate"]');
    expect(estimate?.querySelectorAll('[data-state="na"]')).toHaveLength(2);
    expect(estimate?.textContent).not.toMatch(/\b0\b/);
  });

  it("renders an API failure as an error, not as 'nothing changes'", () => {
    render(<ImpactPreview projectType="research" field="goal" result={{ ok: false, error: error("error") }} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText(cs.impact.none)).toBeNull();
  });
});
