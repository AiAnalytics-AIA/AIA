// How a run's results read in words (plan research-results-clarity, chunk 2).
import { describe, expect, it } from "vitest";

import type { QuestionResult } from "./research-execution";
import { citedMeasure, compareObjects, czechList, inlineRuns, measureAnchor, measureTarget, objectTarget, readMeasure, separation, setTarget, textBlocks } from "./result-reading";

const support = (status: "REPORTABLE" | "INDICATIVE" | "SUPPRESS") => ({ support_status: status, n_platnych: 140, n_unique_layer_donors: 120, effective_n: 110 });
const choice = (status: "REPORTABLE" | "INDICATIVE" | "SUPPRESS", shares: Record<string, [number, number, number] | [number]>, typ = "vyber"): QuestionResult => ({
  typ, ...support(status),
  celkem_pct: Object.fromEntries(Object.entries(shares).map(([k, v]) => [k, v[0]])),
  intervaly_95: Object.fromEntries(Object.entries(shares).filter(([, v]) => v.length === 3).map(([k, v]) => [k, { low: v[1], high: v[2] }])),
});
const scale = (status: "REPORTABLE" | "INDICATIVE" | "SUPPRESS", mean: number | null, low?: number, high?: number): QuestionResult => ({
  typ: "skala", ...support(status), prumer: mean,
  prumer_interval_95: low === undefined ? null : { low, high },
  top2box_pct: 41, top2box_interval_95: { low: 35, high: 47 },
});

describe("separation", () => {
  it("orders two estimates only when one interval lies wholly above the other", () => {
    expect(separation({ value: 50, low: 45, high: 55 }, { value: 30, low: 25, high: 35 })).toBe("ABOVE");
    expect(separation({ value: 38.4, low: 33, high: 43.2 }, { value: 34.8, low: 30.1, high: 39.9 })).toBe("OVERLAP");
    expect(separation({ value: 50, low: null, high: null }, { value: 1, low: 0, high: 2 })).toBe("UNKNOWN");
  });
});

describe("readMeasure", () => {
  it("does not name a winner whose interval overlaps the runner-up's", () => {
    // The fixture the PR's first summary got wrong: Čaj is ahead only by its estimate.
    const reading = readMeasure(choice("REPORTABLE", { Kávu: [34.8, 30.1, 39.9], Čaj: [38.4, 33, 43.2] }));
    expect(reading.tone).toBe("plain");
    expect(reading.text).toBe("Nejvíce odpovědí: Čaj (38,4 %) a Kávu (34,8 %); pořadí mezi nimi nelze potvrdit, 95% intervaly se překrývají.");
    expect(reading.text).not.toMatch(/Nejčastější odpověď/);
  });

  it("names the leading answer when its interval parts from every other", () => {
    const reading = readMeasure(choice("REPORTABLE", { Ano: [62, 56, 68], Ne: [30, 25, 35], "Nevím": [8, 5, 11] }));
    expect(reading.text).toBe("Nejčastější odpověď: Ano (62,0 %, 95% interval 56,0–68,0 %), spolehlivě před ostatními odpověďmi.");
  });

  it("never reads a missing interval as an order", () => {
    expect(readMeasure(choice("REPORTABLE", { Ano: [62], Ne: [30, 25, 35] })).text)
      .toBe("Nejvíce odpovědí: Ano (62,0 %); bez intervalu nelze pořadí odpovědí posoudit.");
    expect(readMeasure(choice("REPORTABLE", { Ano: [62, 56, 68], Ne: [30] })).text)
      .toMatch(/pořadí mezi nimi nelze potvrdit, některé intervaly chybějí nebo se překrývají/);
  });

  it("speaks of choices, not answers, for a multiple choice", () => {
    expect(readMeasure(choice("REPORTABLE", { A: [70, 64, 76], B: [20, 15, 25] }, "multi")).text)
      .toMatch(/^Nejčastěji vybíráno: A .*spolehlivě před ostatními možnostmi\.$/);
  });

  it("shortens a long tie to the first names and how many more", () => {
    const many = Object.fromEntries(["A", "B", "C", "D", "E", "F"].map((k, i) => [k, [20 - i, 10, 30] as [number, number, number]]));
    expect(readMeasure(choice("REPORTABLE", many)).text).toMatch(/A \(20,0 %\), B \(19,0 %\), C \(18,0 %\) a 3 dalších možností/);
  });

  it("reads a scale's mean with its interval and the scale it was asked on", () => {
    expect(readMeasure(scale("REPORTABLE", 3.42, 3.2, 3.61), [1, 5]).text)
      .toBe("Průměr 3,42 na škále 1–5 (95% interval 3,20–3,61). Horní dva body: 41,0 %.");
    expect(readMeasure(scale("REPORTABLE", 3.42), null, 3).text).toBe("Průměr 3,42 (interval chybí). Horní body (3): 41,0 %.");
  });

  it("says indicative first and shows no number when suppressed", () => {
    expect(readMeasure(scale("INDICATIVE", 3.42, 3.2, 3.61), [1, 5])).toEqual({ tone: "indicative", text: "Orientační: Průměr 3,42 na škále 1–5 (95% interval 3,20–3,61). Horní dva body: 41,0 %." });
    const suppressed = readMeasure(scale("SUPPRESS", 3.73, 3.25, 4.28));
    expect(suppressed).toEqual({ tone: "suppressed", text: "Číselný výsledek je skrytý: podpora dat nestačí." });
    expect(suppressed.text).not.toMatch(/\d/);
  });

  it("says when a question has no numeric summary", () => {
    expect(readMeasure({ typ: "otevrena", ...support("REPORTABLE"), verbatimy: ["dobré"] }).text).toMatch(/^Otevřená otázka: \d+ odpovědí, nekódováno\.$/);
    expect(readMeasure({ typ: "otevrena", ...support("REPORTABLE") }).tone).toBe("empty");
  });
});

describe("compareObjects", () => {
  const object = (id: string, mean: number | null, low?: number, high?: number, status: "REPORTABLE" | "INDICATIVE" | "SUPPRESS" = "REPORTABLE") =>
    ({ id, label: id.toUpperCase(), result: scale(status, mean, low, high) });

  it("names a reliable top and a tied bottom, highest first", () => {
    const c = compareObjects([object("b", 3.0, 2.7, 3.3), object("a", 4.2, 4.0, 4.4), object("c", 2.9, 2.6, 3.2)], [1, 5]);
    expect(c.ranked.map((o) => o.id)).toEqual(["a", "b", "c"]);
    expect(c.domain).toEqual([1, 5]);
    expect(c.top).toBe("Spolehlivě nejvýše hodnocený: A.");
    expect(c.bottom).toBe("Nejníže hodnocené: B a C; pořadí mezi nimi nelze potvrdit.");
  });

  it("says the objects do not differ when every interval meets the leader's", () => {
    const c = compareObjects([object("a", 3.1, 2.8, 3.4), object("b", 3.0, 2.7, 3.3)]);
    expect(c.top).toMatch(/^Objekty se od sebe spolehlivě neliší/);
    expect(c.bottom).toBeNull();
    expect(c.domain).toEqual([2.7, 3.4]);
  });

  it("leaves suppressed and empty objects out, by name, and orders nothing without intervals", () => {
    const c = compareObjects([object("a", 4.2, 4.0, 4.4), object("b", 3.7, 3.2, 4.3, "SUPPRESS"), object("c", null), object("d", 2.0)]);
    expect(c.omitted).toEqual(["B", "C"]);
    expect(c.ranked.map((o) => o.id)).toEqual(["a", "d"]);
    expect(c.top).toBe("Pořadí objektů nelze posoudit: u některých chybí interval.");
  });

  it("keeps each withheld object with its reason, its donors and Kish n, and never a number", () => {
    const c = compareObjects([object("a", 4.2, 4.0, 4.4), object("b", 3.7, 3.2, 4.3, "SUPPRESS"), object("c", null)]);
    expect(c.withheld).toEqual([
      { id: "b", label: "B", reason: "suppressed", donors: expect.any(Number), effectiveN: expect.any(Number) },
      { id: "c", label: "C", reason: "no_mean", donors: expect.any(Number), effectiveN: expect.any(Number) },
    ]);
    expect(c.withheld.map((o) => o.label)).toEqual(c.omitted);
    expect(Object.keys(c.withheld[0])).not.toContain("value");
    expect(c.ranked[0].effectiveN).toEqual(expect.any(Number));
  });

  it("reads a Kish n the aggregate did not store as unknown, never zero", () => {
    const c = compareObjects([{ id: "a", label: "A", result: { ...scale("REPORTABLE", 4.2, 4.0, 4.4), effective_n: undefined as unknown as number } }]);
    expect(c.ranked[0].effectiveN).toBeNull();
  });

  it("says nothing about order with fewer than two objects", () => {
    expect(compareObjects([object("a", 4.2, 4, 4.4)], [1, 5])).toMatchObject({ top: null, bottom: null });
  });
});

describe("citedMeasure", () => {
  const spec = {
    questions: [{ id: "q2", text: "Který nápoj byste si vybrali?", typ: "vyber", options: ["Kávu", "Čaj"] }],
    batteries: [{ id: "napoje", title: "Nápoje", scale: [1, 5] as [number, number], objects: [{ id: "kava", label: "Káva" }] }],
  };

  it("resolves a question's option share, mean and counts to the Data card", () => {
    const share = citedMeasure("q2.pct.2", spec)!;
    expect(share).toMatchObject({ measureId: "q2", title: "Který nápoj byste si vybrali?", what: "podíl odpovědi „Čaj“" });
    expect(share.format(38.4)).toBe("38,4 %");
    expect(citedMeasure("q2.n", spec)!.format(140)).toBe("140");
    expect(citedMeasure("q2.effective_n", spec)!.format(110.25)).toBe("110,3");
    // At the places the claim was admitted at, when it says (V1b): never rounded again.
    expect(share.format(38, 0)).toBe("38 %");
    expect(share.format(38.462, 3)).toBe("38,462 %");
    expect(citedMeasure("q2.n", spec)!.format(140, 0)).toBe("140");
  });

  it("resolves a set object's rating to its object card", () => {
    const mean = citedMeasure("napoje_obj_kava.mean", spec)!;
    expect(mean).toMatchObject({ measureId: "napoje:kava", title: "Káva (Nápoje)", what: "průměr" });
    expect(mean.format(4.2)).toBe("4,20");
    expect(citedMeasure("napoje_obj_kava.top2box", spec)!.what).toBe("horní body škály");
  });

  it("still names what it can without the specification, and nothing for an unknown reference", () => {
    // Without wording a question is said to have none (6c); its id stays the link, never the title.
    expect(citedMeasure("q9.pct.3", null)).toMatchObject({ measureId: "q9", title: "Otázka bez uloženého znění", what: "podíl odpovědi „možnost 3“" });
    expect(citedMeasure("q9.median", spec)).toBeNull();
  });

  it("gives every measure an anchor that is a valid fragment", () => {
    expect(measureAnchor("napoje:kava")).toBe("measure-napoje-kava");
    expect(measureAnchor("q2")).toBe("measure-q2");
  });
});

describe("textBlocks", () => {
  const words = (s: string) => s.replace(/(^|\n)\s*(#+|[-*•–]|\d+[.)])\s+/g, "$1").split(/\s+/).filter(Boolean);
  const blockWords = (blocks: ReturnType<typeof textBlocks>) =>
    blocks.flatMap((b) => (b.kind === "list" ? b.items : [b.text])).join(" ").split(/\s+/).filter(Boolean);

  it("splits paragraphs, lists and headings and keeps every word", () => {
    const text = "## Shrnutí\nKáva vede u mladších.\nČaj u starších.\n\nHlavní body:\n- první bod\n  pokračuje zde\n- druhý bod\n\n1. krok jedna\n2) krok dva";
    const blocks = textBlocks(text);
    expect(blocks).toEqual([
      { kind: "heading", text: "Shrnutí" },
      { kind: "paragraph", text: "Káva vede u mladších. Čaj u starších." },
      { kind: "paragraph", text: "Hlavní body:" },
      { kind: "list", ordered: false, items: ["první bod pokračuje zde", "druhý bod"], start: 1 },
      { kind: "list", ordered: true, items: ["krok jedna", "krok dva"], start: 1 },
    ]);
    expect(blockWords(blocks)).toEqual(words(text));
  });

  it("keeps a date that starts a line as text, and a list's own first number", () => {
    expect(textBlocks("1. ledna 2024 vstoupil zákon v platnost.")).toEqual([{ kind: "paragraph", text: "1. ledna 2024 vstoupil zákon v platnost." }]);
    expect(textBlocks("3. třetí\n4. čtvrtý")).toEqual([{ kind: "list", ordered: true, items: ["třetí", "čtvrtý"], start: 3 }]);
  });

  it("reads plain text as one paragraph and nothing as nothing", () => {
    expect(textBlocks("Jedna věta.\r\nDruhá věta.")).toEqual([{ kind: "paragraph", text: "Jedna věta. Druhá věta." }]);
    expect(textBlocks(null)).toEqual([]);
    expect(textBlocks("  \n\n ")).toEqual([]);
  });

  it("keeps a hyphenated or numeric sentence as text, not a list", () => {
    expect(textBlocks("2024 byl rok změn.\nČesko-slovenský trh roste.")).toEqual([{ kind: "paragraph", text: "2024 byl rok změn. Česko-slovenský trh roste." }]);
  });

  it("drops only the bold markers", () => {
    expect(inlineRuns("Tržní podíl **roste** rychle")).toEqual([{ text: "Tržní podíl ", bold: false }, { text: "roste", bold: true }, { text: " rychle", bold: false }]);
    expect(inlineRuns("bez zvýraznění")).toEqual([{ text: "bez zvýraznění", bold: false }]);
  });

  it("joins long lists in Czech", () => {
    expect(czechList(["A"])).toBe("A");
    expect(czechList(["A", "B"])).toBe("A a B");
    expect(czechList(["A", "B", "C"])).toBe("A, B a C");
  });
});

describe("the Lead's targets on Výsledky", () => {
  it("names a measure, a set and an object row as the Lead's focus finds them", () => {
    expect(measureTarget("q2")).toBe("measure:q2");
    expect(measureTarget("napoje:caj")).toBe("measure:napoje:caj");
    expect(setTarget("napoje")).toBe("set:napoje");
    expect(objectTarget("napoje", "caj")).toBe("object:napoje.caj");
  });
});
