// How the Deep Research tab turns typed text into a setting's JSON value, and what it says
// live still needs. The API checks bounds and the catalogue's rules; these are the shapes.
import { describe, expect, it } from "vitest";

import type { DrSetting, DrSettingsOverview } from "@/lib/api";
import { groupsInOrder, inputKind, missingForLive, parseInput, toInput } from "./deep-research-settings";

describe("parseInput", () => {
  it("reads a whole number for integers and days, and nothing else", () => {
    expect(parseInput("integer", " 400 ")).toEqual({ ok: true, value: 400 });
    expect(parseInput("days", "90")).toEqual({ ok: true, value: 90 });
    expect(parseInput("integer", "4.5")).toEqual({ ok: false, reason: "not_whole" });
    expect(parseInput("integer", "-1")).toEqual({ ok: false, reason: "not_whole" });
    expect(parseInput("days", "")).toEqual({ ok: false, reason: "empty" });
  });

  it("reads a decimal with a Czech comma or a dot for money", () => {
    expect(parseInput("usd", "2,50")).toEqual({ ok: true, value: 2.5 });
    expect(parseInput("usd", "1 000.25")).toEqual({ ok: true, value: 1000.25 });
    expect(parseInput("usd", "pět")).toEqual({ ok: false, reason: "not_number" });
  });

  it("reads a list one entry per line, blank lines dropped; an empty list is a value", () => {
    expect(parseInput("host_list", "a.example\r\n\n  b.example ")).toEqual({ ok: true, value: ["a.example", "b.example"] });
    expect(parseInput("pattern_list", "")).toEqual({ ok: true, value: [] });
  });

  it("reads yes/no as a boolean and passes text as typed, trimmed", () => {
    expect(parseInput("decision", "true")).toEqual({ ok: true, value: true });
    expect(parseInput("decision", "false")).toEqual({ ok: true, value: false });
    expect(parseInput("url", " https://example.org/terms ")).toEqual({ ok: true, value: "https://example.org/terms" });
    expect(parseInput("model_id", "eu.model:1")).toEqual({ ok: true, value: "eu.model:1" });
  });
});

describe("the form's starting value", () => {
  it("starts from what is in force, and from nothing when it is unknown", () => {
    expect(toInput("integer", 1000)).toBe("1000");
    expect(toInput("host_list", ["a.example", "b.example"])).toBe("a.example\nb.example");
    expect(toInput("days", null)).toBe("");
    expect(toInput("status", null)).toBe("proposed");
    expect(toInput("decision", null)).toBe("false");
  });

  it("edits a type it does not know as text", () => {
    expect(inputKind("something_new")).toBe("text");
  });
});

const setting = (key: string, group: string): DrSetting => ({
  key, group, type: "integer", label: key, unit: "", minimum: null, maximum: null, lower_only: false, required_for_live: true, method: false,
  default: null, default_source: "", value: null, origin: "proposed_default", version: null, approved_by: null, approved_at: null, version_count: 0, latest_number: null,
});

describe("the overview", () => {
  const overview: DrSettingsOverview = {
    catalogue_version: "c", may_administer: true,
    missing_for_live: ["retention.snapshots", "provider.search.plan"],
    settings: [setting("provider.search.plan", "provider"), setting("budgets.x", "budgets"), setting("retention.snapshots", "retention"), setting("provider.search.terms_url", "provider")],
  };

  it("lists what live needs in the catalogue's order, not the API list's", () => {
    expect(missingForLive(overview).map((s) => s.key)).toEqual(["provider.search.plan", "retention.snapshots"]);
  });

  it("groups settings in the order their groups first appear", () => {
    expect(groupsInOrder(overview.settings).map((g) => [g.group, g.settings.map((s) => s.key)])).toEqual([
      ["provider", ["provider.search.plan", "provider.search.terms_url"]],
      ["budgets", ["budgets.x"]],
      ["retention", ["retention.snapshots"]],
    ]);
  });
});
