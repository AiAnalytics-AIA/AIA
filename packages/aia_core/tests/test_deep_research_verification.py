"""Verification in the agent-directed mode: independence, tracing, supersession, conflicts.

Plan ``deep-research-web-search.md`` §§ 8.3-8.5, chunk 12. Fictional publishers and
hosts (``*-dr.example``), recorded verifier answers, nothing sent anywhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

import pytest

from aia_core.domain.ai_contracts import schema_supports_strict, validate_structured_output
from aia_core.domain.deep_research.agents import AgentRole, agent_definition, prompt_for
from aia_core.domain.deep_research.contracts import (
    Channel,
    EvidenceItem,
    EvidenceType,
    Measure,
    MeasureBasis,
    QuarantineReason,
    RecommendedUse,
    SnapshotLink,
    SourceKind,
    evidence_id,
)
from aia_core.domain.deep_research.merge import (
    Candidate,
    SourceFacts,
    TrackEvidence,
    merge_evidence,
)
from aia_core.domain.deep_research.reputation import Publisher, RegisterStatus, ReputationRegister
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1, SourceClass, SourceTier
from aia_core.domain.deep_research.tracing import PrimaryStatus, TraceSource, trace_findings
from aia_core.domain.deep_research.triangulation import (
    ConflictCause,
    ConflictStatus,
    ConflictTolerance,
    IndependenceSource,
    MeasuredFinding,
    PeriodSpan,
    detect_conflicts,
    independence_groups,
    period_span,
    publisher_identity,
    resolve_conflict,
    resolve_requests,
)
from aia_core.domain.deep_research.verification import (
    SupersessionRule,
    review_candidates,
    supersessions,
    verifier_item,
)
from aia_core.domain.deep_research.verifier import (
    Attack,
    ClaimJudgement,
    ClaimVerdict,
    Verification,
)
from aia_core.domain.residency import DataClass

RETRIEVED = date(2026, 9, 27)
STAT = "https://stat-dr.example"
AGENCY = "https://pruzkum-dr.example"

REGISTER = ReputationRegister(
    version="test-register-1",
    status=RegisterStatus.PROPOSED,
    publishers=(
        Publisher(
            "Statistický úřad DR",
            ("SÚDR", "Statistical Office DR"),
            ("stat-dr.example",),
            SourceClass.OFFICIAL_STATISTICS,
            SourceTier.T1,
            ("datastat",),
        ),
        Publisher(
            "Agentura Průzkum DR",
            ("APDR",),
            ("pruzkum-dr.example",),
            SourceClass.INDUSTRY_RESEARCH,
            SourceTier.T3,
        ),
    ),
)

TABLE = SOURCE_TABLE_V1.extended(
    "test-verification-table",
    {
        "stat-dr.example": SourceClass.OFFICIAL_STATISTICS,
        "pruzkum-dr.example": SourceClass.INDUSTRY_RESEARCH,
        "zpravy-a-dr.example": SourceClass.MEDIA,
        "zpravy-b-dr.example": SourceClass.MEDIA,
        "zpravy-c-dr.example": SourceClass.MEDIA,
        "noviny-dr.example": SourceClass.MEDIA,
    },
)

SHARE = "podíl kupujících rostlinné nápoje"


def measure(value: float, **fields: Any) -> Measure:
    defaults: dict[str, Any] = {
        "unit": "%",
        "period": "Y2025",
        "geography": "CZ",
        "measure_name": SHARE,
    }
    return Measure(value=value, **{**defaults, **fields})


def item(
    url: str,
    claim: str,
    *,
    ref: str,
    measures: Sequence[Measure] = (),
    quote: str | None = None,
    span: tuple[int, int] | None = None,
) -> EvidenceItem:
    quote = quote or claim
    return EvidenceItem.model_validate(
        {
            "evidence_id": evidence_id("f" * 64, ref, quote, claim),
            "track_id": "DRT-W-q-000000000001",
            "subject_key": "q-000000000001",
            "channel": Channel.WEB,
            "source_kind": SourceKind.WEB_PAGE,
            "source_ref": ref,
            "source_url": url,
            "source_title": "t",
            "claim": claim,
            "quote": quote,
            "quote_span": span or (0, len(quote)),
            "evidence_type": EvidenceType.OTHER,
            "source_date": None,
            "geography": "",
            "population": "",
            "topics": (),
            "data_class": DataClass.CLASS_C_INTERNAL,
            "agent_outcome_overlap": False,
            "agent_recommended_use": RecommendedUse.CONTEXT_ONLY,
            "agent_source_quality": 0.5,
            "measures": tuple(measures),
        }
    )


def candidates(*items: EvidenceItem, published: date = date(2025, 6, 1)) -> list[Candidate]:
    track = TrackEvidence(
        track_id="DRT-W-q-000000000001",
        evidence=items,
        sources={
            i.source_ref: SourceFacts(
                ref=i.source_ref,
                kind=i.source_kind,
                url=i.source_url,
                published=published,
                retrieved=RETRIEVED,
            )
            for i in items
        },
    )
    merged = merge_evidence([track], questionnaire=(), table=TABLE)
    assert not merged.quarantined
    return list(merged.candidates)


def judge(
    verdict: ClaimVerdict = ClaimVerdict.SUPPORTED,
    *,
    evidence: str,
    attacks: Sequence[Attack] = (),
    superseded_by: str | None = None,
    reason: str = "posouzeno podle citace",
) -> ClaimJudgement:
    return ClaimJudgement(
        evidence_id=evidence,
        verdict=verdict,
        attacks=list(attacks),
        superseded_by=superseded_by,
        search=None,
        reason=reason,
    )


def traces_for(cands: Sequence[Candidate], texts: dict[str, str] | None = None) -> dict[str, Any]:
    items = [c.evidence for c in cands]
    sources = {
        i.source_ref: TraceSource(
            ref=i.source_ref, url=i.source_url, text=(texts or {}).get(i.source_ref, i.quote)
        )
        for i in items
    }
    records, _leads = trace_findings(items, sources, register=REGISTER)
    return {r.evidence_id: r for r in records}


def review(
    cands: Sequence[Candidate],
    verdicts: dict[str, ClaimJudgement] | None = None,
    *,
    texts: dict[str, str] | None = None,
    published: dict[str, date | None] | None = None,
) -> Any:
    verdicts = verdicts or {}
    judgements = {
        c.evidence.evidence_id: verdicts.get(c.evidence.evidence_id)
        or judge(evidence=c.evidence.evidence_id)
        for c in cands
    }
    groups = independence_groups(
        [
            IndependenceSource(
                ref=c.evidence.source_ref,
                publisher=publisher_identity(
                    url=c.evidence.source_url, source_ref=c.evidence.source_ref, register=REGISTER
                ),
                text=(texts or {}).get(c.evidence.source_ref, c.evidence.quote),
            )
            for c in cands
        ]
    )
    return review_candidates(
        cands,
        judgements,
        groups=groups,
        traces=traces_for(cands, texts),
        published=published or {},
        register=REGISTER,
    )


# --------------------------------------------------------------------------- #
# Publisher independence
# --------------------------------------------------------------------------- #

RELEASE = (
    "Agentura Průzkum DR dnes zveřejnila výsledky letošního průzkumu nákupního chování. "
    "Rostlinné nápoje podle průzkumu pravidelně kupuje čtyřicet pět procent domácností v "
    "Česku, nejčastěji ovesné a mandlové. Zájem roste zejména ve velkých městech a mezi "
    "mladšími lidmi, kteří nápoje kupují častěji než starší. Průzkum proběhl na jaře na "
    "reprezentativním vzorku domácností a agentura ho opakuje každý rok ve stejném termínu."
)
CLAIM = "Rostlinné nápoje pravidelně kupuje 45 % domácností v Česku."


def test_a_syndicated_press_release_counts_once() -> None:
    copies = {
        "SNP-a": f"Praha (ČTK) -- {RELEASE}",
        "SNP-b": f"{RELEASE} Zdroj: ČTK.",
        "SNP-c": f"Brno -- {RELEASE}",
        "SNP-d": "Vlastní šetření redakce Noviny DR mezi čtenáři přineslo jiný pohled na trh: "
        "rostlinné nápoje podle něj kupuje 45 % domácností v Česku, hlavně ve městech.",
    }
    found = candidates(
        item("https://zpravy-a-dr.example/a", CLAIM, ref="SNP-a"),
        item("https://zpravy-b-dr.example/b", CLAIM + " ", ref="SNP-b"),
        item(
            "https://zpravy-c-dr.example/c", "Rostlinné nápoje kupuje 45 % domácností.", ref="SNP-c"
        ),
        item(
            "https://noviny-dr.example/d",
            "Rostlinné nápoje kupuje 45 % domácností v Česku.",
            ref="SNP-d",
        ),
    )
    by_ref = {c.evidence.source_ref: c for c in found}
    # The merge counts every other site as a confirmation: three for each copy.
    assert len(by_ref["SNP-a"].confirmations) == 3
    outcome = review(found, texts=copies)
    accepted = {a.evidence.source_ref: a for a in outcome.accepted}
    # Three sites carrying one release are one confirmation; the newspaper's own survey another.
    assert len(accepted["SNP-d"].confirmations) == 1
    assert accepted["SNP-d"].confirmations[0] in {
        by_ref[r].evidence.evidence_id for r in ("SNP-a", "SNP-b", "SNP-c")
    }
    for copy in ("SNP-a", "SNP-b", "SNP-c"):
        assert accepted[copy].confirmations == (by_ref["SNP-d"].evidence.evidence_id,)
    # Confidence is the merge's formula over independent confirmations only.
    assert accepted["SNP-a"].confidence == pytest.approx(
        by_ref["SNP-a"].score.score + 0.1, abs=1e-9
    )
    assert accepted["SNP-a"].confidence < by_ref["SNP-a"].confidence

    groups = independence_groups(
        [
            IndependenceSource(
                ref=r,
                publisher=publisher_identity(
                    url=by_ref[r].evidence.source_url, source_ref=r, register=REGISTER
                ),
                text=t,
            )
            for r, t in copies.items()
        ]
    )
    assert groups["SNP-a"] == groups["SNP-b"] == groups["SNP-c"] != groups["SNP-d"]
    assert groups["SNP-a"].syndicated and not groups["SNP-d"].syndicated


def test_two_pages_of_one_publisher_are_one_confirmation() -> None:
    found = candidates(
        item(f"{STAT}/tabulka", CLAIM, ref="SNP-1"),
        item("https://www.stat-dr.example/zprava", CLAIM + " ", ref="SNP-2"),
        item("https://noviny-dr.example/d", CLAIM + "  ", ref="SNP-3"),
    )
    texts = {"SNP-1": "Tabulka 3 domácnosti.", "SNP-2": "Zpráva o spotřebě.", "SNP-3": "Jiný text."}
    accepted = {a.evidence.source_ref: a for a in review(found, texts=texts).accepted}
    assert len(accepted["SNP-3"].confirmations) == 1
    assert len(accepted["SNP-1"].confirmations) == 1


def test_an_unregistered_host_is_its_registrable_domain() -> None:
    one = publisher_identity(
        url="https://www.a.zpravy-dr.example/x", source_ref="S", register=REGISTER
    )
    two = publisher_identity(url="https://b.zpravy-dr.example/y", source_ref="S", register=REGISTER)
    assert one.key == two.key == "host:zpravy-dr.example" and not one.registered
    stat = publisher_identity(
        url="https://data.stat-dr.example/t", source_ref="S", register=REGISTER
    )
    assert stat.registered and stat.name == "Statistický úřad DR"
    knowledge = publisher_identity(url=None, source_ref="KNW-ab12@3", register=REGISTER)
    assert knowledge.key == "knowledge:KNW-ab12"


# --------------------------------------------------------------------------- #
# Primary tracing
# --------------------------------------------------------------------------- #

NEWS = (
    "Trh rostlinných nápojů roste. Podle SÚDR kupuje rostlinné nápoje 45 % domácností v Česku. "
    "Podrobná čísla jsou v tabulce spotřeby úřadu."
)


def _news_item() -> EvidenceItem:
    quote = "kupuje rostlinné nápoje 45 % domácností v Česku"
    start = NEWS.index(quote)
    return item(
        "https://noviny-dr.example/trh",
        "Rostlinné nápoje kupuje 45 % domácností v Česku.",
        ref="SNP-news",
        quote=quote,
        span=(start, start + len(quote)),
        measures=[measure(45, population="HOUSEHOLDS")],
    )


def test_a_secondary_finding_raises_a_lead_to_its_publisher_with_the_link() -> None:
    news = _news_item()
    link = SnapshotLink(kind="anchor", url=f"{STAT}/tabulka-2025", text="tabulce spotřeby")
    records, leads = trace_findings(
        [news],
        {"SNP-news": TraceSource(ref="SNP-news", url=news.source_url, text=NEWS, links=(link,))},
        register=REGISTER,
    )
    [record] = records
    assert record.status is PrimaryStatus.SECONDARY and record.cited == ("Statistický úřad DR",)
    assert record.traced_to is None
    [lead] = leads
    assert lead.lead_id == record.lead_id and lead.evidence_id == news.evidence_id
    assert lead.publisher == "Statistický úřad DR" and lead.hosts == ("stat-dr.example",)
    assert lead.data_interfaces == ("datastat",)
    assert lead.link == f"{STAT}/tabulka-2025"  # ladder rung 1: the page links it
    assert "45 %" in lead.need


def test_a_link_in_the_quote_s_context_cites_its_publisher() -> None:
    text = "Rostlinné nápoje kupuje 45 % domácností v Česku, uvádí tabulka spotřeby."
    quote = "Rostlinné nápoje kupuje 45 % domácností v Česku"
    news = item("https://noviny-dr.example/t", quote + ".", ref="SNP-n", quote=quote)
    link = SnapshotLink(kind="anchor", url=f"{STAT}/t", text="tabulka spotřeby")
    unrelated = SnapshotLink(kind="anchor", url=f"{AGENCY}/x", text="jiný článek")
    records, leads = trace_findings(
        [news],
        {
            "SNP-n": TraceSource(
                ref="SNP-n", url=news.source_url, text=text, links=(unrelated, link)
            )
        },
        register=REGISTER,
    )
    assert records[0].status is PrimaryStatus.SECONDARY
    assert records[0].cited == ("Statistický úřad DR",) and leads[0].link == f"{STAT}/t"


def test_a_secondary_finding_is_traced_to_its_primary_when_the_figure_is_captured() -> None:
    news = _news_item()
    table = item(
        f"{STAT}/tabulka-2025",
        "Rostlinné nápoje kupuje 45 % domácností v Česku.",
        ref="SNP-stat",
        measures=[measure(45, population="HOUSEHOLDS")],
    )
    other = item(
        f"{STAT}/jina",
        "Ovesné nápoje kupuje 30 % domácností v Česku.",
        ref="SNP-other",
        measures=[measure(30, population="HOUSEHOLDS")],
    )
    sources = {
        "SNP-news": TraceSource(ref="SNP-news", url=news.source_url, text=NEWS),
        "SNP-stat": TraceSource(ref="SNP-stat", url=table.source_url, text=table.quote),
        "SNP-other": TraceSource(ref="SNP-other", url=other.source_url, text=other.quote),
    }
    records, leads = trace_findings([news, other, table], sources, register=REGISTER)
    by_id = {r.evidence_id: r for r in records}
    assert by_id[news.evidence_id].status is PrimaryStatus.SECONDARY
    assert by_id[news.evidence_id].traced_to == table.evidence_id
    assert by_id[table.evidence_id].status is PrimaryStatus.PRIMARY
    assert leads == ()


def test_an_unknown_publisher_or_no_register_is_undetermined_never_primary() -> None:
    page = item("https://noviny-dr.example/x", CLAIM, ref="SNP-x")
    sources = {"SNP-x": TraceSource(ref="SNP-x", url=page.source_url, text=page.quote)}
    [record], _ = trace_findings([page], sources, register=REGISTER)
    assert record.status is PrimaryStatus.UNDETERMINED
    stat = item(f"{STAT}/x", CLAIM, ref="SNP-s")
    [record], leads = trace_findings(
        [stat], {"SNP-s": TraceSource(ref="SNP-s", url=stat.source_url, text=NEWS)}, register=None
    )
    assert record.status is PrimaryStatus.UNDETERMINED and leads == ()


def test_an_inflected_name_the_register_does_not_list_is_not_read() -> None:
    text = "Podle Statistického úřadu DR kupuje rostlinné nápoje 45 % domácností."
    page = item("https://noviny-dr.example/x", text, ref="SNP-x")
    [record], _ = trace_findings(
        [page],
        {"SNP-x": TraceSource(ref="SNP-x", url=page.source_url, text=text)},
        register=REGISTER,
    )
    assert record.status is PrimaryStatus.UNDETERMINED


# --------------------------------------------------------------------------- #
# Supersession
# --------------------------------------------------------------------------- #


def test_a_newer_figure_from_the_same_publisher_supersedes() -> None:
    old = item(
        f"{STAT}/2023",
        "V roce 2023 kupovalo rostlinné nápoje 38 % domácností v Česku.",
        ref="SNP-2023",
        measures=[measure(38, period="Y2023", population="HOUSEHOLDS")],
    )
    new = item(
        f"{STAT}/2025",
        "V roce 2025 kupuje rostlinné nápoje 45 % domácností v Česku.",
        ref="SNP-2025",
        measures=[measure(45, period="Y2025", population="HOUSEHOLDS")],
    )
    elsewhere = item(
        f"{AGENCY}/2026",
        "V roce 2026 kupuje rostlinné nápoje 47 % domácností v Česku.",
        ref="SNP-ag",
        measures=[measure(47, period="Y2026", population="HOUSEHOLDS")],
    )
    outcome = review(candidates(old, new, elsewhere))
    accepted = {a.evidence.evidence_id for a in outcome.accepted}
    assert accepted == {new.evidence_id, elsewhere.evidence_id}  # another publisher's is not newer
    [q] = outcome.quarantined
    assert q.evidence_id == old.evidence_id and q.reason is QuarantineReason.SUPERSEDED
    [s] = outcome.supersessions
    assert s.superseded_by == (new.evidence_id,) and s.rule is SupersessionRule.NEWER_PERIOD


def test_a_final_figure_supersedes_the_preliminary_one_for_the_same_period() -> None:
    prelim = item(
        f"{STAT}/predbezne",
        "Předběžně spotřeba v roce 2025 činila 41 mil. litrů.",
        ref="SNP-p",
        measures=[
            measure(
                41,
                unit="l",
                scale=1_000_000,
                measure_name="spotřeba",
                basis=MeasureBasis.PRELIMINARY,
            )
        ],
    )
    final = item(
        f"{STAT}/konecne",
        "Spotřeba v roce 2025 činila 42 mil. litrů.",
        ref="SNP-f",
        measures=[
            measure(
                42, unit="l", scale=1_000_000, measure_name="spotřeba", basis=MeasureBasis.ACTUAL
            )
        ],
    )
    outcome = review(candidates(prelim, final))
    assert [a.evidence.evidence_id for a in outcome.accepted] == [final.evidence_id]
    assert outcome.supersessions[0].rule is SupersessionRule.REVISED
    # A preliminary figure never supersedes the final one.
    found = supersessions(
        [prelim, final],
        publishers={prelim.evidence_id: "p", final.evidence_id: "p"},
        published={},
        eligible=frozenset({prelim.evidence_id, final.evidence_id}),
    )
    assert set(found) == {prelim.evidence_id}


def test_a_superseding_figure_must_itself_be_verified() -> None:
    old = item(f"{STAT}/a", "Old 38 %.", ref="SNP-a", measures=[measure(38, period="Y2023")])
    new = item(f"{STAT}/b", "New 45 %.", ref="SNP-b", measures=[measure(45, period="Y2025")])
    found = candidates(old, new)
    outcome = review(
        found,
        {new.evidence_id: judge(ClaimVerdict.UNSUPPORTED, evidence=new.evidence_id)},
    )
    assert [a.evidence.evidence_id for a in outcome.accepted] == [old.evidence_id]
    assert outcome.supersessions == ()


def test_a_finding_with_several_figures_is_superseded_only_when_every_one_is() -> None:
    change = item(
        f"{STAT}/vyvoj",
        "Podíl vzrostl z 38 % v roce 2023 na 45 % v roce 2025.",
        ref="SNP-c",
        measures=[measure(38, period="Y2023"), measure(45, period="Y2025")],
    )
    latest = item(f"{STAT}/2025", "V roce 2025 je to 45 %.", ref="SNP-l", measures=[measure(45)])
    outcome = review(candidates(change, latest))
    assert {a.evidence.evidence_id for a in outcome.accepted} == {
        change.evidence_id,
        latest.evidence_id,
    }


def test_the_verifier_proposes_superseded_and_code_decides() -> None:
    # Unnamed measures: code cannot match the series, the verifier's word can stand.
    old = item(
        f"{STAT}/a", "Starší údaj 38 %.", ref="SNP-a", measures=[measure(38, measure_name=None)]
    )
    new = item(
        f"{STAT}/b", "Novější údaj 45 %.", ref="SNP-b", measures=[measure(45, measure_name=None)]
    )
    other = item(
        f"{AGENCY}/c", "Údaj agentury 47 %.", ref="SNP-c", measures=[measure(47, measure_name=None)]
    )
    found = candidates(old, new, other)
    ok = review(
        found,
        {
            old.evidence_id: judge(
                ClaimVerdict.SUPERSEDED,
                evidence=old.evidence_id,
                superseded_by=new.evidence_id,
                attacks=[Attack.NEWER_FIGURE],
            )
        },
    )
    [q] = ok.quarantined
    assert (
        q.reason is QuarantineReason.SUPERSEDED
        and ok.supersessions[0].rule is SupersessionRule.VERIFIER
    )
    # Another publisher's figure, or none named: the verdict cannot stand; nothing is accepted.
    for by in (other.evidence_id, None, "EV-0000000000000000"):
        refused = review(
            found,
            {
                old.evidence_id: judge(
                    ClaimVerdict.SUPERSEDED, evidence=old.evidence_id, superseded_by=by
                )
            },
        )
        [q] = refused.quarantined
        assert q.reason is QuarantineReason.UNVERIFIED and "cannot accept" in q.detail
    # An older figure named as the newer one is refused by its measures.
    dated_old = item(
        f"{STAT}/x", "2023: 38 %.", ref="SNP-x", measures=[measure(38, period="Y2023")]
    )
    dated_new = item(
        f"{STAT}/y", "2025: 45 %.", ref="SNP-y", measures=[measure(45, period="Y2025")]
    )
    pair = candidates(dated_old, dated_new)
    wrong = review(
        pair,
        {
            dated_new.evidence_id: judge(
                ClaimVerdict.SUPERSEDED,
                evidence=dated_new.evidence_id,
                superseded_by=dated_old.evidence_id,
            )
        },
    )
    by_id = {q.evidence_id: q for q in wrong.quarantined}
    assert by_id[dated_new.evidence_id].reason is QuarantineReason.UNVERIFIED
    assert "older period" in by_id[dated_new.evidence_id].detail


# --------------------------------------------------------------------------- #
# The verifier's verdicts
# --------------------------------------------------------------------------- #


def test_an_overstated_generalisation_is_caught() -> None:
    claim = "Rostlinné nápoje kupuje 45 % všech dospělých lidí v Česku."
    quote = "kupuje rostlinné nápoje 45 % domácností"
    overstated = item(f"{STAT}/t", claim, ref="SNP-t", quote=quote)
    [candidate] = candidates(overstated)
    outcome = review(
        [candidate],
        {
            overstated.evidence_id: judge(
                ClaimVerdict.OVERSTATED,
                evidence=overstated.evidence_id,
                attacks=[Attack.OVERSTATED_GENERALISATION, Attack.WRONG_ATTRIBUTE],
                reason="citace mluví o domácnostech, tvrzení o všech dospělých",
            )
        },
    )
    assert outcome.accepted == ()
    [q] = outcome.quarantined
    assert q.reason is QuarantineReason.OVERSTATED_BY_VERIFIER
    assert "overstated_generalisation" in q.detail and "domácnostech" in q.detail


def test_a_candidate_without_a_judgement_is_unverified_never_accepted() -> None:
    lone = item(f"{STAT}/t", CLAIM, ref="SNP-t")
    [candidate] = candidates(lone)
    groups = independence_groups([])
    outcome = review_candidates(
        [candidate],
        {},
        groups=groups,
        traces=traces_for([candidate]),
        published={},
        register=REGISTER,
    )
    assert outcome.accepted == () and outcome.quarantined[0].reason is QuarantineReason.UNVERIFIED


def test_a_proposed_search_is_a_lead_with_its_publisher_resolved_by_the_register() -> None:
    lone = item(f"{AGENCY}/t", CLAIM, ref="SNP-t")
    [candidate] = candidates(lone)
    judgement = ClaimJudgement.model_validate(
        {
            "evidence_id": lone.evidence_id,
            "verdict": "supported",
            "attacks": ["newer_figure"],
            "superseded_by": None,
            "search": {
                "query": "podíl domácností rostlinné nápoje 2026",
                "publisher": "SÚDR",
                "why": "novější údaj",
            },
            "reason": "podporuje",
        }
    )
    outcome = review([candidate], {lone.evidence_id: judgement})
    [lead] = outcome.verifier_leads
    assert lead.publisher == "Statistický úřad DR" and lead.publisher_named == "SÚDR"


def test_what_the_verifier_is_shown_carries_no_agent_reasoning() -> None:
    a = item(f"{STAT}/a", "38 %.", ref="SNP-a", measures=[measure(38, period="Y2023")])
    b = item(f"{STAT}/b", "45 %.", ref="SNP-b", measures=[measure(45)])
    found = candidates(a, b)
    traces = traces_for(found)
    shown = verifier_item(
        found[0], excerpt="okolí", trace=traces[found[0].evidence.evidence_id], related=found[1:]
    )
    assert set(shown) == {
        "evidence_id",
        "claim",
        "quote",
        "excerpt",
        "measures",
        "source",
        "related",
    }
    assert shown["measures"][0]["period"] == "Y2023" and "denominator" not in shown["measures"][0]
    assert shown["source"]["primary"] == "primary"
    assert [r["evidence_id"] for r in shown["related"]] == [found[1].evidence.evidence_id]
    assert "agent_source_quality" not in str(shown)


def test_the_independent_verifier_is_its_own_critic_with_a_strict_contract() -> None:
    agent = agent_definition(AgentRole.INDEPENDENT_VERIFIER, max_output_tokens=2048)
    assert agent.agent_id == "aia.deep_research.independent_verifier"
    assert agent.output_contract is Verification
    assert schema_supports_strict(agent.schema)
    text = prompt_for(AgentRole.INDEPENDENT_VERIFIER)
    assert all(f"'{v.value}'" in text for v in ClaimVerdict)
    assert all(f"'{a.value}'" in text for a in Attack)
    good = {
        "judgements": [
            {
                "evidence_id": "EV-1",
                "verdict": "superseded",
                "attacks": ["newer_figure"],
                "superseded_by": "EV-2",
                "search": None,
                "reason": "novější údaj",
            }
        ]
    }
    assert validate_structured_output(Verification, structured=good, text="").ok
    for bad in ({"verdict": "maybe"}, {"attacks": ["guess"]}, {"invented": 1}):
        payload = {"judgements": [{**good["judgements"][0], **bad}]}
        assert not validate_structured_output(Verification, structured=payload, text="").ok, bad


# --------------------------------------------------------------------------- #
# Conflicts and resolve tracks
# --------------------------------------------------------------------------- #


def finding(
    eid: str, value: float, publisher: str, *, primary: bool = False, **m: Any
) -> MeasuredFinding:
    return MeasuredFinding(
        evidence_id=eid,
        publisher=f"host:{publisher}",
        publisher_name=publisher,
        primary=primary,
        source_url=f"https://{publisher}/x",
        measure=measure(value, **m),
    )


def test_values_within_rounding_are_one_figure_not_a_conflict() -> None:
    assert detect_conflicts([finding("EV-a", 45, "a"), finding("EV-b", 45.4, "b")]) == ()
    assert len(detect_conflicts([finding("EV-a", 45, "a"), finding("EV-b", 45.6, "b")])) == 1
    assert (
        len(
            detect_conflicts(
                [finding("EV-a", 45.0, "a"), finding("EV-b", 45.4, "b")],
                ConflictTolerance(relative=0.01),
            )
        )
        == 0
    )


def test_figures_of_different_measures_places_or_periods_are_not_compared() -> None:
    base = finding("EV-a", 45, "a")
    for other in (
        finding("EV-b", 30, "b", measure_name="jiný ukazatel"),
        finding("EV-b", 30, "b", geography="CZ-PR"),
        finding("EV-b", 30, "b", period="Y2023"),
        finding("EV-b", 30, "b", measure_name=None),
        finding("EV-b", 30, "b", period="Q2"),
    ):
        assert detect_conflicts([base, other]) == (), other


def test_a_conflict_explained_by_the_measures_needs_no_resolve_track() -> None:
    [definition] = detect_conflicts(
        [
            finding("EV-a", 45, "a", population="HOUSEHOLDS"),
            finding("EV-b", 38, "b", population="PERSONS"),
        ]
    )
    assert (definition.cause, definition.status) == (
        ConflictCause.DEFINITION,
        ConflictStatus.EXPLAINED,
    )
    [period] = detect_conflicts(
        [finding("EV-a", 45, "a", period="Y2024"), finding("EV-b", 38, "b", period="Y2024/2025")]
    )
    assert period.cause is ConflictCause.PERIOD
    [basis] = detect_conflicts(
        [
            finding("EV-a", 45, "a", basis=MeasureBasis.ESTIMATE),
            finding("EV-b", 38, "b", basis=MeasureBasis.ACTUAL),
        ]
    )
    assert basis.cause is ConflictCause.BASIS
    assert resolve_requests([definition, period, basis]) == ()


def test_a_conflict_is_resolved_to_a_definition_difference_by_its_primary_sources() -> None:
    news = finding("EV-news", 45, "noviny-dr.example")
    blog = finding("EV-blog", 38, "zpravy-a-dr.example")
    [conflict] = detect_conflicts([news, blog])
    assert (conflict.cause, conflict.status) == (ConflictCause.UNEXPLAINED, ConflictStatus.OPEN)
    [request] = resolve_requests([conflict])
    assert request.conflict_id == conflict.conflict_id
    assert [s.evidence_id for s in request.sides] == ["EV-blog", "EV-news"]
    assert "45 %" in request.objective and "38 %" in request.objective
    assert "neprůměruj" in request.wanted

    # The resolve track brings back each value's primary, with the population each states.
    primaries = [
        finding("EV-stat", 45, "stat-dr.example", primary=True, population="HOUSEHOLDS"),
        finding("EV-agency", 38, "pruzkum-dr.example", primary=True, population="PERSONS"),
        finding("EV-noise", 52, "stat-dr.example", primary=True, population="HOUSEHOLDS"),
    ]
    resolution = resolve_conflict(conflict, primaries)
    assert resolution.status is ConflictStatus.RESOLVED
    assert resolution.cause is ConflictCause.DEFINITION
    assert resolution.primaries == ("EV-agency", "EV-stat")
    assert "HOUSEHOLDS" in resolution.detail and "PERSONS" in resolution.detail


def test_a_conflict_no_primary_explains_stays_a_conflict() -> None:
    [conflict] = detect_conflicts([finding("EV-a", 45, "a"), finding("EV-b", 38, "b")])
    resolution = resolve_conflict(conflict, [finding("EV-s", 45, "s", primary=True)])
    assert resolution.status is ConflictStatus.UNRESOLVED
    assert resolution.primaries == (None, "EV-s") or resolution.primaries == ("EV-s", None)
    assert "no primary source was found" in resolution.detail


def test_conflicts_among_accepted_findings_are_detected_in_the_review() -> None:
    a = item("https://noviny-dr.example/a", "Kupuje 45 %.", ref="SNP-a", measures=[measure(45)])
    b = item(f"{AGENCY}/b", "Kupuje 38 %.", ref="SNP-b", measures=[measure(38)])
    outcome = review(candidates(a, b))
    [conflict] = outcome.conflicts
    assert conflict.status is ConflictStatus.OPEN
    assert [r.conflict_id for r in outcome.resolve_requests] == [conflict.conflict_id]


@pytest.mark.parametrize(
    ("text", "span"),
    [
        ("Y2025", PeriodSpan(2025 * 12, 2025 * 12 + 11)),
        ("2025", PeriodSpan(2025 * 12, 2025 * 12 + 11)),
        ("2024/25", PeriodSpan(2024 * 12, 2025 * 12 + 11)),
        ("Y2024/2025", PeriodSpan(2024 * 12, 2025 * 12 + 11)),
        ("2025-Q2", PeriodSpan(2025 * 12 + 3, 2025 * 12 + 5)),
        ("2025-H2", PeriodSpan(2025 * 12 + 6, 2025 * 12 + 11)),
        ("2025-03", PeriodSpan(2025 * 12 + 2, 2025 * 12 + 2)),
        ("Q2", None),
        ("M03", None),
        ("letos", None),
        (None, None),
    ],
)
def test_a_period_is_placed_only_when_its_year_is_stated(
    text: str | None, span: PeriodSpan | None
) -> None:
    assert period_span(text) == span
