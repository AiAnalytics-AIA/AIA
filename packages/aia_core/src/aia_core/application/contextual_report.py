"""Read pinned interpretation research into a separate, unapproved study report.

No model calls, respondent context, or changes to frozen run outputs. External
citations have their own L labels; they never enter the respondent evidence ledger.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from aia_core.application.analysis_results import reconstruct_run
from aia_core.application.deep_research import BundleNotReady, DeepResearchRuns, run_settings
from aia_core.application.report import (
    RESEARCH_SUBTITLE,
    ReportCompositionRefused,
    compose_internal_report,
)
from aia_core.application.report_chapters import report_chapters
from aia_core.application.report_export import REVIEW_STAMP_RECORD
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.analysis import ANALYSIS_MODULES, AnalysisModuleId
from aia_core.domain.deep_research.bundle import EvidenceBundle, SnapshotRef
from aia_core.domain.deep_research.contracts import (
    DeepResearchRequest,
    EvidenceItem,
    EvidenceOrigin,
    QualityStatus,
    SourceKind,
    SubjectKind,
)
from aia_core.domain.deep_research.document_types import (
    DOCUMENT_RULES_VERSION,
    DocumentType,
    DocumentTyping,
    document_rules_of,
    document_type,
)
from aia_core.domain.deep_research.gaps import AcquisitionReason
from aia_core.domain.deep_research.integration import DeepResearchPurpose, InterpretationLineage
from aia_core.domain.deep_research.reputation import REPUTATION_REGISTER_V1
from aia_core.domain.deep_research.settings import Origin, SettingsPinCorrupt
from aia_core.domain.deep_research.topicality import (
    TOPICALITY_VERSION,
    TopicJudgement,
    TopicScreen,
    TopicVerdict,
    judged_topic,
    topic_screen,
)
from aia_core.domain.deep_research.triangulation import publisher_identity
from aia_core.domain.fieldwork import OriginKind, origin_kind
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.report.model import (
    Block,
    BulletList,
    Callout,
    CalloutKind,
    Classification,
    Column,
    Heading,
    Inline,
    Link,
    ListItem,
    Paragraph,
    Quote,
    ReportDocument,
    ReportKind,
    ReportMeta,
    Section,
    Table,
    TableRow,
    Text,
    TextCell,
    text,
)
from aia_core.domain.scope import Permission, StudyContext
from aia_core.infrastructure.artifact_repository import (
    Artifact,
    ArtifactNotFound,
    ArtifactRepository,
    ArtifactStatus,
)
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import ArtifactStore, IntegrityError, ObjectNotFound

CONTEXT_REPORT_CONTRACT = "aia-contextual-report-5"
# Stored beside the run's own report, on the Study's design project (ADR 0016).
CONTEXT_REPORT_ARTIFACT_TYPE = "research_internal_docx_with_research"
CONTEXT_REPORT_STAGE = "REPORT"
#: The Deep Research setting that signs off the source table (domain.deep_research.settings).
SOURCE_TIERS_SETTING: Final = "sources.tiers"
#: Why a source was not obtained, before the list of its titles: for one source and for several.
_ACQUISITION_REASONS: dict[AcquisitionReason, tuple[str, str]] = {
    AcquisitionReason.PAYWALL: (
        "Zdroj vyžaduje placený přístup",
        "Zdroje vyžadují placený přístup",
    ),
    AcquisitionReason.LOGIN: ("Zdroj vyžaduje přihlášení", "Zdroje vyžadují přihlášení"),
    AcquisitionReason.NOT_PUBLIC: (
        "Zdroj nebyl veřejně přístupný",
        "Zdroje nebyly veřejně přístupné",
    ),
    AcquisitionReason.NOT_FOUND: ("Zdroj se nepodařilo nalézt", "Zdroje se nepodařilo nalézt"),
    # Said of the sources, never of how many websites: two pages of one host are not "webů".
    AcquisitionReason.ROBOTS: (
        "Automatické získání zdroje zakázala pravidla robots.txt",
        "Automatické získání těchto zdrojů zakázala pravidla robots.txt",
    ),
    AcquisitionReason.NOT_PURSUED: (
        "Získání tohoto zdroje nebylo v tomto běhu dokončeno",
        "Získání těchto zdrojů nebylo v tomto běhu dokončeno",
    ),
}


def _web_url(url: str | None) -> str | None:
    if url:
        parsed = urlsplit(url)
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username:
            return url
    return None


#: What a source's declared class says, in words. Decided by its domain alone
#: (``deep_research.sources``): credibility of the publisher, never topicality.
_SOURCE_CLASS = {
    "OFFICIAL_STATISTICS": "oficiální statistika",
    "GOVERNMENT_OR_REGULATOR": "státní instituce nebo regulátor",
    "PEER_REVIEWED": "recenzovaná publikace",
    "ACADEMIC_INSTITUTION": "akademická instituce",
    "PREPRINT": "preprint",
    "INDUSTRY_RESEARCH": "odborný průzkum z praxe",
    "MEDIA": "médium",
    "FORUM_OR_SOCIAL": "diskusní fórum nebo sociální síť",
    "CLIENT_KNOWLEDGE": "znalosti klienta",
    "UNKNOWN": "neurčený typ",
}
#: Why a finding was not accepted, in the report's words (``QuarantineReason``; one each).
_QUARANTINE = {
    "target_outcome_overlap": "překrývá se s tím, co má výzkum teprve zjistit",
    "deterministic_target_overlap": "překrývá se s počítaným výsledkem",
    # The score is the domain's type and the page's age together (sources.py): an old page on an
    # acceptable domain falls below the threshold too, so the domain alone is never blamed.
    "low_source_quality": "hodnocení zdroje (typ domény a stáří stránky) je pod prahem přijetí",
    "no_independent_confirmation": "bez nezávislého potvrzení",
    "ungrounded_excerpt": "citace není ve zdroji",
    "citation_outside_track": "citace z jiného hledání",
    "number_not_in_quote": "číslo není v citaci",
    "source_contains_instructions": "zdroj obsahuje pokyny pro model",
    "unsupported_by_verifier": "ověření nepotvrdilo",
    "overstated_by_verifier": "ověření označilo za přehnané",
    "unverified": "neověřeno",
    "questionnaire_leakage": "prozrazuje dotazník",
    "measure_not_in_source": "měřená veličina není ve zdroji",
    "measure_missing": "chybí měřená veličina",
    "superseded": "nahrazeno novějším",
    "retracted_source": "zdroj byl stažen",
    "off_topic": "netýká se tématu, pro které bylo hledáno",
    "topic_undetermined": "souvislost s tématem hledání nelze posoudit",
    "student_thesis": "studentská kvalifikační práce",
}
_QUALITY = {
    QualityStatus.GROUNDED: "všechna plánovaná hledání doběhla",
    QualityStatus.PARTIAL: "část hledání nebyla dokončena nebo byla zablokována",
    QualityStatus.NO_EVIDENCE: "hledání doběhla, ale žádné zjištění neprošlo kontrolou",
}


#: What the study's own answers are, said once beside the literature (origin_kind).
_ORIGIN_SENTENCE: Final[dict[OriginKind | None, str]] = {
    OriginKind.SIMULATED: "Odpovědi této studie jsou smyšlené a nejsou odhadem žádné populace. ",
    OriginKind.MODELLED: (
        "Odpovědi této studie modelovali AI respondenti; nejsou měřením skutečných osob. "
    ),
}


def _host(url: str | None) -> str | None:
    host = urlsplit(url).hostname if url else None
    return host.removeprefix("www.") if host else None


class TopicRulesUnread(Enum):
    """Today's topic rules could not be applied to a review merged before them: the stored plan
    they read the client's names from (``DeepResearchRuns.frozen_request``) is missing, does not
    verify, or is not the run's request. Whether they would set any finding aside is unknown."""

    PLAN_UNVERIFIED = "plan_unverified"


#: What a plan read fails with when the plan is not there to read as stored: the run's own
#: refusal, the store's verdict on the object (missing, corrupt), and a payload that is not a
#: request. A refusal of the person's access is none of these, and still refuses the report;
#: nor is a store that failed to answer (a timeout, throttling: the base ``StorageError``),
#: which a retry may read, so it fails the request as before rather than storing a newest
#: draft without the labels (cross-review).
_PLAN_UNREADABLE: Final = (
    BundleNotReady,
    ObjectNotFound,
    IntegrityError,
    ArtifactNotFound,
    ValueError,
    KeyError,
    TypeError,
)


def todays_topic_rules(
    bundle: EvidenceBundle, read_request: Callable[[], DeepResearchRequest]
) -> TopicScreen | TopicRulesUnread | None:
    """The topic rules a review's chapter is read by today (D4): none for a review merged under
    them (its merge judged every finding, and ``read_request`` is never called); otherwise
    today's, over its sealed subjects and the client terms its plan kept -- or, when that plan
    cannot be read, :attr:`TopicRulesUnread.PLAN_UNVERIFIED`, which the chapter says in one
    callout. A review composed without its labels is still a report; the labels need the plan,
    the rest of the chapter does not (cross-review: a plan that did not verify refused the
    whole report with literature)."""
    if judged_topic(bundle.versions.get("merge", "")):
        return None
    try:
        request = read_request()
    except _PLAN_UNREADABLE:
        return TopicRulesUnread.PLAN_UNVERIFIED
    return topic_screen(bundle.subjects, client_terms=request.client_terms)


def literature_sections(
    bundle: EvidenceBundle,
    *,
    research_run_id: str,
    origin: OriginKind | None = None,
    tiers_approved: bool | None = None,
    topics: TopicScreen | TopicRulesUnread | None = None,
) -> tuple[Section, ...]:
    """Publish accepted source claims; citation checks do not approve model inferences.

    The chapter keeps credibility and relevance apart (research-integrity-report chunk 2).
    Code checked that each quote is verbatim in its captured source and that the claim's
    numbers are in the quote, and the verifier read the claim against the quote; nobody
    checked that a source is about the same concept, population, place and period as the
    study. So every finding is printed with the research topic it was gathered for and its
    cited passage, every source with what its domain says about it, and a review resting on
    one publisher says so in words -- the publisher as Deep Research's own independence rule
    reads it (``triangulation.publisher_identity`` over the reputation register), so a landing
    page and its PDF are one publisher and two ministries on gov.cz are two. A sparse review is
    said briefly, once. ``origin`` is the study's respondents' origin kind, for the one sentence
    that says what they are; unknown says nothing. ``tiers_approved`` is whether the review's
    pinned settings sign off the source table (``sources.tiers`` approved as ``approved``,
    ADR 0022); ``None`` for a review that pinned none, which says so, never guessed either way.

    Whether code judged each finding's topic is the bundle's own record (its merge version
    carries the topic rules, D4): the chapter says what that check covers and what it leaves to
    the reader. A review merged before them is never judged again by the engine (a start on an
    unchanged target returns it); with ``topics``, today's rules over its frozen request, each
    accepted finding they would set aside is labelled with the reason and one callout names
    their sources -- never removed, re-scored or recounted, the bundle and its seal as stored.
    With :attr:`TopicRulesUnread.PLAN_UNVERIFIED`, one callout says today's topic check could
    not be applied, so an unlabelled finding is not read as one that passes it.
    The document rules (D4) likewise: a review merged before them has its accepted web sources
    typed now, by their address and title (Client Knowledge never), and a student thesis is
    named in its source's type cell, after each of its findings and in that one callout, ahead
    of the topic as the merge would set it aside.
    """
    if not bundle.verify():
        raise ReportCompositionRefused("Deep Research bundle seal is invalid")
    topic_judged = judged_topic(bundle.versions.get("merge", ""))
    documents_typed = document_rules_of(bundle.versions.get("merge", ""))
    snapshots = {s.snapshot_id: s for s in bundle.snapshots}
    # What today's merge would set aside first (merge.py's order): a student thesis, then a
    # finding off its topic. Each for a review merged before those rules only.
    theses: dict[str, DocumentTyping] = {}
    if documents_typed is None:
        for found in bundle.accepted:
            typed = _composed_type(found.evidence, snapshots)
            if typed.type is DocumentType.STUDENT_THESIS:
                theses[found.evidence.evidence_id] = typed
    would_reject: dict[str, TopicJudgement] = {}
    if isinstance(topics, TopicScreen) and not topic_judged:
        for found in bundle.accepted:
            if found.evidence.evidence_id in theses:
                continue
            judgement = topics.judge(found.evidence)
            if judgement.verdict is not TopicVerdict.ON_TOPIC:
                would_reject[found.evidence.evidence_id] = judgement
    # A finding today's topic check would have judged (a thesis is set aside before it), when
    # that check could not be applied: unknown, said once, never read as passing.
    topics_unread = (
        topics is TopicRulesUnread.PLAN_UNVERIFIED
        and not topic_judged
        and any(a.evidence.evidence_id not in theses for a in bundle.accepted)
    )
    accepted = {a.evidence.evidence_id: a for a in bundle.accepted}
    labels: dict[str, str] = {}
    # url or ref -> (label, url, title, date, retrieved, host, source class, findings)
    sources: dict[str, dict[str, Any]] = {}
    subjects = {s.key: s for s in bundle.subjects}
    for a in bundle.accepted:
        e = a.evidence
        snapshot = snapshots.get(e.source_ref)
        url = _web_url(e.source_url or (snapshot.final_url if snapshot else None))
        key = url or e.source_ref
        if key not in sources:
            sources[key] = {
                "label": f"L{len(sources) + 1}",
                "url": url,
                "title": e.source_title or e.source_ref,
                "date": e.source_date or "neuvedeno",
                "retrieved": snapshot.retrieved_at.date().isoformat() if snapshot else "neuvedeno",
                "host": _host(url),
                "publisher": publisher_identity(
                    url=url, source_ref=e.source_ref, register=REPUTATION_REGISTER_V1
                ),
                "class": a.score.source_class,
                "table": a.score.table_version,
                "thesis": False,
                "findings": 0,
                "subjects": [],
            }
        source = sources[key]
        source["findings"] += 1
        source["thesis"] = source["thesis"] or e.evidence_id in theses
        if e.subject_key not in source["subjects"]:
            source["subjects"].append(e.subject_key)
        labels[e.evidence_id] = source["label"]
    by_label = {v["label"]: v for v in sources.values()}

    def cited(value: str, ids: tuple[str, ...]) -> Paragraph:
        if not ids or any(i not in accepted for i in ids):
            raise ReportCompositionRefused("synthesis cites evidence outside its accepted bundle")
        content: list[Inline] = [Text(value + " ")]
        for label in dict.fromkeys(labels[i] for i in ids):
            url = by_label[label]["url"]
            content.append(Link(f"[{label}]", url) if url else Text(f"[{label}]"))
            content.append(Text(" "))
        return Paragraph(tuple(content))

    blocks: list[Block] = [
        Paragraph(
            text(
                "Tato kapitola doplňuje zmrazené výsledky studie o veřejné zdroje, které vyhledal "
                "nástroj Deep Research. Jde o cílenou rešerši, nikoli o systematický přehled "
                "literatury, a její zjištění nejsou odpověďmi respondentů této studie; odkazy L "
                "jsou proto vedeny odděleně od evidence studie."
            )
        ),
        Paragraph(
            text(_relevance_sentence(topic_judged, frozenset(s.kind for s in bundle.subjects)))
        ),
    ]
    if EvidenceOrigin.RECORDED_FIXTURE in bundle.origins:
        blocks.append(
            Paragraph(
                text(
                    "Část podkladů pochází z nahraných testovacích výměn. Tato rešerše proto "
                    "dokládá funkci systému a nesmí být vydávána za aktuální živý výzkum."
                )
            )
        )
    synthesis = bundle.synthesis.check if bundle.synthesis else None
    if synthesis:
        # Preserve the foreign-citation refusal, even though proposed prose is omitted.
        for finding in synthesis.findings:
            if not finding.evidence_ids or any(i not in accepted for i in finding.evidence_ids):
                raise ReportCompositionRefused(
                    "synthesis cites evidence outside its accepted bundle"
                )
        blocks.append(
            Paragraph(
                text(
                    "Automatický návrh syntézy prošel kontrolou citací a čísel, nikoli "
                    "schválením věcné platnosti všech interpretací. Generované závěry proto do "
                    "kapitoly nevstupují; uvedena jsou jen přijatá zjištění ze zdrojů."
                )
            )
        )

    blocks.append(Heading("Rozsah rešerše", 2))
    blocks.append(Paragraph(text("Rešerše hledala podklady k těmto tématům:")))
    blocks.append(BulletList(tuple(ListItem(text(s.text)) for s in bundle.subjects)))
    rejected = Counter(q.reason.value for q in bundle.quarantined)
    blocks.append(
        Paragraph(
            text(
                f"Zachycené stránky zdrojů: {len(bundle.snapshots)}. Přijatá zjištění: "
                f"{len(bundle.accepted)}, citované zdroje: {len(sources)}. Odmítnutá zjištění: "
                f"{len(bundle.quarantined)}. Stav hledání: "
                f"{_QUALITY.get(bundle.quality_status, bundle.quality_status.value)}. "
                "Počet zachycených stran nevypovídá o kvalitě ani úplnosti přehledu."
                + (
                    " Důvody odmítnutí: "
                    + "; ".join(
                        f"{_QUARANTINE.get(reason, reason)} ({count}krát)"
                        for reason, count in rejected.most_common()
                    )
                    + "."
                    if rejected
                    else ""
                )
            )
        )
    )
    publishers = {v["publisher"].key: v["publisher"].name for v in sources.values()}
    if not accepted:
        blocks.append(
            Callout(
                CalloutKind.LIMITATION,
                text(
                    "Rešerše nepřinesla žádné přijaté zjištění. Literatura proto výsledky této "
                    "studie nepodpírá ani nezpochybňuje a nenabízí žádný srovnávací údaj."
                ),
                title="Bez opory v literatuře",
            )
        )
    elif len(publishers) == 1:
        (only,) = publishers.values()
        blocks.append(
            Callout(
                CalloutKind.LIMITATION,
                text(
                    f"Všechna přijatá zjištění ({len(bundle.accepted)}) pocházejí od jediného "
                    f"vydavatele ({only}). Rešerše tak nenabízí nezávislé potvrzení ani srovnání "
                    "zdrojů; čtěte ji jako jeden doklad, nikoli jako stav poznání."
                ),
                title="Rešerše stojí na jednom vydavateli",
            )
        )
    if theses or would_reject:

        def named(ids: Mapping[str, object]) -> str:
            flagged = list(dict.fromkeys(labels[i] for i in ids))
            return f"{len(ids)}, {'ze zdroje' if len(flagged) == 1 else 'ze zdrojů'} " + ", ".join(
                flagged
            )

        rules = []
        if theses:
            rules.append(
                f"Studentská kvalifikační práce podle pravidel {DOCUMENT_RULES_VERSION}: "
                f"{named(theses)}."
            )
        if would_reject:
            rules.append(
                "Nepodporuje téma, pro které bylo hledáno, nebo to nelze posoudit, podle kontroly "
                f"tématu {TOPICALITY_VERSION}: {named(would_reject)}."
            )
        # With today's topic check not applied, the count is of the document rules alone: a
        # lower bound, never the total under today's rules (cross-review).
        failed = len(theses) + len(would_reject)
        total = (
            f"nejméně {failed} (dnešní kontrolu tématu nebylo možné použít)"
            if topics_unread
            else str(failed)
        )
        blocks.append(
            Callout(
                CalloutKind.LIMITATION,
                text(
                    "Rešerše vznikla před dnešními pravidly pro přijetí zjištění. Přijatá "
                    f"zjištění, která by podle nich neprošla: {total}. "
                    + " ".join(rules)
                    + " U každého je níže uveden důvod. Kapitola je uvádí tak, jak je rešerše "
                    "přijala, a nemění počty ani pečeť balíčku; čtěte je s touto výhradou."
                ),
                title="Zjištění, která by dnešní pravidla nepřijala",
            )
        )
    if topics_unread:
        blocks.append(
            Callout(
                CalloutKind.LIMITATION,
                text(
                    f"Rešerše vznikla před dnešní kontrolou tématu ({TOPICALITY_VERSION}) a tu "
                    "na ni nebylo možné použít: uložený plán rešerše, z něhož kontrola čte "
                    "jména klienta, se nepodařilo ověřit. Zda by některé z přijatých zjištění "
                    "dnes kontrolou tématu neprošlo, proto není známo; že u zjištění není uveden "
                    "důvod, neznamená, že by jí prošlo. Kapitola uvádí zjištění tak, jak je "
                    "rešerše přijala."
                ),
                title="Dnešní kontrolu tématu nebylo možné použít",
            )
        )

    if accepted:
        blocks.append(Heading("Přijatá zjištění a jejich citace", 2))
        if not synthesis or not synthesis.findings:
            blocks.append(
                Paragraph(
                    text(
                        "Souvislá syntéza nebyla přijata; uvedena jsou jednotlivá ověřená zjištění."
                    )
                )
            )
        for a in bundle.accepted:
            e = a.evidence
            subject = subjects.get(e.subject_key)
            label = labels[e.evidence_id]
            blocks.append(cited(e.claim, (e.evidence_id,)))
            blocks.append(
                Quote(
                    text=e.quote,
                    attribution=f"[{label}] {by_label[label]['title']}"
                    + (f"; hledáno k tématu: {subject.text}" if subject else ""),
                    synthetic=False,
                )
            )
            thesis = theses.get(e.evidence_id)
            if thesis is not None:
                blocks.append(
                    Paragraph(
                        text(
                            f"Dnešní pravidla typů dokumentů ({DOCUMENT_RULES_VERSION}) by toto "
                            f"zjištění nepřijala: {_QUARANTINE['student_thesis']} "
                            f"({thesis.words}). Rešerše vznikla před nimi a zjištění přijala; "
                            "uvedeno je beze změny."
                        )
                    )
                )
            rejected_now = would_reject.get(e.evidence_id)
            if rejected_now is not None:
                reason = (
                    "off_topic"
                    if rejected_now.verdict is TopicVerdict.OFF_TOPIC
                    else "topic_undetermined"
                )
                blocks.append(
                    Paragraph(
                        text(
                            f"Dnešní kontrola tématu ({TOPICALITY_VERSION}) by toto zjištění "
                            f"nepřijala: {_QUARANTINE[reason]} ({rejected_now.detail}). "
                            "Rešerše vznikla před ní a zjištění přijala; uvedeno je beze změny."
                        )
                    )
                )
            # Numeric metadata may capture just the first year of a range. Keep
            # numbers with the accepted claim's full scope instead of reconstructing
            # an independently unverified indicator or period from those fields.
        has_numeric_data = any(
            measure.unit or measure.measure_name
            for a in bundle.accepted
            for measure in a.evidence.measures
        )
        if not has_numeric_data:
            blocks.append(
                Paragraph(
                    text(
                        "Přijaté zdroje neobsahují strukturovaný číselný benchmark. "
                        "Z dostupné literatury proto nelze odvozovat referenční hodnotu ani "
                        "číselný rozdíl vůči výsledkům této studie."
                    )
                )
            )
        blocks.append(
            Table(
                id="tab-literature-sources",
                title="Citované zdroje a co o nich AIA ví",
                columns=(
                    # Wide enough for an ISO date on one line (it broke at "2025-10-" in the
                    # rendered PDF, research-integrity-report 4).
                    Column("Zdroj", width_weight=3.4),
                    Column("Doména a její typ", width_weight=3),
                    Column("Datum", width_weight=1.7),
                    Column("Zjištění", width_weight=0.9),
                ),
                rows=tuple(
                    TableRow(
                        (
                            TextCell(f"[{v['label']}] {v['title']}"),
                            TextCell(
                                f"{v['host'] or 'bez webové adresy'}: "
                                f"{_source_type(str(v['class']), thesis=v['thesis'])}"
                            ),
                            TextCell(str(v["date"])),
                            TextCell(str(v["findings"])),
                        )
                    )
                    for v in sources.values()
                ),
                source=f"Ověřený balíček Deep Research {research_run_id}",
                notes=(
                    _table_note(
                        ", ".join(sorted({str(v["table"]) for v in sources.values()})),
                        tiers_approved,
                    )
                    + _document_note(documents_typed)
                    + " Autora, metodu a vzorek zdroje AIA nezaznamenává; před srovnáním "
                    "s výsledky je ověřte ve zdroji.",
                ),
            )
        )

    blocks.extend(
        [
            Heading("Jak rešerši číst vedle výsledků", 2),
            Paragraph(
                text(
                    "Postoj, chování a hodnocení jsou odlišné ukazatele. Číselné srovnání "
                    "vyžaduje shodu definice, jednotky, období, území a jmenovatele; chybějící "
                    "údaj srovnatelnost nedokládá. "
                    + _ORIGIN_SENTENCE.get(origin, "")
                    + "Rešerše nemění uložené odpovědi, analýzu ani výpočet sociomap."
                )
            ),
        ]
    )

    brief = bundle.synthesis.brief if bundle.synthesis else None
    needs: list[str] = []
    withheld_needs = 0
    if brief:
        for gap in brief.gaps:
            # A search gap's model-authored reason can contain the same unsupported
            # inference as a summary. Report the unmet need, not that inference.
            # A need written with a number nobody cited is withheld (gaps.py); its marker is
            # not for a reader, but each one is a need of its own, counted, never merged.
            if gap.text_withheld:
                withheld_needs += 1
                continue
            need = gap.need.strip().rstrip(".")
            if _norm(need) not in {_norm(n) for n in needs}:
                needs.append(need)
    if withheld_needs:
        needs.append(
            _withheld("podklad bez uvedeného znění", "podklady bez uvedeného znění", withheld_needs)
        )
    if needs:
        blocks.append(
            Paragraph(text("V tomto běhu nebyly doloženy tyto podklady: " + "; ".join(needs) + "."))
        )
    if brief and brief.acquisition_gaps:
        # One line per reason, the titles together, how to obtain them once: a sparse review
        # is said briefly instead of repeating the same notice for every missing source.
        grouped: dict[AcquisitionReason, list[tuple[str, str]]] = {}
        withheld: Counter[AcquisitionReason] = Counter()
        for acquisition in brief.acquisition_gaps:
            entries = grouped.setdefault(acquisition.reason, [])
            how = acquisition.how_to_obtain.strip()
            if acquisition.text_withheld:
                # Its title is not for a reader; it is still a source of its own, counted.
                withheld[acquisition.reason] += 1
                entries.append(("", how))
            elif _norm(acquisition.title) not in {_norm(t) for t, _ in entries if t}:
                entries.append((acquisition.title, how))
        items: list[ListItem] = []
        for reason, entries in grouped.items():
            hows = list(dict.fromkeys(h for _, h in entries if h))
            titles = [t for t, _ in entries if t]
            if withheld[reason]:
                titles.append(
                    _withheld(
                        "zdroj bez uvedeného názvu", "zdroje bez uvedeného názvu", withheld[reason]
                    )
                )
            many = len(titles) + max(0, withheld[reason] - 1) > 1
            items.append(
                ListItem(
                    text(
                        f"{_ACQUISITION_REASONS[reason][1 if many else 0]}: "
                        + "; ".join(titles)
                        + "."
                        + (f" {' '.join(hows)}" if hows else "")
                    )
                )
            )
        blocks.append(Heading("Podklady pro doplnění rešerše", 2))
        blocks.append(BulletList(tuple(items)))
    blocks.append(Heading("Literatura a zdroje", 2))
    blocks.extend(
        Paragraph(
            (
                Text(
                    f"[{v['label']}] {v['title']}. Datum zdroje: {v['date']}. "
                    f"Získáno: {v['retrieved']}. "
                ),
                Link(v["url"], v["url"]),
            )
            if v["url"]
            else text(
                f"[{v['label']}] {v['title']}. Datum zdroje: {v['date']}. "
                f"Získáno: {v['retrieved']}."
            )
        )
        for v in sources.values()
    )
    # The review and its seal, and nothing of the report's status: a version states that in its
    # footers alone, so an approved one's stamp is the whole truth (D2). The stamp reads only the
    # renderer's own status marks, never words (a study's may say "neschválení"), so these words
    # are held by the tests that render this report (``review_stamp``).
    blocks.append(
        Paragraph(
            text(f"Deep Research: {research_run_id}. Pečeť ověřeného balíčku: {bundle.sha256}.")
        )
    )
    return (Section("Literární rešerše a externí kontext", tuple(blocks), id="literature"),)


def _composed_type(evidence: EvidenceItem, snapshots: Mapping[str, SnapshotRef]) -> DocumentTyping:
    """A web finding's source typed by today's document rules, by its title and the address the
    chapter cites it by (a web finding's own is its page's final address, the one the merge
    types). Client Knowledge is never typed: a person approved it as the client's own."""
    if evidence.source_kind is not SourceKind.WEB_PAGE:
        return DocumentTyping(DocumentType.UNDETERMINED)
    snapshot = snapshots.get(evidence.source_ref)
    url = evidence.source_url or (snapshot.final_url if snapshot else None)
    return document_type(url, evidence.source_title)


def _source_type(source_class: str, *, thesis: bool) -> str:
    """What a source's domain says, and a student thesis typed at composition, in the one type
    cell (a column of its own would narrow the date's). An academic host the document rules
    leave undetermined may still hold one: they recognise declared registers, archives, path
    segments and titles only."""
    words = _SOURCE_CLASS.get(source_class, "neurčený typ")
    if thesis:
        return f"{words}; studentská kvalifikační práce (určeno při sestavení zprávy)"
    if source_class == "ACADEMIC_INSTITUTION":
        return f"{words} (může jít i o studentskou práci)"
    return words


def _document_note(typed_by: str | None) -> str:
    """How the document type was decided: by the review's own merge, or only now, at
    composition; neither reads the content, and neither excludes a thesis it does not
    recognise."""
    if typed_by is not None:
        return (
            f" Studentské kvalifikační práce rešerše odmítla podle pravidel {typed_by}, a to "
            "jen podle adresy a názvu zdroje; práci, kterou tato pravidla nepoznají, nevylučuje."
        )
    return (
        " Rešerše vznikla před pravidly typů dokumentů; studentské kvalifikační práce mezi "
        f"jejími zdroji rozpoznávají až při sestavení zprávy pravidla {DOCUMENT_RULES_VERSION}, "
        "a to jen podle adresy a názvu zdroje; práci, kterou nepoznají, nevylučují."
    )


def _relevance_sentence(topic_judged: bool, kinds: frozenset[SubjectKind]) -> str:
    """What code checked of a finding's relevance, by the review's own record (D4): with the
    topic rules, what they check and what they leave; without them, that nobody checked.

    Each check is said of the topics it runs for (``topicality.TopicScreen.judge_text``), named
    as the reader sees them in the chapter's list of topics, and only for the kinds of topic
    the review holds (``kinds``, its subjects'): the object's own words (R1) for a topic that
    is an object's name, and for a cross (another topic with an object after a dash); two
    shared words (R3) for a question or a framed context -- in Interpretation Research every
    such topic is a framing (``interpretation.FRAMINGS``) of a result, a research question, the
    study's goal, a category or a pair of objects -- and for a cross's part before the dash;
    the concept swap (R4) for any topic naming a concept of a family. Cross-review: the
    sentence claimed the object check for "a question about it", which never runs for a framed
    question about an object (a QUESTION, not a CROSS), and named the two-word check only for
    research questions."""
    if not topic_judged:
        return (
            "U každého zjištění AIA ověřila, že citovaná pasáž je doslova v zachyceném zdroji "
            "a že čísla tvrzení jsou v ní uvedena; ověřovací model posoudil, zda pasáž "
            "tvrzení podporuje. Neověřila však, zda se zdroj týká stejného jevu, populace, "
            "území a období jako tato studie. To posuzuje čtenář: u každého zjištění je proto "
            "uvedeno téma, pro které bylo hledáno, a doslovná citace, a u každého zdroje jeho "
            "typ podle domény."
        )
    checks = [
        "U každého zjištění AIA ověřila, že citovaná pasáž je doslova v zachyceném zdroji "
        "a že čísla tvrzení jsou v ní uvedena; ověřovací model posoudil, zda pasáž "
        "tvrzení podporuje. AIA také ověřila, že se zjištění týká tématu, pro které bylo "
        "hledáno, a to podle druhu tématu."
    ]
    if SubjectKind.OBJECT in kinds:
        checks.append(
            "U tématu, které je názvem objektu, ověřila, že citace nebo název zdroje obsahuje "
            "ta slova jeho názvu, kterými se liší od ostatních objektů této rešerše (je-li "
            "objekt v rešerši jediný, celý název)."
        )
    if SubjectKind.QUESTION in kinds:
        checks.append(
            "U tématu, které je otázkou nebo popisem hledaného kontextu (k výsledku otázky, "
            "výzkumné otázce, cíli studie, kategorii nebo dvojici objektů), ověřila, že "
            "tvrzení, citace a název zdroje dohromady sdílejí aspoň dvě jeho slova (zbývá-li "
            "jediné, to jedno); nepočítají se přitom slova, kterými AIA téma uvozuje, jména "
            "klienta, tázací slova a slova s číslicí."
        )
    if SubjectKind.CROSS in kinds:
        checks.append(
            "U tématu, které za pomlčkou připojuje název objektu, ověřila obojí: u objektu za "
            "pomlčkou slova jeho názvu, u části před pomlčkou její slova jako u otázky."
        )
    checks.append(
        "U každého tématu, které jmenuje pojem z pevně dané skupiny (druh bankovního "
        "produktu; objekt této rešerše, je-li jich v ní víc), ověřila také, že citace ani "
        "název zdroje nejmenují místo něj jiný pojem téže skupiny. "
        "Neověřila však, zda se zdroj týká stejné populace, území a období jako tato studie, "
        "ani zda shoda slov znamená shodu významu. "
        "To posuzuje čtenář: u každého zjištění je proto uvedeno téma, pro které bylo hledáno, "
        "a doslovná citace, a u každého zdroje jeho typ podle domény."
    )
    return " ".join(checks)


def _withheld(one: str, several: str, count: int) -> str:
    """Items whose text is withheld, said as how many there are and as what is known of them,
    that their text is not given: three withheld needs printed as one "další nedoložený
    podklad" (review 2), and "další" and "nedostupný" said what nobody knew (review 3).
    Counts print as "label: number" (chunk 4)."""
    return one if count == 1 else f"{several} (počet: {count})"


def _table_note(tables: str, approved: bool | None) -> str:
    """Where a source's type comes from, and whether the review's own pinned settings sign the
    table off (ADR 0022): a priced live route runs only once they do, so a fixed "not approved"
    contradicted every live review's record (review 3)."""
    if approved is None:
        return (
            f"Typ zdroje určuje tabulka zdrojů ({tables}) jen podle domény, nikoli podle obsahu; "
            "zda byla tabulka schválena, rešerše nezaznamenala (vznikla před připínáním "
            "nastavení)."
        )
    if approved:
        return (
            f"Typ zdroje určuje tabulka zdrojů ({tables}), kterou organizace schválila "
            "v nastavení Deep Research a rešerše si ji připnula, a to jen podle domény, nikoli "
            "podle obsahu."
        )
    return (
        f"Typ zdroje určuje navržená tabulka zdrojů ({tables}), kterou organizace dosud "
        "neschválila, a to jen podle domény, nikoli podle obsahu."
    )


def _norm(value: str) -> str:
    # The checked synthesis and brief may state the same gap with different punctuation.
    return re.sub(r"[\W_]+", " ", value.casefold()).strip()


@dataclass(frozen=True, slots=True)
class _Composed:
    """A composed report with literature and every source it was composed from."""

    document: ReportDocument
    run: Mapping[str, Any]
    sources: dict[str, Any]
    depends_on: tuple[str, ...]


def contextual_report(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    deep_research_run_id: str,
) -> ReportDocument:
    """Resolve both owned runs, verify their exact lineage and compose the document."""
    return _compose(
        session, scope, store, run_id=run_id, deep_research_run_id=deep_research_run_id
    ).document


def stored_contextual_report(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    deep_research_run_id: str,
    build: str = "",
) -> tuple[Artifact, bytes]:
    """The report with literature as a stored, unapproved draft artifact, and its bytes.

    Composed from the same verified sources every time; rendered and stored only when
    no valid artifact exists for exactly those sources. A later download of the same
    pair reads the stored bytes, and a person can approve that artifact (B2) -- a
    document rendered afresh on each download could never be the one approved.
    """
    from aia_core.infrastructure.report_docx.renderer import DocxRenderer

    composed = _compose(
        session, scope, store, run_id=run_id, deep_research_run_id=deep_research_run_id
    )
    artifacts = research_artifacts(session, scope, store)
    key = fingerprint(composed.sources)
    found = artifacts.find_reusable(
        project_id=composed.run["project_id"],
        stage_type=CONTEXT_REPORT_STAGE,
        artifact_type=CONTEXT_REPORT_ARTIFACT_TYPE,
        input_fingerprint=key,
    )
    drafts = prepared_drafts(
        artifacts, composed.run, run_id=run_id, deep_research_run_id=deep_research_run_id
    )
    if found is not None and drafts and drafts[-1].artifact_id == found.artifact_id:
        return found, artifacts.read(found.artifact_id)
    # Not stored, or stored but no longer the newest draft of this contract (its composed sources
    # changed and changed back; defensive, no known path reaches it): stored again, so the draft
    # just composed is the one every read names, its PDF included.
    data = DocxRenderer().render(composed.document)
    artifact, _created = artifacts.put(
        project_id=composed.run["project_id"],
        revision=int(composed.run["project_revision"]),
        stage_type=CONTEXT_REPORT_STAGE,
        artifact_type=CONTEXT_REPORT_ARTIFACT_TYPE,
        data=data,
        content_type=DocxRenderer.media_type,
        input_fingerprint=key,
        runtime_version=build,
        metadata={
            "run_id": run_id,
            "deep_research_run_id": deep_research_run_id,
            "report_kind": ReportKind.INTERNAL.value,
            "review_state": "DRAFT_UNAPPROVED",
            "report_contract": CONTEXT_REPORT_CONTRACT,
            "evidence_bundle_sha256": composed.sources["bundle"],
            **REVIEW_STAMP_RECORD,
        },
        depends_on=list(composed.depends_on),
        reuse=False,
    )
    return artifact, data


def prepared_drafts(
    artifacts: ArtifactRepository,
    run: Mapping[str, Any],
    *,
    run_id: str,
    deep_research_run_id: str,
    any_contract: bool = False,
) -> list[Artifact]:
    """Every valid draft of ``run``'s report with this review, oldest first: composed under the
    current contract, or with ``any_contract`` under any. :func:`stored_contextual_report` keeps
    the draft it composes the newest of the current contract; ``report_variants`` serves that
    one, else the newest of an earlier contract, said to be earlier (review 2: an earlier one
    read as current for ever; review 3: hiding it lost a prepared, possibly approved, report
    whenever composing it again is refused)."""
    return [
        a
        for a in artifacts.list_for_stage(
            project_id=str(run["project_id"]),
            revision=int(run["project_revision"]),
            stage_type=CONTEXT_REPORT_STAGE,
        )
        if a.artifact_type == CONTEXT_REPORT_ARTIFACT_TYPE
        and a.status is ArtifactStatus.VALID
        and a.metadata.get("run_id") == run_id
        and a.metadata.get("deep_research_run_id") == deep_research_run_id
        and (any_contract or a.metadata.get("report_contract") == CONTEXT_REPORT_CONTRACT)
    ]


def _compose(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    deep_research_run_id: str,
) -> _Composed:

    scope.require(Permission.EDIT_STUDY)
    run = ResearchRuns(session, scope).get(run_id)
    service = DeepResearchRuns(session, scope)
    deep_run = service.get(deep_research_run_id)
    if str(deep_run["status"]) != "COMPLETED":
        raise ReportCompositionRefused("Deep Research must be completed before export")
    # Whether the source table the chapter names is signed off is the review's own pinned record
    # (ADR 0022), never assumed either way; a pin that does not verify refuses the report.
    try:
        pinned = run_settings(dict(deep_run.get("metadata") or {}))
    except SettingsPinCorrupt as exc:
        raise ReportCompositionRefused("the review's settings pin does not verify") from exc
    tiers_approved = (
        None
        if pinned is None
        else pinned[SOURCE_TIERS_SETTING].origin is Origin.APPROVED
        and pinned.value(SOURCE_TIERS_SETTING) == "approved"
    )
    provenance = service.provenance(deep_research_run_id, store=store)
    lineage = service.resolve_lineage(deep_research_run_id, store=store)
    if (
        provenance.purpose is not DeepResearchPurpose.INTERPRETATION_RESEARCH
        or not isinstance(lineage, InterpretationLineage)
        or lineage.research_run_id != run_id
        or lineage.design.design_revision_id != run["metadata"]["design_revision_id"]
    ):
        raise ReportCompositionRefused("Deep Research does not interpret this research run")
    bundle = service.bundle(deep_research_run_id, store=store)
    if (
        bundle.design_revision_id != lineage.design.design_revision_id
        or bundle.design_revision != lineage.design.design_revision
    ):
        raise ReportCompositionRefused("Deep Research bundle has different design lineage")
    # A review merged before the topic rules (D4) is labelled by today's, over its own frozen
    # request: its subjects as sealed, the client terms its plan kept. USD 0, nothing re-run.
    # A plan that cannot be read leaves the labels out and says so.
    topics = todays_topic_rules(
        bundle, lambda: service.frozen_request(deep_research_run_id, store=store)
    )
    analysis = reconstruct_run(session, scope, store, run_id=run_id)
    first = analysis.modules[AnalysisModuleId.EXECUTIVE]
    if first.result is None:
        raise ReportCompositionRefused("executive analysis is incomplete")
    # The same run-derived chapters as the stored internal report (complete-study-report B1d).
    chapters = report_chapters(
        research_artifacts(session, scope, store),
        run,
        analysis,
        map_artifact_id=next(
            (
                (s.get("output") or {}).get("artifact_id")
                for s in run["steps"]
                if s["node_key"] == "sociomap"
            ),
            None,
        ),
        run_id=run_id,
    )
    names = ScopeRepository(session)
    meta = ReportMeta(
        kind=ReportKind.INTERNAL,
        title="Výzkumná zpráva s literární rešerší",
        subtitle=RESEARCH_SUBTITLE[origin_kind(first.record.labels.data_origin)],
        client_name=names.client_of_study(scope).name,
        study_name=names.get_study(scope).name,
        study_id=scope.study_id,
        issued_on=deep_run["created_at"].date(),
        revision=lineage.design.design_revision,
        method_status=first.result.method_status,
        classification=Classification.INTERNAL,
        identifiers=(
            ("Běh", run_id),
            ("Varianta", "s literární rešerší"),
            ("Deep Research", deep_research_run_id),
            # The seal is what the chapter prints and the bundle verifies; the artifact's
            # SHA-256 is the stored file. Two hashes, so two names a reader can tell apart.
            ("Pečeť balíčku", provenance.evidence_bundle_seal),
            ("Artefakt balíčku (SHA-256)", provenance.evidence_bundle_artifact_sha256),
            ("Kontrakt", CONTEXT_REPORT_CONTRACT),
        ),
    )
    document = compose_internal_report(
        analysis,
        meta,
        map_sections=chapters.maps,
        context_sections=literature_sections(
            bundle,
            research_run_id=deep_research_run_id,
            origin=origin_kind(first.record.labels.data_origin),
            tiers_approved=tiers_approved,
            topics=topics,
        ),
        question_tables=chapters.questions,
        design=chapters.design,
        method=chapters.method,
        research_question_gaps=chapters.gaps,
    )
    modules = [analysis.modules[m.module_id] for m in ANALYSIS_MODULES]
    return _Composed(
        document=document,
        run=run,
        sources={
            "contract": CONTEXT_REPORT_CONTRACT,
            "run_id": run_id,
            "deep_research_run_id": deep_research_run_id,
            "analysis": [m.artifact_sha256 for m in modules],
            "sociomap": chapters.map_sha256,
            "bundle": provenance.evidence_bundle_artifact_sha256,
            # The topic and document rules the chapter reads an older review by: a change of
            # either composes afresh.
            "topicality": TOPICALITY_VERSION,
            "documents": DOCUMENT_RULES_VERSION,
            # Composed without today's topic labels: another document than with them.
            **(
                {"topic_rules": TopicRulesUnread.PLAN_UNVERIFIED.value}
                if topics is TopicRulesUnread.PLAN_UNVERIFIED
                else {}
            ),
            "title": meta.title,
            "subtitle": meta.subtitle,
            "client": meta.client_name,
            "study": meta.study_name,
            "issued_on": meta.issued_on.isoformat(),
        },
        depends_on=(*(m.artifact_id for m in modules), chapters.map_artifact_id),
    )
