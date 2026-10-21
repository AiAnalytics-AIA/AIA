import { describe, expect, it } from "vitest";
import { removeAttachment, restoreAttachment } from "./brief";
import type { ResearchProject } from "./model";

const p = (attachments: unknown[]) => ({ briefing: { attachments, situation: "S" } }) as unknown as ResearchProject;
const a = { kind: "url", url: "https://a.test" }, b = { kind: "file", attachment_id: "ART-1" }, c = { kind: "url", url: "https://c.test" };

describe("restoreAttachment: the undo of removeAttachment (audit A28)", () => {
  it("puts the record back where it was, keeping the rest of the briefing", () => {
    const removed = removeAttachment(p([a, b, c]), 1);
    expect(restoreAttachment(removed, 1, b)).toEqual(p([a, b, c]));
  });
  it("puts it at the end when the list has since grown shorter, and into an empty brief", () => {
    expect(restoreAttachment(p([a]), 5, b).briefing.attachments).toEqual([a, b]);
    expect(restoreAttachment({ briefing: {} } as unknown as ResearchProject, 0, b).briefing.attachments).toEqual([b]);
  });
});
