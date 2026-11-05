<!-- The research behind ADR 0046, converted from the owner's document "AIA pivot research: rebuilding for business decisions" (2 Nov 2026) with pandoc; text unchanged, escapes removed. Its anchors are @ 57c133a. -->

# AIA pivot research: rebuilding for business decisions

Nov 2, 2026 · Nigel Blount

Keep almost all of AIA. Build the data contracts and the model platform
first, replace the Sociomap engine's statistics but not its layout, and
lead with traceable evidence, which no competitor read here offers.

## Executive summary: ten findings

1.  **The pivot is not in the repository, and the new lane is unbuilt.**

    -   Survey fieldwork is still live and being extended.

    -   ADR 0044 is Proposed, with its build plan at 0 of 32 chunks.

    -   Client data contracts do not exist, so no client dataset can
        enter an analysis.

Order: an ADR recording the pivot, then data contracts, then the model
platform. (Where the brief and the code differ)

2.  **The Sociomap engine's statistics do not hold on business rows;
    its layout does.**

    -   Two independent random walks look "related" about three times
        in four at the 5% level (Granger & Newbold).

    -   Benjamini-Hochberg is not guaranteed for two-sided correlation
        tests.

    -   Split-half compares two periods, not two samples.

Replace centring, baseline, pair floors, BH and split-half; keep layout,
terrain and determinism. (A1, A4)

3.  **No published validation of Sociomapping on business data exists.**
    The main evidence is a thesis supervised by the method's author, on
    peer ratings in teams of up to about 25. A synthetic suite with
    planted structure and null worlds must pass before any business map
    says a structure is real. Check the SOMECS name and licence before
    using it. (A5; method recommendation)

4.  **With 24--36 monthly rows, none of the network alternatives was
    demonstrated.** Graphical lasso, NETS and PCMCI were all shown at
    hundreds or thousands of observations. Ship the scenario-sensitivity
    map and the expert objects × properties map first. (A3, A6)

5.  **Deep Research's verbatim-quote rule is AIA's strongest asset.**
    Commercial deep-research modes left 12.5% to 97.5% of statements
    unsupported by their own sources (DeepTRACE, Aug 2025). One agent
    cited non-existent URLs 13.3% of the time. Keep the rule and add
    citation recall beside precision. (B1)

6.  **The next research value is structured data and typed numbers,
    computed by code.** The model proposes a query key or a concept;
    code fetches the value and extracts it with its unit. Rule-based
    extraction beat a few-shot LLM on value and unit (F1 85.6 against
    59.1). (B2; Deep Research v2 spec)

7.  **Czech public registers are lawful to build on.** They are official
    works with no database right, and the law requires them to be
    published as open data. The binding limits are elsewhere:

    -   GDPR for named natural persons: the Czech DPA fined a register
        copier CZK 500,000.

    -   Machine-readable opt-outs from text and data mining (OLG
        Hamburg, Dec 2025).

    -   VIES's ban on reuse.

    -   ARES's limit of 500 queries a minute.

(C2, C3)

8.  **Financial statements are the data gap.** Sbírka listin holds them
    only as PDF or XHTML, and small firms need not publish a P&L.
    Non-filing was widespread in 2019 by CRIF's count. Plan PDF
    extraction with review, or buy structured data. (C1)

9.  **The planned quantitative methods are the right ones, with four
    corrections:**

    -   include input correlations;

    -   test PERT's beta shape against data;

    -   judge forecasts by MASE, never MAPE with zeros;

    -   declare one discount rate and never lower it because a model is
        simulated.

Top-down market sizing from Prodcom carries Eurostat's own under-10%
coverage-error estimate. Logistics benchmarks for Czechia and Poland
were not found. (D1--D3)

10. **AIA's white space is real but narrowing.** No vendor read
    combines a decision rule fixed in advance, sourced external research
    and number-level provenance for small and mid-size EU firms with EU
    residency. Workday says it has paired Monte Carlo with scenario
    audit trails since 2026 (vendor claims). (E3)

## Where the brief and the code differ

The quantitative model platform, client data contracts and the Sociomap
business spike exist only on paper, and no retirement of survey
fieldwork is recorded anywhere. Every row below was read from
origin/develop at commit 57c133a (1 Nov 2026). main is 4,972 commits
behind develop and holds almost none of brief §2.

  -------------------------------------------------------------------------------------------------------------------
  Brief §2 says    What develop holds                Anchor @ 57c133a
  ---------------- --------------------------------- ----------------------------------------------------------------
  Grades           Grades are MEASURED, CALIBRATED,  packages/aia_core/src/aia_core/domain/report/evidence.py:41-46
  CALCULATED /     MODELLED, HOLDOUT_PENDING,        
  ESTIMATED /      UNKNOWN. CALCULATED and ESTIMATED 
  MODELLED         appear only in ADR 0044.          

  Data class B =   B = derived client (aggregates,   domain/residency.py:51-67; commit 4959b1cb
  design, C =      summaries); C = internal and      
  public           non-client. Class gates have been 
                   advisory in every environment     
                   since 28 Oct 2026.                

  A quantitative   Designed only. ADR 0044 is        docs/architecture/adr/0044-quantitative-model-studies.md:3;
  model platform   Proposed (29 Oct 2026); its build domain/scope.py:465-466
  (§2.4)           plan is 0 of 32 chunks. No Monte  
                   Carlo, Iman-Conover, Sobol, EVPPI 
                   or Holt-Winters code. StudyKind   
                   is RESEARCH or SIMULATION only.   

  Data contracts   Not built. Uploaded datasets stay .planning/plans/client-data-in-analysis.md
  and bindings     ineligible for analysis until an  
  (planned)        accepted data contract exists.    

  Fieldwork,       No retirement decision found. AI  apps/executors/src/aia_executors/ai_fieldwork.py; ADR 0024
  questionnaire,   fieldwork was last changed 29 Oct 
  audience and     2026; ADR 0024 (panel-grounded    
  panel retired    respondents) was accepted 26 Oct  
  and frozen       2026; the fieldwork,              
  (§2.7)           questionnaire and audience plans  
                   are in progress.                  

  A spike runs the Nothing for 36×12 or 40×10. Only  prototypes/research-stages/README.md:106-110
  engine on 36×12, prototype images of 800 fictional 
  40×10 and 800×7  scenarios × 7 options             
  synthetic sets   ("Sociomapa strategií"); the    
                   script that made them is not in   
                   the repo.                         

  Deep Research    In develop, Brave and 7           .planning/plans/deep-research-web-search.md:1226-1251;
  live routes:     connectors are on; Wikipedia and  apps/executors/src/aia_executors/deep_research_live.py
  Wikipedia,       Common Crawl are off; no          
  Brave, Common    connector has been probed live.   
  Crawl            ADR 0017 is Proposed and ADR 0021 
                   Held. Connectors exist for ARES,  
                   ČSÚ DataStat, Eurostat, NKOD,     
                   OpenAlex, Crossref and Wayback    
                   CDX; none for ČNB, TED, GLEIF,    
                   VIES or Sbírka listin.            

  The Lead edits   Per-change accept of agent        .planning/plans/working-copy-edit-ops.md:12;
  change by change proposals (WCE6) and the          .planning/plans/lead-orchestration.md:7-8
  and starts       multi-step plan card (LO3/LO4)    
  priced work      are not built; today a card       
  through an       covers one priced request per     
  approval card    turn.                             

  Report editor    Built, off until                  domain/report/sources.py:1; ADR 0045
  ONLYOFFICE       AIA_ONLYOFFICE_URL and its secret 
                   are set. ADR 0045 (reports per    
                   situation) is Proposed; the       
                   section-source manifest already   
                   exists.                           

  Metodika method  Covers Sociomap methods only. A   ADR 0023:247-248
  register         register for quantitative methods 
                   exists only in ADR 0044.          

  SOMECS H-Model,  H-Model built as experimental,    domain/sociomap/hmodel.py:1; ADR 0044 §12
  WIND, objects ×  off by default; WIND and objects  
  properties       × properties designed only.       
  -------------------------------------------------------------------------------------------------------------------

Two documents on develop no longer match the code: CLAUDE.md still calls
advisory class gates develop-only, and
docs/architecture/deep-research-connectors.md still calls registered
connectors "unregistered".

## Keep, extend, replace

Keep the platform, the evidence model, the report engine and Deep
Research's core. Build the data contracts and the model platform first.
Replace the Sociomap engine's statistics but not its layout. Nothing in
§2 needs replacing wholesale. "Status" is what develop holds at
57c133a; the verdicts are \[inference\] from the evidence named.

  ------------------------------------------------------------------------------
  §2 component      Status          Verdict           Reason and evidence
  ----------------- --------------- ----------------- --------------------------
  FastAPI +         Built           Keep              Nothing read argues
  PostgreSQL                                          against it.

  Workflow engine:  Built, tested   Keep              Every new capability (B2,
  leases,                                             D) is a step or a route on
  heartbeats,                                         it.
  checkpoints,                                        
  replay without                                      
  paying twice,                                       
  cost ceiling                                        

  Per-study budgets Built           Keep              Priced routes (ČÚZK
  and wallets                                         outputs, commercial data)
                                                      fit the tool-cost ledger.

  Approval ledger   Built           Extend            Also record data-contract
                                                      approvals, GDPR balancing
                                                      tests and Art. 14 notices
                                                      (C2).

  Governed gateway, Built; class    Keep, fix         Correct the class
  Bedrock EU, data  gates advisory                    definitions (B = derived
  classes                                             client, C = internal) and
                                                      decide whether gates
                                                      enforce before client data
                                                      flows.

  "Models propose, Built           Keep              Code beats LLMs at
  code computes, a                                    extracting quantities
  person approves"                                   (CQE), LLM credibility
                                                      ratings match experts only
                                                      at ρ 0.50, and StatGPT
                                                      keeps the model away from
                                                      the numbers (B).

  Research Lead     Built behind a  Extend            Build per-change accept of
  "Ada"           switch                            proposals and the plan
                                                      card (not built).

  Admitted claims:  Built           Extend            Kish effective n is a
  policy, support,                                    survey-weighting measure;
  interval, tier                                      time-ordered business data
                                                      need an
                                                      autocorrelation-adjusted
                                                      effective n (A1).

  Grades CALCULATED Designed (ADR   Extend            Settle one vocabulary
  / ESTIMATED /     0044); code                       before quantitative
  MODELLED          uses MEASURED,                    results reach a report.
                    CALIBRATED,                       
                    MODELLED                          

  Report engine,    Built           Keep              It is the differentiator
  locked numbers,                                     (E3).
  approvals,                                          
  section-source                                      
  manifest                                            

  ONLYOFFICE editor Built, off      Keep              Switch it on.

  Metodika and the  Built for       Extend            Register quantitative
  method register   Sociomap                          methods and each Sociomapa
                    methods                           systémů mode separately.

  Client sources:   Built           Extend            Read both Czech P&L
  SHA-256, located                                    layouts; extract PDF
  segments                                            statements with person
                                                      review (C1, D1).

  Personal-column   Built           Extend            Add the GDPR record for
  masking                                             named natural persons
                                                      taken from registers (C2).

  Client knowledge  Built           Keep              ---
  with frozen                                         
  revisions                                           

  Data contracts    Designed only   Build first       No client dataset can
  and bindings                                        enter an analysis until
                                                      they exist; every D method
                                                      needs them.

  Model-type        Designed        Build             Matches the evidence in D.
  contract                                            

  Cost scenarios:   Designed        Keep, extend      Add time-driven
  line kinds, NPV,                                    cost-to-serve and capacity
  payback,                                            priced per unit of space
  break-even                                          (D1).

  Data checks: MAD, Designed        Keep              Add Prodcom-style flags:
  seasonality,                                        negative apparent
  reconciliation                                      consumption is an error,
                                                      not zero (D2).

  PERT Monte Carlo  Designed        Extend            Test the beta shape
                                                      against data; sample
                                                      disagreeing experts as a
                                                      mixture (D1).

  Iman-Conover rank Designed        Keep              Omitting correlation is
  correlation                                         the larger documented
                                                      error (Wall 1997, 3-lens).

  Sobol (Jansen) or Designed        Keep              Not challenged; Sandia's
  PRCC; PCG64                                         practice reads scenario
  streams; EVPPI                                      samples the same way (A2).

  Backtests judged  Designed        Change            MASE with seasonal
  on held-out MAE                                     scaling; exponential
                                                      smoothing bottom-up as the
                                                      benchmark (D1).

  Decision rule     Designed        Keep, specify     One declared discount rate
  judged on a                                         per study; never lowered
  probability                                         for simulation (D1).

  Deep Research:    Built           Keep              Unsupported statements are
  six steps, one                                      commercial agents' main
  gate, snapshots,                                    measured failure (B1).
  verbatim rule                                       

  Deep Research     Partly on in    Extend            Structured routes, typed
  routes and        develop                           extraction, citation
  purposes                                            recall, credibility v2,
                                                      as-of, monitoring (Deep
                                                      Research v2 spec).

  The gate's       Built           Extend            Per-source rate limits,
  egress control                                      TDM-reservation checks,
                                                      retention limits (C2).

  Sociomap layout,  Built           Keep              It renders any
  terrain,                                            dissimilarity matrix (A1).
  determinism                                         

  Sociomap          Built           Replace           Not valid on
  statistics:                                         autocorrelated business
  centring,                                           rows (A1--A4).
  baseline, pair                                      
  floors, BH,                                         
  split-half                                          

  SOMECS objects ×  H-Model         Extend            Expert scoring is a
  properties,       experimental;                     validated decision aid
  H-Model, WIND     rest designed                     (A6). Check the SOMECS
                                                      name and licence first
                                                      (A5).

  Retired           Still live      Record the        No retirement is recorded
  AI-respondent                     decision          in the repository; write
  fieldwork,                                          it as an ADR before
  questionnaire,                                      building on the pivot.
  audience                                            

  Frozen panel      Live            Hold              Its licence decides
                                                      whether it can feed market
                                                      counts; at most ESTIMATED
                                                      (C4).
  ------------------------------------------------------------------------------

## A. Re-applying the Sociomap engine to business systems

The engine's layout and drawing can be reused, but its statistics
cannot: on 24--36 autocorrelated rows, plain correlations,
Benjamini-Hochberg and split-half credibility will report structure that
is not there. No published validation of Sociomapping or SOMECS on
business observation matrices was found, so AIA must validate this use
itself.

### A1 Each step, on business observations

  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Step                 Valid on business    Replace with                 Evidence
  (aia-sociomap-5)     rows?                                             
  -------------------- -------------------- ---------------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Per-person (row)     No. A month's or    Per-variable transformation  \[inference\]
  centring             branch's values     declared up front (log for   
                       across KPIs in       skewed money, log-ratio for  
                       different units have shares), then robust         
                       no common scale.     per-variable standardisation 

  "Unrelated"        No. Independent      A null built per variable:   Ebisuzaki 1997; Kugiumtzis 1999 (A4)
  baseline             trending series look phase-randomised or IAAFT    
                       related.             surrogates after detrending  
                                            and deseasonalising; for     
                                            Monte Carlo rows, the        
                                            imposed input correlation    
                                            matrix                       

  Pair floors of 10 or No. Rows are not     A floor on effective sample  [Pyper & Peterman 1998](https://doi.org/10.1139/f98-104) (3-lens)
  5                    independent pairs.   size, from an                
                                            autocorrelation-adjusted     
                                            formula (Bayley-Hammersley,  
                                            modified by Pyper &          
                                            Peterman)                    

  Benjamini-Hochberg   Not guaranteed. BH   Benjamini-Yekutieli as the   [Benjamini & Yekutieli
  with a noise rule    is proven under      default, or an FDR           2001](https://projecteuclid.org/journals/annals-of-statistics/volume-29/issue-4/The-control-of-the-false-discovery-rate-in-multiple-testing/10.1214/aos/1013699998.pdf);
                       positive regression  calibrated by block          [Cai & Liu 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4894362) (3-lens)
                       dependence, which    resampling                   
                       two-sided                                         
                       correlation tests do                              
                       not inherit.                                      

  Sparse design        Yes, as a rule for   Keep; feed it the corrected  \[inference\]
                       which relations are  tests                        
                       drawn                                             

  Layout (soft-rank    Yes. It renders a    Keep; report Stress-1,       [smacof manual](https://cran.r-universe.dev/smacof/doc/manual.html) (quote)
  Spearman stress +    dissimilarity        stress per point, a          
  Coulomb; interval    matrix; only the     random-data stress benchmark 
  MDS)                 matrix changes.      and a permutation test       

  Split-half           No. Two halves of a  Moving or stationary block   Künsch 1989; Politis & Romano 1994 (A4)
  credibility          time series are two  bootstrap, with              
                       periods, so they     Procrustes-aligned layout    
                       differ by drift, not stability                    
                       noise.                                            

  Respondent placement Changes meaning:     Periods: a trajectory with   \[inference\]
  and density          rows become periods  arrows; units (branches,     
                       or units             SKUs): placement, with       
                                            density only above a stated  
                                            n                            

  Segments             Become regimes; 36   Report regimes only from a   \[inference\]; regime-switching models not researched in this pass
                       rows rarely support  declared break or a model;   
                       them                 otherwise none               

  Terrain (IDW         Yes, as a display of Keep, labelled as            \[inference\]
  heights)             one chosen outcome   interpolation, never as an   
                                            estimate                     
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

On Benjamini-Hochberg versus Benjamini-Yekutieli, the evidence is
direct. BY "controls the FDR ... for any joint distribution of the test
statistics" but divides q by about ln(m) + 0.58, which is about 4.8 for
the 66 pairs of 12 KPIs \[inference: arithmetic\]. In Cai & Liu's
simulation (n = 50, nominal FDR 0.2, i.i.d. rows), Fisher-z with BH gave
an actual FDR of 0.29 on normal data and 0.91 on a normal mixture;
Fisher-z with BY gave 0.03 and 0.53. Every one of these results assumes
independent rows, so none covers autocorrelated months (3-lens).

### A2 Pitfalls in business matrices

-   **Spurious correlation.** Regressing one independent random walk on
    another (length 50) rejected "no relationship" at the 5% level
    about three-quarters of the time; mean \|t\| was 4.5 against an
    expected 0.8 ([Granger & Newbold
    1974](https://gwern.net/doc/economics/1974-granger.pdf); 3-lens).

-   **Differencing is a trade.** Prewhitening or first-differencing
    controls false positives, but "decrease\[s\] power in the common
    situations where low-frequency (slowly changing) processes are
    important sources of covariation"; adjusting the degrees of freedom
    instead kept error rates near nominal (Pyper & Peterman 1998;
    3-lens). Trending KPIs therefore need a stated choice: levels with
    adjusted df, or changes.

-   **Effective sample size is itself uncertain.** Thiébaux & Zwiers
    found its estimate's standard deviation exceeded the effective
    sample size (cited in [Ebisuzaki
    1997](https://doi.org/10.1175/1520-0442(1997)010<2147:AMTETS>2.0.CO;2);
    quote).

-   **Block bootstrap is asymptotic.** Consistency needs block length
    growing with n while a vanishing share of it (Künsch 1989). The
    automatic block-length evidence covers only N = 200 and 800, and at
    N = 200 with strong autocorrelation the variance estimate was biased
    well below the truth ([Patton, Politis & White
    2009](https://public.econ.duke.edu/~ap172/Patton_Politis_White_2009.pdf);
    quote). With 24--36 rows there are only a handful of independent
    blocks, so intervals must be reported as unreliable \[inference\].

-   **Outliers.** "A single outlier could reduce the correlation by 50%
    or completely reverse it"; skipped correlations stayed accurate
    with outliers and cost at most 23% power under normality. The
    authors advise choosing a method "given the data at hand and not
    given their results" ([Pernet, Wilcox & Rousselet
    2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC3541537); quote).

-   **Mixed units and compositional shares.** Not covered by any source
    read in this pass. Ranks remove units but not trends; shares that
    sum to one need log-ratios \[inference; Aitchison not read\].

-   **Maps of the model's own Monte Carlo scenarios.** The scenarios'
    co-movement is produced by the model's equations and by the rank
    correlation AIA imposes (Iman & Conover 1982). Such a map shows how
    the model propagates its assumptions, which is sensitivity analysis:
    Sandia's sampling-based practice reads it through correlation,
    partial rank correlation and standardised rank regression
    coefficients ([Helton et al.
    2006](https://www.osti.gov/servlets/purl/897617); quote). It can
    claim "in this model, under these inputs, A and B move together";
    it can never claim that the market or the firm behaves so
    \[inference\].

### A3 Alternatives and complements

  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Method                                                                                                                What it estimates          Shown on        Fit for 24--36   Can feed the
                                                                                                                                                                   rows             layout?
  --------------------------------------------------------------------------------------------------------------------- -------------------------- --------------- ---------------- ---------------
  [Graphical lasso](https://pmc.ncbi.nlm.nih.gov/articles/PMC3019769) (2008)                                            A sparse inverse           11 variables,   Not shown        Yes: partial
                                                                                                                        covariance: a zero means   7,466           \[inference:     correlations as
                                                                                                                        conditional independence;  observations    about 1/200 of   similarities
                                                                                                                        assumes i.i.d. Gaussian                    that data per    \[inference\]
                                                                                                                        rows                                       variable\]       

  [NETS](https://researchonline.lse.ac.uk/id/eprint/90493/3/Barigozzi_et_al_2019_Journal_of_Applied_Econometrics.pdf)   A sparse VAR: directed     100 series, T = No: a            Yes, as two
  (2019)                                                                                                                Granger links plus         250--1,000      12-variable      networks
                                                                                                                        contemporaneous partial    (about 80%      VAR(1) has 144   \[inference\]
                                                                                                                        correlations               power at T =    lag coefficients 
                                                                                                                                                   750); 90        \[inference\];   
                                                                                                                                                   stocks, 3,021   LASSO "can be   
                                                                                                                                                   days            unstable" under 
                                                                                                                                                                   collinearity     

  [PCMCI](https://elib.dlr.de/131630/1/Runge_ScienceAdvances_2019.pdf) (2019)                                           Lagged causal links by     "Dozens to     No; it assumes   Arrows, not a
                                                                                                                        conditional-independence   hundreds of     causal           layout
                                                                                                                        tests                      variables for   sufficiency      
                                                                                                                                                   sample sizes of ("probably the  
                                                                                                                                                   a few hundred   strongest        
                                                                                                                                                   or more"       assumption")    
                                                                                                                                                                   and stationarity 

  MDS diagnostics ([smacof](https://cran.r-universe.dev/smacof/doc/manual.html))                                        Stress-1, stress per       Any             Yes              It benchmarks
                                                                                                                        point, random-data and     dissimilarity                    the existing
                                                                                                                        permutation benchmarks,    matrix                           layout
                                                                                                                        jackknife and bootstrap                                     
                                                                                                                        stability                                                   

  Dynamic factor models, Bayesian networks, NOTEARS, Granger tests, system dynamics, Markov regime switching            ---                        ---             Not researched   ---
                                                                                                                                                                   in this pass     
                                                                                                                                                                   (unknown)        
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

All quote-checked. None of the three network estimators was demonstrated
anywhere near 24--36 rows, so with monthly data the defensible options
are correlations of transformed series with dependence-aware testing,
expert scoring (A6), or model-based scenario maps that say what they are
\[inference\].

### A4 Credibility for business maps

-   **Null model.** Ebisuzaki's random-phase test keeps one series'
    power spectrum and randomises its phases; its rejection rates were
    "much better than those for the bootstrap method" for N = 8--64
    (3-lens). It is too liberal "when trends were dominant" (3-lens)
    and "inappropriate" for strong seasonality, so detrend and
    deseasonalise first. Randomise each variable independently, never
    with shared phases, which would keep the cross-correlation under
    test \[inference from verifiers\].

-   **Surrogate quality.** Use IAAFT to keep each variable's
    distribution, and check the surrogates reproduce the original
    autocorrelation before testing: a mismatch makes "a high
    significance level" meaningless (Kugiumtzis, [Phys. Rev. E 60,
    2808, 1999](https://arxiv.org/pdf/physics/9905021); 3-lens).

-   **Stability.** Block-bootstrap the rows, re-run the layout,
    Procrustes-align each map to the original and report how far each
    object moves (smacof bootmds, jackmds, Procrustes; quote).

-   **Fit.** Report Stress-1 against random-data stress and a
    permutation test of stress (smacof randomstress, permtest; quote).

-   **Reporting.** Per relation: estimate, block-bootstrap interval, the
    null used, the FDR method and the time scale it reflects (levels or
    changes). Per map: stress against its null and object stability.
    "This structure is real" may be said only when a relation beats
    its surrogate null after FDR and survives resampling \[inference\].

### A5 Prior art and evidence of validity

-   **The main evaluation is internal.** It is a 2014 rigorous thesis at
    Charles University, supervised by Radvan Bahbouh, the method's
    author, written by a member of the development team since 2006
    ([record](https://dspace.cuni.cz/handle/20.500.11956/57021)). It
    shows the map reproduces the rank order of its input well: average
    row-wise Spearman above 0.8 for teams up to 10 and above 0.7 for
    10--20, across 131 work groups (1,499 people); at 20--25 members
    real data stayed above 0.7 while random matrices averaged below 0.5.
    Twenty-nine trained raters read maps alike (kappa 0.813
    fixed-marginal). The thesis itself notes few groups of 20 or more.
    Test-retest figures (0.73--0.89 at 14 days) are cited from the
    author's own work.

-   **What that does not show.** Neither test shows that conclusions
    drawn from a map are valid, and all the data are peer ratings in
    teams of up to about 25 \[inference\].

-   **The one outside peer-reviewed use** found ([Giusino et al.
    2023](https://eprints.whiterose.ac.uk/205779/1/10-1108_TPM-11-2022-0077.pdf),
    *Team Performance Management*) has a QED co-author and measured
    participants' perceptions only, with a small sample and no control
    group.

-   **Business use.** The thesis cites an application to "economic
    systems" (Bahbouh & Bahbouh 2002); a Wikipedia article flagged as
    promotional describes a "large systems" mode for subject × object
    preference matrices used in marketing. No validation of either was
    found.

-   **SOMECS.** A [Seznam Zprávy
    report](https://www.seznamzpravy.cz/clanek/domaci-kauzy-velke-zakazky-s-nejasnym-smyslem-auditory-v-zalozne-zaujal-specialni-byznys-269849)
    (17 Feb 2025) expands SOMECS as "Sociomap-based Models of Economic
    Systems" and quotes Radvan Bahbouh that QED Group does team
    sociomapping while his brother's work covers economic systems. The
    brief's "SOMECS by R. Bahbouh, QED Group" may therefore conflate
    two lines of work. The same report covers a credit union's
    sociomapping contracts: it says the ČNB found no one had assessed
    their "real value, purpose and substance", while stating the
    activity itself was not the problem, and that law-enforcement
    authorities are looking into the case. These are the article's
    statements, not findings of this research. \[inference\] Check
    licensing and naming with counsel before AIA markets anything as
    SOMECS.

-   All A5 items are quote-checked; nothing here was adversarially
    verified.

### A6 Objects × properties versus the observation matrix

-   Experts scoring options on criteria is multi-criteria decision
    analysis. In a controlled experiment (145 participants), AHP, SMART
    and MACBETH tools were all "useful": participants who changed
    their ranking followed the tool. AHP and SMART were rated helpful
    and easy; inconsistency in judgements "had no effect on the
    usefulness"; but MACBETH's criterion weights agreed poorly with
    AHP's (Kendall 0.33). One decision problem only ([Ishizaka & Siraj
    2018](https://eprints.whiterose.ac.uk/117125/1/1-s2.0-S0377221717304885-main.pdf);
    quote).

-   When to use which \[inference\]: objects × properties for strategic
    options and competitors, where there are few observations and the
    question is how options compare on stated criteria; the observation
    matrix for many comparable units (branches, SKUs, customers) or for
    a model's scenarios read as sensitivity; a WIND-style height layer
    as a display of one outcome over either layout.

### A summary

  -----------------------------------------------------------------------
  §2.6 component        Verdict     Why
  --------------------- ----------- -------------------------------------
  Layout engine,        Keep        It renders any dissimilarity matrix;
  determinism, pinned               add Stress-1 and benchmark nulls.
  spec                              

  Terrain (IDW)         Keep        A display of a chosen outcome,
                                    labelled as interpolation.

  Per-person centring   Replace     Declared per-variable transformation
                                    and robust standardisation.

  "Unrelated"         Replace     Per-variable surrogate nulls after
  baseline                          detrending (Ebisuzaki; IAAFT).

  Pair floors           Replace     Effective-sample-size floors.

  BH with noise rule    Replace     BY by default, or
                                    resampling-calibrated FDR; BH is not
                                    guaranteed here.

  Split-half            Replace     Block bootstrap plus Procrustes
  credibility                       stability.

  Respondent placement, Extend      Trajectories for periods; regimes
  density, segments                 only from declared breaks.

  SOMECS objects ×      Extend      Expert scoring is a validated
  properties, H-Model,              decision aid in its own right (A6).
  WIND                              

  Claim of validity for Do not make No published validation exists;
  business maps                     AIA's synthetic validation (below)
                                    comes first.
  -----------------------------------------------------------------------

## B. Deep Research beyond current tools

The best commercial agents still state many things their own sources do
not support, so AIA's rule that a finding exists only with a verbatim
quote in a snapshot is its strongest asset and should stay. What it
lacks are structured-data routes, typed numeric extraction,
citation-recall measurement and monitoring; the literature gives a
measurable target for each. *Check* marks how a claim was tested:
**3-lens** = passed three adversarial verifiers (quote fidelity,
contradiction, currency); **quote** = the quote was confirmed word for
word in the source, but not adversarially verified.

### B1 State of the art and where it fails

  -----------------------------------------------------------------------------------------------------------
  Study (date, status)                                   Finding                               Check
  ------------------------------------------------------ ------------------------------------- --------------
  [DeepTRACE](https://arxiv.org/pdf/2509.04499), Venkit  Citation accuracy (share of citations 3-lens
  et al., arXiv Sep 2025, ICLR 2026; results as of 27    whose source supports the statement)  
  Aug 2025                                               ran "from 40--80% across systems".  
                                                         Unsupported-statement rates in        
                                                         deep-research modes: Perplexity       
                                                         97.5%, Copilot Think Deeper 90.2%,    
                                                         YouChat 74.6%, Gemini 53.6%, GPT-5    
                                                         12.5%. Its LLM judge agreed with      
                                                         humans at Pearson r = 0.62.           

  [DeepResearch                                          Citation precision and citation       3-lens
  Bench](https://arxiv.org/pdf/2506.11763), Du et al.,   volume diverge: Perplexity had the    
  arXiv Jun 2025 (outputs Apr--May 2025)                 highest citation accuracy (90.24%)    
                                                         with 31.26 effective citations per    
                                                         task; Gemini had the most (111.21) at 
                                                         81.44%. The maintainers have since    
                                                         re-scored with newer judges, so the   
                                                         absolute figures are dated; the       
                                                         ranking held.                         

  [BrowseComp](https://arxiv.org/pdf/2504.12516),        1,266 hard-to-find questions.         3-lens
  OpenAI, Apr 2025                                       Browsing lifted GPT-4o only from 0.6% 
                                                         to 1.9%; an early Deep Research       
                                                         scored 51.5% but was trained on       
                                                         BrowseComp-style data. Browsing       
                                                         models were worse calibrated:         
                                                         calibration error 91% for Deep        
                                                         Research against 65--69% for          
                                                         non-browsing models.                  

  [URL hallucination                                     Deep-research agents cited            3-lens
  study](https://arxiv.org/pdf/2604.03173), Rao, Wong &  non-existent URLs (no live page, no   
  Callison-Burch, arXiv Apr 2026, preprint               Wayback capture) 10.7% of the time    
                                                         against 4.8% for search-augmented     
                                                         models; the gap is mostly one agent   
                                                         (Gemini 13.3%; OpenAI 3.5%). Giving   
                                                         models a link-checking tool cut       
                                                         non-resolving URLs from 16.0% to 0.6% 
                                                         (GPT-5.1).                            

  [BrowseComp-Plus](https://arxiv.org/abs/2508.06600),   On a fixed corpus, swapping GPT-5's  figures
  Chen et al., Aug 2025; ACL 2026                        retriever from BM25 to a neural       confirmed;
                                                         embedder raised accuracy from 55.9%   original
                                                         to 70.1%; with all gold documents     wording
                                                         supplied, gpt-4.1 scored 93.49%       refuted as
                                                         against 14.58% with BM25. Retrieval   overreaching
                                                         quality, not only reasoning, limits   
                                                         these agents.                         
  -----------------------------------------------------------------------------------------------------------

Benchmarks that exist: BrowseComp and BrowseComp-Plus (hard retrieval),
DeepResearch Bench (report quality RACE + citation FACT), DeepTRACE
(citation audit), GAIA, Humanity's Last Exam, Mind2Web 2,
DeepResearchGym and WebWalker. None tests Czech sources, registers,
statistical series or numeric extraction into typed values \[inference:
none of the papers read covers them\].

### B2 The six capabilities, with measured targets

  -------------------------------------------------------------------------------------------------------------------------------------------------------------
  Capability      What the evidence says                                                                                            Target to adopt     Check
  --------------- ----------------------------------------------------------------------------------------------------------------- ------------------- -------
  Structured      The IMF's [StatGPT](https://bookstore.imf.org/books/statgpt-ai-for-official-statistics) (Mar 2026) lets the      The model never     quote
  registers and   model only translate a request into a query against the agency's API; the figure comes from the API. On          writes a number: it 
  statistical     [LoTuS](https://dbdbd2025.uantwerpen.be/wp-content/uploads/2025/12/dbdbd25_29.pdf), text-to-SQL over official     proposes an SDMX    
  series          statistics tables reached 0.59 execution accuracy; the tables average 33--35 columns against 5--7 in Spider/BIRD. key; code fetches.  
                  [Eurostat's                                                                                                      Target: 100% of     
                  API](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-getting-started/sdmx2.1)   series values       
                  is SDMX 2.1 with versioned code lists and structures.                                                             byte-equal to the   
                                                                                                                                    API response;       
                                                                                                                                    query-proposal      
                                                                                                                                    accuracy measured   
                                                                                                                                    on a labelled set.  

  Archive         [RFC 7089](https://www.rfc-editor.org/rfc/rfc7089) (Memento, 2013): a TimeGate returns the nearest capture, which Record the          quote
  as-of-date      "may differ significantly" from the requested date, and a request before the first capture returns the first    capture's own      
  research        one, not an error. Archived bodies are not byte-identical to the original (URL rewriting, banners).               datetime beside the 
                                                                                                                                    requested one;      
                                                                                                                                    refuse a capture    
                                                                                                                                    outside a declared  
                                                                                                                                    tolerance. Never    
                                                                                                                                    compare archive     
                                                                                                                                    hashes with live    
                                                                                                                                    hashes.             

  Numeric         On NewsQuant, a rule-based extractor ([CQE](https://aclanthology.org/2023.emnlp-main.793), EMNLP 2023) scored F1  Code extracts value quote
  extraction into 92.0 for values and 85.6 for value+unit; few-shot GPT-3 scored 70.6 and 59.1 and "hallucinated" values. Linking and unit; the model 
  typed inputs    the quantity to its concept is harder: F1 57.0 under strict matching. Annotators fully agreed on only 62% of      only proposes the   
                  annotations.                                                                                                      concept and period, 
                                                                                                                                    which a person      
                                                                                                                                    accepts. Target:    
                                                                                                                                    value+unit F1 ≥     
                                                                                                                                    0.90 on a Czech     
                                                                                                                                    labelled set before 
                                                                                                                                    use.                

  Triangulation   On [QuanTemp](https://arxiv.org/abs/2403.17169) (SIGIR 2024, 15,514 real numerical claims), the best verifier     Decompose before    quote
  and             reached macro-F1 58.32; GPT-4 few-shot 36.50. Splitting a claim into sub-questions added 8.84 points.             verifying; report   
  contradiction   [FEVER](https://aclanthology.org/N18-1074/) (2018): requiring the right evidence cut accuracy from 50.91% to      agreement and       
                  31.87%.                                                                                                           contradiction per   
                                                                                                                                    input; target       
                                                                                                                                    macro-F1 on a       
                                                                                                                                    labelled Czech set, 
                                                                                                                                    never a single      
                                                                                                                                    accuracy.           

  Precedent and   In [COLIEE 2025](https://arxiv.org/abs/2509.08025), the best legal case retrieval scored micro-F1 0.3353 (recall  Treat precedents as quote
  case-outcome    0.3735); paragraph entailment 0.3195; outcome prediction 76.5% accuracy.                                          candidates a person 
  retrieval                                                                                                                         confirms; measure   
                                                                                                                                    recall@50 on a      
                                                                                                                                    curated set; do not 
                                                                                                                                    promise outcome     
                                                                                                                                    prediction.         

  Scheduled       A [survey](https://arxiv.org/abs/1901.02660) (ACM CSUR 2020, older than 3 years) models page changes as a Poisson Poll structured     quote
  monitoring and  process and finds most systems poll at fixed intervals; about 65% of 150 million pages did not change in eleven   sources by their    
  change alerts   weeks. Eurostat's dataflows carry an UPDATE_DATA timestamp.                                                      own update          
                                                                                                                                    annotations; poll   
                                                                                                                                    pages at an         
                                                                                                                                    estimated change    
                                                                                                                                    rate; alert only on 
                                                                                                                                    a changed extracted 
                                                                                                                                    value, not a        
                                                                                                                                    changed page.       
  -------------------------------------------------------------------------------------------------------------------------------------------------------------

Citation metrics to adopt: DeepTRACE's citation accuracy (precision)
and citation thoroughness (recall), with its own thresholds as targets
--- accuracy ≥ 90%, unsupported statements \< 10%, thoroughness ≥ 50%
(3-lens). ALCE's NLI-based checks agreed with humans at kappa 0.698
(recall) and 0.525 (precision)
([ALCE](https://arxiv.org/abs/2305.14627), 2023; quote), so any
automatic judge needs calibrating against human labels first.

### B3 Web archives

-   **Common Crawl.** An audit of 41 releases (2013--2026) found its
    coverage gaps come from discovery, not opt-outs: only 1 of 36 hosts
    blocked its crawler, while 8 of 45 traced URLs were never captured.
    Client-rendered pages and linked PDFs yield almost no text ([WAC
    2026](https://aclanthology.org/2026.wac-1.21/), 29 Oct 2026; quote).
    Checking only recent releases roughly doubles the apparent gap.

-   **Memento.** RFC 7089 gives one protocol over many archives:
    TimeGate, TimeMap (application/link-format, pageable) and a
    Memento-Datetime that promises the capture will not change (quote).

-   **Wayback CDX.** Already researched in the repository
    (docs/architecture/deep-research-connectors.md §5). Not
    re-researched; its rate limits and terms remain unconfirmed.

-   **Combining them** \[inference\]: query Common Crawl's index
    (cheap, bulk) first, Wayback CDX for the gaps, and the Czech
    national archive through Memento where it allows; store each
    capture's own datetime and archive as provenance.

Terms and coverage, all quote-checked:

-   **Common Crawl terms** ([ToU](https://commoncrawl.org/terms-of-use),
    last updated 7 Mar 2024) grant a "limited, non-exclusive" licence
    and neither permit nor forbid commercial use; Common Crawl
    "strongly recommends" legal advice "before making any use,
    including commercial use". Crawled pages "may be subject to
    separate terms" of their owners, harvesting personal information
    for separate use is forbidden, and content may be removed "at any
    time". AIA's own content-addressed snapshot, not the Common Crawl
    copy, is therefore the durable evidence \[inference\].

-   **Size and Czech share.** The latest release, CC-MAIN-2026-43, has
    2,169,426,757 page captures
    ([statistics](https://commoncrawl.github.io/cc-crawl-statistics/plots/crawlsize/monthly.csv)).
    Czech is about 1.15% of HTML pages in the last three releases,
    against about 42% English ([language
    table](https://commoncrawl.github.io/cc-crawl-statistics/plots/languages);
    Common Crawl's own CLD2 figures, not an independent study).

-   **Webarchiv (Národní knihovna ČR).** Only a secondary source could
    be read: online access covers publishers who agreed; everything else
    is viewable only on library terminals
    ([Wikipedia](https://en.wikipedia.org/wiki/Webarchiv), edited Sep
    2026). webarchiv.cz answered automated requests with HTTP 404.
    Whether it exposes Memento or CDX is unknown.

-   **Unknown:** the Internet Archive's terms on automated access and
    any official rate limit (its terms page renders client-side and
    returned no text), and whether the Memento TimeTravel aggregator
    still runs (its host did not resolve).

### B4 Source credibility for business facts

Score a source per claim type, not per domain, keep "unknown scores
lowest", and never let a model assign credibility. All findings below
are quote-checked.

  ---------------------------------------------------------------------------------------------------------------------------------
  Source                                                                                      What it establishes
  ------------------------------------------------------------------------------------------- -------------------------------------
  [Lin et al., PNAS Nexus](https://pmc.ncbi.nlm.nih.gov/articles/PMC10500312/), Sep 2023      Six expert rating sets over 11,520
  (older than 3 years)                                                                        news domains agree substantially:
                                                                                              Pearson r 0.32--0.86, Spearman
                                                                                              0.32--0.90. Their first principal
                                                                                              component explains 68.21% of variance
                                                                                              and gives an open 0--1 score. The
                                                                                              authors warn that a domain rating
                                                                                              "assumes each domain produces
                                                                                              content of identical quality" and is
                                                                                              less accurate than checking items.
                                                                                              NewsGuard forbids publishing
                                                                                              aggregates that include its ratings.

  [NewsGuard criteria](https://www.newsguardtech.com/ratings/rating-process-criteria/),       Nine pass/fail criteria weighted 22,
  updated 14 Apr 2026                                                                         18, 12.5, 12.5, 10, 7.5, 7.5, 5, 5
                                                                                              points (false content, responsible
                                                                                              gathering, corrections, news vs
                                                                                              opinion, headlines, ownership,
                                                                                              advertising labels, who is in charge,
                                                                                              named authors); bands from 0--39 to
                                                                                              100.

  [Wikipedia perennial                                                                        Five tiers (generally reliable in its
  sources](https://en.wikipedia.org/wiki/Wikipedia:Reliable_sources/Perennial_sources),       area, no consensus, generally
  edited 28 Oct 2026                                                                          unreliable, deprecated, blacklisted);
                                                                                              "a source's reliability depends on
                                                                                              the claim". Bloomberg and the FT are
                                                                                              generally reliable for business;
                                                                                              Bloomberg company profiles, built
                                                                                              from press releases, only for
                                                                                              uncontroversial facts; Crunchbase is
                                                                                              deprecated as largely user-generated.
                                                                                              Syndicated content is judged by its
                                                                                              original publisher; a discussion
                                                                                              older than four years is flagged
                                                                                              stale.

  [European Statistics Code of                                                                16 principles, 84 indicators.
  Practice](https://ec.europa.eu/eurostat/documents/4031688/8971242/KS-02-18-142-EN-N.pdf),   Checkable items for a statistical
  2017 edition (older than 3 years)                                                           source: professional independence
                                                                                              (1), errors measured and documented
                                                                                              (12.2), revisions analysed (12.3),
                                                                                              preliminary results marked (13.5),
                                                                                              internal arithmetic coherence (14.1).

  [Yang & Menczer](https://arxiv.org/abs/2304.00228v3), WebSci 2025                           Nine LLMs' credibility ratings
                                                                                              agreed with each other (Spearman
                                                                                              0.79) but only moderately with
                                                                                              experts (0.50), showed a liberal bias
                                                                                              by default, and shifted with an
                                                                                              assigned partisan role.
  ---------------------------------------------------------------------------------------------------------------------------------

Proposed extension of AIA's class/score tables \[inference, built on
the rows above\]:

1.  Key each score by (source, claim type), with an area of expertise, a
    review date and a four-year stale flag.

2.  Class order: official statistics; statutory registers and filings;
    established business press and wires; other news domains; a company
    about itself (uncontroversial self-description only); user-generated
    aggregators; unknown (lowest).

3.  Official statistics get a pass/fail sub-score from the Code of
    Practice indicators above; preliminary and flash figures are tagged.

4.  News domains get AIA's own reviewers' pass/fail score on
    NewsGuard-style weighted criteria, seeded from Lin et al.'s open
    score, never from NewsGuard data.

5.  Deprecated and blacklisted sources are excluded, not merely scored
    low; disclosed AI-written content is treated as unreliable.

6.  Syndicated copies take the original publisher's score and never
    count as independent corroboration.

7.  A model may route an unknown source to a person for classification;
    it never sets the score.

### B summary

  --------------------------------------------------------------------------
  §2.5 component             Verdict   Why
  -------------------------- --------- -------------------------------------
  Verbatim quote in a        Keep      Unsupported statements are the
  same-track snapshot                  dominant measured failure of
                                       commercial agents (DeepTRACE).

  Six-step pipeline, one     Keep      Nothing found argues against them;
  gate, content-addressed              every new capability below fits as a
  snapshots, tool-cost                 route or step.
  ledger                               

  Search routes (Brave,      Extend    Add SDMX/register routes where code
  Wikipedia, Common Crawl)             fetches and the model only proposes
                                       the query (StatGPT pattern).

  Number handling            Extend    Add a typed-quantity extractor in
                                       code (value, unit, period, range,
                                       source, licence); models propose
                                       concept and period only.

  Verifier and confirmation  Extend    Add claim decomposition,
  bonus                                contradiction records, and citation
                                       recall alongside precision.

  Purposes                   Extend    Add as-of-date (Memento), precedent
                                       candidates and scheduled monitoring
                                       as new purposes.

  Source class/score tables  Extend    See B4.
  --------------------------------------------------------------------------

## C. Data sources and the law

Czech statutory registers carry no database right and must be published
as open data, so AIA can lawfully build on them. The real limits are
GDPR for the natural persons named in them, machine-readable
text-and-data-mining opt-outs on everything else, and per-source terms:
VIES forbids reuse outright, and ARES may block more than 500 queries a
minute. Financial statements are the gap: they sit in Sbírka listin as
PDF files, and small firms need not file a profit and loss account.

### C1 The sources

  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Source                                                                                   Holds and access                                              Terms, cost, frequency                                                                                                          Gaps                                                                                                                                                  Check
  ---------------------------------------------------------------------------------------- ------------------------------------------------------------- ------------------------------------------------------------------------------------------------------------------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------- -------------------
  [ARES](https://ares.gov.cz/stranky/vyvojar-info)                                         Identity, address, legal form, NACE, VAT and status across    "Anyone may use it" under the [operating conditions](https://ares.gov.cz/stranky/podminky-provozu): users sending "more than No financial statements \[inference from one sample record and the source list\]                                                                      quote
                                                                                           VR, RŽP, RES, DPH, IR, CEDR and others; REST JSON, OpenAPI    500 queries a minute" or spreading queries over many IPs may be blocked; data are "information only", not an official                                                                                                                                                              
                                                                                           v1.40 (documentation updated 31 Aug 2026)                     record; no fee stated                                                                                                                                                                                                                                                                 

  Commercial register and Sbírka listin ([dataor.justice.cz](https://dataor.justice.cz/))  Register extracts (full with history, or current) per court,  Free; terms page not read. Statements are due within 12 months; non-filing is fined up to 3% of total assets                    Statements are documents, not data. Small and micro firms without audit need not publish the P&L. CRIF reported in 2019 that over two-thirds of       quote
                                                                                           legal form and year, as CSV or XML; statements filed as PDF                                                                                                                                   companies had not filed for the year before last (2017)                                                                                               
                                                                                           or XHTML                                                                                                                                                                                      ([ČT24](https://ct24.ceskatelevize.cz/clanek/domaci/pres-290-tisic-firem-nezverejnuje-sve-hospodareni-novela-zakona-ma-zavest-tvrde-postihy-69087),   
                                                                                                                                                                                                                                                                                         secondary, dated)                                                                                                                                     

  ČÚZK cadastre                                                                            Free [REST                                                    Paid outputs priced by Decree 358/2013 Sb., e.g. 100 Kč per title-deed extract and 10 Kč per parcel record (verifier-reported); API call quota per account is not published                                                                                                           3-lens (API);
                                                                                           API-KN](https://cuzk.gov.cz/aplikace-dp/zakladni-informace)   quarterly transaction statistics (Q3 2026 out on 15 Oct 2026)                                                                                                                                                                                                                         prices
                                                                                           after registration (ApiKey; selected parcel, building, unit                                                                                                                                                                                                                                                                                         verifier-reported
                                                                                           and proceedings data; no personal data); paid WSDP and remote                                                                                                                                                                                                                                                                                       
                                                                                           access for verified outputs and ownership                                                                                                                                                                                                                                                                                                           

  Czech procurement (ISVZ open data)                                                       Two series: XML up to end January 2024; JSON from February    Free yearly files ([MMR reply, 16 Mar                                                                                           A structural break at Jan/Feb 2024. MMR's stated position is that NEN data visible only after login may not be disclosed to the unauthorised         3-lens
                                                                                           2024, drawn from the Registr veřejných zakázek (VVZ, NEN,     2026](https://mmr.gov.cz/getmedia/e42bc7d7-d766-40de-9582-915d922a5529/MMR-20211-2026-31-ze-dne-14-3-2026.pdf.aspx?ext=.pdf))                                                                                                                                                         
                                                                                           Tender arena, TENDERMARKET)                                                                                                                                                                                                                                                                                                                         

  EU TED                                                                                   [TED API                                                      Free and anonymous; eForms mandatory from 25 Oct 2023                                                                           Historical series mix legacy TED XML and eForms schemas                                                                                               3-lens
                                                                                           v3](https://docs.ted.europa.eu/api/latest/index.html):                                                                                                                                                                                                                                                                                              
                                                                                           searching and retrieving published notices needs no key;                                                                                                                                                                                                                                                                                            
                                                                                           daily and monthly XML packages                                                                                                                                                                                                                                                                                                                      

  ČNB                                                                                      Daily fixing as TXT/XML for any date, yearly files back to    Free; published working days after 14:30; the ČNB says it will restrict "excessive automated access"                          Rates are per quantity (100 HUF, 100 JPY) with comma decimals                                                                                         quote
                                                                                           1991, a REST API at api.cnb.cz; ARAD has month-end and                                                                                                                                                                                                                                                                                              
                                                                                           monthly-average series                                                                                                                                                                                                                                                                                                                              

  ECB Data Portal                                                                          SDMX 2.1 REST at data-api.ecb.europa.eu, CSV on request,      Free; reuse terms are on a separate page not read here                                                                          Its own examples switch TLS verification off: do not copy them                                                                                        quote
                                                                                           whole datasets in one call                                                                                                                                                                                                                                                                                                                          

  [Eurostat](https://ec.europa.eu/eurostat/help/copyright-notice)                          SDMX 2.1 API (see B2)                                         Commercial reuse allowed with no licence or application, on acknowledging the source; modified data must say so                 Not reusable commercially: non-Eurostat sources, some non-EU data, Swiss and Liechtenstein trade data                                                 quote

  [ČSÚ DataStat](https://csu.gov.cz/zakladni-informace-pro-pouziti-api-datastatu)          REST catalogue and query API; CSV, JSON-STAT, XLSX; no login  CC BY 4.0 for statistics released through csu.gov.cz; derived data must be labelled as derived; the old public database closes  No SDMX or rate limit documented                                                                                                                      quote
                                                                                                                                                         at the end of 2026                                                                                                                                                                                                                                                                    

  [GLEIF](https://www.gleif.org/en/lei-data/gleif-api)                                     LEI records, parent-child ownership (Level 2), BIC and ISIN   Licence not on the page read                                                                                                    Only entities with an LEI                                                                                                                             quote
                                                                                           mappings; production since autumn 2020                                                                                                                                                                                                                                                                                                              

  [VIES](https://ec.europa.eu/taxation_customs/vies/#/disclaimer)                          Today's validity of one VAT number; name and address where   "Any retransmission ... whether for a commercial purpose or otherwise ... is expressly forbidden"; abusive IPs are blocked    No history, no search, no bulk through the API                                                                                                        quote
                                                                                           the member state allows                                                                                                                                                                                                                                                                                                                             

  [data.europa.eu](https://dataeuropa.gitlab.io/data-provider-manual/api-documentation/)   Search API (read-only, paged) and SPARQL over harvested       Each dataset keeps its source's licence, including non-commercial ones                                                         Metadata only                                                                                                                                         quote
                                                                                           metadata                                                                                                                                                                                                                                                                                                                                            

  Commercial firm data                                                                     [Merk](https://api.merk.cz/docs/): REST API with Czech        Contract                                                                                                                        Prices for Cribis, MagnusWeb, Orbis and Creditinfo not found; Hlídač státu refused automated access                                                   quote
                                                                                           financial statements; financial endpoints limited to 10                                                                                                                                                                                                                                                                                             
                                                                                           requests a minute; prices not published (7-day trial). Cribis                                                                                                                                                                                                                                                                                       
                                                                                           (CRIF) is offered at VŠE as a replacement for Albertina and                                                                                                                                                                                                                                                                                         
                                                                                           MagnusWeb there                                                                                                                                                                                                                                                                                                                                     
  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

### C2 What the law permits

  --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Question               Rule                                  Source                                                                                                                                                                                                Check
  ---------------------- ------------------------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- -------
  Database right         The maker of a database built with    [Directive 96/9/EC Art. 7](https://www.legislation.gov.uk/eudr/1996/9/article/7/adopted); [Act 121/2000 Sb.](https://www.zakonyprolidi.cz/cs/2000-121) §§ 88a--93 (secondary host)                    quote
                         "substantial investment" can stop                                                                                                                                                                                                         
                         extraction of "the whole or of a                                                                                                                                                                                                           
                         substantial part", and "repeated                                                                                                                                                                                                          
                         and systematic" taking of                                                                                                                                                                                                                  
                         insubstantial parts. In Czech law a                                                                                                                                                                                                         
                         lawful user may use insubstantial                                                                                                                                                                                                           
                         parts "for any purpose", if not                                                                                                                                                                                                           
                         systematically; the free licences for                                                                                                                                                                                                       
                         substantial parts are non-commercial.                                                                                                                                                                                                       
                         The right lasts 15 years.                                                                                                                                                                                                                   

  Public registers       Official works include "a publicly   Act 121/2000 Sb.; [Smítal 2023](https://pravniprostor.cz/clanky/obcanske-pravo/uzivani-verejne-dostupnych-databazi-ke-komercnim-ucelum) (secondary)                                                   quote
                         accessible register and its                                                                                                                                                                                                                 
                         collection of documents" (§ 3(a)),                                                                                                                                                                                                         
                         and § 94 applies that to database                                                                                                                                                                                                           
                         makers. Commentary names the                                                                                                                                                                                                                
                         commercial register and similar                                                                                                                                                                                                             
                         registers, limited to those                                                                                                                                                                                                                 
                         established by law.                                                                                                                                                                                                                         

  What counts as         "Obtaining" means seeking out       [Court of Appeal quoting the ECJ](https://caselaw.nationalarchives.gov.uk/ewca/civ/2005/863); [Husovec &                                                                                              quote
  investment             existing materials, not creating them Derclaye](https://legalblogs.wolterskluwer.com/copyright-blog/access-to-information-and-competition-concerns-enter-the-sui-generis-rights-infringement-test-the-cjeu-redefines-the-database-right/)   
                         (BHB v William Hill, C-203/02, 2004). (secondary)                                                                                                                                                                                           
                         Copying by a specialised search                                                                                                                                                                                                             
                         engine infringes only if it deprives                                                                                                                                                                                                        
                         the maker of income needed to redeem                                                                                                                                                                                                        
                         its investment (CV-Online Latvia,                                                                                                                                                                                                           
                         C-762/19, 2021).                                                                                                                                                                                                                            

  Text and data mining   Art. 4 allows mining of "lawfully    [DSM Directive Art. 4](https://www.legislation.gov.uk/eudr/2019/790/article/4/adopted); Act 121/2000 Sb. § 39c; [Menčík                                                                               quote
                         accessible" content, not limited to  2024](https://www.epravo.cz/top/aktualne/vytezovani-verejne-dostupnych-autorskych-del-pro-ucely-trenovani-umele-inteligence-118625.html) (secondary)                                                  
                         research, unless rights are reserved                                                                                                                                                                                                        
                         "by machine-readable means" online;                                                                                                                                                                                                       
                         copies may be kept only "for as long                                                                                                                                                                                                       
                         as is necessary". Art. 3 is for                                                                                                                                                                                                            
                         research bodies only. Czech § 39c                                                                                                                                                                                                           
                         (Act 429/2022 Sb.) matches and, per                                                                                                                                                                                                         
                         its explanatory report, covers                                                                                                                                                                                                              
                         commercial use; a reservation in                                                                                                                                                                                                            
                         terms-of-use text is not enough.                                                                                                                                                                                                            

  What                   LG Hamburg (27 Sep 2024) said a       [Filikhina & Elsäß](https://www.technologyslegaledge.com/2025/12/robert-kneschke-v-laion-judgment-of-10-december-2025-ref-5-u-104-24/) (secondary)                                                    quote
  "machine-readable"   natural-language reservation is                                                                                                                                                                                                             
  means                  generally enough; OLG Hamburg (10 Dec                                                                                                                                                                                                       
                         2025, 5 U 104/24) disagreed: it must                                                                                                                                                                                                        
                         be "interpreted by machines", and                                                                                                                                                                                                         
                         "mere machine detectability is not                                                                                                                                                                                                         
                         sufficient". A further appeal to the                                                                                                                                                                                                       
                         BGH was allowed; its outcome is                                                                                                                                                                                                             
                         unknown.                                                                                                                                                                                                                                    

  Open data              High-value datasets (company          [Reg. (EU) 2023/138](https://iho.int/uploads/user/Inter-Regional%20Coordination/IENWG%20and%20EC%20-%20IHO%20Cooperation/IENWG13/IENWG13_2023_03B_Commission_Implementing_Regulation_21122022.pdf);   quote
                         information and accounts at company   [Act 106/1999 Sb.](https://www.zakonyprolidi.cz/cs/1999-106) (secondary host)                                                                                                                         
                         level, statistics except microdata,                                                                                                                                                                                                         
                         cadastral parcels) must be free, via                                                                                                                                                                                                        
                         API, under CC0 or CC BY 4.0 or less                                                                                                                                                                                                         
                         restrictive terms; applied since                                                                                                                                                                                                            
                         2024. Czech § 5a(2) requires                                                                                                                                                                                                                
                         registers to be published as open                                                                                                                                                                                                           
                         data, except Sbírka listin documents,                                                                                                                                                                                                       
                         with names withheld unless tied to                                                                                                                                                                                                          
                         business or a statutory-body role.                                                                                                                                                                                                          

  GDPR on register data  The Czech DPA (ÚOOÚ) fined a company  [ÚOOÚ order UOOU-04153/20-4](https://uoou.gov.cz/media/poskytnute-informace/2025/1292025/prikaz-cj-uoou-0415320-4.pdf); [GDPR Art.                                                                    quote
                         CZK 500,000 in 2020 for copying sole  14](https://www.legislation.gov.uk/eur/2016/679/article/14/adopted); [epravo 2020](https://www.epravo.cz/top/clanky/dalsi-zpracovani-osobnich-udaju-zverejnenych-organy-verejne-moci-110749.html)     
                         traders' data from the trade and                                                                                                                                                                                                           
                         commercial registers onto its                                                                                                                                                                                                               
                         website: copying a register not run                                                                                                                                                                                                         
                         as open data "without added value"                                                                                                                                                                                                        
                         fails the necessity test of Art.                                                                                                                                                                                                            
                         6(1)(f); Art. 14 notice is still owed                                                                                                                                                                                                       
                         for public data, and the                                                                                                                                                                                                                    
                         disproportionate-effort exemption was                                                                                                                                                                                                       
                         rejected. Its 2019 inspection held                                                                                                                                                                                                          
                         that personal data published as open                                                                                                                                                                                                        
                         data may be reused commercially after                                                                                                                                                                                                       
                         a balancing test (secondary report).                                                                                                                                                                                                        

  Beneficial owners      Public access to beneficial-ownership [eucrim](https://eucrim.eu/news/cjeu-no-unrestricted-access-to-data-of-beneficial-owners/) (secondary)                                                                                                quote
                         data is "a serious interference"                                                                                                                                                                                                          
                         with Charter Arts. 7 and 8; the AML                                                                                                                                                                                                         
                         provision allowing it is invalid (WM                                                                                                                                                                                                        
                         and Sovim, 22 Nov 2022).                                                                                                                                                                                                                    

  Website terms          Contract terms may restrict use of a  [IPKat](https://ipkitten.blogspot.com/2015/01/breaking-cjeu-says-that-owner-of-online.html) (secondary)                                                                                               quote
                         database protected by neither                                                                                                                                                                                                               
                         copyright nor the database right                                                                                                                                                                                                            
                         (Ryanair v PR Aviation, C-30/14,                                                                                                                                                                                                            
                         2015). No Czech decision on terms                                                                                                                                                                                                           
                         against scrapers was found.                                                                                                                                                                                                                 
  --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

No official CJEU text could be read: EUR-Lex and Curia refuse automated
access, so the judgments are cited through secondary copies.

### C3 Lawful status of AIA's routes

All rows are \[inference\] from C2.

  -----------------------------------------------------------------------
  Route                             Status
  --------------------------------- -------------------------------------
  Czech statutory registers through Lawful and open. No database right.
  open data or API (ARES,           Named sole traders and directors
  commercial register, RES)         still need a balancing test and an
                                    Art. 14 notice before AIA stores
                                    them.

  High-value datasets: ČSÚ,         Lawful and open, with attribution and
  Eurostat, ČÚZK parcels, company   "derived" labels.
  data                              

  Public company websites with no   Lawfully reachable for mining under §
  machine-readable opt-out          39c, commercial use included; keep
                                    copies only as long as necessary; no
                                    substantial extraction from a
                                    protected database.

  Content behind a free login or    Lawfully reachable within the account
  API key                           terms; not to be redistributed.

  A site whose robots.txt disallows Treat as reserved: do not mine it
  crawlers                          commercially. No court has ruled on a
                                    plain Disallow.

  Register data not published as    Unlawful on the ÚOOÚ's 2020
  open data, republished with names reasoning.
  in client reports                 

  VIES results stored or passed on  Forbidden by its terms.

  Substantial or systematic         Unlawful where it puts the maker's
  extraction from private databases investment at risk.
  (job boards, aggregators)         

  Bulk harvesting of                High risk; do not collect.
  beneficial-owner data; NEN        
  login-only data                   
  -----------------------------------------------------------------------

### C4 The frozen panel and market-sizing counts

Whether the licensed Czech panel may lawfully feed market-sizing counts
is **unknown**: it depends on its licence, which this research did not
see. If its records are pseudonymised they remain personal data, and
only aggregates that prevent singling out, linkage and inference count
as anonymous ([WP29 Opinion
05/2014](https://ec.europa.eu/justice/article-29/documentation/opinion-recommendation/files/2014/wp216_en.pdf);
quote). Statistically, a panel count is a weighted sample estimate, so
it could only ever enter a result as ESTIMATED, with an interval
\[inference\]. Recommendation: keep it frozen until counsel has read the
licence.

### C summary

  ------------------------------------------------------------------------
  §2 component       Verdict         Why
  ------------------ --------------- -------------------------------------
  Existing           Keep            Lawful, open and free; this research
  connectors (ARES,                  verified their terms.
  DataStat,                          
  Eurostat, NKOD)                    

  Procurement        Extend          Wire both ISVZ series and TED; join
  connector                          them at Feb 2024; parse both schemas.
  (recorded only)                    

  Sources without a  Extend          Add ČNB, ECB, GLEIF and ČÚZK API-KN.
  connector                          Never store VIES results.

  Financial          Extend          Sbírka listin is PDF only: extract
  statements                         with person review, or buy structured
                                     data (Merk API); expect missing P&Ls
                                     for small firms.

  The gate's egress Extend          Add per-source rate limits (ARES 500
  control                            a minute), robots.txt and
                                     TDM-reservation checks, and a
                                     retention limit on mined copies.

  Dataset preview    Keep, and       Add a record of the Art. 6(1)(f)
  that masks         extend          balancing test and Art. 14 notice for
  personal columns                   any named natural person.

  Panel as a source  Hold            Licence unknown; at most an ESTIMATED
  of market counts                   input with an interval.
  ------------------------------------------------------------------------

## D. Modelling the four families on client data

The methods ADR 0044 plans are the defensible ones. The evidence adds
four corrections:

-   model input correlations;

-   check PERT's beta shape against the data;

-   judge forecasts with MASE, not raw MAE, and never with MAPE when
    zeros occur;

-   never present an NPV distribution discounted at a risk-adjusted rate
    as a measure of risk.

No usable logistics or warehouse benchmarks for Czechia or Poland were
found (D3).

### D1 Methods, data and failures by family

  -------------------------------------------------------------------------------------------------------------------------------------------------------------
  Family       Defensible method and evidence                                                                        Check      Data it needs   Typical
                                                                                                                                (ledger, CRM,   failures
                                                                                                                                orders)         
  ------------ ----------------------------------------------------------------------------------------------------- ---------- --------------- ---------------
  Finance      **Correlations.** Leaving input correlations out of a Monte Carlo cost model "leads to serious       3-lens     Cash-flow lines Accrual timing
               misassessment of risk", and mattered more than choosing lognormal or beta; on that data lognormal               by period,      read as cash;
               fitted better than beta ([Wall 1997](https://ideas.repec.org/a/taf/conmgt/v15y1997i3p241-258.html),              capex,          one-off items
               abstract). The effect sits mainly in high percentiles, and one 1995 study ranks the choice of                    financing terms left in the run
               distribution higher (verifier-reported).                                                                                         rate
                                                                                                                                                \[inference\]

  Finance      **Discount rates.** For an undiversified private owner, Damodaran divides the market beta by the      quote                      
               correlation with the market ("total beta"); his worked example gives a 14.50% cost of equity for                               
               the owner against 9.38% for a diversified buyer ([valuation                                                                      
               notes](https://pages.stern.nyu.edu/~adamodar/podcasts/valfall15/valsession20.pdf), secondary).                                   
               Simulating does not remove risk, so the rate must not be lowered in a Monte Carlo NPV ([SME                                      
               1996](https://onemine.org/documents/-mis-use-of-monte-carlo-simulations-in-npv-analysis), abstract).                             
               Discounting simulated cash flows at a risk-adjusted rate and presenting the NPV spread as risk                                   
               double-counts it                                                                                                                 
               ([Vose](https://riskwiki.vosesoftware.com/DeterminingtheNPVofacapitalinvestment.php), blog).                                     
               Averaging two experts' three-point estimates narrows the spread; sample from each instead (Vose).                               

  Accounting   **Time-driven ABC.** Two estimates per resource group: cost per unit of capacity and the units each   3-lens     Ledger by cost  Unallocated
               order or customer uses; practical capacity is about 80% of theoretical for people; the estimate need  (case);    centre and      overheads;
               only be within 5--10%; warehouse capacity can be priced per cubic metre ([Kaplan                      quote      nature, staff   miscoded
               2005](https://hbswk.hbs.edu/item/rethinking-activity-based-costing), secondary). A Belgian wholesaler (method)   time, order     accounts
               chose between ABC and TDABC "to calculate profitability at the order and the customer level"                   lines with      \[inference\]
               ([Everaert et al. 2008](https://econpapers.repec.org/RePEc:eee:joaced:v:26:y:2008:i:3:p:118-154)).               activity counts 
                                                                                                                                (lines, picks,  
                                                                                                                                deliveries),    
                                                                                                                                customer master 

  Accounting   **Czech statements.** Decree 500/2002 Sb. sets the layout; the P&L may be by nature (Annex 2) or by   quote                      Missing P&L and
               function (Annex 3), so ingestion must read both; micro and small firms need no cash-flow statement                               cash flow for
               ([decree text](https://esipa.cz/sbirka/sbsrv.dll/sb?CP=2002s500&DR=SB), secondary host).                                         small filers
                                                                                                                                                (C1)

  Operations   **Forecasting.** In M5 (42,840 Walmart series), only 7.5% of 5,507 teams beat the                     3-lens     Order lines     Stock-outs
               exponential-smoothing bottom-up benchmark. The winner beat it by 22.4% overall, but the top 50 gained            with date, SKU, censor demand;
               only about 3% at product-store level ([Makridakis et al.,                                                        quantity,       returns netted
               M5](https://statmodeling.stat.columbia.edu/wp-content/uploads/2021/10/M5_accuracy_competition.pdf),              returns; stock  into sales;
               preprint of IJF 2022).                                                                                           positions; lead duplicates
                                                                                                                                times           \[inference\]

  Operations   **Forecast metric.** MASE scales errors by the in-sample naive error, so it compares across series;   3-lens                     Intermittent
               MAPE and RMSPE are "infinite or undefined" when any actual is zero ([Hyndman & Koehler                                         SKUs break
               2006](https://robjhyndman.com/papers/mase.pdf)). For seasonal data, scale by the seasonal naive                                  percentage
               (verifier-reported, FPP3).                                                                                                       errors

  Operations   **Inventory.** The textbook z-formula for safety stock is exact only when the reorder quantity is 1;  quote                      
               the normal approximation holds only when the demand standard deviation is below a third of the mean;                             
               control on inventory position, not on-hand stock ([Factory Physics                                                               
               2020](https://factoryphysics.com/inventory-part-ii-calculating-safety-stock-correctly), blog).                                   
               Queueing and capacity planning were not researched.                                                                              

  Market       See D2.                                                                                                          Sales by        
  sizing                                                                                                                        customer        
                                                                                                                                segment and     
                                                                                                                                region (CRM)    
                                                                                                                                for bottom-up   
                                                                                                                                triangulation   
  -------------------------------------------------------------------------------------------------------------------------------------------------------------

### D2 Top-down market sizing from public statistics

-   **Formula.** Eurostat defines apparent consumption as production +
    imports − exports; "a negative result indicates a problem with
    either the production or external trade figures" ([Prodcom
    metadata](https://ec.europa.eu/eurostat/cache/metadata/EN/prom_esms.htm),
    Sep 2026). Flag negatives for review; never clip them to zero
    (3-lens).

-   **Error bounds.** Eurostat "can estimate that the overall coverage
    error at EU27 level is under 10%". That is an informal estimate of
    coverage error only, with no figure for Czechia (3-lens). Prodcom is
    a cut-off sample, so it publishes no sampling errors (quote).

-   **Confidentiality and rounding.** National confidential values are
    suppressed (:C). Unsafe EU totals are published rounded, to be read
    as PROD_VALUE ± PROD_VALUE_BASE ([quick
    guide](https://ec.europa.eu/eurostat/documents/d/prodcom/quick-guide-on-accessing-prodcom-data-ds-059367),
    Oct 2026; 3-lens).

-   **One dataset.** DS-059367 carries production, imports and exports
    in one unit per product from reference year 2025, so apparent
    consumption can be computed in value and quantity. Earlier years
    need another dataset, and EU totals count only extra-EU trade
    (3-lens and quote).

-   **For AIA** \[inference\]: compute apparent consumption per product;
    carry the rounding base and at least a 10% coverage band as the
    interval; mark :C gaps; triangulate with ČSÚ and the client's own
    sales; grade the result ESTIMATED. Household budget surveys,
    structural business statistics and published accuracy studies of
    top-down sizing were not researched in this pass (unknown).

### D3 Precedents and benchmarks for logistics, e-commerce and capacity

Not found. No source on 3PL cost benchmarks, Czech or Polish warehouse
rents, parcel prices or e-commerce return rates was read in this pass.
The candidates are the rent reports of CBRE, Cushman & Wakefield, JLL
and Colliers; APEK and Heureka for e-commerce; Eurostat's ICT surveys;
and ČSÚ and Eurostat labour-cost series. Until they are read, the
warehouse-versus-3PL example rests on client data and stated inputs
only.

### D summary

  ------------------------------------------------------------------------
  §2.4 component        Verdict      Why
  --------------------- ------------ -------------------------------------
  Model-type contract   Keep         Every source above assumes inputs can
  with input provenance              be traced.

  Cost-scenario family  Keep, extend Add time-driven cost-to-serve per
  (fixed, variable,                  order and customer, and capacity
  step, capital; NPV;                priced per unit of space.
  payback; break-even)               

  Data checks (MAD      Keep         Add a check that both Czech P&L
  outliers,                          layouts reconcile.
  seasonality,                       
  reconciliation)                    

  PERT Monte Carlo      Extend       Test the beta shape against data
                                     (Wall found lognormal fitted better);
                                     sample disagreeing experts as a
                                     mixture, never an average.

  Iman-Conover rank     Keep         Omitting correlation is the larger
  correlation                        documented error (Wall).

  Backtests judged on   Change       Use MASE (seasonal scaling); never
  held-out MAE                       MAPE with zeros; add exponential
                                     smoothing bottom-up as the benchmark
                                     to beat.

  Decision rule judged  Keep,        Declare one discount rate per study,
  on a probability      specify      apply it to all options, and never
                                     lower it because the model is
                                     simulated.

  PCG64 streams,        Keep         Not challenged by anything read; not
  Sobol/PRCC, EVPPI                  researched in depth here.
  ------------------------------------------------------------------------

## E. Competitive landscape and white space

Big planning suites now ship Monte Carlo and scenario audit trails
(Workday, 2026), and spreadsheet add-ins sell Monte Carlo for about
€3,000 a year. But no vendor read here describes a decision rule fixed
before the data, number-level provenance to external sources, or Czech
public data. That combination, for small and mid-size firms with EU
residency, is AIA's white space \[inference\], and it is narrowing.
Coverage is partial: Gartner and several vendors refused automated
access.

### E1 Vendors

  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Vendor (evidence date)                                                                                                                                                               Modelling and     Provenance and        Price                                                                                  Documented weakness                                                                                                    Check
                                                                                                                                                                                       uncertainty       external data                                                                                                                                                                                                                       
  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ ----------------- --------------------- -------------------------------------------------------------------------------------- ---------------------------------------------------------------------------------------------------------------------- ----------------
  Workday, Adaptive from Workday ([May 2026                                                                                                                                            Decision          "Every scenario      Not published                                                                          Number-level provenance and external research not described \[inference\]                                              Audit trail and
  release](https://newsroom.workday.com/2026-05-27-Workday-Introduces-Adaptive-Decision-Intelligence,-Bringing-Planning-Questions,-Scenarios,-and-Decisions-Into-One-AI-Experience);   Intelligence      carries an audit                                                                                                                                                                                                                    decision log
  [Sep 2026 post](https://blog.workday.com/en-us/adaptive-workday-new-era-decision-intelligence.html))                                                                                 compares          trail": data                                                                                                                                                                                                                       3-lens;
                                                                                                                                                                                       scenarios and     sources, assumptions,                                                                                                                                                                                                               "built-in Monte
                                                                                                                                                                                       runs "Monte      who approved; a                                                                                                                                                                                                                     Carlo as of 27
                                                                                                                                                                                       Carlo simulations record of decisions                                                                                                                                                                                                                 May" refuted as
                                                                                                                                                                                       to show a range   "and why". Named                                                                                                                                                                                                                  overstated
                                                                                                                                                                                       of likely         sources are internal                                                                                                                                                                                                                (early adopters
                                                                                                                                                                                       outcomes for each (planning data, CRM,                                                                                                                                                                                                                only)
                                                                                                                                                                                       option";         HR, warehouses).                                                                                                                                                                                                                    
                                                                                                                                                                                       early-adopter                                                                                                                                                                                                                                         
                                                                                                                                                                                       only at launch,                                                                                                                                                                                                                                       
                                                                                                                                                                                       generally                                                                                                                                                                                                                                             
                                                                                                                                                                                       available per the                                                                                                                                                                                                                                     
                                                                                                                                                                                       September post                                                                                                                                                                                                                                        

  Aera Technology ([AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-2eleg2lr5dcuk))                                                                                    "Optimization,   The listing claims    USD 420,000 for 12 months, per contract unit                                           Few public reviews; scenario method not published                                                                      Price 3-lens;
                                                                                                                                                                                       predictions,      visibility "down to                                                                                         ([RFP.Wiki](https://www.rfp.wiki/artificial-intelligence/decision-intelligence-platforms/aera-technology/cloverpop),   capability
                                                                                                                                                                                       modeling, and     the transaction                                                                                              secondary)                                                                                                             claims from the
                                                                                                                                                                                       artificial        level"; Aera's                                                                                                                                                                                                                    listing refuted
                                                                                                                                                                                       intelligence"    current pages claim a                                                                                                                                                                                                               as out of date
                                                                                                                                                                                                         decision ledger and                                                                                                                                                                                                                 
                                                                                                                                                                                                         data residency                                                                                                                                                                                                                      
                                                                                                                                                                                                         (verifier-reported)                                                                                                                                                                                                                 

  Lumivero \@RISK ([product page](https://lumivero.com/products/atrisk/))                                                                                                              Excel add-in, 90+ None described        €2,900 a year Professional, €3,500 Industrial                                          Windows-only; reviewers cite a learning curve and "poor transparency of the underlying calculation"                  3-lens (product,
                                                                                                                                                                                       distributions,                          ([Vose](https://www.vosesoftware.com/Articles/At-RISK-Pricing-and-Alternatives.php),   ([Capterra](https://www.capterra.com/p/59453/RISK/), secondary)                                                        Windows); quote
                                                                                                                                                                                       thousands of                            Oct 2026, secondary)                                                                                                                                                                                          (price, reviews)
                                                                                                                                                                                       iterations; a                                                                                                                                                                                                                                         
                                                                                                                                                                                       2026 "@RISK                                                                                                                                                                                                                                          
                                                                                                                                                                                       Agent" links it                                                                                                                                                                                                                                      
                                                                                                                                                                                       to Anthropic                                                                                                                                                                                                                                          
                                                                                                                                                                                       Claude over MCP                                                                                                                                                                                                                                       

  ProbabilityManagement.org, SIPmath 3.0 ([2021 release](https://probabilitymanagement.org/blog/2021/9/6/the-sipmath-30-standard-and-analytic-solver-v20215), older than 3 years)      An open standard: Arrays of trials, not Free standard; non-profit                                                              ---                                                                                                                    3-lens
                                                                                                                                                                                       Metalog           sources                                                                                                                                                                                                                             
                                                                                                                                                                                       distributions, a                                                                                                                                                                                                                                      
                                                                                                                                                                                       portable                                                                                                                                                                                                                                              
                                                                                                                                                                                       random-number                                                                                                                                                                                                                                         
                                                                                                                                                                                       generator and a                                                                                                                                                                                                                                       
                                                                                                                                                                                       copula layer for                                                                                                                                                                                                                                      
                                                                                                                                                                                       "coherent,                                                                                                                                                                                                                                           
                                                                                                                                                                                       auditable"                                                                                                                                                                                                                                           
                                                                                                                                                                                       uncertainty;                                                                                                                                                                                                                                          
                                                                                                                                                                                       trials reproduce                                                                                                                                                                                                                                      
                                                                                                                                                                                       identically in                                                                                                                                                                                                                                        
                                                                                                                                                                                       Excel, Python and                                                                                                                                                                                                                                     
                                                                                                                                                                                       R                                                                                                                                                                                                                                                     

  Lucanet xP&A (formerly Causal)                                                                                                                                                       Scenario          Not described         Not published                                                                          Unsourced marketing figures ("100x fewer formulas")                                                                  3-lens
                                                                                                                                                                                       planning; no                                                                                                                                                                                                                                          (acquisition);
                                                                                                                                                                                       Monte Carlo                                                                                                                                                                                                                                           quote
                                                                                                                                                                                       mentioned                                                                                                                                                                                                                                             

  Pigment and Anaplan ([Pigment's comparison](https://www.pigment.com/compare/anaplan-vs-pigment), Jan 2026, vendor)                                                                  Connected         "Audit logs" here   Not published                                                                          Pigment says Anaplan needs imports to move data between models (a competitor's claim)                                 quote
                                                                                                                                                                                       planning          means user and access                                                                                                                                                                                                               
                                                                                                                                                                                                         logs, not number                                                                                                                                                                                                                    
                                                                                                                                                                                                         provenance                                                                                                                                                                                                                          

  Mosaic                                                                                                                                                                               FP&A; acquired by ---                   ---                                                                                    ---                                                                                                                    quote
                                                                                                                                                                                       HiBob (HR                                                                                                                                                                                                                                             
                                                                                                                                                                                       software) in Feb                                                                                                                                                                                                                                      
                                                                                                                                                                                       2025, now aimed                                                                                                                                                                                                                                       
                                                                                                                                                                                       at workforce                                                                                                                                                                                                                                          
                                                                                                                                                                                       planning                                                                                                                                                                                                                                              

  Cloverpop                                                                                                                                                                            Qualitative       Decision records      Cost cited as a barrier for small teams (RFP.Wiki, secondary)                          Product reviews from 2015 are older than 3 years                                                                       quote
                                                                                                                                                                                       decision records;                                                                                                                                                                                                                                     
                                                                                                                                                                                       scored low on                                                                                                                                                                                                                                         
                                                                                                                                                                                       simulation by                                                                                                                                                                                                                                         
                                                                                                                                                                                       RFP.Wiki                                                                                                                                                                                                                                              
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Not found in this research: prices for Anaplan, Board, Jedox, OneStream,
Planful, Vena, Cube, Datarails and Abacum; Quantexa, Peak, Tellius,
Pyramid Analytics and Diwo; Power BI Copilot, Tableau Pulse, ThoughtSpot
and Hex; AlphaSense, Perplexity Enterprise and Elicit; any Czech or CEE
player.

### E2 Analyst views

Unknown. Gartner's Magic Quadrant for Decision Intelligence Platforms
and a 2026 press release about it both refused automated access, and no
decision-intelligence market-size estimate was read.

### E3 Where AIA's white space is

  ----------------------------------------------------------------------------------
  Capability    Workday        Aera          \@RISK      SIPmath      AIA (as
                Adaptive                                              designed)
  ------------- -------------- ------------- ----------- ------------ --------------
  Monte Carlo   Yes, from 2026 Not stated    Yes         Yes          Designed, not
  on decision                                            (standard)   built (ADR
  options                                                             0044)

  Audit trail   Scenario:      Decision      None        Auditable    Every printed
  level         sources,       ledger        described   trial arrays number tied to
                assumptions,   (vendor)                               a graded
                approver                                              ledger entry

  Sourced       Not described  "Internal    No          No           Yes: Deep
  external                     and                                    Research with
  research                     external"                             verbatim
                               data,                                  quotes
                               unspecified                            

  Decision rule Not described  Not described No          No           Yes
  fixed before                                                        
  the data                                                            

  Price for an  Not published  USD 420,000 a About       Free         To be set
  SME                          year per unit €2,900 a                 
                                             year                     

  EU data       Not found      Claimed       Desktop     n/a          Yes (Bedrock
  residency                    (vendor)                               EU route)
  ----------------------------------------------------------------------------------

All \[inference\] from E1 and the inventory. The defensible position:
one-off, high-stakes decisions for Czech and EU small and mid-size
firms, where the evidence has to be assembled from client data, Czech
registers and research, the rule is fixed in advance, and every number
in the report can be traced. The threats are visible already: Workday
now pairs Monte Carlo with scenario audit trails for its customers, and
\@RISK has put an AI agent beside spreadsheet Monte Carlo. Buyer
complaints in the sources point the same way: decisions made in "shadow
spreadsheets" (Workday's framing), opaque calculations (@RISK reviews)
and cost for small teams (Cloverpop) --- all vendor or secondary
evidence.

### E summary

  ------------------------------------------------------------------------
  §2 component            Verdict          Why
  ----------------------- ---------------- -------------------------------
  Admitted claims and a   Keep: it is the  No vendor read offers
  graded ledger behind    differentiator   number-level provenance.
  every number                             

  Deep Research with      Keep: it is the  No vendor read offers sourced
  verbatim quotes         differentiator   external research.

  Pre-registered decision Keep and make    Not described by any vendor
  rule                    prominent        read.

  Monte Carlo and         Build (ADR 0044) Now table stakes in FP&A
  scenarios                                suites.

  Uncertainty format      Extend           Consider SIPmath 3.0 export so
                                           clients can reuse AIA's trials
                                           in their own tools.
  ------------------------------------------------------------------------

## Sociomapa systémů method recommendation

Ship it first as a scenario-sensitivity map and an expert objects ×
properties map. Ship the observation-matrix map on real periods or units
only after it passes a synthetic validation that recovers known
structure and draws nothing in null worlds. Everything in this section
is \[inference\] built on section A, unless a source is named.

### Four modes, four claims

  ---------------------------------------------------------------------------
  Mode          Rows            A relation     It may claim      Grade
                                means                            
  ------------- --------------- -------------- ----------------- ------------
  Scenario map  The client      Outputs        "In this model,  MODELLED
                model's Monte  co-move inside under these       
                Carlo scenarios the model      inputs, A and B   
                (≥ 800)                        move together"   

  Unit map      Comparable      Variables      Association       ESTIMATED
                units:          co-vary across across units,     
                branches, SKUs, units          with an interval  
                customers                                        

  Period map    24--36 months   Variables      Weak association  ESTIMATED;
                                co-move over   at a stated time  edges that
                                time after     scale             fail are not
                                detrending                       drawn

  Expert map    Options or      Similar scored The scorers'     MODELLED,
  (objects ×    competitors     profiles       judgement, named  inputs
  properties)   scored on                                        stated by a
                criteria by                                      person
                people                                           
  ---------------------------------------------------------------------------

### Each step

  ---------------------------------------------------------------------------
  Step          Keep or       Preprocessing              Credibility test
                change                                   
  ------------- ------------- -------------------------- --------------------
  Input matrix  Change        Declared per variable:     Report the
                              unit, transformation (log, transformation
                              log-ratio for shares),     beside every
                              detrend or difference,     relation
                              deseasonalise when two or  
                              more cycles exist; robust  
                              standardisation            

  Relation      Change        Pearson on transformed     Choose the statistic
  statistic                   series, or a skipped       before seeing
                              correlation where outliers results
                              are flagged (Pernet 2013)  

  Baseline      Replace       Per-variable surrogates    Surrogates must
                              (IAAFT, independent        reproduce each
                              phases) after detrending;  series'
                              for scenarios, the imposed autocorrelation
                              input correlation          (Kugiumtzis 1999)

  Pair floors   Replace       Effective-sample-size      Suppress relations
                              floor from an              below the floor
                              autocorrelation-adjusted   
                              formula                    

  Multiple      Replace       Benjamini-Yekutieli by     Report q and the
  testing                     default;                   method
                              resampling-calibrated FDR  
                              if the methodology lead    
                              approves it                

  Sparse design Keep          ---                        ---

  Layout        Keep          ---                        Stress-1 and stress
                                                         per point against a
                                                         random-data
                                                         benchmark and a
                                                         permutation test
                                                         (smacof)

  Split-half    Replace       ---                        Block bootstrap of
                                                         rows (block length
                                                         declared);
                                                         Procrustes-aligned
                                                         displacement per
                                                         object

  Placement and Change        Periods drawn as a         Placement stability
  density                     trajectory; units placed,  under the same
                              density above a stated n   bootstrap

  Segments      Change        Regimes only from a        None without a
                              declared break or an       declared break
                              explicit model             

  Terrain       Keep          Height = one chosen        Labelled as
                              outcome                    interpolation

  Determinism   Keep          Seeds and PCG64 streams    Re-run gives an
                              recorded per run           identical map
  ---------------------------------------------------------------------------

### Never claim

-   That a relation is causal, or that one variable drives another.

-   That a scenario map shows how the market or the firm behaves.

-   That a structure is real unless it beats its surrogate null after
    FDR and survives resampling.

-   That distances between objects are effect sizes in any unit.

-   That terrain heights between observed points are estimates.

-   Regimes from 24--36 months without a declared break.

-   Validity on the strength of Sociomapping's team-communication
    evidence, which does not cover this use (A5).

### Validation plan on synthetic data with known structure

Each generator runs for 1,000 seeded replicates at T or n of 24, 36, 60
and 120, and its fixtures are pinned by SHA-256 like F1--F9.

1.  **Null worlds.** Independent random walks (Granger-Newbold's case),
    independent AR(1) series at ρ = 0.3, 0.7 and 0.95, and seasonal
    series with no cross-relation. Pass: the share of replicates with
    any false edge stays at or below the nominal FDR.

2.  **Known factors.** Twelve KPIs from three latent factors plus AR(1)
    noise and trends. Pass: cluster recovery (adjusted Rand index) and
    edge precision and recall against the true correlations, reported as
    a curve over T.

3.  **Known sparse network.** A sparse VAR(1), as in NETS's
    simulations. Records which contemporaneous links the map finds and
    which lagged links it cannot see.

4.  **Contamination.** 10% of rows replaced by outliers (Pernet's
    design) and one level shift. Pass: robust statistics keep precision
    within a stated tolerance.

5.  **Compositional shares.** Shares that sum to one. Pass: no spurious
    negative edges after log-ratio transformation.

6.  **Units.** 40 branches × 10 drivers with planted clusters and
    unequal noise.

7.  **Scenarios.** 800 × 7 options from a cost model with a known
    Iman-Conover input correlation. Pass: the map's output correlations
    match the analytically computed ones within Monte Carlo error, and
    its strongest relations agree with Sobol or PRCC rankings.

The three datasets the brief names (36 × 12, 40 × 10, 800 × 7) fit
generators 2, 6 and 7; the spike should be re-run with planted ground
truth and null worlds, and its script committed. The pass thresholds are
a decision for the methodology lead (Questions, below).

## Deep Research v2 spec

Build structured routes and typed numeric extraction first: they turn
research into model inputs, and both are mostly code that already has a
pattern in the repository. The six-step pipeline, the gate and the
verbatim rule stay; every capability below is a new gate route, a new
step or a new purpose. The ranking and the effort estimates are
\[inference\]; each target cites the evidence in B.

  ------------------------------------------------------------------------------------------------------------
  Rank   Capability      Where it goes      Value          Effort         Measurable       Test
                                                                          target           
  ------ --------------- ------------------ -------------- -------------- ---------------- -------------------
  1      Structured      New gate routes:   High           Low--medium:   100% of admitted Recorded doubles of
         registers and   SDMX (Eurostat,                   four           series values    each API, golden
         statistical     ECB), ČSÚ                         connectors     byte-equal to    responses pinned by
         series          DataStat, ČNB,                    exist          the API          hash
                         GLEIF, TED, both                                 response;        
                         ISVZ series;                                     query-proposal   
                         extend ARES. The                                 accuracy         
                         model proposes a                                 measured on a    
                         query key; code                                  labelled set     
                         fetches.                                         (LoTuS reached   
                                                                          0.59 on harder   
                                                                          text-to-SQL)     

  2      Numeric         New step between   High           Medium         Value + unit F1  300+ labelled
         extraction into verify and                                       ≥ 0.90 on a      sentences from
         typed inputs    synthesize; a                                    Czech labelled   annual reports, ČSÚ
         (value, unit,   rule-based                                       set before use   releases and price
         period, range,  extractor in code;                               (CQE reached     lists, two
         source,         the model proposes                               85.6 on English  annotators
         licence)        concept and period                               news; few-shot   
                         only; a person                                   GPT-3 59.1)      
                         accepts                                                           

  3      Citation        Extend the verify  High           Low            Citation         Calibrate the judge
         precision and   step: DeepTRACE's                               accuracy ≥ 90%,  on 100
         recall          citation accuracy                                unsupported      human-labelled
                         and thoroughness,                                statements \<    statement--source
                         plus a link-health                               10%,             pairs; report kappa
                         check                                            thoroughness ≥   
                                                                          50%              
                                                                          (DeepTRACE's    
                                                                          "acceptable"   
                                                                          bands)           

  4      Source          Extend the         Medium--high   Low            100% of admitted Table fixtures; a
         credibility v2  declared                                         sources carry a  test that a
                         class/score                                      class or         model-proposed
                         tables: (source,                                 "unknown"; no  score is refused
                         claim type) keys,                                score set by a   
                         Code-of-Practice                                 model            
                         checklist for                                                     
                         statistics, review                                                
                         date and 4-year                                                   
                         stale flag                                                        

  5      Triangulation   Extend merge and   High           Medium         Macro-F1 on a    Seeded
         and             verify: decompose                                labelled Czech   contradictions in
         contradiction   each numeric claim                               set of supported recorded sources
                         into                                             / refuted /      
                         sub-questions;                                   conflicting      
                         record agreement                                 claims           
                         or contradiction                                 (QuanTemp's     
                         per typed input; a                               best is 58.32,   
                         person resolves                                  so expect to     
                         contradictions                                   need a person)   

  6      As-of-date      New route: Memento Medium         Medium         100% of admitted Recorded TimeGate
         research        TimeGate and                                     archive findings answers, including
                         Wayback CDX beside                               carry the        a request before
                         the Common Crawl                                 capture's own   the first capture
                         index; new purpose                               datetime within  (RFC 7089 returns
                         "as of"                                        a declared       the first)
                                                                          tolerance of the 
                                                                          requested date   

  7      Scheduled       New purpose plus a Medium         Medium         No missed        Replay of captured
         monitoring and  schedule: poll                                   release on       page and series
         change alerts   structured series                                series that      versions
                         by their own                                     publish update   
                         update annotations                               stamps; false    
                         (Eurostat                                        alerts on        
                         UPDATE_DATA); poll                               unchanged values 
                         pages at an                                      below a stated   
                         estimated change                                 rate             
                         rate; alert only                                                  
                         when an extracted                                                 
                         value changes                                                     

  8      Precedents and  New purpose:       Medium         High           Recall@50 on a   Curated set of
         case outcomes   candidates only,                                 curated set; no  known precedents
                         confirmed by a                                   outcome          per decision type
                         person                                           prediction       
                                                                          offered (COLIEE  
                                                                          2025's best     
                                                                          retrieval F1 was 
                                                                          0.34)            
  ------------------------------------------------------------------------------------------------------------

The gate itself needs three additions before routes 1 and 6 go live:
per-source rate limits (ARES's 500 a minute), a robots.txt and
TDM-reservation check before any fetch for mining, and a retention limit
on mined copies (C2).

## Data source register

Every public source here is free to read, and all but VIES and NEN's
login-only data can lawfully feed a model; four have a working connector
in AIA today, and a fifth (procurement) only records. Legal status
follows C2--C3; "open" means lawful reuse with attribution. Families:
**F** finance, **A** accounting, **O** operations, **M** market sizing.

  ----------------------------------------------------------------------------------------------------------
  Source                Legal status           Cost                  Families        AIA connector today
  --------------------- ---------------------- --------------------- --------------- -----------------------
  ARES                  Open; no database      Free                  M (firm counts  ares-subject-1
                        right (official work);                       by NACE), O     
                        GDPR for named natural                       (counterparty   
                        persons; block above                         checks)         
                        500 queries a minute                                         

  Commercial register   Open data; official    Free                  M, O            None
  (dataor.justice.cz)   work                                                         

  Sbírka listin         Official work, but not Free to read;         A, F (peer      None
  (financial            in the open-data       extraction costs      benchmarks)     
  statements)           obligation; PDF or     effort                                
                        XHTML only                                                   

  ČÚZK REST API-KN      Free under its terms   Free                  O (sites,       None
                        after registration;                          warehouses)     
                        parcels are a                                                
                        high-value dataset                                           

  ČÚZK WSDP and remote  Paid, verified outputs Per output, e.g. 100  O, F (property  None
  access                                       Kč per title-deed     values)         
                                               extract                               
                                               (verifier-reported)                   

  ISVZ procurement open Open                   Free                  M (public       isvz-notice-1, recorded
  data                                                               demand), O      only
                                                                     (price          
                                                                     benchmarks)     

  NEN data behind login Not to be disclosed    ---                   ---             Do not collect
                        (MMR's stated                                               
                        position)                                                    

  EU TED                Open, anonymous        Free                  M, O            None

  ČNB rates (fixing,    Open; ČNB restricts    Free                  F               None
  ARAD)                 excessive automated                                          
                        access                                                       

  ECB Data Portal       Free API; reuse terms  Free                  F               None
                        not read                                                     

  Eurostat              Open for commercial    Free                  M, O            eurostat-statistics-1
                        reuse with                                                   
                        acknowledgement, with                                        
                        listed exceptions                                            

  ČSÚ DataStat          CC BY 4.0; derived     Free                  M, O, F         csu-datastat-1
                        data labelled                                                

  NKOD and              Licence per dataset,   Free                  M (discovery)   nkod-sparql-1 (NKOD
  data.europa.eu        some non-commercial                                          only)

  GLEIF                 Licence not confirmed  Free                  F, A (entity    None
                        in this research                             and ownership   
                                                                     matching)       

  VIES                  Reuse and              Free                  O (one-off      Never store results
                        retransmission                               validation      
                        forbidden                                    only)           

  Merk                  Commercial contract    Not published; 7-day  F, A, M         None
                                               trial                                 

  Cribis (CRIF),        Commercial contract    Not found             F, A, M         None
  MagnusWeb (D&B),                                                                   
  Orbis (Moody's),                                                                  
  Creditinfo                                                                         

  Licensed Czech panel  Depends on its         Sunk                  M at most, as   Frozen
  (frozen)              licence; GDPR if                             ESTIMATED       
                        pseudonymised                                                
  ----------------------------------------------------------------------------------------------------------

## Questions for the methodology lead

Ten statistical decisions only the methodology owner should make. Each
recommendation is \[inference\] from the section cited.

  --------------------------------------------------------------------------------
  \#    Decision                Options                 Recommendation
  ----- ----------------------- ----------------------- --------------------------
  1     Multiple-testing        \(a\)                   \(b\) now. Evaluate (c) on
        control on maps (A1)    Benjamini-Hochberg; (b) the synthetic suite before
                                Benjamini-Yekutieli;    switching; (a) has no
                                (c) FDR calibrated by   guarantee for two-sided
                                block resampling; (d)   correlation tests.
                                Cai & Liu's bootstrap  
                                test for correlation    
                                matrices                

  2     Levels or changes for   \(a\) Difference or     (c), labelled by time
        trending KPIs (A2)      prewhiten; (b) keep     scale, with (a) as the
                                levels and adjust       default edge set:
                                degrees of freedom; (c) differencing controls
                                show both               false positives, but loses
                                                        power when slow processes
                                                        drive co-movement.

  3     Effective-sample-size   \(a\) Bartlett /        (b), with the floor set
        formula and floor (A1)  Bayley-Hammersley; (b)  from the synthetic power
                                Pyper & Peterman's     curves, not fixed in
                                modified version; the   advance.
                                floor's value          

  4     Credibility resampling  \(a\) Moving block; (b) (b), plus (c) below 48
        for 24--36 rows (A4)    stationary bootstrap    rows: the automatic rules
                                with automatic block    were shown only at N = 200
                                length; (c) report      and 800.
                                stability only, no      
                                intervals, below a      
                                minimum length          

  5     Surrogate null (A4)     \(a\) Phase             \(b\) per variable, after
                                randomisation; (b)      detrending and
                                IAAFT; (c) block        deseasonalising, with a
                                permutation             check that the surrogates
                                                        reproduce each series'
                                                        autocorrelation.

  6     Relation statistic (A2) \(a\) Pearson on        \(a\) by default and (c)
                                transformed series; (b) where outliers are
                                Spearman; (c) skipped   flagged, both fixed before
                                correlation             results are seen.

  7     Pass thresholds for the Values for false-edge   False-edge rate at or
        synthetic validation    rate, cluster recovery  below the nominal q; the
        suite (method           and layout displacement other two set by the
        recommendation)                                 methodology lead from a
                                                        first run.

  8     Discount rate inside    \(a\) Risk-free rate on One rate declared per
        probabilistic decision  simulated flows; (b)    study and applied to all
        rules (D1)              risk-adjusted rate,     options; report how
                                reading only the        sensitive the verdict is
                                probability of clearing to it; never lower it
                                it; (c) the client's   because the model is
                                WACC                    simulated.

  9     PERT inputs (D1)        \(a\) PERT (beta)       \(b\) where data exist and
                                throughout; (b) fit     (c) always for
                                beta or lognormal to    disagreement; averaging
                                data where data exist;  experts understates
                                (c) mixture sampling    spread.
                                when experts disagree   

  10    Forecast evaluation     \(a\) Held-out MAE; (b) (b), scaled by the
        (D1)                    MASE; (c) RMSSE as in   seasonal naive for
                                M5                      seasonal series; never
                                                        MAPE where zeros occur.
  --------------------------------------------------------------------------------

Two decisions are not statistical but block the methodology work: the
grade vocabulary (CALCULATED and ESTIMATED in ADR 0044 against MEASURED
and CALIBRATED in code), and whether the frozen panel may ever be an
input (its licence, C4).

## How this was researched

About 445 claims from the section runs and about 200 from the gap-fill
agents carry a quote confirmed word for word against the fetched page;
62 of them also passed three adversarial verifiers. Everything else is
labelled inference, verifier-reported or unknown.

-   **Code.** origin/develop at 57c133a was read in a separate worktree.
    Every statement about the code carries a file:line anchor.

-   **Section runs.** One run per section, each with six search angles.
    Each run fetched up to 20 sources and kept a claim only if grep -F
    found its quote in the fetched text. The 15 strongest claims per
    section went to three verifiers with distinct jobs: quote fidelity,
    contradiction, currency and source strength. Two refutations removed
    a claim. Sections D and E were re-verified after a usage limit
    interrupted them.

-   **Gap-fill.** Four agents covered what the cap left out: A3, A5 and
    A6; B3 and B4; the law in C; and the registers in C. Their claims
    are quote-checked, single-pass. I re-checked 19 of their quotes
    against the saved pages, and all matched.

-   **Labels.**

    -   **3-lens:** passed the three verifiers.

    -   **quote:** the quote was confirmed, but the claim was not
        adversarially verified.

    -   **verifier-reported:** a fact a verifier found while checking,
        not itself quote-gated.

    -   **secondary:** not the original publisher.

    -   **\[inference\]:** this analysis's own reasoning.

    -   **Older than 3 years:** flagged where B1 and E ask for it.

  -------------------------------------------------------------------------
  Section     3-lens confirmed      Refuted     Quote-checked claims
  ----------- --------------------- ----------- ---------------------------
  A           14                    1           81

  B           9                     6           110

  C           13                    2           98

  D           15                    0           82

  E           11                    4           74
  -------------------------------------------------------------------------

**Refused or unreachable, and not routed around.** EUR-Lex, Curia,
Gartner, BusinessWire, OpenReview, JSTOR, ScienceDirect, the Mozilla
Foundation, MDPI, Springer (rate limit), the Hlídač státu API,
webarchiv.cz and web.archive.org. One early test loaded EUR-Lex in a
headless browser after a bot challenge, before the rule against that was
in place; nothing cited comes from that fetch.

**Not found.**

-   **D3:** logistics and warehouse benchmarks.

-   **E2:** analyst views and market size; also Czech and CEE
    competitors, and most planning-suite prices.

-   **Methods not researched:** compositional data, regime switching,
    dynamic factor models, Bayesian networks, NOTEARS and system
    dynamics.

-   **Archives:** the Internet Archive's terms and rate limits, and
    Webarchiv's interfaces.

-   **Law:** official texts of the CJEU judgments.

-   **Panel:** the frozen panel's licence.

**Cost.**

  -----------------------------------------------------------------------
  Stage               Subagent tokens    Note
  ------------------- ------------------ --------------------------------
  First attempt       3.9M               Blocked by the network policy

  Five section runs   23.3M              363 agents; 94 failed at the
                                         usage limit

  Resume              Not reported       Re-ran completed work; stopped
                                         after about 32 agents

  Gap-fill            0.8M               

  D and E             7.7M               
  re-verification                        

  **Total**           **About 36M, plus  Against an estimate of about 20M
                      the stopped        
                      resume**           
  -----------------------------------------------------------------------

**Where it lives.** This doc is not in the repository. Under the
repository's own rule ("the repository is the memory"), the pivot
decision and the method changes above should land as an ADR and plan
files before anything is built.

## Bibliography

Every source below was opened between 1 and 2 November 2026; the date
after each is its own publication or update date. Sources only seen as
search snippets are not listed.

**A. Sociomap on business data**

-   Benjamini & Yekutieli, The control of the false discovery rate under
    dependency, Ann. Stat. 2001 ---
    [link](https://projecteuclid.org/journals/annals-of-statistics/volume-29/issue-4/The-control-of-the-false-discovery-rate-in-multiple-testing/10.1214/aos/1013699998.pdf)

-   Cai & Liu, Large-scale multiple testing of correlations, JASA 2016
    --- [link](https://pmc.ncbi.nlm.nih.gov/articles/PMC4894362)

-   Ebisuzaki, significance of correlation with serially correlated
    data, J. Climate 1997 ---
    [link](https://doi.org/10.1175/1520-0442(1997)010<2147:AMTETS>2.0.CO;2)

-   Kugiumtzis, test for nonlinearity with surrogates, Phys. Rev. E 1999
    --- [link](https://arxiv.org/pdf/physics/9905021)

-   Pyper & Peterman, correlation with autocorrelated time series, CJFAS
    1998 --- [link](https://doi.org/10.1139/f98-104)

-   Granger & Newbold, Spurious regressions in econometrics, J.
    Econometrics 1974 ---
    [link](https://gwern.net/doc/economics/1974-granger.pdf)

-   Ernst, Shepp & Wyner, Yule's nonsense correlation, Ann. Stat. 2017
    --- [link](https://projecteuclid.org/euclid.aos/1498636874)

-   Künsch, The jackknife and the bootstrap for general stationary
    observations, Ann. Stat. 1989 ---
    [link](https://projecteuclid.org/euclid.aos/1176347265)

-   Patton, Politis & White, correction to automatic block-length
    selection, Econometric Reviews 2009 ---
    [link](https://public.econ.duke.edu/~ap172/Patton_Politis_White_2009.pdf)

-   smacof R package manual, Oct 2026 ---
    [link](https://cran.r-universe.dev/smacof/doc/manual.html)

-   tseries tsbootstrap reference ---
    [link](https://search.r-project.org/CRAN/refmans/tseries/html/tsbootstrap.html)

-   Iman & Conover 1982, bibliographic record ---
    [link](https://ftp.math.utah.edu/pub/tex/bib/idx/communstatsimulcomput1980/11/3/311-334.html)

-   Helton et al., SAND2006-5557, Sandia 2006 ---
    [link](https://www.osti.gov/servlets/purl/897617)

-   Surrogate data testing, Wikipedia, Oct 2025 (secondary) ---
    [link](https://en.wikipedia.org/wiki/Surrogate_data_testing)

-   Friedman, Hastie & Tibshirani, graphical lasso, Biostatistics 2008
    --- [link](https://pmc.ncbi.nlm.nih.gov/articles/PMC3019769)

-   Barigozzi & Brownlees, NETS, J. Applied Econometrics 2019 ---
    [link](https://researchonline.lse.ac.uk/id/eprint/90493/3/Barigozzi_et_al_2019_Journal_of_Applied_Econometrics.pdf)

-   Runge et al., PCMCI, Science Advances 2019 ---
    [link](https://elib.dlr.de/131630/1/Runge_ScienceAdvances_2019.pdf)

-   Pernet, Wilcox & Rousselet, Robust correlation analyses, Front.
    Psychol. 2013 ---
    [link](https://pmc.ncbi.nlm.nih.gov/articles/PMC3541537)

-   Ishizaka & Siraj, AHP, SMART and MACBETH compared, EJOR 2018 ---
    [link](https://eprints.whiterose.ac.uk/117125/1/1-s2.0-S0377221717304885-main.pdf)

-   Reliabilita a validita sociomapování komunikace, Univerzita Karlova,
    2014 --- [link](https://dspace.cuni.cz/handle/20.500.11956/57021)

-   Diploma thesis on interpreting sociomaps, Univerzita Karlova, 2008
    --- [link](https://dspace.cuni.cz/handle/20.500.11956/17500)

-   Hrbata, Using the Sociomapping Method in Defence Department,
    Vojenské rozhledy 4/2012 ---
    [link](https://www.vojenskerozhledy.cz/artkey/vor-201204-0010_using-the-sociomapping-method-in-defence-department.php)

-   Giusino et al., Team Performance Management 2023 ---
    [link](https://eprints.whiterose.ac.uk/205779/1/10-1108_TPM-11-2022-0077.pdf)

-   Sociomapping, Wikipedia (flagged promotional; secondary) ---
    [link](https://en.wikipedia.org/wiki/Sociomapping)

-   Pšenička, Seznam Zprávy, 17 Feb 2025 ---
    [link](https://www.seznamzpravy.cz/clanek/domaci-kauzy-velke-zakazky-s-nejasnym-smyslem-auditory-v-zalozne-zaujal-specialni-byznys-269849)

**B. Deep Research**

-   Du et al., DeepResearch Bench, arXiv Jun 2025 ---
    [link](https://arxiv.org/pdf/2506.11763)

-   Venkit et al., DeepTRACE, arXiv Sep 2025 (ICLR 2026) ---
    [link](https://arxiv.org/pdf/2509.04499)

-   Chen et al., BrowseComp-Plus, Aug 2025 ---
    [link](https://arxiv.org/abs/2508.06600)

-   Wei et al., BrowseComp, OpenAI, Apr 2025 ---
    [link](https://arxiv.org/pdf/2504.12516)

-   Rao, Wong & Callison-Burch, URL hallucination, arXiv Apr 2026 ---
    [link](https://arxiv.org/pdf/2604.03173)

-   Analytics India Magazine, Google deep research agent, Dec 2025
    (secondary) ---
    [link](https://analyticsindiamag.com/ai-news-updates/googles-new-deep-research-agent-scores-sota-results-on-benchmarks)

-   QuanTemp, SIGIR 2024 --- [link](https://arxiv.org/abs/2403.17169)

-   CQE quantity extraction, EMNLP 2023 ---
    [link](https://aclanthology.org/2023.emnlp-main.793)

-   ALCE, EMNLP 2023 (older than 3 years) ---
    [link](https://arxiv.org/abs/2305.14627)

-   CiteEval, ACL 2025 --- [link](https://arxiv.org/abs/2506.01829)

-   FEVER, NAACL 2018 (older than 3 years) ---
    [link](https://aclanthology.org/N18-1074/)

-   Eurostat SDMX 2.1 API guide ---
    [link](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-getting-started/sdmx2.1)

-   IMF, StatGPT, Mar 2026 ---
    [link](https://bookstore.imf.org/books/statgpt-ai-for-official-statistics)

-   NOWJ at COLIEE 2025, Sep 2025 ---
    [link](https://arxiv.org/abs/2509.08025)

-   LoTuS, DBDBD 2025 ---
    [link](https://dbdbd2025.uantwerpen.be/wp-content/uploads/2025/12/dbdbd25_29.pdf)

-   Thiry, Manolescu & Liberti, SDMX question answering, 2020 (older
    than 3 years) ---
    [link](https://researchportal.ip-paris.fr/fr/publications/a-question-answering-system-for-interacting-with-sdmx-databases/)

-   Web change detection survey, ACM CSUR 2020 (older than 3 years) ---
    [link](https://arxiv.org/abs/1901.02660)

-   RFC 7089, Memento, 2013 (older than 3 years) ---
    [link](https://www.rfc-editor.org/rfc/rfc7089)

-   Common Crawl coverage audit, WAC 2026 ---
    [link](https://aclanthology.org/2026.wac-1.21/)

-   Lin et al., news domain quality ratings, PNAS Nexus 2023 (older than
    3 years) ---
    [link](https://pmc.ncbi.nlm.nih.gov/articles/PMC10500312/)

-   NewsGuard rating criteria, Apr 2026 ---
    [link](https://www.newsguardtech.com/ratings/rating-process-criteria/)

-   Wikipedia: Reliable sources/Perennial sources, Oct 2026 ---
    [link](https://en.wikipedia.org/wiki/Wikipedia:Reliable_sources/Perennial_sources)

-   European Statistics Code of Practice, 2017 edition ---
    [page](https://ec.europa.eu/eurostat/web/quality/european-quality-standards/european-statistics-code-of-practice),
    [PDF](https://ec.europa.eu/eurostat/documents/4031688/8971242/KS-02-18-142-EN-N.pdf)

-   Yang & Menczer, LLM credibility ratings, WebSci 2025 ---
    [link](https://arxiv.org/abs/2304.00228v3)

-   Common Crawl terms of use, Mar 2024 ---
    [link](https://commoncrawl.org/terms-of-use); CCBot ---
    [link](https://commoncrawl.org/ccbot); crawl statistics ---
    [size](https://commoncrawl.github.io/cc-crawl-statistics/plots/crawlsize/monthly.csv),
    [languages](https://commoncrawl.github.io/cc-crawl-statistics/plots/languages)

-   Webarchiv, Wikipedia (secondary) ---
    [link](https://en.wikipedia.org/wiki/Webarchiv)

**C. Data sources and law**

-   ČÚZK: free provision (2020) ---
    [link](https://cuzk.gov.cz/Katastr-nemovitosti/Poskytovani-udaju-z-KN/Informace-o-bezuplatnem-poskytovani-udaju-katastru.aspx);
    remote access, Apr 2026 ---
    [link](https://cuzk.gov.cz/aplikace-dp/zakladni-informace); ZÚ
    terms, Mar 2026 ---
    [link](https://geoportal.cuzk.gov.cz/Dokumenty/Podminky_EN.pdf)

-   ARES: developer information ---
    [link](https://ares.gov.cz/stranky/vyvojar-info); operating
    conditions --- [link](https://ares.gov.cz/stranky/podminky-provozu);
    open data --- [link](https://ares.gov.cz/stranky/otevrena-data); MF
    page, Aug 2026 ---
    [link](https://mf.gov.cz/cs/ministerstvo/informacni-systemy/ares)

-   Public registers open data ---
    [dataor.justice.cz](https://dataor.justice.cz/); Advokátní deník,
    Mar 2019 (secondary) ---
    [link](https://advokatnidenik.cz/2019/03/26/otevrena-data-verejnych-rejstriku-budou-jiz-brzy-v-plnem-provozu/);
    Pohoda on filing statements, Sep 2024 (secondary) ---
    [link](https://portal.pohoda.cz/dane-ucetnictvi-mzdy/ucetnictvi/vkladani-ucetni-zaverky-do-sbirky-listin/);
    ČT24, Jan 2019 (secondary) ---
    [link](https://ct24.ceskatelevize.cz/clanek/domaci/pres-290-tisic-firem-nezverejnuje-sve-hospodareni-novela-zakona-ma-zavest-tvrde-postihy-69087)

-   Procurement: MMR reply MMR-20211/2026-31, Mar 2026 ---
    [link](https://mmr.gov.cz/getmedia/e42bc7d7-d766-40de-9582-915d922a5529/MMR-20211-2026-31-ze-dne-14-3-2026.pdf.aspx?ext=.pdf);
    TED API ---
    [link](https://docs.ted.europa.eu/api/latest/index.html); TED
    re-users Q&A, Jun 2023 ---
    [link](https://op.europa.eu/en/web/ted-reusers-workshops/questions-and-answers1);
    TED re-users minutes, Sep 2022 ---
    [link](https://op.europa.eu/el/web/reusers-ted-2022/minutes);
    Dataharvest 2020 slides ---
    [link](https://dataharvest.eu/wp-content/uploads/2020/09/Health_Dataharvest-2020_Tenders_Cruz-TED.pdf)

-   ČNB: exchange-rate FAQ ---
    [link](https://www.cnb.cz/cs/casto-kladene-dotazy/Kurzy-devizoveho-trhu-na-www-strankach-CNB);
    ARAD methodology ---
    [link](https://www.cnb.cz/docs/ARADY/MET_LIST/kurzy_cs.pdf)

-   ECB Data Portal API ---
    [overview](https://data.ecb.europa.eu/help/api/overview),
    [tips](https://data.ecb.europa.eu/help/api/useful-tips)

-   Eurostat copyright and licence policy ---
    [link](https://ec.europa.eu/eurostat/help/copyright-notice),
    [link](https://ec.europa.eu/eurostat/statistics-explained/index.php/Copyright/licence_policy)

-   GLEIF API --- [link](https://www.gleif.org/en/lei-data/gleif-api)

-   VIES --- [technical
    information](https://ec.europa.eu/taxation_customs/vies/#/technical-information),
    [disclaimer](https://ec.europa.eu/taxation_customs/vies/#/disclaimer),
    [FAQ](https://ec.europa.eu/taxation_customs/vies/#/faq)

-   ČSÚ: DataStat release, Sep 2026 ---
    [link](https://csu.gov.cz/produkty/csu-predstavuje-novou-verzi-datastatu-pro-prehlednejsi-praci-se-statistickymi-daty);
    API guide, Apr 2025 ---
    [link](https://csu.gov.cz/zakladni-informace-pro-pouziti-api-datastatu);
    conditions of use, Aug 2026 ---
    [link](https://csu.gov.cz/conditions_for_use_and_further_dissemination)

-   data.europa.eu --- [API
    documentation](https://dataeuropa.gitlab.io/data-provider-manual/api-documentation/),
    [FAQ](https://data.europa.eu/en/faq)

-   Merk --- [API documentation](https://api.merk.cz/docs/), [data
    packages](https://www.merk.cz/datove-balicky/); VŠE library on
    Cribis, Jan 2026 (secondary) ---
    [link](https://library.vse.cz/news/cribis-new-available-database-for-company-data-at-prague-university-of-economics-and-business/)

-   Directive 96/9/EC Art. 7 ---
    [link](https://www.legislation.gov.uk/eudr/1996/9/article/7/adopted);
    Directive 2019/790 Arts. 3 and 4 --- [Art.
    3](https://www.legislation.gov.uk/eudr/2019/790/article/3/adopted),
    [Art.
    4](https://www.legislation.gov.uk/eudr/2019/790/article/4/adopted);
    GDPR Art. 14 ---
    [link](https://www.legislation.gov.uk/eur/2016/679/article/14/adopted)
    (official texts as adopted, UK National Archives host)

-   Act 121/2000 Sb. ---
    [link](https://www.zakonyprolidi.cz/cs/2000-121); Act 106/1999 Sb.
    --- [link](https://www.zakonyprolidi.cz/cs/1999-106) (consolidated,
    secondary host)

-   Commission Implementing Regulation (EU) 2023/138 ---
    [link](https://iho.int/uploads/user/Inter-Regional%20Coordination/IENWG%20and%20EC%20-%20IHO%20Cooperation/IENWG13/IENWG13_2023_03B_Commission_Implementing_Regulation_21122022.pdf);
    data.europa.eu on high-value datasets, Apr 2026 ---
    [link](https://data.europa.eu/en/news-events/news/high-value-datasets-what-has-changed-and-what-will-come-next)

-   BHB v William Hill, quoted in \[2005\] EWCA Civ 863 ---
    [link](https://caselaw.nationalarchives.gov.uk/ewca/civ/2005/863);
    CV-Online v Melons, Husovec & Derclaye, Jun 2021 ---
    [link](https://legalblogs.wolterskluwer.com/copyright-blog/access-to-information-and-competition-concerns-enter-the-sui-generis-rights-infringement-test-the-cjeu-redefines-the-database-right/);
    Ryanair v PR Aviation, IPKat, Jan 2015 ---
    [link](https://ipkitten.blogspot.com/2015/01/breaking-cjeu-says-that-owner-of-online.html);
    WM and Sovim, eucrim ---
    [link](https://eucrim.eu/news/cjeu-no-unrestricted-access-to-data-of-beneficial-owners/);
    Kneschke v LAION, Dec 2025 ---
    [link](https://www.technologyslegaledge.com/2025/12/robert-kneschke-v-laion-judgment-of-10-december-2025-ref-5-u-104-24/)

-   Smítal, commercial use of public databases, Oct 2023 ---
    [link](https://pravniprostor.cz/clanky/obcanske-pravo/uzivani-verejne-dostupnych-databazi-ke-komercnim-ucelum);
    Menčík, TDM in Czech law, Oct 2024 ---
    [link](https://www.epravo.cz/top/aktualne/vytezovani-verejne-dostupnych-autorskych-del-pro-ucely-trenovani-umele-inteligence-118625.html);
    further processing of public personal data, Mar 2020 ---
    [link](https://www.epravo.cz/top/clanky/dalsi-zpracovani-osobnich-udaju-zverejnenych-organy-verejne-moci-110749.html)

-   ÚOOÚ order UOOU-04153/20-4, Sep 2020 ---
    [link](https://uoou.gov.cz/media/poskytnute-informace/2025/1292025/prikaz-cj-uoou-0415320-4.pdf);
    WP29 Opinion 05/2014 on anonymisation ---
    [link](https://ec.europa.eu/justice/article-29/documentation/opinion-recommendation/files/2014/wp216_en.pdf)

**D. Modelling**

-   Damodaran, valuation session 20, 2015 (secondary) ---
    [link](https://pages.stern.nyu.edu/~adamodar/podcasts/valfall15/valsession20.pdf)

-   Wall, Distributions and correlations in Monte Carlo simulation, CME
    1997 ---
    [link](https://ideas.repec.org/a/taf/conmgt/v15y1997i3p241-258.html)

-   (Mis)use of Monte Carlo simulations in NPV analysis, SME 1996
    (abstract) ---
    [link](https://onemine.org/documents/-mis-use-of-monte-carlo-simulations-in-npv-analysis)

-   Vose, Determining the NPV of a capital investment (blog) ---
    [link](https://riskwiki.vosesoftware.com/DeterminingtheNPVofacapitalinvestment.php)

-   Kaplan, Rethinking activity-based costing, HBS Working Knowledge
    2005 ---
    [link](https://hbswk.hbs.edu/item/rethinking-activity-based-costing)

-   Decree 500/2002 Sb. ---
    [link](https://esipa.cz/sbirka/sbsrv.dll/sb?CP=2002s500&DR=SB)

-   Everaert, Bruggeman & De Creus, Sanac case, J. Accounting Education
    2008 ---
    [link](https://econpapers.repec.org/RePEc:eee:joaced:v:26:y:2008:i:3:p:118-154)

-   Makridakis, Spiliotis & Assimakopoulos, M5 accuracy competition
    (preprint 2020; IJF 2022) ---
    [preprint](https://statmodeling.stat.columbia.edu/wp-content/uploads/2021/10/M5_accuracy_competition.pdf),
    [record](https://econpapers.repec.org/RePEc:eee:intfor:v:38:y:2022:i:4:p:1346-1364);
    M5 uncertainty record ---
    [link](https://fds.duke.edu/db/aas/stat/faculty/bob.winkler/publications/361214)

-   Hyndman & Koehler, Another look at measures of forecast accuracy,
    IJF 2006 ---
    [link](https://www.doi.org/10.1016/J.IJFORECAST.2006.03.001)

-   Makridakis Competitions, Wikipedia (secondary) ---
    [link](https://en.wikipedia.com/wiki/Makridakis_Competitions)

-   Factory Physics, Calculating safety stock correctly, 2020 (blog) ---
    [link](https://factoryphysics.com/inventory-part-ii-calculating-safety-stock-correctly)

-   Eurostat Prodcom metadata, Sep 2026 ---
    [link](https://ec.europa.eu/eurostat/cache/metadata/EN/prom_esms.htm);
    Prodcom DS-059367 quick guide, Oct 2026 ---
    [link](https://ec.europa.eu/eurostat/documents/d/prodcom/quick-guide-on-accessing-prodcom-data-ds-059367)

**E. Competitors**

-   Aera Decision Cloud, AWS Marketplace ---
    [link](https://aws.amazon.com/marketplace/pp/prodview-2eleg2lr5dcuk)

-   RFP.Wiki, Aera vs Cloverpop, Oct 2026 (secondary) ---
    [link](https://www.rfp.wiki/artificial-intelligence/decision-intelligence-platforms/aera-technology/cloverpop)

-   Horizont on Cloverpop, Oct 2015 (secondary, older than 3 years) ---
    [link](https://www.horizont.net/marketing/nachrichten/Cloverpop-Dieses-Tool-soll-Managern-helfen-die-richtige-Entscheidung-zu-treffen-136809)

-   Workday, Adaptive Decision Intelligence, May 2026 ---
    [link](https://newsroom.workday.com/2026-05-27-Workday-Introduces-Adaptive-Decision-Intelligence,-Bringing-Planning-Questions,-Scenarios,-and-Decisions-Into-One-AI-Experience);
    Adaptive from Workday, Sep 2026 ---
    [link](https://blog.workday.com/en-us/adaptive-workday-new-era-decision-intelligence.html)

-   HiBob acquires Mosaic, FF News, Feb 2025 (secondary) ---
    [link](https://ffnews.com/newsarticle/fintech/hibob-acquires-financial-planning-and-analysis-platform-mosaic-expanding-capabilities-to-empower-people-first-cfos/)

-   Pigment, Anaplan vs Pigment, Jan 2026 (vendor) ---
    [link](https://www.pigment.com/compare/anaplan-vs-pigment)

-   Causal joins the Lucanet group (now redirects to Lucanet xP&A) ---
    [link](https://causal.app/blog/causal-joins-the-lucanet-group)

-   Vose, \@RISK pricing and alternatives, Oct 2026 (competitor) ---
    [link](https://www.vosesoftware.com/Articles/At-RISK-Pricing-and-Alternatives.php)

-   Capterra, \@RISK, Oct 2026 (secondary) ---
    [link](https://www.capterra.com/p/59453/RISK/)

-   Lumivero \@RISK --- [link](https://lumivero.com/products/atrisk/)

-   ProbabilityManagement.org, SIPmath 3.0, Sep 2021 (older than 3
    years) ---
    [link](https://probabilitymanagement.org/blog/2021/9/6/the-sipmath-30-standard-and-analytic-solver-v20215);
    Probability Power Grid, Jan 2026 ---
    [link](https://www.probabilitymanagement.org/probability-power-grid-2026)

**Repository (read at origin/develop 57c133a)**

-   CLAUDE.md; docs/architecture/adr/0010, 0017, 0021--0024, 0038, 0044,
    0045; docs/architecture/deep-research-connectors.md;
    docs/architecture/deep-research-common-crawl.md; .planning/plans/
    (cost-model-study, quantitative-families, deep-research-web-search,
    client-data-in-analysis, lead-orchestration, working-copy-edit-ops);
    prototypes/research-stages/README.md; code anchors as cited in
    "Where the brief and the code differ".
