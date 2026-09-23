from __future__ import annotations
import contextvars
from typing import Any, Callable

_PROGRESS = contextvars.ContextVar('npc_ai_progress', default=None)
_CANCEL = contextvars.ContextVar('npc_ai_cancel', default=None)


def bind_runtime(progress: Callable[[dict[str, Any]], None] | None = None,
                 cancel: Callable[[], bool] | None = None):
    return (_PROGRESS.set(progress), _CANCEL.set(cancel))


def reset_runtime(tokens) -> None:
    try: _PROGRESS.reset(tokens[0])
    except Exception: pass
    try: _CANCEL.reset(tokens[1])
    except Exception: pass


def report(payload: dict[str, Any] | str) -> None:
    cb = _PROGRESS.get()
    if not cb: return
    try:
        cb(payload if isinstance(payload, dict) else {'phase': str(payload)})
    except Exception:
        pass


def cancel_requested() -> bool:
    cb = _CANCEL.get()
    if not cb: return False
    try: return bool(cb())
    except Exception: return False


def is_cancel_exception(exc: BaseException | None) -> bool:
    """Recognize cooperative cancellation through wrapper exception chains."""
    seen=set();cur=exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if type(cur).__name__=='ClaudeCodeCancelled' or str(cur).strip()=='JOB_CANCELLED':
            return True
        cur=getattr(cur,'__cause__',None) or getattr(cur,'__context__',None)
    return False
