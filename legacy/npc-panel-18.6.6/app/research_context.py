"""Dual-agent Research Context for NPC Panel.

Contract
--------
* OFF means OFF: no OpenAI/Anthropic research call is made.
* ON uses the globally selected provider (OpenAI or Anthropic) fail-closed.
* Dual-agent behavior is retained only for injected test fixtures / historical comparison.
* Their output is evidence, never respondent data and never an automatic calibration.
* Near-target outcome evidence is quarantined to prevent benchmark/survey leakage.
* Only evidence passing deterministic merge rules is converted to prompt context.
* Every research run is persisted with provider, model, URLs, timestamps and SHA-256.

The live provider calls intentionally use each provider's server-side web-search tool.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from runtime_config import (
    DEFAULT_ANTHROPIC_RESEARCH_MODEL,
    DEFAULT_OPENAI_RESEARCH_MODEL,
)

SAFE_USE = "context_only"
EXCLUDE_USE = "exclude_target_leakage"


@dataclass
class ResearchConfig:
    enabled: bool = False
    topic: str = ""
    openai_model: str = DEFAULT_OPENAI_RESEARCH_MODEL
    anthropic_model: str = DEFAULT_ANTHROPIC_RESEARCH_MODEL
    max_sources_per_agent: int = 8
    strict_consensus: bool = True
    allow_single_agent_primary: bool = True
    allow_degraded_single_agent: bool = True
    max_context_blocks: int = 8

    @classmethod
    def from_obj(cls, obj: Any) -> "ResearchConfig":
        if obj in (None, False):
            return cls(enabled=False)
        if obj is True:
            return cls(enabled=True)
        if not isinstance(obj, dict):
            raise TypeError("research_context musi byt boolean nebo object")
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in obj.items() if k in known})


@dataclass
class EvidenceItem:
    claim: str
    why_relevant: str
    source_title: str
    source_url: str
    source_date: str | None = None
    evidence_type: str = "other"  # primary_source | peer_reviewed | official_report | other
    geography: str = ""
    population: str = ""
    topics: list[str] = field(default_factory=list)
    source_quality: float = 0.5
    outcome_overlap: bool = False
    recommended_use: str = SAFE_USE
    agent: str = ""


@dataclass
class AgentResearch:
    agent: str
    model: str
    topic: str
    searched_at: str
    findings: list[EvidenceItem]
    error: str | None = None


@dataclass
class ResearchBundle:
    enabled: bool
    topic: str
    created_at: str
    agents: list[AgentResearch]
    accepted: list[dict[str, Any]]
    quarantined: list[dict[str, Any]]
    config: dict[str, Any]
    quality_status: str = "NO_RESEARCH"
    sha256: str = ""

    def finalize_hash(self) -> "ResearchBundle":
        payload = asdict(self)
        payload["sha256"] = ""
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.sha256 = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical_url(url: str) -> str:
    try:
        p = urlsplit(str(url).strip())
        if p.scheme not in {"http", "https"} or not p.netloc:
            return ""
        host = p.netloc.lower().removeprefix("www.")
        path = re.sub(r"/$", "", p.path or "")
        return urlunsplit((p.scheme.lower(), host, path, p.query, ""))
    except Exception:
        return ""


def _tokens(s: str) -> set[str]:
    s = re.sub(r"[^a-z0-9á-ž]+", " ", str(s).lower())
    stop = {"a", "i", "v", "ve", "na", "se", "je", "jsou", "pro", "do", "z", "ze", "že", "to", "u"}
    return {x for x in s.split() if len(x) >= 4 and x not in stop}


def _similarity(a: str, b: str) -> float:
    x, y = _tokens(a), _tokens(b)
    if not x or not y:
        return 0.0
    return len(x & y) / len(x | y)


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    if not m:
        m = re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise ValueError("research agent nevratil JSON object")
    return json.loads(m.group(1))


def _schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "why_relevant": {"type": "string"},
                        "source_title": {"type": "string"},
                        "source_url": {"type": "string"},
                        "source_date": {"type": ["string", "null"]},
                        "evidence_type": {"type": "string"},
                        "geography": {"type": "string"},
                        "population": {"type": "string"},
                        "topics": {"type": "array", "items": {"type": "string"}},
                        "source_quality": {"type": "number", "minimum": 0, "maximum": 1},
                        "outcome_overlap": {"type": "boolean"},
                        "recommended_use": {"type": "string"},
                    },
                    "required": [
                        "claim", "why_relevant", "source_title", "source_url",
                        "source_date", "evidence_type", "geography", "population",
                        "topics", "source_quality", "outcome_overlap", "recommended_use",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["findings"],
        "additionalProperties": False,
    }


def _research_prompt(topic: str, questions: list[dict[str, Any]], max_sources: int) -> str:
    qtext = "\n".join(f"- {q.get('id')}: {q.get('text')}" for q in questions)
    return f"""You are one of TWO INDEPENDENT evidence researchers for a Czech synthetic survey system.
Research topic: {topic or 'infer from the survey questions below'}
Survey questions:\n{qtext}

Find at most {max_sources} high-quality, relevant sources/studies that provide BACKGROUND CONTEXT needed to interpret these questions. Cover the Czech Republic first, then deliberately search relevant foreign markets/analogues and peer-reviewed or high-quality academic/industry studies. Include market/category structure, consumer behavior and motivations, barriers, price/value sensitivity where relevant, channels/media, competition/alternatives, segmentations, cultural or regulatory context, documented mechanisms, contradictions and important evidence gaps. Prefer primary/official sources, peer-reviewed studies and reputable research institutions. Search independently; do not assume what the other agent finds.

The goal is a genuinely deep topic/market evidence scan, not a shallow list of generic sources. When Czech evidence is weak, say so and use the best foreign analogue explicitly labelled as such.

CRITICAL ANTI-LEAKAGE RULE:
If a source directly reports the answer, prevalence, vote share, purchase intent, mean score, or an almost identical outcome to ANY survey question above, keep it in the research log but set outcome_overlap=true and recommended_use='exclude_target_leakage'. Such evidence MUST NOT be injected into respondent prompts. Do not turn published survey outcomes into synthetic respondent attributes.

Allowed context is factual environment/mechanism/background (e.g. regulation, price level, documented mechanism, market structure, eligibility definitions), not the target answer. Paraphrase; do not copy long source passages.

For every finding return source URL, title, date if known, geography/population, evidence type, topics, source_quality 0..1, outcome_overlap, and recommended_use ('context_only' or 'exclude_target_leakage'). Return only the requested JSON object."""


def _coerce_findings(obj: dict[str, Any], agent: str) -> list[EvidenceItem]:
    out: list[EvidenceItem] = []
    for x in obj.get("findings", []) if isinstance(obj, dict) else []:
        try:
            url = _canonical_url(x.get("source_url", ""))
            if not url:
                continue
            use = str(x.get("recommended_use", SAFE_USE))
            overlap = bool(x.get("outcome_overlap", False))
            if overlap:
                use = EXCLUDE_USE
            out.append(EvidenceItem(
                claim=str(x.get("claim", "")).strip()[:1200],
                why_relevant=str(x.get("why_relevant", "")).strip()[:600],
                source_title=str(x.get("source_title", "")).strip()[:300],
                source_url=url,
                source_date=(str(x.get("source_date"))[:40] if x.get("source_date") else None),
                evidence_type=str(x.get("evidence_type", "other")).strip().lower(),
                geography=str(x.get("geography", "")).strip()[:100],
                population=str(x.get("population", "")).strip()[:160],
                topics=[str(t).strip() for t in (x.get("topics") or []) if str(t).strip()][:8],
                source_quality=max(0.0, min(1.0, float(x.get("source_quality", 0.5)))),
                outcome_overlap=overlap,
                recommended_use=use,
                agent=agent,
            ))
        except Exception:
            continue
    return [x for x in out if x.claim and x.source_title]


def _openai_research(topic: str, questions: list[dict[str, Any]], cfg: ResearchConfig) -> AgentResearch:
    searched = _now()
    try:
        from provider_auth import create_openai_client
        from ai_router import _openai_repair_model
        client = create_openai_client(max_retries=2)
        prompt = _research_prompt(topic, questions, cfg.max_sources_per_agent)
        model_id = _openai_repair_model(client, str(cfg.openai_model or "gpt-5.6"))
        r = client.responses.create(
            model=model_id,
            input=prompt,
            tools=[{"type": "web_search", "search_context_size": "high"}],
            text={"format": {"type": "json_schema", "name": "npc_research_evidence",
                             "schema": _schema(), "strict": True}},
            store=False,
        )
        obj = _extract_json(getattr(r, "output_text", ""))
        return AgentResearch("openai", str(getattr(r,"model",None) or model_id), topic, searched,
                             _coerce_findings(obj, "openai"))
    except Exception as e:
        return AgentResearch("openai", cfg.openai_model, topic, searched, [], str(e)[:500])


def _anthropic_text(response: Any) -> str:
    parts = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "\n".join(parts)


def _anthropic_research(topic: str, questions: list[dict[str, Any]], cfg: ResearchConfig) -> AgentResearch:
    searched = _now()
    try:
        from provider_auth import create_anthropic_client, resolve_available_anthropic_model
        client = create_anthropic_client(max_retries=3)
        prompt = _research_prompt(topic, questions, cfg.max_sources_per_agent)
        tools = [{"type": "web_search_20250305", "name": "web_search",
                  "max_uses": max(1, cfg.max_sources_per_agent)}]
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        response = None
        for _ in range(3):
            response = client.messages.create(
                model=resolve_available_anthropic_model(cfg.anthropic_model),
                max_tokens=5000,
                messages=messages,
                tools=tools,
            )
            if getattr(response, "stop_reason", None) != "pause_turn":
                break
            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response.content},
            ]
        obj = _extract_json(_anthropic_text(response))
        return AgentResearch("anthropic", cfg.anthropic_model, topic, searched,
                             _coerce_findings(obj, "anthropic"))
    except Exception as e:
        return AgentResearch("anthropic", cfg.anthropic_model, topic, searched, [], str(e)[:500])



def _claude_code_research(topic: str, questions: list[dict[str, Any]], cfg: ResearchConfig, agent_name: str) -> AgentResearch:
    searched = _now()
    try:
        from claude_code_provider import research_structured_call
        prompt = _research_prompt(topic, questions, cfg.max_sources_per_agent)
        rr = research_structured_call(
            system=("Jsi evidence research agent pro NPC Panel. Pracuj pouze s webovými zdroji. "
                    "Nevymýšlej fakta ani URL. Přímé outcome benchmarky odděluj kvůli anti-leakage."),
            messages=[{"role":"user","content":prompt}], schema=_schema(),
            schema_name='npc_background_research', model=cfg.anthropic_model, timeout=420, max_turns=8)
        return AgentResearch(agent_name, str(rr.get('model') or cfg.anthropic_model), topic, searched,
                             _coerce_findings(rr.get('data') or {}, agent_name))
    except Exception as e:
        return AgentResearch(agent_name, cfg.anthropic_model, topic, searched, [], str(e)[:700])

def _deterministic_target_overlap(item: EvidenceItem, questions: list[dict[str, Any]]) -> bool:
    """Conservative second-line leakage screen independent of agent self-labels.

    Prior survey outcomes close to the tested wording are exactly the evidence that
    can make a synthetic panel look accurate without predicting anything. We only
    trigger on outcome-like language/numbers PLUS lexical overlap with a target
    question, so generic background statistics are less likely to be quarantined.
    """
    claim = item.claim.lower()
    outcome_signal = bool(re.search(
        r"%|procent|respondent|dotázan|dotazan|would|purchase intent|buy|koup|"
        r"souhlas|support|vote|volil|prefer|zvaž|zvaz|ochot|intent|mean score|průměr|prumer",
        claim, re.I))
    if not outcome_signal:
        return False
    for q in questions:
        target = str(q.get("text", "")) + " " + " ".join(q.get("kategorie") or [])
        if _similarity(item.claim, target) >= 0.24:
            return True
    return False


def _merge_agents(agents: list[AgentResearch], cfg: ResearchConfig,
                  questions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings = [x for a in agents for x in a.findings]
    quarantined: list[dict[str, Any]] = []
    safe: list[EvidenceItem] = []
    for x in findings:
        deterministic_overlap = _deterministic_target_overlap(x, questions)
        if x.outcome_overlap or x.recommended_use != SAFE_USE or deterministic_overlap:
            reason = "target_outcome_overlap" if (x.outcome_overlap or x.recommended_use != SAFE_USE) else "deterministic_target_overlap"
            quarantined.append({**asdict(x), "reason": reason})
        elif x.source_quality < 0.55:
            quarantined.append({**asdict(x), "reason": "low_source_quality"})
        else:
            safe.append(x)

    accepted: list[dict[str, Any]] = []
    used: set[int] = set()
    for i, x in enumerate(safe):
        if i in used:
            continue
        peers = []
        for j, y in enumerate(safe):
            if j == i or y.agent == x.agent:
                continue
            same_url = _canonical_url(y.source_url) == _canonical_url(x.source_url)
            similar = _similarity(x.claim, y.claim) >= 0.42
            if same_url or similar:
                peers.append((j, y))
        if peers:
            j, y = max(peers, key=lambda z: z[1].source_quality)
            used.update({i, j})
            best = x if x.source_quality >= y.source_quality else y
            accepted.append({
                **asdict(best),
                "consensus": True,
                "agents": sorted({x.agent, y.agent}),
                "supporting_urls": sorted({_canonical_url(x.source_url), _canonical_url(y.source_url)}),
                "merge_confidence": round(min(0.98, 0.55 + 0.22 * (x.source_quality + y.source_quality)), 3),
            })
        elif (not cfg.strict_consensus or
              (cfg.allow_single_agent_primary and x.evidence_type in {"primary_source", "peer_reviewed", "official_report"}
               and x.source_quality >= 0.90)):
            used.add(i)
            accepted.append({
                **asdict(x), "consensus": False, "agents": [x.agent],
                "supporting_urls": [_canonical_url(x.source_url)],
                "merge_confidence": round(0.65 * x.source_quality, 3),
            })
        else:
            quarantined.append({**asdict(x), "reason": "no_independent_confirmation"})

    accepted.sort(key=lambda x: (bool(x.get("consensus")), float(x.get("merge_confidence", 0))), reverse=True)
    return accepted[: cfg.max_context_blocks], quarantined


def run_dual_research(
    config: ResearchConfig | dict[str, Any] | bool | None,
    questions: list[dict[str, Any]],
    *,
    mock_agents: dict[str, Any] | None = None,
    provider_override: str | None = None,
    progress=None,
) -> ResearchBundle:
    """Run research on the globally selected AI engine, or do nothing when disabled.

    ``mock_agents`` is test-only injection and intentionally undocumented in the UI.
    """
    cfg = config if isinstance(config, ResearchConfig) else ResearchConfig.from_obj(config)
    _progress = progress if callable(progress) else (lambda _x: None)
    topic = (cfg.topic or "").strip()
    if not cfg.enabled:
        return ResearchBundle(False, topic, _now(), [], [], [], asdict(cfg)).finalize_hash()

    if mock_agents is None:
        from provider_auth import provider_key_ready, get_ai_provider, normalize_ai_provider
        provider=normalize_ai_provider(provider_override or get_ai_provider())
        if not provider_key_ready(provider):
            raise RuntimeError(f"Research Context ON vyžaduje připravený zvolený provider: {provider}.")
        if provider=="claude_code_subscription":
            # Two independent, sequential research passes preserve the original
            # consensus idea while staying within a single subscription slot.
            _progress("Research Context · agent 1/2 hledá primární a kvalitní zdroje")
            agents = [_claude_code_research(topic, questions, cfg, 'claude_code_A')]
            _progress("Research Context · agent 2/2 nezávisle ověřuje první průchod")
            agents.append(_claude_code_research(topic, questions, cfg, 'claude_code_B'))
            if not any(not a.error for a in agents):
                # One final compact retry on the SAME selected provider. This is
                # resilience, not cross-provider fallback. It catches transient
                # Claude Code/WebSearch failures after the long-context transport
                # fix without hiding a persistent auth/capacity error.
                recovery_cfg=ResearchConfig(**asdict(cfg))
                recovery_cfg.max_sources_per_agent=max(3,min(5,int(cfg.max_sources_per_agent)))
                _progress("Research Context · recovery průchod po chybě obou agentů")
                agents.append(_claude_code_research(topic, questions, recovery_cfg, 'claude_code_recovery'))
        elif provider=="openai":
            _progress("Research Context · OpenAI hledá a ověřuje zdroje")
            agents = [_openai_research(topic, questions, cfg)]
        else:
            _progress("Research Context · Anthropic hledá a ověřuje zdroje")
            agents = [_anthropic_research(topic, questions, cfg)]
    else:
        agents = []
        for name in ("openai", "anthropic"):
            val = mock_agents.get(name)
            if isinstance(val, AgentResearch):
                agents.append(val)
            elif isinstance(val, dict):
                agents.append(AgentResearch(name, f"mock-{name}", topic, _now(),
                                             _coerce_findings(val, name)))
            else:
                agents.append(AgentResearch(name, f"mock-{name}", topic, _now(), [], "mock missing"))

    successful = [a for a in agents if not a.error]
    if len(successful) == 0:
        errors = "; ".join(f"{a.agent}: {a.error}" for a in agents if a.error)
        raise RuntimeError("Research Context selhal — nedokončil ani jeden agent. " + errors)
    if len(successful) == 1 and not cfg.allow_degraded_single_agent:
        errors = "; ".join(f"{a.agent}: {a.error}" for a in agents if a.error)
        raise RuntimeError("Dual research nedokončen a degraded režim je vypnutý. " + errors)

    _progress("Research Context · syntéza, deduplikace a evidence quarantine")
    accepted, quarantined = _merge_agents(successful, cfg, questions)
    quality = "DUAL_VERIFIED" if len(successful) >= 2 else ("SINGLE_AGENT_DEGRADED" if mock_agents is not None else "SINGLE_PROVIDER_SELECTED")
    return ResearchBundle(True, topic, _now(), agents, accepted, quarantined,
                          asdict(cfg), quality_status=quality).finalize_hash()



def bundle_from_obj(obj: dict[str, Any] | ResearchBundle | None) -> ResearchBundle | None:
    if obj is None:
        return None
    if isinstance(obj, ResearchBundle):
        return obj
    if not isinstance(obj, dict):
        raise TypeError('research bundle musi byt object')
    agents=[]
    for a in obj.get('agents') or []:
        findings=[EvidenceItem(**x) for x in (a.get('findings') or []) if isinstance(x,dict)]
        agents.append(AgentResearch(str(a.get('agent') or ''),str(a.get('model') or ''),str(a.get('topic') or ''),
                                    str(a.get('searched_at') or ''),findings,a.get('error')))
    return ResearchBundle(bool(obj.get('enabled')),str(obj.get('topic') or ''),str(obj.get('created_at') or ''),agents,
                          list(obj.get('accepted') or []),list(obj.get('quarantined') or []),dict(obj.get('config') or {}),
                          quality_status=str(obj.get('quality_status') or 'NO_RESEARCH'),sha256=str(obj.get('sha256') or ''))

def save_bundle(bundle: ResearchBundle, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(bundle), ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load_bundle(path: str | Path) -> ResearchBundle:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    agents = []
    for a in obj.get("agents", []):
        findings = [EvidenceItem(**x) for x in a.get("findings", [])]
        agents.append(AgentResearch(a["agent"], a["model"], a.get("topic", ""),
                                    a.get("searched_at", ""), findings, a.get("error")))
    return ResearchBundle(bool(obj.get("enabled")), obj.get("topic", ""), obj.get("created_at", ""),
                          agents, obj.get("accepted", []), obj.get("quarantined", []),
                          obj.get("config", {}), quality_status=obj.get("quality_status", "NO_RESEARCH"),
                          sha256=obj.get("sha256", ""))


def bundle_to_kontext(bundle: ResearchBundle):
    """Convert accepted evidence to ``KontextovyBlok`` objects for per-question filtering."""
    from kontext import KontextovyBlok
    blocks = []
    for i, x in enumerate(bundle.accepted, 1):
        blocks.append(KontextovyBlok(
            id=f"research_{i:02d}_{hashlib.sha1(x['claim'].encode('utf-8')).hexdigest()[:8]}",
            text=x["claim"],
            temata=list(x.get("topics") or []),
            datum=(x.get("source_date") or bundle.created_at[:10]),
            zdroj=x.get("source_url", ""),
            jistota=float(x.get("merge_confidence", 0.6)),
        ))
    return blocks
