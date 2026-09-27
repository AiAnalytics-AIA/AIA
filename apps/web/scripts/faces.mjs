/**
 * The self-hosted faces, served from public/skin/fonts/ at /skin/fonts/. One list:
 * AIA's own pages import the fonts.css that build-tokens.mjs generates from these
 * entries. The family names must match the first entry of each stack in
 * tokens.type.families; build-tokens.mjs refuses a stack no entry provides.
 */
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

export const FACES = [
  { family: "IBM Plex Sans", file: "IBMPlexSans-Regular.woff2", weight: 400, style: "normal" },
  { family: "IBM Plex Sans", file: "IBMPlexSans-Italic.woff2", weight: 400, style: "italic" },
  { family: "IBM Plex Sans", file: "IBMPlexSans-Medium.woff2", weight: 500, style: "normal" },
  { family: "IBM Plex Sans", file: "IBMPlexSans-SemiBold.woff2", weight: 600, style: "normal" },
  { family: "IBM Plex Mono", file: "IBMPlexMono-Regular.woff2", weight: 400, style: "normal" },
  { family: "IBM Plex Mono", file: "IBMPlexMono-Medium.woff2", weight: 500, style: "normal" },
  { family: "Source Serif 4", file: "SourceSerif4-Regular.woff2", weight: 400, style: "normal" },
  { family: "Source Serif 4", file: "SourceSerif4-Italic.woff2", weight: 400, style: "italic" },
  { family: "Source Serif 4", file: "SourceSerif4-Semibold.woff2", weight: 600, style: "normal" },
  { family: "Source Serif 4 Display", file: "SourceSerif4Display-Semibold.woff2", weight: 600, style: "normal" },
];

export const FONT_URL_BASE = "/skin/fonts/";

for (const f of FACES) {
  if (!existsSync(join(root, "public/skin/fonts", f.file))) throw new Error(`FACES names ${f.file}, which is not in public/skin/fonts/`);
}

/** One @font-face rule per entry. */
export function fontFaceCss() {
  return FACES.map(
    (f) =>
      `@font-face { font-family: "${f.family}"; src: url("${FONT_URL_BASE}${f.file}") format("woff2"); font-weight: ${f.weight}; font-style: ${f.style}; font-display: swap; }`,
  );
}
