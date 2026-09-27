"""Provider credential handling for NPC Panel desktop runtime.

The local desktop app treats its own ``.env`` file as the explicit settings source.
A stale process-wide ANTHROPIC_API_KEY must not silently override a key saved from
NPC Settings. Anthropic clients are constructed with the resolved key explicitly,
so SDK/environment precedence cannot drift between modules.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any
from edition_config import allowed_providers, load_edition

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
# Secondary, always-writable location. A packaged install can live in a read-only
# directory (Program Files, app bundle); without this the UI reports "saved" while
# nothing was persisted.
HOME_ENV_PATH = Path.home() / ".npc_panel" / ".env"
OFFICIAL_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
AI_PROVIDER_ENV = "NPC_AI_PROVIDER"
VALID_AI_PROVIDERS = {"anthropic", "openai", "claude_code_subscription"}

# Machine-level variables that silently change how the SDK authenticates. A stale
# ANTHROPIC_AUTH_TOKEN makes the SDK send an Authorization header instead of the
# API key, which the API answers with 401 even when the saved key is correct.
HOSTILE_ANTHROPIC_ENV = (
    "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_URL",
    "ANTHROPIC_PROFILE", "ANTHROPIC_IDENTITY_TOKEN", "ANTHROPIC_IDENTITY_TOKEN_FILE",
    "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_ORGANIZATION_ID",
)
HOSTILE_OPENAI_ENV = ("OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENAI_ORG_ID", "OPENAI_ORGANIZATION")


class _CleanProviderEnv:
    """Temporarily remove machine-level credential overrides during client init.

    The SDKs capture these at construction time, so a narrow window is enough and
    the user's own shell environment is left untouched afterwards.
    """

    def __init__(self, names: tuple[str, ...]):
        self._names = names
        self._saved: dict[str, str] = {}

    def __enter__(self):
        for n in self._names:
            if n in os.environ:
                self._saved[n] = os.environ.pop(n)
        return self

    def __exit__(self, *exc):
        os.environ.update(self._saved)
        return False


def detected_env_overrides() -> list[str]:
    """Report machine-level variables that can break an otherwise valid key."""
    return [n for n in (HOSTILE_ANTHROPIC_ENV + HOSTILE_OPENAI_ENV) if os.environ.get(n)]


def _unquote(value: str) -> str:
    value = str(value or "").strip().lstrip("\ufeff")
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value


def normalize_secret(value: str | None, *, variable: str = "ANTHROPIC_API_KEY") -> str:
    """Normalize the common ways users paste API keys into a password field.

    Accepted inputs include the raw value as well as ``ANTHROPIC_API_KEY=...``,
    ``export ANTHROPIC_API_KEY=...`` and quoted values. Internal whitespace is
    rejected rather than silently modified.
    """
    value = _unquote(str(value or ""))
    if not value:
        return ""
    # Users often paste the whole .env line into the UI.
    m = re.match(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", value, re.S)
    if m and m.group(1) in {variable, "ANTHROPIC_API_KEY", "OPENAI_API_KEY"}:
        value = _unquote(m.group(2))
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    value = _unquote(value)
    if any(ch.isspace() for ch in value):
        raise ValueError(f"{variable} obsahuje mezeru nebo zalomení řádku. Vložte samotný klíč.")
    return value


def _read_env_file(path: Path | None = None) -> dict[str, str]:
    path = path or ENV_PATH
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if not k:
            continue
        try:
            out[k] = normalize_secret(v, variable=k)
        except ValueError:
            # Keep invalid local values visible to diagnostics without using them.
            out[k] = _unquote(v)
    return out


def _read_local_env() -> dict[str, str]:
    """Merge every NPC-owned env location; the app directory wins over the home copy."""
    merged: dict[str, str] = {}
    for path in (HOME_ENV_PATH, ENV_PATH):
        for k, v in _read_env_file(path).items():
            if v:
                merged[k] = v
    return merged


def local_env_paths() -> list[dict[str, Any]]:
    out = []
    for path in (ENV_PATH, HOME_ENV_PATH):
        out.append({"path": str(path), "exists": path.is_file(),
                    "keys": sorted(k for k, v in _read_env_file(path).items() if v)})
    return out


def resolve_secret(variable: str) -> tuple[str, str]:
    """Return ``(value, source)`` with local NPC settings taking precedence.

    This precedence is intentional for the single-user desktop product. It fixes a
    common failure where an old system environment variable remained active after a
    new key was saved in the UI.
    """
    local = _read_local_env().get(variable, "")
    if local:
        return normalize_secret(local, variable=variable), "npc_local_env"
    process = os.environ.get(variable, "")
    if process:
        return normalize_secret(process, variable=variable), "process_environment"
    return "", "missing"


def get_anthropic_api_key(*, required: bool = True) -> str:
    key, _ = resolve_secret("ANTHROPIC_API_KEY")
    if required and not key:
        raise ValueError("Chybí Anthropic API klíč. Vložte jej v Nastavení → Anthropic / Claude.")
    return key


def get_openai_api_key(*, required: bool = True) -> str:
    key, _ = resolve_secret("OPENAI_API_KEY")
    if required and not key:
        raise ValueError("Chybí OpenAI API klíč.")
    return key


def has_anthropic_key() -> bool:
    try:
        return bool(get_anthropic_api_key(required=False))
    except ValueError:
        return False


def has_openai_key() -> bool:
    try:
        return bool(get_openai_api_key(required=False))
    except ValueError:
        return False


def normalize_ai_provider(value: str | None, *, default: str = "claude_code_subscription") -> str:
    """Normalize the three explicit LIVE transports supported by the product.

    ``anthropic`` is the internal id for the user-facing Claude API path.
    Unknown/local/fake values are never accepted for LIVE execution.
    """
    from provider_runtime import normalize_live_provider
    return normalize_live_provider(value, normalize_live_provider(default))


def get_ai_provider() -> str:
    """Global default runtime; a project/stage may override it explicitly."""
    local = _read_local_env().get(AI_PROVIDER_ENV, "")
    raw = local or os.environ.get(AI_PROVIDER_ENV, "") or str(load_edition().get("default_provider") or "claude_code_subscription")
    return normalize_ai_provider(raw)


def provider_key_ready(provider: str | None = None) -> bool:
    p=normalize_ai_provider(provider or get_ai_provider())
    if p == "anthropic":
        try:
            return bool(anthropic_key_kind(get_anthropic_api_key(required=False)).get("usable"))
        except Exception:
            return False
    if p == "openai":
        try:
            return bool(get_openai_api_key(required=False))
        except Exception:
            return False
    try:
        from claude_code_provider import health
        return bool(health().get("ok"))
    except Exception:
        return False

def anthropic_key_kind(key: str) -> dict[str, Any]:
    """Distinguish key types that look valid but cannot call /v1/messages.

    Admin keys and console OAuth tokens are the most common reason a user is sure
    the key is correct while the API keeps answering 401/403.
    """
    k = str(key or "")
    if not k:
        return {"kind": "MISSING", "usable": False, "message": "Klíč není nastaven."}
    if k.startswith("sk-ant-admin"):
        return {"kind": "ADMIN_KEY", "usable": False,
                "message": "Vložen je Admin API key. Ten neumí volat /v1/messages. Vytvořte běžný API key (sk-ant-api…) v Anthropic Console → API Keys."}
    if k.startswith("sk-ant-oat") or k.startswith("sk-ant-ort"):
        return {"kind": "OAUTH_TOKEN", "usable": False,
                "message": "Vložen je OAuth/přihlašovací token, ne API klíč. V Anthropic Console → API Keys vytvořte klíč sk-ant-api…"}
    if k.startswith("sk-ant-api") or k.startswith("sk-ant-"):
        return {"kind": "API_KEY", "usable": True, "message": ""}
    if k.startswith("sk-"):
        return {"kind": "FOREIGN_KEY", "usable": False,
                "message": "Tenhle klíč vypadá jako OpenAI klíč vložený do pole pro Anthropic. Vložte ho do pole OpenAI."}
    return {"kind": "UNKNOWN", "usable": False,
            "message": "Klíč nemá formát Anthropic API klíče (očekává se sk-ant-api…)."}


def _fingerprint(key: str) -> str:
    if not key:
        return ""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]


def anthropic_key_info() -> dict[str, Any]:
    kind = {"kind": "MISSING", "usable": False, "message": ""}
    try:
        key, source = resolve_secret("ANTHROPIC_API_KEY")
        kind = anthropic_key_kind(key)
        valid_format = bool(key) and bool(kind.get("usable"))
        error = "" if (not key or valid_format) else (kind.get("message") or "Klíč nemá obvyklý prefix sk-ant-api.")
    except Exception as exc:
        key, source, valid_format, error = "", "invalid", False, str(exc)
    return {
        "present": bool(key),
        "source": source,
        "format_ok": valid_format,
        "key_kind": kind.get("kind"),
        "env_overrides": [n for n in HOSTILE_ANTHROPIC_ENV if os.environ.get(n)],
        "suffix": ("…" + key[-6:]) if len(key) >= 6 else "",
        "fingerprint": _fingerprint(key),
        "error": error,
        "base_url": os.environ.get("NPC_ANTHROPIC_BASE_URL", OFFICIAL_ANTHROPIC_BASE_URL),
    }


def create_anthropic_client(*, max_retries: int = 4):
    import anthropic
    key = get_anthropic_api_key(required=True)
    # Ignore an accidental/stale ANTHROPIC_BASE_URL inherited from the machine.
    # A custom gateway must be opted into explicitly through NPC_ANTHROPIC_BASE_URL.
    base_url = os.environ.get("NPC_ANTHROPIC_BASE_URL", OFFICIAL_ANTHROPIC_BASE_URL).strip()
    # ANTHROPIC_AUTH_TOKEN / profile / federation variables outrank an explicit key in
    # some SDK versions and produce a 401 that looks like "the saved key is wrong".
    with _CleanProviderEnv(HOSTILE_ANTHROPIC_ENV):
        return anthropic.Anthropic(api_key=key, base_url=base_url, max_retries=max_retries)


def create_openai_client(*, max_retries: int = 2):
    """Single construction path for OpenAI.

    Every module must use this. Constructing ``OpenAI()`` without an explicit key
    means a key saved in NPC Settings is invisible to that module.
    """
    from openai import OpenAI
    key = get_openai_api_key(required=True)
    base_url = os.environ.get("NPC_OPENAI_BASE_URL", "").strip()
    with _CleanProviderEnv(HOSTILE_OPENAI_ENV):
        if base_url:
            return OpenAI(api_key=key, base_url=base_url, max_retries=max_retries)
        return OpenAI(api_key=key, max_retries=max_retries)


def _writable_env_path(preferred: Path) -> Path:
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        probe = preferred.parent / ".npc_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return preferred
    except Exception:
        HOME_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        return HOME_ENV_PATH


def save_local_keys(*, anthropic_key: str | None = None, openai_key: str | None = None,
                    ai_provider: str | None = None, clear_empty: bool = False, path: Path | None = None) -> dict[str, Any]:
    path = _writable_env_path(path or ENV_PATH)
    existing = _read_env_file(path)
    supplied = {
        "ANTHROPIC_API_KEY": anthropic_key,
        "OPENAI_API_KEY": openai_key,
    }
    for variable, raw in supplied.items():
        if raw is None:
            continue
        value = normalize_secret(raw, variable=variable)
        if value:
            existing[variable] = value
            # Keep the current server process consistent with the saved setting.
            os.environ[variable] = value
        elif clear_empty:
            existing.pop(variable, None)
            os.environ.pop(variable, None)
    if ai_provider is not None:
        selected = normalize_ai_provider(ai_provider)
        existing[AI_PROVIDER_ENV] = selected
        os.environ[AI_PROVIDER_ENV] = selected
    lines = ["# NPC Panel local API keys. Never share this file."]
    for k in sorted(existing):
        if existing[k]:
            lines.append(f"{k}={existing[k]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "saved": True,
        "env_path": str(path),
        "env_overrides": detected_env_overrides(),
        "has_anthropic_key": has_anthropic_key(),
        "has_openai_key": has_openai_key(),
        "has_ai_key": bool(has_anthropic_key() or has_openai_key()),
        "ai_provider": get_ai_provider(),
        "anthropic": anthropic_key_info(),
        "openai": openai_key_info(),
    }


def classify_ai_exception(exc: Exception, provider: str | None = None) -> dict[str, Any]:
    """Classify a provider failure using the product-wide selected engine.

    This deliberately does not try the other provider.  It exists for UI/job
    diagnostics so an OpenAI failure can never be presented as an Anthropic
    failure (and vice versa).
    """
    p = normalize_ai_provider(provider or get_ai_provider())
    if p == "anthropic":
        return classify_anthropic_exception(exc)
    text = str(exc)
    low = text.lower()
    if p == "claude_code_subscription":
        quota=any(x in low for x in ("usage limit","session limit","rate limit","quota","credits","resets"))
        return {"provider":p,"kind":"QUOTA" if quota else "RUNTIME","status_code":getattr(exc,"status_code",None),
                "user_message":"Claude Code dosáhl limitu předplatného; projekt je bezpečně uložen a lze pokračovat po resetu nebo explicitně přes Claude API." if quota else "Claude Code runtime selhal. Projekt a dokončené artefakty zůstávají uložené.",
                "retryable":bool(quota),"raw":text[:1000]}
    low = text.lower()
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status == 401 or "incorrect api key" in low or "authentication" in low:
        kind, msg = "AUTHENTICATION", "OpenAI odmítlo použitý API klíč (401). Uložte platný OpenAI API key a spusťte Test připojení."
    elif status == 403 or "permission" in low:
        kind, msg = "PERMISSION", "OpenAI klíč je rozpoznaný, ale nemá oprávnění k této operaci/modelu."
    elif status == 404 or ("model" in low and ("not found" in low or "does not exist" in low)):
        kind, msg = "MODEL", "OpenAI autentizace prošla, ale zvolený model není pro tento účet dostupný nebo má jiné ID."
    elif status == 429 or "rate_limit" in low or "quota" in low or "insufficient_quota" in low:
        kind, msg = "RATE_LIMIT", "OpenAI API hlásí rate limit nebo nedostatečnou kvótu/kredit."
    elif any(x in low for x in ("connection", "timeout", "timed out", "temporarily unavailable", "502", "503", "504")):
        kind, msg = "TRANSPORT", "OpenAI API je dočasně nedostupné nebo spojení selhalo."
    else:
        kind, msg = "OTHER", text[:700] or type(exc).__name__
    return {"ok": False, "kind": kind, "provider": p, "message": msg, "detail": text[:700]}


def classify_anthropic_exception(exc: Exception) -> dict[str, Any]:
    text = str(exc)
    low = text.lower()
    status = getattr(exc, "status_code", None)
    if status == 401 or "authentication_error" in low or "api key is invalid" in low:
        return {
            "ok": False,
            "kind": "AUTHENTICATION",
            "message": "Anthropic odmítl použitý API klíč (401). Uložte klíč z Anthropic Console a spusťte Test připojení.",
            "detail": text[:700],
        }
    if status == 403 or "permission" in low:
        return {"ok": False, "kind": "PERMISSION", "message": "Klíč je rozpoznaný, ale nemá oprávnění k této operaci/modelu.", "detail": text[:700]}
    if status == 404 or "not_found" in low or "model" in low and "not found" in low:
        return {"ok": False, "kind": "MODEL", "message": "Autentizace prošla, ale zvolený model není pro tento účet dostupný nebo má jiné ID.", "detail": text[:700]}
    if status == 429 or "rate_limit" in low:
        return {"ok": False, "kind": "RATE_LIMIT", "message": "Anthropic klíč funguje, ale API hlásí limit/rate limit.", "detail": text[:700]}
    return {"ok": False, "kind": "OTHER", "message": text[:700] or type(exc).__name__, "detail": text[:700]}


def probe_anthropic(model: str | None = None) -> dict[str, Any]:
    """Make the smallest practical provider probe and classify failures.

    The call can incur a negligible provider charge if a metadata/count-tokens
    endpoint is not available in the installed SDK.
    """
    from runtime_config import resolve_model, DEFAULT_MODEL
    info = anthropic_key_info()
    if not info["present"]:
        return {"ok": False, "kind": "MISSING", "message": "Anthropic API klíč není nastaven.", "credential": info}
    if not info["format_ok"]:
        return {"ok": False, "kind": "FORMAT", "message": info["error"], "credential": info}
    try:
        c = create_anthropic_client(max_retries=0)
        # Probe the model the runtime would really use. Testing a configured-but-retired
        # ID reported "authentication passed, model unavailable" even though every real
        # call would have succeeded on the substituted model.
        requested = resolve_model(model or DEFAULT_MODEL)
        model_id = resolve_available_anthropic_model(model or DEFAULT_MODEL)
        substituted = model_id if model_id != requested else ""
        if hasattr(c, "models") and hasattr(c.models, "retrieve"):
            try:
                m = c.models.retrieve(model_id)
                return {"ok": True, "kind": "OK", "model": getattr(m, "id", model_id), "method": "models.retrieve",
                        "substituted_model": substituted, "requested_model": requested,
                        "message": (f"Anthropic funguje. Nakonfigurovaný model {requested} účet nevidí, používá se {model_id}."
                                    if substituted else "Anthropic API funguje."),
                        "credential": info}
            except Exception as exc:
                classified = classify_anthropic_exception(exc)
                if classified["kind"] in {"AUTHENTICATION", "PERMISSION"}:
                    return {**classified, "credential": info}
                # For model-specific failures continue to a message/count-token probe.
        if hasattr(c.messages, "count_tokens"):
            try:
                c.messages.count_tokens(model=model_id, messages=[{"role": "user", "content": "ping"}])
                return {"ok": True, "kind": "OK", "model": model_id, "method": "messages.count_tokens",
                        "substituted_model": substituted, "requested_model": requested,
                        "message": (f"Anthropic funguje. Nakonfigurovaný model {requested} účet nevidí, používá se {model_id}."
                                    if substituted else "Anthropic API funguje."),
                        "credential": info}
            except Exception as exc:
                classified = classify_anthropic_exception(exc)
                return {**classified, "credential": info, "model": model_id}
        c.messages.create(model=model_id, max_tokens=1, messages=[{"role": "user", "content": "OK"}])
        return {"ok": True, "kind": "OK", "model": model_id, "method": "messages.create(max_tokens=1)",
                "substituted_model": substituted, "requested_model": requested,
                "message": "Anthropic API funguje.", "credential": info}
    except Exception as exc:
        return {**classify_anthropic_exception(exc), "credential": info}



def list_anthropic_models() -> dict[str, Any]:
    """Return models visible to the configured Anthropic key.

    This is diagnostic only. It never makes a generation request. Older SDKs or
    accounts may not expose the model-list endpoint; that condition is reported
    without breaking the product.
    """
    info = anthropic_key_info()
    if not info.get("present"):
        return {"ok": False, "kind": "MISSING", "models": [], "message": "Anthropic API klíč není nastaven."}
    try:
        c = create_anthropic_client(max_retries=0)
        api = getattr(c, "models", None)
        fn = getattr(api, "list", None) if api is not None else None
        if fn is None:
            return {"ok": False, "kind": "UNSUPPORTED_SDK", "models": [], "message": "Instalovaná verze Anthropic SDK neumí vypsat modely; použije se přímý probe."}
        page = fn(limit=100)
        data = getattr(page, "data", None) or []
        models=[]
        for m in data:
            mid=str(getattr(m,"id","") or "").strip()
            if mid:
                models.append({"id":mid,"display_name":str(getattr(m,"display_name","") or ""),"created_at":str(getattr(m,"created_at","") or "")})
        return {"ok": True, "kind": "OK", "models": models, "message": f"Účet zpřístupňuje {len(models)} modelů."}
    except Exception as exc:
        return {**classify_anthropic_exception(exc), "models": []}


_MODEL_CACHE: dict[str, Any] = {"ts": 0.0, "models": []}
_MODEL_CACHE_TTL = 1800.0


def visible_anthropic_models(*, force: bool = False) -> list[str]:
    """Cached list of model IDs the configured key can actually use."""
    import time as _time
    if not force and _MODEL_CACHE["models"] and (_time.time() - float(_MODEL_CACHE["ts"])) < _MODEL_CACHE_TTL:
        return list(_MODEL_CACHE["models"])
    listing = list_anthropic_models()
    if listing.get("ok"):
        ids = [str(x.get("id")) for x in listing.get("models", []) if x.get("id")]
        _MODEL_CACHE.update(ts=_time.time(), models=ids)
        return list(ids)
    return list(_MODEL_CACHE["models"])


def _family_of(name: str) -> str:
    low = str(name or "").lower()
    for fam in ("opus", "sonnet", "haiku"):
        if fam in low:
            return fam
    return ""


def resolve_available_anthropic_model(name: str | None) -> str:
    """Map an alias/ID onto a model the account really has.

    A configured model ID that the account cannot see used to surface as a generic
    AI outage. Here it is repaired: the same family, newest visible variant.
    """
    from runtime_config import resolve_model
    configured = resolve_model(name)
    try:
        visible = visible_anthropic_models()
    except Exception:
        return configured
    if not visible or configured in visible:
        return configured
    fam = _family_of(name) or _family_of(configured)
    candidates = [m for m in visible if fam and fam in m.lower()]
    if not candidates:
        candidates = [m for m in visible if m.startswith("claude-")]
    if not candidates:
        return configured
    # Dated suffixes sort chronologically; newest visible variant is the safest pick.
    return sorted(candidates)[-1]


def anthropic_model_diagnostics() -> dict[str, Any]:
    """Validate the three NPC aliases against the current account."""
    from runtime_config import MODELS
    listing=list_anthropic_models()
    visible={x.get("id") for x in listing.get("models",[]) if x.get("id")}
    checks=[]
    for alias, info in MODELS.items():
        row={"alias":alias,"model":info.model_id}
        if listing.get("ok"):
            row.update(ok=info.model_id in visible, kind="OK" if info.model_id in visible else "MODEL_NOT_VISIBLE")
            if not row["ok"]:
                # Offer compatible visible choices from the same family instead of failing opaquely.
                fam=alias.lower()
                row["alternatives"]=[m for m in sorted(visible) if fam in m.lower()][:10]
        else:
            probe=probe_anthropic(info.model_id)
            row.update(ok=bool(probe.get("ok")),kind=probe.get("kind"),message=probe.get("message"))
        checks.append(row)
    return {"listing":listing,"checks":checks,"all_ok":all(x.get("ok") for x in checks)}

def openai_key_info() -> dict[str, Any]:
    try:
        key, source = resolve_secret("OPENAI_API_KEY")
        valid_format = bool(key) and (key.startswith("sk-") or key.startswith("sess-") or len(key) > 20)
        error = "" if (not key or valid_format) else "OpenAI klíč má neobvyklý formát."
    except Exception as exc:
        key, source, valid_format, error = "", "invalid", False, str(exc)
    return {"present":bool(key),"source":source,"format_ok":valid_format,
            "suffix":("…"+key[-6:]) if len(key)>=6 else "","fingerprint":_fingerprint(key),"error":error}


def probe_openai(model: str | None = None) -> dict[str, Any]:
    info=openai_key_info()
    try:
        import openai as _openai_pkg
        sdk_version=str(getattr(_openai_pkg,'__version__','unknown'))
    except Exception:
        sdk_version='missing' 
    if not info["present"]:
        return {"ok":False,"kind":"MISSING","message":"OpenAI API klíč není nastaven.","credential":info}
    try:
        from openai import OpenAI
        from runtime_config import DEFAULT_OPENAI_RESEARCH_MODEL
        c=OpenAI(api_key=get_openai_api_key(required=True),max_retries=0)
        if not hasattr(c,'responses'):
            return {"ok":False,"kind":"SDK_OUTDATED","message":f"OpenAI Python SDK {sdk_version} je příliš staré a nemá Responses API. Spusťte OPRAVIT_INSTALACI.bat / aktualizaci dependencies.","sdk_version":sdk_version,"credential":info}
        model_id=str(model or os.environ.get("NPC_OPENAI_ASSISTANT_MODEL") or DEFAULT_OPENAI_RESEARCH_MODEL or "gpt-5")
        # The Responses API rejects max_output_tokens below 16 with a 400 that reads
        # like a broken key. Keep the probe at the documented minimum.
        r=c.responses.create(model=model_id,input="Reply only OK.",max_output_tokens=16)
        return {"ok":True,"kind":"OK","model":getattr(r,"model",None) or model_id,"message":"OpenAI API funguje.","sdk_version":sdk_version,"credential":info}
    except Exception as exc:
        status=getattr(exc,"status_code",None)
        low=str(exc).lower()
        if status==401 or "invalid api key" in low or "authentication" in low: kind="AUTHENTICATION";msg="OpenAI odmítl API klíč (401)."
        elif status==403: kind="PERMISSION";msg="OpenAI klíč nemá oprávnění k této operaci/modelu."
        elif status==429: kind="RATE_LIMIT";msg="OpenAI API hlásí rate limit / kvótu."
        elif status==404 or ("model" in low and "not found" in low): kind="MODEL";msg="Zvolený OpenAI model není dostupný."
        else: kind="OTHER";msg=str(exc)[:700] or type(exc).__name__
        return {"ok":False,"kind":kind,"message":msg,"detail":str(exc)[:700],"sdk_version":sdk_version,"credential":info}
