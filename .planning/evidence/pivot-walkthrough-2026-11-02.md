# Stage-by-stage walkthrough, 2 Nov 2026: the owner's decisions

Read-only record of the owner's answers in the PM coordinator's chat (coordinator 4), 2 Nov 2026, while walking the canvas "AIA Obchodní model – prototyp" (https://claude.ai/artifact/HM9rmiwAM9asP8hfyn1XHp, versions 9-10) stage by stage. Each decision quotes the option he chose, or his own words. ADR 0046 § The owner's walkthrough summarises them and names where each lands. Canvas fixes noted here are applied in the canvas, not in this repository.

## Stage 1 · Zadání
- W1. A new plan builds the business Zadání (triage into 8 parts, decision core, rule with risk limit, R1–R7 in code, model parts, hand-off), proposed name `decision-brief`; reuses artifact-brief's working copy and cost-model-study CR7. ("New plan"; folded into #1150 at his "Into #1150 before it merges")
- W2. Triage asks every question that matters, ordered by importance; the first three open, the rest under "Další otázky (n)". ("All that matter, top 3 first")
- W3. No crown amount in triage; the value of information in Kč appears only on Výsledky (M4 §06). ("Yes, remove it")
- W4. The model switch is a question in the decision core (Z3): "Potřebuje rozhodnutí výpočet?", Ada proposes, the researcher confirms; Data/Předpoklady/Model/Výsledky and the Model sub-step appear only on yes. ("In the core (Z3)")
- W5. Canvas: badge "Výzkum" (+ "Obchodní model" once the model is on); Z0 six steps; Z7 hands to Data, Předpoklady, Model, Zpráva; budget 50 USD. Done in canvas v10 (1793623942-f340).

## Stage 2 · Data
- W6. The data contract and its quality report are accepted on the Data step; Zadání only lists the files it needs. client-data-in-analysis#10 rewritten, D-37 superseded. ("On Data")
- W7. Numbers from client documents (PDF contracts, offers): Ada proposes the number with its page, code checks it appears literally on that page, the researcher accepts each. New chunk in client-data-in-analysis. ("Quoted, checked, accepted")
- W8. Estimates computed from client rows (e.g. order loss after a delay from matched groups) are Metodika methods: "odhad (interní)" until A. Bahbouh registers them. New chunk beside client-data-in-analysis#4. ("Registered method")
- Canvas fix pending: MV1 "Třída materiálu: A" → "Důvěrný" (no data classes on screen).

## Stage 3 · Rešerše
- W9. A source's credibility tier is named in words: Úřední / Oborový / Ostatní, never A/B/C (those stay the data classes, off screen). Canvas MV2b and deep-research-v2 DRV5. ("Úřední / Oborový / Ostatní")
- W10. Porter's force strength (and any rating beside a cited quote) is the researcher's labelled judgement with their name; Ada may propose it with a reason. analysis-frameworks AF0/AF6. ("Researcher, labelled")
- W11. A run shows citation accuracy and unsupported claims; completeness (recall) is the method's tested level from the evaluation set (DRV4), labelled so, never a per-run number. Canvas MV2 §03. ("Accuracy per run, recall from tests")
- W12. "Spustit Deep Research…" on the stage opens Ada's priced card in the Lead pane; no paid start from a stage (#550). Canvas MV2, MV2b. ("Open the Lead's card")

## Stage 4 · Předpoklady
- W13. A "Souvislosti" table: Ada proposes pairs of inputs that move together, with a strength and a reason; the researcher accepts each; independence is stated, never assumed. Iman–Conover in code (cost-model-study CR3; ADR 0046 decision 10 (1)). ("Ada proposes, researcher accepts")
- W14. Each assumption's distribution follows its source: from client data, the estimate's own distribution and interval; from a person's range, PERT; people who disagree, a mixture of their ranges; shown per row (ADR 0046 decision 10 (2)). ("By source")
- W15. "Ručí" always names a person at the client. A value fixed by contract is fixed (no range) with its page, unless the contract allows a change, which is then the range's stated reason. ("A person, fixed if contractual")
- W16. The discount rate is a fixed study parameter on Předpoklady with its guarantor (the finance director), applied to every option; Výsledky shows how the verdict moves at other rates (ADR 0046 decision 10 (4)). ("Předpoklady, fixed, tested")
- Coordinator's proposal, not asked: the Metodika module is named "Obchodní modely" (canvas), not "Nákladové modely" (cost-model-study CP10).

## Stage 5 · Model
- W17. One composable cash-flow model type: line items from a closed set of kinds (PŘÍJEM, KAPITÁL, FIXNÍ, VARIABILNÍ, JEDNORÁZOVĚ, plus capacity and timing rules), formulas from a closed vocabulary; Ada proposes items, the researcher accepts, code checks and computes. Cost scenarios become its first template. Rewrites cost-model-study CP1/CP2/CM1–CM7. ("Composable cash-flow model")
- W18. NPV computed both before and after tax; the rule reads one, the other is shown beside it. Tax rate and depreciation method are parameters on Předpoklady. ("Both views")
- W19. Legal context (the owner: "we might need to incorporate some legal context for this softare, as optiizing taxes and or contract law, employment law"). Its shape, from his answers:
  - Role: cited rules and constraints. A legal point is a verbatim quote of a specific provision (law, paragraph, version in force on a date) captured from an official source; it becomes a model parameter (tax rate, depreciation, notice period, minimum wage, overtime) or a constraint a person accepts. AIA flags what applies and never gives legal advice. ("Cited rules and constraints")
  - Areas in the MVP: tax, contract law, employment law. ("Tax, Contract law, Employment law")
  - Sign-off: the researcher accepts legal points like any other finding; the report carries a disclaimer that it is not legal advice. ("The researcher")
  - Jurisdictions: Czech law (e-Sbírka) and EU law (EUR-Lex). ("Czech + EU")
  - Needs: a new plan (proposed `legal-context`): e-Sbírka and EUR-Lex as gate routes (public-data-routes), provisions captured with their version date (as-of, deep-research-v2 DRV7), a typed legal parameter/constraint (Předpoklady, Model), a legal point kind in the report outline, the disclaimer; an ADR amendment to 0046 (decision 7 widens from public data to the law itself).
- Canvas fix pending: own-operations costs (A, A2) escalate with the wage-growth input instead of staying flat.

## Stage 6 · Výsledky
- W20. Every tab's headline for an option is the median with its 90 % interval; the base-case value appears only as "v základu", in a smaller line where a table needs one figure (e.g. IRR). Canvas M3 §04, M4b, M4f. ("Median + interval leads")
- W21. A result's grade follows its method, not its inputs: a deterministic formula is "výpočet" (even over an estimated input), Monte Carlo and statistical estimates are "odhad". Goes into the one grade table (Q1, cost-model-study CP8). ("By method")
- W22. Verdict labels such as "realistické" / "ověřit" are always the researcher's labelled judgement. Canvas M4e. ("Researcher's judgement")
- Canvas fix pending: M4c "daň posuzuje finanční ředitel zvlášť" → the after-tax view beside before-tax (W18).

## Stage 7 · Sociomapa
- W23. Board M5 (the earlier map on aia-sociomap-5's old statistics) is kept for history, labelled "Nahrazeno: Sociomapa systémů (MV3)", and taken off the study's path (Trh → Sociomapa goes to MV3). ("Mark superseded, off the path")
- W24. OPEN: what the maps draw is to be rethought ("i think we still have to rethink what the maps draw, lets leave this open for now"). Left open with it: who scores on the expert map, the minimum number of raters, and MV3's claim, which contradicts M5's hedge reading (B2 vs C2). sociomapa-systemu SYS9/SYS10 and situation-reports EX1–EX2 wait on it.

## Stage 8 · Osnova zprávy
- W25. An unverified point blocks the hand-off to Zpráva until the researcher finds its source or removes it; nothing is dropped silently. research-findings-stage FND2/FND8. ("Block until resolved")
- W26. Optional shared review: the researcher may share a closed stop with the client's decision-makers as a read-only page (points, visuals, sources) for comments; their agreement is recorded in the approval ledger; the report is then written from it. A new chunk in research-findings-stage (sharing, comments, the ledger subject). ("Optional shared review")
- Canvas fix pending: MV4 point 3.1 and its table show the median with its interval (W20), not the base case +8,8.

## Stage 9 · Zpráva
- W27. Until A. Bahbouh registers a method, its estimates still go into the client report, labelled "metoda čeká na schválení metodikem"; approving shows a warning and records it on the ledger row; never a refusal (as RD0, 22 Oct). ADR 0046 decision 5's "INTERNAL_ONLY until registered" and M-5 change accordingly. ("Include, labelled, warn")
- W28. The report is Czech in the MVP; English after. ("Czech, English later")
- Coordinator's finding: the grade legend has three grades; the decisions add a public source with its quote, the researcher's labelled judgement (W10, W22) and a cited legal provision (W19). The report's "realistický … ověřit" must print as a judgement.
- Canvas fix pending: M6 shows the median in the finance paragraph (W20), both tax views (W18), the full grade legend.
