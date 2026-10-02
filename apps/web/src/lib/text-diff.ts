// A line diff for comparing two versions of a prompt. Pure, no dependencies.
//
// Prompts are short (the store caps them at 12 000 characters), so the textbook
// longest-common-subsequence table is exact and cheap; there is no heuristic that
// could show a change that is not there or hide one that is.

export type DiffOp = { kind: "same" | "add" | "del"; text: string };

/** The line-level edit script from `before` to `after`. Line endings are normalised. */
export function diffLines(before: string, after: string): DiffOp[] {
  const a = split(before);
  const b = split(after);
  // lcs[i][j]: length of the longest common subsequence of a[i..] and b[j..].
  const lcs: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const ops: DiffOp[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      ops.push({ kind: "same", text: a[i] });
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      ops.push({ kind: "del", text: a[i++] });
    } else {
      ops.push({ kind: "add", text: b[j++] });
    }
  }
  while (i < a.length) ops.push({ kind: "del", text: a[i++] });
  while (j < b.length) ops.push({ kind: "add", text: b[j++] });
  return ops;
}

/** True when the two texts differ at all (after line-ending normalisation). */
export function differs(before: string, after: string): boolean {
  return normalise(before) !== normalise(after);
}

/** How many lines were added and removed, for a one-line summary of a change. */
export function summarise(ops: DiffOp[]): { added: number; removed: number } {
  return {
    added: ops.filter((o) => o.kind === "add").length,
    removed: ops.filter((o) => o.kind === "del").length,
  };
}

const normalise = (text: string) => text.replace(/\r\n?/g, "\n");
const split = (text: string) => normalise(text).split("\n");
