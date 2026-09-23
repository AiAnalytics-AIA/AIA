"""Server-side AI provider router for NPC Panel.

Design contract (10.16.1+):

* One credential layer (:mod:`provider_auth`) for every cloud call.
* Every provider is tried through a *ladder*: native structured output first, then
  the same provider again with a plain JSON contract. A schema/model incompatibility
  therefore never looks like a provider outage.
* Only a real credential/transport failure moves the request to the next provider.
* ``local_fallback`` upstream is reached only after every provider truly failed.
* Every result carries provider/model/attempt audit.

Browser code never calls a provider directly.
"""
from __future__ import annotations
import json, os, re, time
from typing import Any

from runtime_config import DEFAULT_OPENAI_RESEARCH_MODEL, resolve_model
from provider_auth import (
    has_anthropic_key, has_openai_key, get_openai_api_key,
    create_anthropic_client, create_openai_client,
    resolve_available_anthropic_model, visible_anthropic_models,
)
from anthropic_compat import create_message

# Failure kinds that make the *provider* unusable for this request. Everything else
# is a request-shape problem and is retried on the same provider first.
PROVIDER_FATAL = {"MISSING", "AUTHENTICATION", "PERMISSION", "QUOTA", "TRANSPORT", "SDK_OUTDATED"}

OPENAI_MODEL_PREFERENCE = [
    "gpt-5.6", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
    "gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano",
    "gpt-5.2", "gpt-5.1", "gpt-5", "gpt-5-mini", "gpt-4.1", "gpt-4o-mini",
]

_OPENAI_MODEL_CACHE: dict[str, Any] = {"ts": 0.0, "models": []}


# --------------------------------------------------------------------------- #
# error classification
# --------------------------------------------------------------------------- #

def classify_provider_exception(exc: Exception) -> str:
    """Map an SDK exception onto a routing decision without losing wrapped provider detail."""
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    raw = str(exc)
    low = raw.lower()
    tagged = re.search(r"\[(MISSING|AUTHENTICATION|PERMISSION|QUOTA|MODEL|SCHEMA|TRANSPORT|SDK_OUTDATED|MAX_TURNS|OTHER)\]", raw)
    if tagged:
        return tagged.group(1)
    if "key missing" in low or ("chybí" in low and "klíč" in low):
        return "MISSING"
    if ("no attribute" in low and "responses" in low) or ("has no attribute 'responses'" in low) or "sdk_outdated" in low:
        return "SDK_OUTDATED"
    if status == 401 or "authentication_error" in low or "api key is invalid" in low or "incorrect api key" in low:
        return "AUTHENTICATION"
    if status == 403 or "permission_error" in low or "permission denied" in low or "not permitted" in low:
        return "PERMISSION"
    if "error_max_turns" in low or "max turns" in low or "max_turns" in low:
        return "MAX_TURNS"
    if status == 429 or "rate_limit" in low or "quota" in low or "insufficient_quota" in low or "credit balance" in low:
        return "QUOTA"
    if status == 404 or ("model" in low and any(x in low for x in ("not found", "does not exist", "not_found", "invalid", "unsupported", "not available", "access"))):
        return "MODEL"
    if status == 400 or "invalid_request" in low or "schema" in low or "json_schema" in low or \
       "nevrátil json" in low or "nevratil json" in low or "prázdnou odpověď" in low or "prazdnou odpoved" in low or \
       "did not return json" in low or "empty response" in low:
        return "SCHEMA"
    if any(x in low for x in ("connection", "timeout", "timed out", "temporarily unavailable",
                              "ssl", "proxy", "getaddrinfo", "name resolution", "overloaded",
                              "internal server error", "502", "503", "504")):
        return "TRANSPORT"
    return "OTHER"


def _is_fatal(kind: str) -> bool:
    return kind in PROVIDER_FATAL

def _is_cancel_exception(exc: BaseException | None) -> bool:
    seen=set(); cur=exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if type(cur).__name__=='ClaudeCodeCancelled' or str(cur).strip()=='JOB_CANCELLED': return True
        cur=getattr(cur,'__cause__',None) or getattr(cur,'__context__',None)
    return False


# --------------------------------------------------------------------------- #
# JSON helpers
# --------------------------------------------------------------------------- #

def extract_json(text: str) -> dict[str, Any]:
    """Recover a JSON object from a plain-text model answer."""
    t = str(text or "").strip()
    if not t:
        raise RuntimeError("Provider vrátil prázdnou odpověď.")
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.S | re.I)
    if m:
        return json.loads(m.group(1))
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        return json.loads(t[start:end + 1])
    raise RuntimeError("Provider nevrátil JSON objekt: " + t[:240])


def _json_contract_system(system: str, schema: dict[str, Any], schema_name: str) -> str:
    """Prompt-level equivalent of a structured-output contract."""
    return (
        (system or "").rstrip()
        + "\n\nVÝSTUPNÍ KONTRAKT:\n"
        + "Vrať POUZE jeden validní JSON objekt odpovídající tomuto JSON Schema. "
        + "Bez úvodu, bez komentáře, bez markdown bloku.\n"
        + f"Název schématu: {schema_name}\n"
        + json.dumps(schema, ensure_ascii=False)[:12000]
    )


def _input_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for m in messages or []:
        role = str(m.get("role") or "user")
        content = m.get("content", "")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
        else:
            out.append({"role": role, "content": json.dumps(content, ensure_ascii=False, default=str)})
    return out


# --------------------------------------------------------------------------- #
# schema handling
# --------------------------------------------------------------------------- #

def schema_supports_strict(schema: Any) -> bool:
    """OpenAI strict mode rejects free-form objects.

    Rather than mutating the contract (which silently changes the returned data
    shape), an incompatible schema simply skips the strict tier. This is the exact
    reason the 10.16.0 OpenAI fallback could never complete the copilot contract:
    ``research_plan``/``filters``/``metadata`` are free-form objects.
    """
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            props = schema.get("properties")
            if not isinstance(props, dict) or not props:
                return False
            for v in props.values():
                if not schema_supports_strict(v):
                    return False
        if schema.get("type") == "array":
            return schema_supports_strict(schema.get("items") or {})
        for key in ("anyOf", "oneOf", "allOf"):
            if key in schema:
                return all(schema_supports_strict(x) for x in schema.get(key) or [])
    return True


def strictify(schema: Any) -> Any:
    """Make an object schema satisfy OpenAI strict mode (all keys required)."""
    if not isinstance(schema, dict):
        return schema
    out = dict(schema)
    if out.get("type") == "object" and isinstance(out.get("properties"), dict):
        out["properties"] = {k: strictify(v) for k, v in out["properties"].items()}
        out["required"] = list(out["properties"].keys())
        out["additionalProperties"] = False
    if out.get("type") == "array" and isinstance(out.get("items"), dict):
        out["items"] = strictify(out["items"])
    for key in ("anyOf", "oneOf", "allOf"):
        if isinstance(out.get(key), list):
            out[key] = [strictify(x) for x in out[key]]
    return out


# --------------------------------------------------------------------------- #
# OpenAI
# --------------------------------------------------------------------------- #

def _openai_model() -> str:
    return str(os.environ.get("NPC_OPENAI_SURVEY_MODEL") or DEFAULT_OPENAI_RESEARCH_MODEL or "gpt-5")


def _openai_visible_models(client: Any, *, force: bool = False) -> list[str]:
    if not force and _OPENAI_MODEL_CACHE["models"] and (time.time() - float(_OPENAI_MODEL_CACHE["ts"])) < 1800:
        return list(_OPENAI_MODEL_CACHE["models"])
    try:
        page = client.models.list()
        ids = [str(getattr(m, "id", "")) for m in getattr(page, "data", []) or []]
        ids = [x for x in ids if x]
        _OPENAI_MODEL_CACHE.update(ts=time.time(), models=ids)
        return ids
    except Exception:
        return list(_OPENAI_MODEL_CACHE["models"])


def _openai_repair_model(client: Any, wanted: str) -> str:
    """Pick a model the account actually has instead of failing on a stale ID."""
    visible = _openai_visible_models(client, force=True)
    if not visible or wanted in visible:
        return wanted
    for cand in OPENAI_MODEL_PREFERENCE:
        if cand in visible:
            return cand
    chat = [m for m in visible if m.startswith(("gpt-", "o1", "o3", "o4"))]
    return sorted(chat)[-1] if chat else wanted


def _openai_call(client: Any, *, model: str, system: str, messages: list[dict[str, Any]],
                 max_tokens: int, response_format: dict[str, Any] | None) -> Any:
    kwargs: dict[str, Any] = {
        "model": model,
        "input": _input_messages(messages),
        # OpenAI rejects budgets under 16 tokens with a confusing 400.
        "max_output_tokens": max(16, int(max_tokens)),
    }
    if system:
        kwargs["instructions"] = system
    if response_format:
        kwargs["text"] = {"format": response_format}
    return client.responses.create(**kwargs)


def _openai_usage(r: Any) -> tuple[int, int]:
    u = getattr(r, "usage", None)
    return int(getattr(u, "input_tokens", 0) or 0), int(getattr(u, "output_tokens", 0) or 0)


def _openai_structured(*, system: str, messages: list[dict[str, Any]], schema: dict[str, Any], schema_name: str,
                       max_tokens: int, model: str | None = None) -> dict[str, Any]:
    """OpenAI structured call with schema-failure recovery on the same provider."""
    client = create_openai_client(max_retries=2)
    mid = str(model or _openai_model())
    name = str(schema_name or "npc_output")[:64]
    attempts: list[str] = []
    last: Exception | None = None

    tiers: list[tuple[str, dict[str, Any] | None, str]] = []
    if schema_supports_strict(schema):
        tiers.append(("json_schema_strict",
                      {"type": "json_schema", "name": name, "schema": strictify(schema), "strict": True},
                      system))
    tiers.append(("json_object", {"type": "json_object"}, _json_contract_system(system, schema, name)))
    tiers.append(("text_contract", None, _json_contract_system(system, schema, name)))

    for tier, fmt, sys_prompt in tiers:
        for repair_model in (False, True):
            try:
                use_model = _openai_repair_model(client, mid) if repair_model else mid
                r = _openai_call(client, model=use_model, system=sys_prompt, messages=messages,
                                 max_tokens=max_tokens, response_format=fmt)
                txt = str(getattr(r, "output_text", "") or "").strip()
                data = extract_json(txt)
                tin, tout = _openai_usage(r)
                return {"data": data, "provider": "openai", "model": getattr(r, "model", None) or use_model,
                        "fallback_used": False, "attempts": ["openai:" + tier], "mode": tier,
                        "tok_in": tin, "tok_out": tout}
            except Exception as exc:
                last = exc
                kind = classify_provider_exception(exc)
                attempts.append(f"{tier}:{kind}")
                if _is_fatal(kind):
                    raise
                if kind != "MODEL":
                    break  # schema/output problem -> next tier, same provider
    final_kind = classify_provider_exception(last or RuntimeError("unknown OpenAI failure"))
    raise RuntimeError(f"[{final_kind}] OpenAI nedokončil požadavek ({', '.join(attempts[-3:])}): {str(last)[:700]}")


def _openai_text(*, system: str, messages: list[dict[str, Any]], max_tokens: int,
                 model: str | None = None) -> dict[str, Any]:
    client = create_openai_client(max_retries=2)
    mid = str(model or _openai_model())
    last: Exception | None = None
    for repair_model in (False, True):
        try:
            use_model = _openai_repair_model(client, mid) if repair_model else mid
            r = _openai_call(client, model=use_model, system=system, messages=messages,
                             max_tokens=max_tokens, response_format=None)
            tin, tout = _openai_usage(r)
            return {"text": str(getattr(r, "output_text", "") or ""), "tok_in": tin, "tok_out": tout,
                    "chyba": None, "provider": "openai", "model": getattr(r, "model", None) or use_model}
        except Exception as exc:
            last = exc
            if classify_provider_exception(exc) != "MODEL":
                raise
    raise RuntimeError(str(last))


# --------------------------------------------------------------------------- #
# Anthropic
# --------------------------------------------------------------------------- #

def _anthropic_capacity_call(fn, *args, **kwargs):
    """Anthropic API capacity retry contract: 5s -> 15s -> 45s, then park upstream.

    Authentication/schema/model errors fail immediately.  Tests may override the
    wait sequence with NPC_API_CAPACITY_RETRY_SECONDS=0,0,0.
    """
    import os as _os, time as _time
    raw=_os.environ.get('NPC_API_CAPACITY_RETRY_SECONDS','5,15,45')
    try: waits=[max(0.0,float(x.strip())) for x in raw.split(',') if x.strip()]
    except Exception: waits=[5.0,15.0,45.0]
    if not waits: waits=[5.0,15.0,45.0]
    last=None
    for attempt in range(len(waits)+1):
        try:return fn(*args,**kwargs)
        except Exception as exc:
            last=exc;status=getattr(exc,'status_code',None) or getattr(exc,'status',None);low=str(exc).lower()
            capacity=(status in {429,503}) or ('rate_limit' in low) or ('overloaded' in low) or ('service unavailable' in low)
            if not capacity or attempt>=len(waits):raise
            if waits[attempt]:_time.sleep(waits[attempt])
    raise last


def _anthropic_structured(*, system: str, messages: list[dict[str, Any]], schema: dict[str, Any], schema_name: str,
                          anthropic_model: str, max_tokens: int) -> dict[str, Any]:
    """Anthropic structured call: tool-use first, JSON contract as same-provider retry."""
    client = create_anthropic_client(max_retries=0)
    name = str(schema_name or "npc_output")[:64]
    mid = resolve_available_anthropic_model(anthropic_model)
    tool = {"name": name, "description": "Return the required structured NPC output.", "input_schema": schema}
    attempts: list[str] = []
    last: Exception | None = None

    for tier in ("tool_use", "json_contract"):
        for repair_model in (False, True):
            try:
                if repair_model:
                    visible_anthropic_models(force=True)
                    mid = resolve_available_anthropic_model(anthropic_model)
                if tier == "tool_use":
                    r = _anthropic_capacity_call(create_message, client, model=mid, max_tokens=max_tokens, system=system, messages=messages,
                                       tools=[tool], tool_choice={"type": "tool", "name": name})
                    blocks = [x for x in getattr(r, "content", []) if getattr(x, "type", None) == "tool_use"]
                    if not blocks:
                        raise RuntimeError("Anthropic nevrátil strukturovaný tool output.")
                    data = dict(getattr(blocks[0], "input", {}) or {})
                else:
                    r = _anthropic_capacity_call(create_message, client, model=mid, max_tokens=max_tokens,
                                       system=_json_contract_system(system, schema, name), messages=messages)
                    text = "".join(str(getattr(b, "text", "") or "") for b in getattr(r, "content", [])
                                   if getattr(b, "type", None) == "text")
                    data = extract_json(text)
                u = getattr(r, "usage", None)
                return {"data": data, "provider": "anthropic", "model": mid, "fallback_used": False,
                        "attempts": ["anthropic:" + tier], "mode": tier,
                        "tok_in": int(getattr(u, "input_tokens", 0) or 0),
                        "tok_out": int(getattr(u, "output_tokens", 0) or 0)}
            except Exception as exc:
                last = exc
                kind = classify_provider_exception(exc)
                attempts.append(f"{tier}:{kind}")
                if _is_fatal(kind):
                    raise
                if kind != "MODEL":
                    break
    final_kind = classify_provider_exception(last or RuntimeError("unknown Anthropic failure"))
    raise RuntimeError(f"[{final_kind}] Anthropic nedokončil požadavek ({', '.join(attempts[-3:])}): {str(last)[:700]}")


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #

def _provider_order(prefer: str) -> list[str]:
    # No silent cross-provider fallback; paid API continuation is explicit.
    from provider_auth import normalize_ai_provider
    return [normalize_ai_provider(prefer)]

def call_structured(*, system: str, messages: list[dict[str, Any]], schema: dict[str, Any], schema_name: str,
                    anthropic_model: str = "sonnet", openai_model: str | None = None, max_tokens: int = 4000,
                    prefer: str = "anthropic", allow_fallback: bool = True, timeout: int | None = None,
                    claude_max_turns: int = 8, claude_interactive: bool = False) -> dict[str, Any]:
    """Execute a JSON contract on the selected provider.

    ``allow_fallback=False`` is the production contract used by the unified product:
    if the selected provider fails, the call fails closed instead of crossing to the
    other vendor. Development/legacy callers can still opt into router fallback.
    """
    from provider_auth import normalize_ai_provider
    selected = normalize_ai_provider(prefer)
    order = _provider_order(selected) if allow_fallback else [selected]
    errors: list[tuple[str, str]] = []
    for provider in order:
        try:
            if provider == "anthropic":
                if not has_anthropic_key(): raise RuntimeError("Anthropic key missing")
                out = _anthropic_structured(system=system, messages=messages, schema=schema, schema_name=schema_name, anthropic_model=anthropic_model, max_tokens=max_tokens)
            elif provider == "claude_code_subscription":
                from claude_code_provider import structured_call
                out = structured_call(system=system,messages=messages,schema=schema,schema_name=schema_name,model=anthropic_model,max_tokens=max_tokens,timeout=int(timeout or (75 if claude_interactive else 180)),max_turns=claude_max_turns,interactive=claude_interactive)
            else:
                if not has_openai_key(): raise RuntimeError("OpenAI key missing")
                out = _openai_structured(system=system, messages=messages, schema=schema, schema_name=schema_name, max_tokens=max_tokens, model=openai_model)
            out["fallback_used"] = provider != order[0]
            out["attempts"] = [p for p, _ in errors] + list(out.get("attempts") or [provider])
            if errors:
                out["previous_errors"] = [{"provider": p, "error": e[:350]} for p, e in errors]
            return out
        except Exception as exc:
            if _is_cancel_exception(exc):
                raise
            errors.append((provider, f"[{classify_provider_exception(exc)}] {exc}"))
    raise RuntimeError("Žádný AI provider nedokončil strukturovaný požadavek. "
                       + " | ".join(f"{p}: {e[:1500]}" for p, e in errors))


def call_text(kw: dict[str, Any], *, anthropic_model: str = "sonnet", openai_model: str | None = None, max_tokens: int = 200,
              prefer: str = "anthropic", allow_fallback: bool = True) -> dict[str, Any]:
    """Execute one Anthropic-shaped request on the selected provider.

    ``allow_fallback=False`` is the production contract. A forced tool/schema
    (closed survey questions) is honoured on both providers; the JSON object is
    returned serialized as text so existing parsers are unchanged.
    """
    messages = list(kw.get("messages") or [])
    system = str(kw.get("system") or "")
    tools = list(kw.get("tools") or [])
    schema = None
    schema_name = "npc_response"
    if tools:
        t = tools[0] or {}
        schema = t.get("input_schema") or t.get("parameters")
        schema_name = str(t.get("name") or schema_name)
    from provider_auth import normalize_ai_provider
    selected = normalize_ai_provider(prefer)
    order = _provider_order(selected) if allow_fallback else [selected]
    errors: list[tuple[str, str]] = []
    for provider in order:
        try:
            if provider == "claude_code_subscription":
                from claude_code_provider import structured_call, text_call
                if schema:
                    rr=structured_call(system=system,messages=messages,schema=schema,schema_name=schema_name,model=anthropic_model,max_tokens=max_tokens)
                    # NPC AI RUNTIME FIX: predej skutecne tokeny, ne nuly.
                    return {"text":json.dumps(rr["data"],ensure_ascii=False),"tok_in":rr.get("tok_in",0),"tok_out":rr.get("tok_out",0),"chyba":None,"provider":"claude_code_subscription","model":rr.get("model"),"fallback_used":False,"subscription_usage":True}
                rr=text_call(system=system,messages=messages,model=anthropic_model,max_tokens=max_tokens)
                # NPC AI RUNTIME FIX: predej skutecne tokeny, ne nuly.
                return {"text":rr.get("text",""),"tok_in":rr.get("tok_in",0),"tok_out":rr.get("tok_out",0),"chyba":None,"provider":"claude_code_subscription","model":rr.get("model"),"fallback_used":False,"subscription_usage":True}
            if provider == "openai":
                if not has_openai_key():
                    raise RuntimeError("OpenAI key missing")
                if schema:
                    rr = _openai_structured(system=system, messages=messages, schema=schema,
                                            schema_name=schema_name, max_tokens=max_tokens, model=openai_model)
                    return {"text": json.dumps(rr["data"], ensure_ascii=False), "tok_in": rr["tok_in"],
                            "tok_out": rr["tok_out"], "chyba": None, "provider": "openai",
                            "model": rr.get("model"), "fallback_used": provider != order[0]}
                rr = _openai_text(system=system, messages=messages, max_tokens=max_tokens, model=openai_model)
                rr["fallback_used"] = provider != order[0]
                return rr
            if not has_anthropic_key():
                raise RuntimeError("Anthropic key missing")
            if schema:
                rr = _anthropic_structured(system=system, messages=messages, schema=schema,
                                           schema_name=schema_name, anthropic_model=anthropic_model,
                                           max_tokens=max_tokens)
                return {"text": json.dumps(rr["data"], ensure_ascii=False), "tok_in": rr["tok_in"],
                        "tok_out": rr["tok_out"], "chyba": None, "provider": "anthropic",
                        "model": rr.get("model"), "fallback_used": provider != order[0]}
            client = create_anthropic_client(max_retries=0)
            mid = resolve_available_anthropic_model(anthropic_model)
            params = {k: v for k, v in kw.items() if k not in {"model"}}
            r = _anthropic_capacity_call(create_message, client, model=mid, max_tokens=max_tokens, **params)
            blocks = getattr(r, "content", []) or []
            tool_blocks = [b for b in blocks if getattr(b, "type", None) == "tool_use"]
            text = (json.dumps(getattr(tool_blocks[0], "input", {}) or {}, ensure_ascii=False)
                    if tool_blocks else
                    "".join(str(getattr(b, "text", "") or "") for b in blocks if getattr(b, "type", None) == "text"))
            u = getattr(r, "usage", None)
            return {"text": text, "tok_in": int(getattr(u, "input_tokens", 0) or 0),
                    "tok_out": int(getattr(u, "output_tokens", 0) or 0), "chyba": None,
                    "provider": "anthropic", "model": mid, "fallback_used": provider != order[0]}
        except Exception as exc:
            if _is_cancel_exception(exc):
                raise
            errors.append((provider, f"[{classify_provider_exception(exc)}] {exc}"))
    return {"text": "", "tok_in": 0, "tok_out": 0,
            "chyba": " | ".join(f"{p}: {e[:180]}" for p, e in errors),
            "provider": "none", "fallback_used": bool(allow_fallback and len(order) > 1)}


def roundtrip_test(*, prefer: str = "anthropic") -> dict[str, Any]:
    """End-to-end structured round trip used by Settings → Diagnostika AI.

    This is the only check that proves the whole chain (key → client → model →
    structured contract → parsing) works; a key probe alone cannot.
    """
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}, "note": {"type": "string"}},
              "required": ["ok", "note"], "additionalProperties": False}
    started = time.time()
    try:
        out = call_structured(system="Jsi testovací nástroj. Odpověz stroze.",
                              messages=[{"role": "user", "content": "Vrať ok=true a note='npc'."}],
                              schema=schema, schema_name="npc_roundtrip",
                              anthropic_model="sonnet", max_tokens=200, prefer=prefer, allow_fallback=False)
        return {"ok": bool(out.get("data", {}).get("ok", True)), "provider": out.get("provider"),
                "model": out.get("model"), "mode": out.get("mode"),
                "fallback_used": bool(out.get("fallback_used")),
                "seconds": round(time.time() - started, 2),
                "message": f"Strukturovaný test prošel přes {out.get('provider')} ({out.get('model')})."}
    except Exception as exc:
        return {"ok": False, "provider": "none", "kind": classify_provider_exception(exc),
                "seconds": round(time.time() - started, 2), "message": str(exc)[:700]}
