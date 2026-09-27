# Lifecycle, review and results

## Stage rail

`StageRail` has thirteen cells in pipeline order, and it is the project's primary navigation. Each cell carries a status glyph, a two-digit index, the stage name and a state line. Parked-on-you cells fill amber, running cells get a signal top edge, failed cells a fault top edge, and recovery cells are inverse. The current stage is underlined in `signal`.

- Both lifecycles use the same component. The lifecycle is named in the rail header ("Výzkum" or "Simulace", with its own icon), and the stage names come from `pipeline.py` (`RESEARCH_STAGES`, `SIMULATION_STAGES` @ 17c0a6b). Neither one is a variant of the other.
- On a laptop (`narrow`) cells collapse to glyph and index, and only the current stage keeps its name and state. The status stays readable in every cell because the glyph carries it.
- The component renders the statuses the server sends. It never infers a stage's state from its neighbours.

## Impact preview

Shown **before** an edit is committed, from the domain's `ImpactPreview` (`root_stage`, `invalidate`, `preserve`, `presentation_only`; `pipeline.py:423` @ 17c0a6b):

- a thirteen-cell strip: kept stages sunken, the root stage solid ink, reopened stages hatched, presentation-only changes dashed;
- the two lists, *Zůstane platné* and *Znovu se otevře*, with the number of artifacts kept;
- the re-run cost and time, shown as ranges with their basis ("odhad z posledních 3 běhů fáze Respondenti"). When the server does not provide them, they read *chybí — odhad zatím backend neposkytuje*;
- "Uložit jako novou revizi" (`⌘↵`) and "Zahodit úpravu".

A provider or model change is impact-free by design, and the preview says so in words.

## Revisions

Revisions are immutable. `RevisionHistory` lists each revision with what it changed, who changed it, when, and how many stages it reopened ("žádné (bez dopadu)" is valid). Looking at an older revision puts a hatched **`RevisionBanner`** above the content — "Díváte se na nahrazenou revizi rev 12 · aktuální je rev 14" — with *Porovnat* and *Otevřít aktuální revizi*.

## Gates and sign-off

`ApprovalPanel` shows what is being approved (with its fingerprint), who produced it, the evidence (QA checks, warnings, the number of modelled claims, holdout pending) and what the reviewer is attesting to, written as a sentence they sign. The audit trail follows.

**Separation of duties is a designed state, not a toast.** When the producer is the viewer and self-approval is not enabled, the approve action is replaced by a bordered panel: "Tento výstup nemůžete schválit — vytvořil(a) jste ho vy". It gives the policy source (`SelfApprovalSource`), who can approve instead, and "Požádat o nezávislé schválení". When policy does allow it, the attestation says it will be recorded as a self-approval and names the policy source.

## Results workspace

- **`HeadlineAnswer`** is the sentence a client pays for. It shows the client's question, the answer, the one figure with its grade, n and interval, then the supporting findings one level down, each with its own mark.
- Filters sit in one row above the charts. The evidence legend is always present.
- **`GradedBars`** puts a direct label on every bar (the light-theme categorical colours rely on this relief rule), draws intervals only where they exist, and keeps text in text tokens (never in the series colour). *Chybí* and *potlačeno* have their own marks.
- The respondent explorer uses compact density. Synthetic respondents are labelled as synthetic.

## Sociomapa

- **Visualisation never mutates research truth.** Dragging a node saves a *view override*. The map shows a tag ("Pohled upraven: 3 uzly posunuty · Tomáš Beneš 21. 9. · Obnovit originál"), and every moved node leaves a dashed ghost at its original position joined by a dashed line. "Zobrazit jen originál" removes the layer.
- **What-if is a layer.** What-if nodes are hatched squares with dashed outlines; every other node is a disc. A hatched band across the plot reads "CO-KDYŽ — provizorní vrstva nad zmrazenými výsledky. Není to zjištění." Printing keeps the band.
- **The three modes are *Matice*, *Srovnání* and *Co-když*.** The matrix uses the diverging palette (`viz-div-*`, a grey midpoint) and prints the value in every cell. Comparison draws two maps at the same scale.
- Node fill follows the evidence grammar (filled = measured, disc in a ring = calibrated, hollow = modelled, dashed "?" = unknown). The cluster colour is the categorical palette in fixed order.
