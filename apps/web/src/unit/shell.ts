// The rail's status lines (ADR 0014, area A1), read from what the unit reports.
//
// 18.6.6's final updateState() prints "Core joint · VALID" unconditionally --
// a hard-coded string, whatever BOOT.joint_core.status says (on the workbench it
// says JOINT_UNVALIDATED). The rebuilt rail prints the reported status, or
// nothing when the unit reports none: never a guess (CLAUDE.md §8).

import { ShapeError } from "./projects";

export type RailStatus = {
  release: string | null;
  jointCore: string | null;
  claudeCode: "READY" | "CHECK" | null;
};

const isRecord = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);

/** /api/bootstrap: the edition's version and the joint core's status, nothing else. */
export function parseBootstrap(x: unknown): Pick<RailStatus, "release" | "jointCore"> {
  if (!isRecord(x)) throw new ShapeError("bootstrap není objekt");
  const edition = isRecord(x.edition) ? x.edition : {};
  const joint = isRecord(x.joint_core) ? x.joint_core : {};
  return {
    release: typeof edition.version === "string" && edition.version ? edition.version : null,
    jointCore: typeof joint.status === "string" && joint.status ? joint.status : null,
  };
}

/** /api/providers/claude-code/status: READY only on an explicit ok, as the classic dot. */
export function parseClaudeCode(x: unknown): RailStatus["claudeCode"] {
  if (!isRecord(x)) return null;
  return x.ok === true ? "READY" : "CHECK";
}
