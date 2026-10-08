#!/usr/bin/env bash
#
# Lightweight layering enforcement for AIA.
#
# One rule here per rule stated in ARCHITECTURE.md. Deliberately grep-level: no
# AST, no dependency-graph tool, nothing to install. A checker that needs its own
# toolchain gets disabled the first time that toolchain breaks, and then the
# layering rots silently -- which is the failure this file exists to prevent.
#
# Exit 0 = every rule passes. Run it before every commit; CI runs it blocking.
#
# Adding a rule: state it under Doc follow-up (the docs PR adds it to ARCHITECTURE.md), then add one `forbid` line
# here. Rules are a ratchet -- each one is added only once it already passes, so
# this script is green from the day it lands and a red run always means a
# regression rather than a backlog.
#
# Exemptions are named, never silent. Every `--exclude` below carries a comment
# saying why the file is allowed the thing the rule forbids. Pretending an
# exception does not exist is what kills these scripts.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

FAILED=0
PASSED=0

# forbid <rule-name> <pattern> <path> [excluded-basename ...]
forbid() {
  local rule="$1" pattern="$2" path="$3"; shift 3
  local excludes=(--exclude-dir=node_modules --exclude-dir=.next
                  --exclude-dir=__pycache__ --exclude-dir=.venv)
  while [ $# -gt 0 ]; do excludes+=(--exclude="$1"); shift; done

  if [ ! -e "$path" ]; then
    printf 'skip  %s\n      (path %s does not exist yet)\n' "$rule" "$path"
    return 0
  fi

  local hits
  hits=$(grep -rn "${excludes[@]}" -E "$pattern" "$path" 2>/dev/null || true)

  if [ -n "$hits" ]; then
    printf 'FAIL  %s\n' "$rule"
    printf '%s\n' "$hits" | sed 's/^/      /'
    FAILED=1
  else
    printf 'ok    %s\n' "$rule"
    PASSED=$((PASSED + 1))
  fi
}

CORE=packages/aia_core/src/aia_core
API=apps/api/src/aia_api
WORKER=apps/worker/src/aia_worker
EXECUTORS=apps/executors/src/aia_executors

echo "Layer rules (ARCHITECTURE.md §3)"
echo

# --- Layer 1: the domain is pure -------------------------------------------
#
# The domain layer is importable with nothing installed but Pydantic. That is
# what makes its tests total and instant, and it is the property that decays
# first if it is not checked: one convenient `from sqlalchemy import ...` and
# the rules can no longer be tested without a database.

forbid "domain imports no framework, driver or SDK" \
  '^\s*(from|import)\s+(sqlalchemy|fastapi|starlette|boto3|botocore|httpx|requests|redis|alembic|psycopg)\b' \
  "$CORE/domain/"

# The report is data in the domain and bytes in infrastructure: a document
# library, an XML toolkit or a plotting stack in the domain would make the
# report's rules untestable without them (.planning/plans/report-docx.md).
forbid "domain imports no document, XML or plotting library" \
  '^\s*(from|import)\s+(docx|lxml|matplotlib|numpy|PIL|pptx|openpyxl)\b' \
  "$CORE/domain/"

forbid "domain does not import outward (application, infrastructure)" \
  '^\s*from\s+(\.\.|aia_core\.)(application|infrastructure)\b' \
  "$CORE/domain/"

# --- Layer 2: application orchestrates, it does not serve HTTP --------------

forbid "application layer knows nothing about HTTP" \
  '^\s*(from|import)\s+(fastapi|starlette)\b' \
  "$CORE/application/"

# --- Layer 3: infrastructure is driven, never driving -----------------------

forbid "infrastructure knows nothing about HTTP" \
  '^\s*(from|import)\s+(fastapi|starlette)\b' \
  "$CORE/infrastructure/"

# The AWS SDK is an optional dependency imported lazily inside S3ArtifactStore,
# so that nothing else in the codebase loads an AWS SDK and the package installs
# without one. A second import site would silently make boto3 mandatory.
# Named exemption (ADR 0010): model_adapters/aws_signing.py imports botocore's
# SigV4 signer and credential chain, lazily and for signing only -- no botocore
# client is built there, so nothing can retry or call Bedrock behind the gateway.
forbid "AWS SDK stays behind the storage adapter and the Bedrock signer" \
  '^\s*(from|import)\s+(boto3|botocore)\b' \
  "$CORE" \
  storage.py aws_signing.py
forbid "no botocore client is built for Bedrock (signing only, ADR 0010)" \
  '(boto3|botocore\.session\.get_session\(\))\.client\(|create_client\(' \
  "$CORE/infrastructure/model_adapters/"

# --- AI runtime: AIA owns the contract, providers sit underneath ------------
#
# ADR 0005 decision A. Model traffic goes through GovernedModelGateway, which
# owns retry, fallback, budget, egress and provenance; the adapters under it
# speak to providers through AIA's own transport protocols. A provider SDK or a
# gateway library imported anywhere else is a second call path that can retry,
# fall back or substitute a model without the gateway deciding to -- which is
# exactly what ADR 0005 exists to prevent. No file is exempt today; a live
# transport built on an SDK will be named here, in model_adapters/, when it lands.
forbid "provider SDKs and gateway libraries are not imported (ADR 0005)" \
  '^\s*(from|import)\s+(anthropic|openai|litellm|langchain[a-z_]*|google\.generativeai|mistralai|cohere)\b' \
  "$CORE"
forbid "the API does not call providers directly" \
  '^\s*(from|import)\s+(anthropic|openai|litellm|langchain[a-z_]*|google\.generativeai|mistralai|cohere)\b' \
  "$API"

# The AI runtime runs in the worker, never in a request (ADR 0016, the Agent
# Runtime Foundation): no HTTP route builds, holds or invokes the gateway, an
# adapter or the fieldwork producer. A model call inside a request would have no
# lease, no reservation and no heartbeat.
forbid "the API never builds or invokes the model gateway or an adapter" \
  '(GovernedModelGateway|model_adapters|aia_executors\.ai_)' \
  "$API"
# One composition builds the Bedrock route's adapter: aia_executors/ai_runtime.py,
# from validated settings. Anywhere else it would be a route nobody configured.
forbid "only the AI runtime composition builds the Bedrock adapter" \
  'BedrockConverseAdapter\(' \
  "$EXECUTORS" \
  ai_runtime.py

# --- Layer 4: the worker executes; it does not serve, and it does not know ---
#
# The worker is driven by the engine and drives executors through one protocol
# (aia_worker.executor). It never serves HTTP, never reaches into the API, and
# never names a domain-specific module: an AI or research implementation plugs
# in through the executor registry, and if the worker imported one directly the
# seam would be decoration.

forbid "the worker knows nothing about HTTP" \
  '^\s*(from|import)\s+(fastapi|starlette)\b' \
  "$WORKER"

forbid "the worker never imports the API" \
  '^\s*(from|import)\s+aia_api\b' \
  "$WORKER"

forbid "the worker imports nothing domain-specific" \
  '^\s*(from|import)\s+aia_core\.(domain\.(pipeline|project|sociomap|residency)|infrastructure\.(repositories|artifact_repository|storage|scope_repository))\b' \
  "$WORKER"

# Expensive work never runs inside an API request. The only way a step executes
# is a worker claiming it; a route that claimed, completed or failed an attempt
# would be doing the work in the request, and would hold a lease for exactly as
# long as a browser stayed connected.
forbid "the API never executes workflow steps" \
  '\b(aia_worker|WorkQueue|claim_next|complete_attempt|fail_attempt|release_attempt|abandon_attempt)\b' \
  "$API"

# WorkflowRepository is study-scoped. Its unscoped constructor exists for
# WorkQueue, in the same module, and nothing else may call it: an unscoped
# repository anywhere else is a query across every client's studies.
forbid "only the work queue may query across studies" \
  '_across_studies' \
  "$CORE" \
  workflow_repository.py
forbid "the worker never builds an unscoped repository" \
  '_across_studies' \
  "$WORKER"

# Client Knowledge is reached only through its repository, which takes an issued
# ClientContext or StudyContext and puts the client in the query (ADR 0015
# decision 7). A table used anywhere else is a query that could forget the
# client: an unscoped pool filtered afterwards, which the ADR forbids.
forbid "client knowledge tables are touched only by their repository" \
  'ClientKnowledge(Item|Revision|Proposal)Row' \
  "$CORE" \
  tables.py client_knowledge_repository.py
forbid "the API never touches the client knowledge tables" \
  'ClientKnowledge(Item|Revision|Proposal)Row' \
  "$API"
forbid "the worker never touches the client knowledge tables" \
  'ClientKnowledge(Item|Revision|Proposal)Row' \
  "$WORKER"
forbid "executors never touch the client knowledge tables" \
  'ClientKnowledge(Item|Revision|Proposal)Row' \
  "$EXECUTORS"

# System prompts are data an administrator edits (ADR 0020). Their rows are written and
# read only through the prompt repository, which refuses anyone who may not administer
# the organization, keeps versions immutable, and audits every change. A table used
# anywhere else is an edit or an activation that skipped those three.
forbid "the prompt tables are touched only by their repository" \
  'Prompt(Version|Activation)Row' \
  "$CORE" \
  tables.py prompt_repository.py
forbid "the API never touches the prompt tables" \
  'Prompt(Version|Activation)Row' \
  "$API"
forbid "the worker never touches the prompt tables" \
  'Prompt(Version|Activation)Row' \
  "$WORKER"
forbid "executors never touch the prompt tables" \
  'Prompt(Version|Activation)Row' \
  "$EXECUTORS"

# Deep Research's policy values are data an Admin approves (ADR 0022). Their rows are written
# and read only through their repository, which validates every value against the catalogue,
# refuses anyone who may not administer, keeps versions immutable and audits every change.
forbid "the Deep Research settings tables are touched only by their repository" \
  'DeepResearchSetting(Version|Approval)Row' \
  "$CORE" \
  tables.py deep_research_settings_repository.py
forbid "the API never touches the Deep Research settings tables" \
  'DeepResearchSetting(Version|Approval)Row' \
  "$API"
forbid "the worker never touches the Deep Research settings tables" \
  'DeepResearchSetting(Version|Approval)Row' \
  "$WORKER"
forbid "executors never touch the Deep Research settings tables" \
  'DeepResearchSetting(Version|Approval)Row' \
  "$EXECUTORS"

# Fan-out's shared state (Deep Research chunk 21): one request per host at a time and at
# most N model requests in flight, across every worker process. Written in short
# transactions of their own by one module; a write anywhere else -- inside an attempt's
# fenced unit of work, say, or without the conditional UPDATE -- is a second scheduler
# that can hand one host or one slot to two processes.
forbid "the fan-out coordination tables are touched only by their module" \
  '(HostPoliteness|ModelConcurrencySlot)Row|host_politeness|model_concurrency_slots' \
  "$CORE" \
  tables.py fan_out_coordination.py
forbid "the API never touches the fan-out coordination tables" \
  '(HostPoliteness|ModelConcurrencySlot)Row|host_politeness|model_concurrency_slots' \
  "$API"
forbid "the worker never touches the fan-out coordination tables" \
  '(HostPoliteness|ModelConcurrencySlot)Row|host_politeness|model_concurrency_slots' \
  "$WORKER"
forbid "executors never touch the fan-out coordination tables" \
  '(HostPoliteness|ModelConcurrencySlot)Row|host_politeness|model_concurrency_slots' \
  "$EXECUTORS"

# A Study's design project is found only through the Study (ADR 0016 decision 1).
# The table used anywhere but its repository is a query that could find a design
# project -- and the revisions runs execute -- by something other than scope.
forbid "the study design table is touched only by its repository" \
  'StudyDesignRow' \
  "$CORE" \
  tables.py study_design_repository.py
forbid "the API, worker and executors never touch the study design table" \
  'StudyDesignRow' \
  apps
# A Study's design project is owned (projects.owner): a repository that does not
# name the owner cannot see it. Naming it anywhere else would reopen the path by
# which content that skipped validate_design became a Design Revision (ADR 0016).
forbid "only the design repository and the research runs name the design project's owner" \
  'DESIGN_PROJECT_OWNER' \
  "$CORE" \
  design.py study_design_repository.py research.py
forbid "the API, worker and executors never name the design project's owner" \
  'DESIGN_PROJECT_OWNER|study_design\b' \
  apps
# Licence eligibility (ADR 0016 decision 5): a determination is policy data that
# legal and the data owner change, in one reviewed file. Built anywhere else, it
# would be an approval nobody gave.
forbid "licence determinations are written only in their policy-data module" \
  'LicenceDetermination\(|LicencePolicy\(' \
  "$CORE" \
  licence.py licence_determinations.py
forbid "the API, worker and executors never build a licence policy of their own" \
  'LicenceDetermination\(|LicencePolicy\(' \
  apps
# The fictional fieldwork source (ADR 0016 D1) is kept out of production by
# construction: only the workbench composition may build it, nothing may import
# the workbench composition, and no deployment may name it.
forbid "only the workbench composition imports the fictional fieldwork generator" \
  '^\s*(from|import)\s+\S*synthetic_fieldwork' \
  "$CORE" \
  synthetic_fieldwork.py
forbid "no API code imports the fictional fieldwork generator" \
  '^\s*(from|import)\s+\S*(synthetic_fieldwork|aia_executors\.workbench)' \
  "$API"
forbid "the worker never imports the fictional fieldwork generator" \
  '^\s*(from|import)\s+\S*(synthetic_fieldwork|aia_executors\.workbench)' \
  "$WORKER"
forbid "among the executors, only the workbench composition builds fictional fieldwork" \
  '^\s*(from|import)\s+\S*(synthetic_fieldwork|\.workbench|aia_executors\.workbench)' \
  "$EXECUTORS" \
  workbench.py
forbid "no deployment runs the workbench composition" \
  'aia_executors\.workbench|aia_executors/workbench' \
  deploy
# Recorded web retrieval (Deep Research, plan decision I-9) replays captured
# exchanges and is never a production fallback: it is defined only beside the web
# adapters, built only by the recorded composition, imported by nothing in the
# API or the worker, and named by no deployment. The Common Crawl doubles (plan
# chunk 18: a recorded URL index, recorded archive ranges) are held to the same
# rules, beside their own adapters in common_crawl.py.
# The recorded dataset connector is the same kind of double, beside the connectors.
RECORDED_WEB='RecordedSearch|RecordedFetchTransport|RecordedResolver|RecordedWeb\b|load_recorded_web|RecordedUrlIndex|RecordedArchiveTransport|RecordedDatasetConnector'
forbid "recorded web retrieval is defined only beside the web adapters" \
  "$RECORDED_WEB" \
  "$CORE/infrastructure" \
  web_retrieval.py common_crawl.py dataset_connectors.py
forbid "application code never names recorded web retrieval" \
  "$RECORDED_WEB" \
  "$CORE/application"
forbid "domain code never names recorded web retrieval" \
  "$RECORDED_WEB" \
  "$CORE/domain"
forbid "no API code imports recorded web retrieval" \
  "$RECORDED_WEB|deep_research_recorded" \
  "$API"
forbid "the worker never imports recorded web retrieval" \
  "$RECORDED_WEB|deep_research_recorded" \
  "$WORKER"
forbid "among the executors, only the recorded composition builds recorded web retrieval" \
  "$RECORDED_WEB|deep_research_recorded" \
  "$EXECUTORS" \
  deep_research_recorded.py
forbid "no deployment runs the recorded Deep Research composition" \
  'deep_research_recorded|load_recorded_web' \
  deploy
# Deep Research has no authority over research truth (ADR 0021): it may propose a
# design change for a person to accept and write its own evidence, never a Design
# Revision, a Study's working content or a research run's deterministic artifacts.
# Its code may read a revision and a run's results (``upstream_artifact``,
# ``ResearchRuns.get``); it never names a writer: the design and workspace writers,
# the research step executors and the research run's start, retry or cancel.
DR_WRITES='\.submit\(|StudyWorkspaceRepository|\bresearch_registry|\b(Compile|Preflight|Fieldwork|Aggregate|Sociomap|Sociomapping|Analysis)Executor\b|ResearchRuns\([^)]*\)\.(start|retry|cancel|lift_budget)'
forbid "Deep Research executors never write a design or a research run's results" \
  "$DR_WRITES" \
  "$EXECUTORS/deep_research"
forbid "the Deep Research domain never writes a design or a research run's results" \
  "$DR_WRITES" \
  "$CORE/domain/deep_research"
forbid "the Deep Research service never writes a design or a research run's results" \
  "$DR_WRITES" \
  "$CORE/application/deep_research.py"
# A Design Research proposal becomes a design only through a person's accept
# (ADR 0021 decision 1, ADR 0019 gate 1; deep-research-web-search.md chunk 29):
# ``apply_to_design`` is called by the accept service and nowhere else.
forbid "only the person's accept applies a Design Research proposal to a design" \
  'apply_to_design' \
  "$CORE" \
  design_research.py design_proposals.py
forbid "no executor, worker or route applies a Design Research proposal itself" \
  'apply_to_design' \
  apps
# The focused crawler (plan chunk 17) reaches the web only through the retrieval
# gate it is given: classified, egress-checked, reserved, journaled, robots.txt and
# pacing kept by the gate's transport. An import of infrastructure or of an HTTP
# client here would be a second path out that none of that sees.
forbid "the site crawl imports no infrastructure and no HTTP client" \
  '^\s*(from|import)\s+(\.\.infrastructure|aia_core\.infrastructure|urllib3|urllib\.request|http\.client|socket|ssl|httpx|requests)\b' \
  "$CORE/application/site_crawl.py"
# The acquisition ladder (plan chunk 10) is the same: every rung asks the gate it
# is given. It may read a connector's id and its pure table readers (OpenAlex's open
# copies, Wayback's nearest capture), never a transport, a fetcher or an HTTP client.
forbid "the acquisition ladder imports no transport and no HTTP client" \
  '^\s*(from|import)\s+(\.\.infrastructure\.(web_retrieval|web_retrieval_live|web_retrieval_brave|common_crawl|dataset_connectors)|aia_core\.infrastructure\.(web_retrieval|common_crawl|dataset_connectors)|urllib3|urllib\.request|http\.client|socket|ssl|httpx|requests)\b' \
  "$CORE/application/acquisition_ladder.py"
# An archived copy is for a dead or moved page only (plan deep-research-web-search
# § 7 rung 9): the gate asks the archive only with a permit, and only the archive
# policy issues one. Nothing else may construct it.
forbid "only the archive policy issues an archive permit" \
  'ArchivePermit\(' \
  packages/aia_core/src \
  archive.py
# The public dataset and archive connectors are registered by no composition until
# the Deep Research composition chunk (plan chunk 23) records their routes and prices.
DATASET_CONNECTORS='DataStatConnector|NkodConnector|EurostatConnector|OpenAlexConnector|WaybackCdxConnector|AresConnector|ProcurementNoticeConnector'
for composition in "$API" "$WORKER" "$EXECUTORS" deploy; do
  forbid "no composition registers a dataset connector yet ($composition)" \
    "$DATASET_CONNECTORS" \
    "$composition"
done
# The recorded procurement notice source is the same kind of double, defined only
# beside the procurement connector and refused everywhere the others are.
RECORDED_NOTICES='RecordedNoticeSource'
forbid "the recorded notice source is defined only beside the procurement connector" \
  "$RECORDED_NOTICES" \
  "$CORE/infrastructure" \
  dataset_procurement.py
forbid "application code never names the recorded notice source" \
  "$RECORDED_NOTICES" \
  "$CORE/application"
forbid "domain code never names the recorded notice source" \
  "$RECORDED_NOTICES" \
  "$CORE/domain"
forbid "no API code names the recorded notice source" \
  "$RECORDED_NOTICES" \
  "$API"
forbid "the worker never names the recorded notice source" \
  "$RECORDED_NOTICES" \
  "$WORKER"
forbid "among the executors, only the recorded composition builds the recorded notice source" \
  "$RECORDED_NOTICES" \
  "$EXECUTORS" \
  deep_research_recorded.py
# A revision is what a run executed. The ORM refuses to UPDATE one
# (tables.py, before_update); a bulk update() would go around it.
forbid "no statement updates a project revision" \
  'update\(\s*ProjectRevisionRow' \
  packages/aia_core/src

# --- Layer 4b: executors do the work; they neither serve nor decide scope -----
#
# Step implementations depend on the worker's executor seam and on aia_core.
# They never import the API, never serve HTTP, and -- like the worker -- act
# only under the scope the lease issued them. An executor that could build a
# StudyContext could write another client's artifacts from inside a claimed step.

forbid "executors know nothing about HTTP" \
  '^\s*(from|import)\s+(fastapi|starlette)\b' \
  "$EXECUTORS"

forbid "executors never import the API" \
  '^\s*(from|import)\s+aia_api\b' \
  "$EXECUTORS"

forbid "executors never build their own scope context" \
  '^[^#]*\b(Organization|Client|Study)Context\(' \
  "$EXECUTORS"

forbid "executors never admit their own claims" \
  '^[^#]*\bAdmittedClaim\(' \
  "$EXECUTORS"

forbid "executors never build an unscoped workflow repository" \
  '_across_studies' \
  "$EXECUTORS"

# --- Layer 6: transport validates, delegates, serialises --------------------
#
# A route handler that opens a Session is a route handler that can make a
# decision the domain never saw. dependencies.py and main.py are the composition
# root -- they are where the engine, the session factory and the readiness probe
# legitimately live -- and are exempt by name.
forbid "no database access in the HTTP layer" \
  '^\s*(from|import)\s+sqlalchemy\b' \
  "$API" \
  dependencies.py main.py

# Tables are the infrastructure's private shape. The API talks to repositories,
# which return domain objects; reaching for a table means a query is about to be
# written in a place where it cannot be tested without the whole stack.
forbid "no ORM tables in the HTTP layer" \
  '(from|import)\s+.*infrastructure\.tables\b' \
  "$API"

# --- Authorization: scope is issued, never constructed ----------------------
#
# ScopeResolver is the only issuer of a scope context, via a module-private
# sentinel. If any other module can build one, then a request body, a tool
# payload or a model-generated argument can widen its own scope -- which is the
# whole isolation boundary gone. See docs/architecture/scope-and-authorization.md.
forbid "scope contexts are issued only by ScopeResolver" \
  '^[^#]*\b(Organization|Client|Study)Context\(' \
  "$CORE" \
  scope.py

forbid "the API never builds its own scope context" \
  '^[^#]*\b(Organization|Client|Study)Context\(' \
  "$API"

forbid "the worker never builds its own scope context" \
  '^[^#]*\b(Organization|Client|Study)Context\(' \
  "$WORKER"

# --- Evidence: admission and certificates are issued, never constructed ------
#
# The same capability pattern as scope. An AdmittedClaim is the only form in
# which a number may sit in an analysis result, and only admit_numeric_claims
# can mint one, after field policy, joint structure, support, interval and tier
# have all passed. A JointStatus is the only way the claim gate learns what the
# population's joint structure supports, and only load_joint_status can issue
# one, after checking the certificate against the loaded panel's hash. If any
# other module can build either, a prompt is the enforcement mechanism again.
# See .planning/plans/done/evidence-governance-foundation.md.
forbid "claims are admitted only by the evidence admission gate" \
  '^[^#]*\bAdmittedClaim\(' \
  "$CORE" \
  admission.py

forbid "the API never admits its own claims" \
  '^[^#]*\bAdmittedClaim\(' \
  "$API"

# companions.py is exempt by name, and only for now: it defines a *second*
# JointStatus -- the population loader's own certificate evaluator -- which is a
# duplicate of the evidence one, not a bypass of it. Which of the two is the single
# authority is an open decision (.planning/open-items.md OI-24); this exemption goes
# when that decision lands, not before.
forbid "a joint status is issued only by its loader" \
  '^[^#]*\bJointStatus\(' \
  "$CORE" \
  joint_status.py companions.py

# Field policy and the joint certificate are authority: what a claim may rest on.
# An app that built its own -- a permissive book for a questionnaire, a certificate
# for a run with no panel -- would be a guess presented as that authority. They
# come from the evidence domain's loaders and its instrument declaration, reached
# through the analysis inputs in aia_core, never from the API, the worker or an
# executor (.planning/plans/evidence-backed-analysis.md).
forbid "the API, worker and executors never build field policy or a joint status" \
  '\b(FieldPolicyBook|FieldPolicy|FieldEligibility)\(|\b(load_joint_status|instrument_policy|instrument_policy_book|from_dictionary_rows|from_policy_document)\(' \
  apps

# --- Population: one resolver, one loader ----------------------------------
#
# The reference answered "which population is in use" in four places and loaded
# it through two loaders that returned different populations from the same bytes
# (AIA-reference R4, fixture F10). A RuntimePopulation is issued only by
# PopulationRuntime in application/population.py, through a module-private
# sentinel; runtime.py defines it. Parsing a panel anywhere else is the first step
# of a second loader, so that is refused too; population_parser.py is the parser.
forbid "runtime populations are issued only by the canonical loader" \
  '^[^#]*RuntimePopulation\._issue\(' \
  "$CORE" \
  population.py runtime.py

forbid "the API never issues a runtime population" \
  '^[^#]*RuntimePopulation\._issue\(' \
  "$API"

forbid "population panels are parsed only by the canonical loader" \
  '^[^#]*\bparse_panel\(' \
  "$CORE" \
  population.py population_parser.py

forbid "the API never parses a population panel" \
  '^[^#]*\bparse_panel\(' \
  "$API"

# Establishing and promoting a population is platform administration. The
# operator grant is issued only by PopulationAuthority from trusted configuration
# (application/population_authority.py); authority.py defines it. Neither a study
# nor an organization context implies it, and the API never mints one.
forbid "population-operator grants are issued only by the population authority" \
  '^[^#]*PopulationOperatorGrant\._issue\(' \
  "$CORE" \
  population_authority.py authority.py

forbid "the API never issues a population-operator grant" \
  '^[^#]*PopulationOperatorGrant\._issue\(' \
  "$API"

# --- Sociomap: computable is not deliverable --------------------------------
#
# AIA_SOCIOMAP_V1 and AIA_SOCIOMAP_V2 are presets a run adopts by pinning them
# (research_sociomap.default_methods, recorded on the run) -- neither is an
# approved client methodology (docs/architecture/sociomapa-methodology-decision.md).
# If an application service, worker, route or client could reference it, it
# could fill in a missing spec, and an engineering choice would become client
# methodology by default. Outside the Sociomap domain package (where it is
# defined), its tests and the golden-fixture tool, it may not appear at all.
# See sociomapa-deterministic-engine.md §13.
forbid "application code never substitutes the Sociomap preset" \
  'AIA_SOCIOMAP_V[0-9]+' \
  "$CORE/application/"
forbid "infrastructure never substitutes the Sociomap preset" \
  'AIA_SOCIOMAP_V[0-9]+' \
  "$CORE/infrastructure/"
forbid "the API never substitutes the Sociomap preset" \
  'AIA_SOCIOMAP_V[0-9]+' \
  "$API"
forbid "workers never substitute the Sociomap preset" \
  'AIA_SOCIOMAP_V[0-9]+' \
  apps/worker
forbid "the web client never names the Sociomap preset" \
  'AIA_SOCIOMAP_V[0-9]+' \
  apps/web/src

# --- Tests: the signal is never deleted ------------------------------------
#
# A failing test is a finding (ARCHITECTURE.md §7). Runtime `pytest.skip(...)`
# is allowed and used deliberately -- a missing PostgreSQL or a missing legacy
# reference checkout is a real environment fact. A *static* skip or xfail is
# different: it removes the signal permanently and silently.
forbid "no statically skipped or xfailed tests" \
  '@pytest\.mark\.(skip|xfail)' \
  packages/aia_core/tests
forbid "no statically skipped or xfailed API tests" \
  '@pytest\.mark\.(skip|xfail)' \
  apps/api/tests
forbid "no statically skipped or xfailed worker tests" \
  '@pytest\.mark\.(skip|xfail)' \
  apps/worker/tests
forbid "no statically skipped or xfailed executor tests" \
  '@pytest\.mark\.(skip|xfail)' \
  apps/executors/tests

# --- Presentation: the client renders, it does not decide -------------------
#
# GET /projects/{id}/impact exists precisely so the browser never reasons about
# which stages an edit invalidates. A database client in the web app would mean
# that boundary has been crossed in the most expensive possible way.
forbid "the web client does not talk to a database" \
  '^\s*(import|export).*(from\s+)?['\''"](pg|better-sqlite3|@prisma/client|mysql2|mongodb)['\''"]' \
  apps/web/src

echo
if [ "$FAILED" -ne 0 ]; then
  echo "layer_check: FAILED -- see the rules above and ARCHITECTURE.md §3."
  exit 1
fi
echo "layer_check: $PASSED rules pass."
