"""
executor
~~~~~~~~
The Executor desk — processes estate distribution claims against sealed wills.

Built on top of gate_core.  Registers the executor refusal vocabulary at
import time so that it is in place before any adjudication call, even if only
a subset of submodules is imported by the caller.
"""

from gate_core import register_refusal

# ---------------------------------------------------------------------------
# Register the executor refusal vocabulary for domain 'executor'.
# 'unmeasured' is reserved by gate_core and must NOT be registered here.
# ---------------------------------------------------------------------------
_EXECUTOR_REFUSALS = [
    "death_unverified",
    "seal_broken",
    "will_superseded",
    "sign_unoccupied",
    "share_mismatch",
    "beneficiary_unknown",
]

for _name in _EXECUTOR_REFUSALS:
    register_refusal("executor", _name)

# ---------------------------------------------------------------------------
# Re-export public API
# ---------------------------------------------------------------------------
from executor.registry import ExecutorRegistry
from executor.measurer import ExecutorMeasurer
from executor.claims import make_distribution_claim
from executor.scenarios import run_scenarios, ScenarioResult

__all__ = [
    "ExecutorRegistry",
    "ExecutorMeasurer",
    "make_distribution_claim",
    "run_scenarios",
    "ScenarioResult",
]
