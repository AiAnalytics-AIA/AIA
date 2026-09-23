"""Runtime configuration for NPC Panel.

Survey/orchestration model routing is centralized here. Anthropic and OpenAI are
supported production engines. The provider selected for a LIVE run is fail-closed;
there is no automatic cross-provider fallback. Offline project checks and dry runs
remain provider-independent.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from env_loader import load_dotenv
load_dotenv()

VERSION = (Path(__file__).resolve().parent / "VERSION").read_text(encoding="utf-8").strip()
RELEASE = f"npc-panel-{VERSION}-production-evidence-html"
PANEL_VERSION = "v17.1.2"

@dataclass(frozen=True)
class ModelInfo:
    model_id: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    label: str

# PRESERVED survey/respondent model routing from the prior prototype.
# Defaults track Anthropic's current self-serve lineup (verified August 2026). They
# are only a starting point: provider_auth.resolve_available_anthropic_model checks
# them against the models the account can actually see and substitutes the newest
# visible variant of the same family, so a retired ID never breaks a run.
MODELS: dict[str, ModelInfo] = {
    "haiku": ModelInfo(os.environ.get("NPC_ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001"), 1.00, 5.00, "Claude Haiku"),
    "sonnet": ModelInfo(os.environ.get("NPC_ANTHROPIC_SONNET_MODEL", "claude-sonnet-5"), 2.00, 10.00, "Claude Sonnet"),
    "opus": ModelInfo(os.environ.get("NPC_ANTHROPIC_OPUS_MODEL", "claude-opus-5"), 5.00, 25.00, "Claude Opus"),
}
MODEL_BY_ID = {m.model_id: m for m in MODELS.values()}
DEFAULT_MODEL = MODELS["sonnet"].model_id

# Published rates for models an account may still be pinned to. Cost estimates stay
# honest when the router substitutes a different model than the configured default.
LEGACY_PRICING: dict[str, tuple[float, float]] = {
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-4-1-20250805": (15.00, 75.00),
    "claude-opus-4-5-20251101": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-fable-5": (10.00, 50.00),
}

# These two models belong ONLY to the optional Research Context pipeline.
# They are independently configurable and are never used to replace navrh/import/
# survey orchestration agents.
DEFAULT_OPENAI_RESEARCH_MODEL = os.environ.get("NPC_OPENAI_RESEARCH_MODEL", "gpt-5.6-sol")
DEFAULT_OPENAI_SURVEY_MODEL = os.environ.get("NPC_OPENAI_SURVEY_MODEL", DEFAULT_OPENAI_RESEARCH_MODEL)
DEFAULT_ANTHROPIC_RESEARCH_MODEL = os.environ.get(
    "NPC_ANTHROPIC_RESEARCH_MODEL", MODELS["sonnet"].model_id
)

# Only short aliases are mapped. A concrete dated model ID the user pinned on purpose
# must survive untouched; silently rewriting it would make runs unreproducible.
MODEL_ALIASES: dict[str, str] = {
    "haiku": DEFAULT_MODEL,
    "sonnet": MODELS["sonnet"].model_id,
    "opus": MODELS["opus"].model_id,
}


def resolve_model(name: str | None) -> str:
    if not name:
        return DEFAULT_MODEL
    return MODEL_ALIASES.get(str(name).strip(), str(name).strip())


def pricing(model: str) -> tuple[float, float]:
    model = resolve_model(model)
    info = MODEL_BY_ID.get(model)
    if info:
        return info.input_usd_per_mtok, info.output_usd_per_mtok
    if model in LEGACY_PRICING:
        return LEGACY_PRICING[model]
    return MODELS["sonnet"].input_usd_per_mtok, MODELS["sonnet"].output_usd_per_mtok


def model_label(model: str) -> str:
    model = resolve_model(model)
    return MODEL_BY_ID.get(model, ModelInfo(model, 0, 0, model)).label


def resolve_provider_model(provider: str, name: str | None = None) -> str:
    """Resolve a project model for the selected provider without cross-provider aliases.

    Existing projects store Anthropic quality aliases (haiku/sonnet/opus). When
    OpenAI is selected these aliases intentionally map to the configured OpenAI
    survey model instead of being sent to the OpenAI API as invalid IDs. A concrete
    OpenAI model ID survives unchanged.
    """
    p = str(provider or "anthropic").strip().lower()
    raw = str(name or "").strip()
    if p == "openai":
        if raw and raw.lower() not in MODEL_ALIASES:
            return raw
        return DEFAULT_OPENAI_SURVEY_MODEL
    if p == "claude_code_subscription":
        if raw.lower() in {"haiku","sonnet","opus"}: return raw.lower()
        return raw or "sonnet"
    return resolve_model(raw or DEFAULT_MODEL)


def provider_pricing(provider: str, model: str) -> tuple[float, float]:
    """Return USD / million tokens used by the hard-budget guard.

    Anthropic keeps the audited table above. OpenAI rates are deliberately
    configurable because the selected model can be changed without a code release.
    Conservative defaults keep a hard cap fail-safe (early stop is preferable to
    overspend); deployments should pin exact rates in .env for their chosen model.
    """
    p = str(provider or "anthropic").strip().lower()
    if p == "claude_code_subscription": return (0.0,0.0)
    if p != "openai":
        return pricing(model)
    try:
        ci = float(os.environ.get("NPC_OPENAI_INPUT_USD_PER_MTOK", "15"))
        co = float(os.environ.get("NPC_OPENAI_OUTPUT_USD_PER_MTOK", "75"))
    except Exception:
        ci, co = 15.0, 75.0
    return max(0.0, ci), max(0.0, co)


def provider_model_label(provider: str, model: str) -> str:
    p=str(provider or "anthropic").strip().lower()
    if p == "openai": return f"OpenAI · {model}"
    if p == "claude_code_subscription": return f"Claude Code subscription · {model}"
    return model_label(model)


# ---------------------------------------------------------------- 17.1.2
# Jediny zdroj pravdy pro vychozi nastaveni behu. Drive byly defaulty rozsypane
# mezi run.py (sonnet/sync/full), brief_ukazka.json (haiku/batch) a UI_GUIDE
# (calibrated), takze stejny brief dal jiny vysledek podle vstupniho bodu.
RUN_DEFAULTS: dict = {
    "mode": "batch",            # levnejsi nez sync, stejny vystup
    "model": "sonnet",
    "persona_mode": "calibrated",
    "response_mode": "probability",
    "allow_own_estimates": False,
    "use_case": "internal",
}
