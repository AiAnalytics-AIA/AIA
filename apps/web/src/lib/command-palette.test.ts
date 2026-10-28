import { describe, expect, it } from "vitest";

import type { ClientCard } from "@/lib/api";
import { clientEntries, fold, matchEntries, moveSelection, staticEntries } from "./command-palette";

const client = (id: string, name: string, recent: { id: string; name: string }[] = []): ClientCard => ({
  client_id: id, name, slug: id, your_role: null, active_count: 0, study_count: recent.length, modified_at: null,
  recent: recent.map((s) => ({ study_id: s.id, client_id: id, name: s.name, slug: s.id, kind: "RESEARCH", status: "ACTIVE", accepts_work: true, last_stage: null }) as ClientCard["recent"][number]),
});

describe("command palette", () => {
  it("folds case and accents", () => {
    expect(fold("Rozpočet Studie")).toBe("rozpocet studie");
  });

  it("offers the global places and every settings section", () => {
    const ids = staticEntries().map((e) => e.id);
    expect(ids).toContain("go:clients");
    expect(ids).toContain("go:lead");
    expect(ids).toContain("settings:deep_research");
    expect(staticEntries().find((e) => e.id === "settings:access")!.href).toBe("/app/settings#access");
  });

  it("lists a client and its recent studies, each with its own address", () => {
    const e = clientEntries([client("c1", "Pivovar Zlatá Hora", [{ id: "s1", name: "Vnímání značek" }])]);
    expect(e.map((x) => x.href)).toEqual(["/app/clients/c1", "/app/clients/c1/research/s1"]);
    expect(e[1]!.sub).toBe("Pivovar Zlatá Hora");
  });

  it("matches every typed word, accents ignored, against the label and its line", () => {
    const all = [...staticEntries(), ...clientEntries([client("c1", "Pivovar Zlatá Hora", [{ id: "s1", name: "Vnímání značek" }])])];
    expect(matchEntries(all, "zlata").map((e) => e.id)).toEqual(["client:c1", "study:s1"]);
    expect(matchEntries(all, "vnimani zlata").map((e) => e.id)).toEqual(["study:s1"]);
    expect(matchEntries(all, "neexistuje")).toEqual([]);
    expect(matchEntries(all, "").length).toBe(all.length);
  });

  it("wraps the selection and has none when nothing matches", () => {
    expect(moveSelection(0, -1, 3)).toBe(2);
    expect(moveSelection(2, 1, 3)).toBe(0);
    expect(moveSelection(0, 1, 0)).toBe(-1);
  });
});
