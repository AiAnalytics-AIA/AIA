"""Population errors.

Every one of these is a refusal. The population context has no degraded mode: a
version that cannot be identified, validated, resolved, weighted or enriched is not
used, and the run that needed it does not start. That is the whole difference from
the reference, which swallowed a registry failure (R2), an enrichment failure (R1)
and a missing weight (R3) and carried on against a different population.

Each error carries a stable machine-readable ``reason`` so that callers -- the API
error contract, a workflow step, an operator dashboard -- can branch on the cause
without parsing prose.
"""

from __future__ import annotations

__all__ = [
    "CompanionsIncomplete",
    "EnrichmentFailed",
    "ImportRejected",
    "LineageError",
    "PopulationBindingConflict",
    "PopulationBindingMissing",
    "PopulationBindingRequired",
    "PopulationError",
    "PopulationNotEstablished",
    "PromotionConflict",
    "PromotionRefused",
    "StaticReferenceImmutable",
    "UnknownDatasetVersion",
    "VersionIntegrityError",
    "VersionNotRuntimeEligible",
    "WeightResolutionError",
]


class PopulationError(RuntimeError):
    """Base class: a population operation was refused."""

    reason: str = "population_error"

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        if reason is not None:
            self.reason = reason


class UnknownDatasetVersion(PopulationError):
    """A version id that the registry does not hold."""

    reason = "unknown_version"


class LineageError(PopulationError):
    """A parent that is missing, a cycle, or a descent rule that does not hold."""

    reason = "lineage"


class PromotionRefused(PopulationError):
    """An establish or promote call that the rules do not permit."""

    reason = "promotion_refused"


class StaticReferenceImmutable(PromotionRefused):
    """Any attempt to move, replace or impersonate the static reference.

    The reference raised this even for an explicit call
    (``promote_live_version`` refusing a target that resolved to the static path);
    here it is structural -- a STATIC population has no promote path at all.
    """

    reason = "static_immutable"


class PromotionConflict(PromotionRefused):
    """The caller's expected current version is not the current version.

    Promotion is compare-and-set so that two operators cannot each believe they
    promoted, and so that nobody promotes over a change they have not seen.
    """

    reason = "promotion_conflict"


class PopulationNotEstablished(PopulationError):
    """A population id with no established version."""

    reason = "not_established"


class VersionNotRuntimeEligible(PopulationError):
    """A registered version that has never been bound to a population.

    ``v17_0_BASE`` is the lineage root and a build input only; a run may not be
    resolved against it, even by an explicit pin.
    """

    reason = "not_runtime_eligible"


class VersionIntegrityError(PopulationError):
    """Bytes that do not hash to the version they claim to be.

    The production equivalent of ``_resolve_registered_path`` rejecting a moved
    or swapped file rather than silently using it.
    """

    reason = "integrity"


class ImportRejected(PopulationError):
    """An import that failed at least one validation check.

    Carries every failed check, not only the first, so that one attempt tells an
    operator everything that is wrong with a bundle.
    """

    reason = "import_rejected"

    def __init__(self, message: str, *, failures: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.failures = failures


class CompanionsIncomplete(PopulationError):
    """A version whose contract declares companions has no validated companion set.

    Such a version is registered -- its panel is preserved and validated -- but it
    is not usable: it cannot be established, promoted or resolved for a run, because
    without its companions it cannot say what may be claimed from it.
    """

    reason = "companions_incomplete"


class WeightResolutionError(PopulationError):
    """An unknown weight role, an absent weight column or an unusable weight value.

    There is no default weight and no fallback weight. The reference's
    ``or "vaha_kalibrovana"`` silently moved every result onto the Census 2021
    basis; its column-missing path went fully unweighted (F11).
    """

    reason = "weight"


class EnrichmentFailed(PopulationError):
    """The derived runtime view could not be produced.

    Raised when no enricher is configured for a view that needs one, or when an
    enricher returns anything other than exactly the declared derived fields at the
    panel's row count. The reference's ``except Exception: pass`` around
    ``enrich_panel`` is R1.
    """

    reason = "enrichment"


class PopulationBindingRequired(PopulationError):
    """A run with population-consuming steps was created without a binding."""

    reason = "binding_required"


class PopulationBindingMissing(PopulationError):
    """Population data was requested for a run that recorded no binding."""

    reason = "binding_missing"


class PopulationBindingConflict(PopulationError):
    """An idempotent re-submission asked for a different population than recorded.

    Returning the existing run would silently substitute the recorded version for
    the one the caller asked for.
    """

    reason = "binding_conflict"
