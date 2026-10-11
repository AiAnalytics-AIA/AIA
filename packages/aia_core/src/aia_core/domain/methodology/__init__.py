"""AIA's mathematics and statistics, as the methodologist reads them (ADR 0023).

Each method module -- the Sociomap, aggregation, support, weighting, the response process,
validation, readiness, presentation, simulation -- is a catalogue of steps in computation
order. A step names its formula, the function it describes (pinned by source hash), the
specification fields and constants it reads, the evidence for it and the tests that pin it.
:func:`describe` reads every value from the code; :func:`module_problems` says what a
catalogue is missing. :data:`MODULES` is every registered module.

Pure: stdlib and Pydantic only.
"""

from .catalogue import (
    BuiltinFormula,
    ConstantRef,
    Evidence,
    EvidenceKind,
    MethodModule,
    MethodStep,
    ParameterRef,
    Preset,
    StepGroup,
    Symbol,
)
from .registry import MODULES, module
from .resolution import (
    ABSENT,
    MethodologyReferenceError,
    ModuleView,
    StepView,
    ValueOrigin,
    ValueView,
    describe,
    leaf_paths,
    module_problems,
    read_constant,
    read_path,
    resolve_callable,
)

__all__ = [
    "ABSENT",
    "MODULES",
    "BuiltinFormula",
    "ConstantRef",
    "Evidence",
    "EvidenceKind",
    "MethodModule",
    "MethodStep",
    "MethodologyReferenceError",
    "ModuleView",
    "ParameterRef",
    "Preset",
    "StepGroup",
    "StepView",
    "Symbol",
    "ValueOrigin",
    "ValueView",
    "describe",
    "leaf_paths",
    "module",
    "module_problems",
    "read_constant",
    "read_path",
    "resolve_callable",
]
