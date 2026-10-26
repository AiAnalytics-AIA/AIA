// Co Vedoucí vidí (lead-conversation LC2): a Lead turn's manifest in words, pure. The manifest is
// read from the context the turn froze (GET …/lead/turns/{id}/manifest); a layer it does not hold
// is said to be unrecorded, never shown as empty, and a count nobody recorded is unknown, never 0.

export type OmittedId = { id: string; reason: string };
export type ManifestLayer = {
  layer: string;
  recorded: boolean;
  bytes?: number | null;
  ceiling_bytes: number | null;
  bounded_bytes?: number | null;
  included: string[];
  included_count?: number | null;
  omitted: OmittedId[];
  omitted_count?: number | null;
};
export type ContextManifest = { manifest_version: number; total_bytes: number; ceiling_bytes: number; layers: ManifestLayer[] };
export type TurnManifest = { turn_id: string; recorded: boolean; manifest: ContextManifest | null };
export type OmittedPage = { layer: string; after: number; total: number; omitted: OmittedId[] };

/** Each declared layer's name, in the order the Lead reads them (domain/lead_context.py). */
const LAYER_WORDS: Readonly<Record<string, string>> = {
  prompt: "Pokyny Vedoucího",
  lead: "Jeho soubory a poznámky",
  knowledge: "Znalosti klienta",
  study: "Studie",
  design: "Pracovní kopie a její rozbor",
  runs: "Běhy výzkumu",
  deep_research: "Hloubkový výzkum studie",
  targets: "Výsledky k výkladu",
  external_context_not_evidence: "Design Research (kontext, ne důkaz)",
  view: "Kde jste byli a vaše zpráva",
  memory: "Co jste spolu rozhodli",
  conversation: "Rozhovor",
};

/** What a layer's ids are, counted ("3 poznámky"): only the layers whose ids are items. */
const ITEMS: Readonly<Record<string, readonly [string, string, string]>> = {
  lead: ["poznámka", "poznámky", "poznámek"],
  knowledge: ["znalost", "znalosti", "znalostí"],
  runs: ["běh", "běhy", "běhů"],
  deep_research: ["běh", "běhy", "běhů"],
  targets: ["výsledek", "výsledky", "výsledků"],
  memory: ["záznam", "záznamy", "záznamů"],
};

const REASON_WORDS: Readonly<Record<string, string>> = {
  over_budget: "nevešla se do limitu vrstvy",
  unreadable: "specifikaci běhu se nepodařilo přečíst",
};

const kb = (bytes: number) => `${(bytes / 1024).toLocaleString("cs-CZ", { maximumFractionDigits: 1 })} kB`;

function counted(n: number, [one, few, many]: readonly [string, string, string]): string {
  return `${n} ${n === 1 ? one : n >= 2 && n <= 4 ? few : many}`;
}

export function layerName(layer: string): string {
  return LAYER_WORDS[layer] ?? layer;
}

export function reasonWords(reason: string): string {
  return REASON_WORDS[reason] ?? reason;
}

/** The whole context's size against its bound, or null when nothing was recorded. */
export function totalLine(m: TurnManifest): string | null {
  return m.manifest ? `Celkem ${kb(m.manifest.total_bytes)} z ${kb(m.manifest.ceiling_bytes)}` : null;
}

/** One layer's facts in words: its size against its own bound, what it carried and what it
 *  left out, by count. Unrecorded: one line saying so. */
export function layerLines(l: ManifestLayer): string[] {
  if (!l.recorded) return ["Nezaznamenáno: tato odpověď vrstvu neměla."];
  const lines: string[] = [];
  const size = l.bounded_bytes ?? l.bytes;
  if (typeof size === "number") lines.push(l.ceiling_bytes ? `${kb(size)} z ${kb(l.ceiling_bytes)}` : kb(size));
  const items = ITEMS[l.layer];
  if (items && typeof l.included_count === "number") lines.push(`Viděl ${counted(l.included_count, items)}`);
  if (typeof l.omitted_count === "number" && l.omitted_count > 0) {
    lines.push(l.layer === "conversation"
      ? `Starší tahy vynechány: ${l.omitted_count}`
      : `Vynecháno: ${l.omitted_count}`);
  } else if (l.omitted_count === null || l.omitted_count === undefined) {
    // The layer keeps its newest and drops the rest uncounted: unknown, never "nothing left out".
    lines.push("Starší vynechané se nepočítají");
  }
  return lines;
}

/** Whether the layer left out more ids than the manifest lists (the rest page from the server). */
export function moreOmitted(l: ManifestLayer, shown: number): boolean {
  return l.recorded && l.layer !== "conversation" && typeof l.omitted_count === "number" && l.omitted_count > shown;
}
