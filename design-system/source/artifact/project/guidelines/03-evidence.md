# Evidence and null states

## The epistemic grade

Every figure carries the evidence role that travels with the data. The grade is **achromatic**: it is carried by form, so it survives greyscale print, a dense table and dark mode, and it can never collide with a status or data colour.

| Role | Mark | Number | Chart series | Bar | Map node | Prose |
|---|---|---|---|---|---|---|
| `MEASURED_JOINT` | ■ solid square | plain | solid line | solid fill | filled disc | ■ in the margin |
| `CALIBRATED_CORE` | ▣ framed solid | plain | solid line + square markers | solid fill + inner frame | disc inside a ring | ▣ in the margin |
| `MODELED_BEHAVIOR_PRIOR` | □ hollow square | dotted underline | dashed line | hatched, outlined | hollow ring | □ in the margin **and** "modelováno" in the sentence |
| `EXTERNAL_HOLDOUT_PENDING` | ⬚ dotted square | dotted underline + "neval." tag | dotted line | hatched, dashed outline | dashed ring | a boxed statement on the page |
| *unknown / missing role* | **?** | dashed underline | dotted line + "?" label | dashed outline | dashed ring with "?" | "?" in the margin + "nečíst jako měření" |

Rules:

- **Unknown is never the strongest grade.** `evidenceRole()` maps any role it does not recognise, including a missing one, to `?`. Nothing defaults to ■.
- **Dense tables stay quiet.** A column declares its grade in the header ("Podíl ▣"). A cell carries a mark only when it differs from its column (`Value` `inheritRole`). A 40-row table of calibrated figures shows one mark, not forty.
- **The legend is persistent** (`EvidenceLegend`) on every results surface. After one exposure the marks read without it: filled means measured, hollow means modelled, and "?" means we do not know.
- **Cross-block relationships are not same-person truth.** A relationship between questionnaire blocks is drawn as a *broken* dashed edge, and its label says "mezi bloky — nejde o tutéž osobu". A correlation-matrix cell that was never measured on the same person reads *chybí*, not a number.
- **`EXTERNAL_HOLDOUT_PENDING` appears on the page.** In the Deliverable it is a boxed statement in the chapter it qualifies, in body text size, before the figures.

> **Open (hypothesis until anchored):** the repository names only four roles (`docs/product/README.md` @ 17c0a6b, "`MEASURED_JOINT`, `CALIBRATED_CORE`, `MODELED_BEHAVIOR_PRIOR`, …"). The full list lives in the prototype's `DATA_CONTRACT_v17.json`, which is not in this repository, and the Validation & Evidence context is not started (`docs/architecture/domain-map.md` @ 17c0a6b). The grammar is built for an open set: any role it does not know renders as "?". When the domain publishes the list, each new role gets a row here and a place on the ■ → □ fill scale.

## Null is not zero, and unknown is not neutral

| State | Inline | Table cell | Chart | Means |
|---|---|---|---|---|
| Value | `1 204` | right-aligned figure | the mark | We measured or modelled this |
| Zero | `0` | `0,0 %` | a zero-length bar with its label | We looked, and the answer is zero |
| **Chybí** (not available) | boxed **chybí** in full ink with a hatch | the whole cell hatched at 135° | no bar; a boxed "chybí" label | We never looked, or the answer did not arrive |
| **Potlačeno** (suppressed) | a solid redaction bar + a lock | bar + lock; the reason in the tooltip and the legend | redaction bar + "potlačeno · vzorek < 30" | We have it, but it is withheld (small sample or permission) |
| Loading | a dotted baseline of the expected width | the same | nothing is drawn | We are waiting for the server. After 10 s it becomes *chybí* with "Načíst znovu" |

- *Chybí* is drawn **heavier** than a number: full `null-mark` ink, weight 600, a hatch. Missing data is information, and it must never look softer or more neutral than a bad value.
- Suppression shows its reason. "Potlačeno" without "n < 30" or "bez oprávnění" is not allowed.
- Money follows the same rule: `Money` with `null` renders *chybí*, never `0,00 USD`.
- There are no skeletons and no shimmer. A skeleton is a promise of the shape of an answer that has not arrived.
