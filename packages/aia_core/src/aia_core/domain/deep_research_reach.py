"""Deep Research's reach, stated by code (deep-research-web-search 52, settings-backends SB6).

What a worker composed is the only answer to "which routes can a run use": the worker records,
at start, every route and connector the code builds and what its composition made of each
(:class:`RouteReach`): ``active`` (composed, used), or ``built`` (in the code, not composed,
and why, by the switch that decides it), or ``refused`` (it cannot be composed, and why).
Settings reads the newest record. Two things the worker cannot know are read for the
organization asking, by :func:`for_organization`:

* a priced live route runs only once the organization has approved every setting live needs
  (ADR 0022): ``waiting`` until then, naming what is missing;
* a route carries only the data classes it is approved for: asked for a class it does not
  take, it is ``refused`` with reason ``class`` -- or, where the deployment's class gates are
  advisory (develop), it stays as it is and says the refusal would be recorded and passed.

No screen or document names a route set by hand. Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Final

from .residency import DataClass

__all__ = [
    "ReachKind",
    "ReachState",
    "RouteReach",
    "for_organization",
    "order_reach",
    "reach_from_record",
    "reach_record",
]


class ReachKind(StrEnum):
    SEARCH = "search"
    FETCH = "fetch"
    CONNECTOR = "connector"
    INDEX = "index"
    ARCHIVE = "archive"


class ReachState(StrEnum):
    #: Composed, but a priced route waits for the organization's approved settings.
    WAITING = "waiting"
    ACTIVE = "active"
    #: Cannot be used: it cannot be composed, or it does not take the class asked.
    REFUSED = "refused"
    #: In the code, not composed by this deployment.
    BUILT = "built"


@dataclass(frozen=True, slots=True)
class RouteReach:
    route: str
    kind: ReachKind
    state: ReachState
    #: Why, as a code (``deep_research_off``, ``search_route_other``, ``connector_not_listed``,
    #: ``common_crawl_off``, ``agent_directed_off``, ``unavailable``, ``settings_unapproved``,
    #: ``class``); ``None`` for an active route.
    reason: str | None = None
    #: What decides it, in plain words (a switch and its value, a missing setting).
    detail: str | None = None
    #: The data classes the route is approved for; empty when it is not composed.
    classes: tuple[DataClass, ...] = ()
    #: A live route with a price: it runs only on approved settings.
    priced: bool = False
    #: Where its operator processes a request (EU, NON_EU, UNKNOWN), when composed.
    zone: str | None = None
    #: The settings live still needs approved, for a ``waiting`` route.
    missing_settings: tuple[str, ...] = field(default=())
    #: Advisory class gates: a class refusal is recorded and passed, not enforced.
    class_advisory: bool = False
    #: The route's own exception under advisory gates (``ToolRoute.any_class_when_advisory``,
    #: Brave's search only): it takes a query of any class there. Every other route a class
    #: does not reach is still refused under advisory gates, by residency (RetrievalGate).
    any_class_when_advisory: bool = False


_ORDER: Final = {
    ReachState.WAITING: 0,
    ReachState.ACTIVE: 1,
    ReachState.REFUSED: 2,
    ReachState.BUILT: 3,
}


def order_reach(routes: Iterable[RouteReach]) -> list[RouteReach]:
    """Waiting first, then active, then what is off (refused, built); stable within each."""
    return sorted(routes, key=lambda r: _ORDER[r.state])


def for_organization(
    routes: Sequence[RouteReach],
    *,
    missing_for_live: Sequence[str],
    data_class: DataClass | None = None,
    class_gates_advisory: bool = False,
) -> list[RouteReach]:
    """``routes`` as they stand for one organization: a composed priced route ``waiting`` while
    ``missing_for_live`` is not empty, and with ``data_class``, a composed route that does not
    take it ``refused: class`` -- under advisory gates too, unless the route itself takes any
    class there (``any_class_when_advisory``), which is then marked advisory. A refused route
    is never also waiting: it asks for no settings."""
    out: list[RouteReach] = []
    missing = tuple(sorted(missing_for_live))
    for r in routes:
        composed = r.state in (ReachState.ACTIVE, ReachState.WAITING)
        # The class first: a route the class cannot reach is refused, and asks for no
        # approval of its settings.
        if composed and data_class is not None and data_class not in r.classes:
            if class_gates_advisory and r.any_class_when_advisory:
                r = replace(r, class_advisory=True)
            else:
                approved = ", ".join(c.value for c in r.classes) or "no class"
                r = replace(
                    r,
                    state=ReachState.REFUSED,
                    reason="class",
                    detail=(
                        f"approved for {approved}; refused by residency under advisory gates"
                        if class_gates_advisory
                        else f"approved for {approved}"
                    ),
                    missing_settings=(),
                )
                out.append(r)
                continue
        if composed and r.priced and missing:
            r = replace(
                r,
                state=ReachState.WAITING,
                reason="settings_unapproved",
                detail="the organization has not approved every setting live needs",
                missing_settings=missing,
            )
        out.append(r)
    return order_reach(out)


def reach_record(routes: Sequence[RouteReach]) -> list[dict[str, object]]:
    """``routes`` as stored."""
    return [
        {
            "route": r.route,
            "kind": r.kind.value,
            "state": r.state.value,
            "reason": r.reason,
            "detail": r.detail,
            "classes": [c.value for c in r.classes],
            "priced": r.priced,
            "zone": r.zone,
            "any_class_when_advisory": r.any_class_when_advisory,
        }
        for r in routes
    ]


def reach_from_record(stored: Sequence[dict[str, object]]) -> list[RouteReach]:
    """Routes read back as stored; a value the code no longer knows raises, never guessed."""
    out: list[RouteReach] = []
    for item in stored:
        raw = item.get("classes")
        classes = tuple(DataClass(str(c)) for c in raw) if isinstance(raw, list) else ()
        out.append(
            RouteReach(
                route=str(item["route"]),
                kind=ReachKind(str(item["kind"])),
                state=ReachState(str(item["state"])),
                reason=None if item.get("reason") is None else str(item["reason"]),
                detail=None if item.get("detail") is None else str(item["detail"]),
                classes=classes,
                priced=bool(item.get("priced")),
                zone=None if item.get("zone") is None else str(item["zone"]),
                any_class_when_advisory=bool(item.get("any_class_when_advisory")),
            )
        )
    return out
