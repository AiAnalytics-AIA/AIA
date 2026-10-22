// Every test runs in Europe/Prague, the product's zone, wherever it runs: CI's UTC has no 23- or
// 25-hour day, so a test that crosses a DST change would test nothing there (day-label.test.ts).
// Set before anything reads a Date or builds an Intl formatter.
process.env.TZ = "Europe/Prague";

// findBy* and waitFor wait 1 s by default, a size for an idle machine (CLAUDE.md §7). Measured
// on a loaded 4-core host: a step screen behind next/dynamic loads its module on first render,
// so "offers the three paths…" (QuestionnaireStep) found nothing after 1.17 s; the Metodika
// panel's first render (five fetches, then a large tree) had not appeared after 4 s at load
// average 18. 10 s is one budget for every lookup, set here instead of one test at a time (the
// 4-6 s overrides it replaces were each a smaller copy of it). No assertion changes: a lookup
// that never matches still fails, only later. Vitest's own vi.waitFor is not testing-library's
// and keeps its 1 s default; a call that needs more names its size where it is written.
import { configure } from "@testing-library/dom";

configure({ asyncUtilTimeout: 10_000 });
