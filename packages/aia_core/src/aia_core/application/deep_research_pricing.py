"""What each kind of call a Deep Research run makes may cost, from the deployment's keys.

Plan ``deep-research-web-search.md`` chunk 55 (DRL-0, interfaces I22). Until 2026-10-21 these
prices were worked out in the API router from the API's own copy of the environment
(F-DRL-3), so nothing outside the router -- a Lead plan step in the worker
(``lead-orchestration#LO5a.4``) -- could price a start the same way. They live here now, over
one typed value, :class:`DeepResearchPricingSettings`, which each composition root builds from
the same ``AIA_*`` keys the worker composes Deep Research from (the API's ``config.py``
today). The start (:meth:`~aia_core.application.deep_research.DeepResearchRuns.start`) and the
read-only quote (:meth:`~aia_core.application.deep_research.DeepResearchRuns.quote`) are
priced by these prices and one ceiling function, so a quote and the start it describes
cannot disagree.

Nothing here guesses: a price, window or limit that is not configured makes its kinds
``unknown``, never zero (CLAUDE.md § 8).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from ..domain.deep_research.budgets import CallKind, ResearchMode
from ..domain.deep_research.common_crawl import MIN_SCAN_CUTOFF_BYTES, AthenaPricing
from ..domain.deep_research.request_limits import (
    REQUEST_LIMITS,
    RESEARCH_KINDS,
    KindBudget,
    ModelPrices,
    RequestLimits,
    kind_budgets,
)
from ..domain.deep_research.settings import request_limits
from ..domain.run_cost import DeepResearchPrices, RoutePrice
from ..domain.scope import StudyContext
from ..infrastructure.deep_research_settings_repository import settings_in_force_for_study

__all__ = ["DeepResearchPricingSettings", "SearchRoute"]

SearchRoute = Literal["off", "wikipedia", "brave"]


@dataclass(frozen=True, slots=True)
class DeepResearchPricingSettings:
    """The keys a Deep Research ceiling is priced from, as one deployment states them.

    Each field is the ``AIA_*`` key the worker composes from (``aia_executors.
    deep_research_runtime``): the route's model prices (``AIA_BEDROCK_*_USD_PER_MTOK``), the
    model's window, the research output limit, the thinking budget, the search route and
    Brave's dated price, Common Crawl's switch and index price keys, the listed connectors and
    the two mode switches. ``engine_lead`` is ``AIA_DEEP_RESEARCH_LEAD``: the Deep Research
    engine's *lead researcher* mode, not the Research Lead (Vedoucí výzkumu) (F-DRL-7).

    ``enabled`` is ``AIA_DEEP_RESEARCH_ENABLED`` as this process's environment carries it, or
    ``None`` when it was not given here: what the worker actually composed is the worker's,
    published only once ``lead-orchestration#LO12b``'s record exists.
    """

    input_usd_per_mtok: float | None = None
    output_usd_per_mtok: float | None = None
    cache_read_usd_per_mtok: float | None = None
    cache_write_usd_per_mtok: float | None = None
    context_window_tokens: int | None = None
    max_output_tokens: int | None = None
    thinking_budget_tokens: int | None = None
    #: ``AIA_DEEP_RESEARCH_WEB_SEARCH``; empty: the Wikipedia switch decides, as the worker does.
    web_search: Literal["", "off", "wikipedia", "brave"] = ""
    wikipedia_enabled: bool = False
    brave_usd_per_1000: float | None = None
    common_crawl: bool = False
    common_crawl_max_scan_bytes: int | None = None
    common_crawl_usd_per_tb_scanned: float | None = None
    common_crawl_min_billed_bytes: int | None = None
    common_crawl_billing_increment_bytes: int | None = None
    connectors: str = ""
    agent_directed: bool = False
    engine_lead: bool = False
    enabled: bool | None = None

    def search_route(self) -> SearchRoute:
        """The search route the worker composes from the same keys: off, wikipedia or brave."""
        if self.web_search:
            return self.web_search
        return "wikipedia" if self.wikipedia_enabled else "off"

    def mode(self) -> ResearchMode:
        """The mode the worker composes from the same switches (the engine's lead mode needs
        agent-directed)."""
        if self.engine_lead:
            return ResearchMode.LEAD
        if self.agent_directed:
            return ResearchMode.AGENT_DIRECTED
        return ResearchMode.PLANNED

    def budgets(
        self, limits: Mapping[CallKind, RequestLimits] = REQUEST_LIMITS
    ) -> dict[CallKind, KindBudget] | None:
        """Each kind of model request's window, output limit and reservation, derived as the
        worker derives them (``request_limits.kind_budgets``); ``None`` when a key it needs is
        missing or not a valid value -- unknown, never a guess. ``limits`` are the request
        limits in force (the study's Deep Research settings, chunk 43c)."""
        if (
            self.input_usd_per_mtok is None
            or self.output_usd_per_mtok is None
            or self.context_window_tokens is None
            or self.max_output_tokens is None
        ):
            return None
        try:
            return kind_budgets(
                ModelPrices(
                    input_usd_per_mtok=self.input_usd_per_mtok,
                    output_usd_per_mtok=self.output_usd_per_mtok,
                    cache_read_usd_per_mtok=self.cache_read_usd_per_mtok,
                    cache_write_usd_per_mtok=self.cache_write_usd_per_mtok,
                ),
                context_window_tokens=self.context_window_tokens,
                max_output_tokens=self.max_output_tokens,
                thinking_budget_tokens=self.thinking_budget_tokens,
                limits=limits,
            )
        except ValueError:
            return None

    def prices(
        self, limits: Mapping[CallKind, RequestLimits] = REQUEST_LIMITS
    ) -> DeepResearchPrices:
        """What each kind of call may cost, as this deployment says.

        Each kind of research agent's request reserves its own kind's amount
        (:meth:`budgets`); with a key missing, every model kind is unknown. The retrieval a
        deployment composes (``aia_executors.deep_research_live``) is fee-free but Brave's
        search: the public Wikipedia search, its pages or any public host's, and the listed
        public dataset connectors cost nothing; Brave's search costs its dated price per
        request (unset: unknown, never zero), and a paid route needs the organization's
        sign-off (chunk 44); off, nothing is searched. Common Crawl's index query reserves its
        scan cutoff, billed (unknown without every price key), and its archived pages are
        free. Triage and the focused crawl are composed by no deployment yet, so nothing is
        sent on them.
        """
        budgets = self.budgets(limits)
        model = {
            kind: RoutePrice.unknown()
            if budgets is None
            else RoutePrice.per_call(budgets[kind].reservation_usd)
            for kind in RESEARCH_KINDS
        }
        route = self.search_route()
        free, off = RoutePrice.per_call(0.0), RoutePrice.off()
        if route == "brave":
            per_1000 = self.brave_usd_per_1000
            search = (
                RoutePrice.unknown() if per_1000 is None else RoutePrice.per_call(per_1000 / 1000)
            )
        else:
            search = free if route == "wikipedia" else off
        searching = route != "off"
        # The worker composes Common Crawl only beside a search route and the public fetch.
        crawling = searching and self.common_crawl
        return DeepResearchPrices(
            {
                **model,
                CallKind.SEARCH: search,
                CallKind.FETCH: free if searching else off,
                CallKind.TRIAGE: off,
                CallKind.CRAWL_FETCH: off,
                CallKind.CONNECTOR: free if searching and self.connectors.strip() else off,
                CallKind.URL_INDEX_QUERY: self._index_price() if crawling else off,
                CallKind.ARCHIVE_FETCH: free if crawling else off,
            }
        )

    def study_prices(self, session: Session, scope: StudyContext) -> DeepResearchPrices:
        """:meth:`prices` under the request limits the study's run would pin: a start or a
        quote is priced as the worker will reserve (chunk 43c)."""
        return self.prices(request_limits(settings_in_force_for_study(session, scope)))

    def _index_price(self) -> RoutePrice:
        """A Common Crawl index query's reservation: its scan cutoff, billed; unknown without
        every price key, and unknown for a value the worker would refuse."""
        cutoff = self.common_crawl_max_scan_bytes
        per_tb = self.common_crawl_usd_per_tb_scanned
        minimum = self.common_crawl_min_billed_bytes
        increment = self.common_crawl_billing_increment_bytes
        if cutoff is None or per_tb is None or minimum is None or increment is None:
            return RoutePrice.unknown()
        if cutoff < MIN_SCAN_CUTOFF_BYTES:  # the worker refuses it: no route, no price
            return RoutePrice.unknown()
        try:
            pricing = AthenaPricing(
                usd_per_tb_scanned=per_tb,
                minimum_billed_bytes=minimum,
                billing_increment_bytes=increment,
            )
            return RoutePrice.athena(pricing, cutoff)
        except ValueError:
            return RoutePrice.unknown()
