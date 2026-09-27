from __future__ import annotations

from typing import Any

MAX_FILES = 50
MAX_TOTAL_BYTES = 250 * 1024 * 1024


def batch_add_sources(files: list[dict[str, Any]], *, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Import up to 50 sources as one user action, never calibrating LIVE automatically."""
    from data_library import add_source
    defaults = defaults or {}
    if not isinstance(files, list) or not files:
        raise ValueError("Vyberte alespoň jeden soubor.")
    if len(files) > MAX_FILES:
        raise ValueError(f"Jedna dávka může obsahovat maximálně {MAX_FILES} souborů.")
    total = sum(len(x.get("raw") or b"") for x in files)
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Jedna dávka může mít maximálně 250 MB.")
    out = []
    for x in files:
        raw = x.get("raw") or b""
        try:
            row = add_source(raw=raw, filename=str(x.get("filename") or "source"),
                             source_type=str(x.get("source_type") or defaults.get("source_type") or "other"),
                             title=str(x.get("title") or ""), year=str(x.get("year") or defaults.get("year") or ""),
                             author=str(x.get("author") or defaults.get("author") or ""),
                             source_url=str(x.get("source_url") or defaults.get("source_url") or ""),
                             notes=str(x.get("notes") or defaults.get("notes") or ""))
            out.append({"ok": True, "filename": x.get("filename"), "entry": row})
        except Exception as exc:
            out.append({"ok": False, "filename": x.get("filename"), "error": str(exc)})
    return {"count": len(files), "ok_count": sum(1 for x in out if x["ok"]),
            "failed_count": sum(1 for x in out if not x["ok"]), "total_bytes": total,
            "results": out, "live_population_changed": False}
