"""
citation_gate
~~~~~~~~~~~~~
The Citation Gate desk — processes factual assertions in obituary drafts
against sealed source records (death record, governing will, family record).

Built on top of gate_core.  Registers the citation refusal vocabulary at
import time so that it is in place before any adjudication call, even if only
a subset of submodules is imported by the caller.
"""

from gate_core import register_refusal

# ---------------------------------------------------------------------------
# Register the citation refusal vocabulary for domain 'citation'.
# 'unmeasured' is reserved by gate_core and must NOT be registered here.
# ---------------------------------------------------------------------------
_CITATION_REFUSALS = [
    "missing_citation",
    "unsupported_claim",
    "source_contradicts",
]

for _name in _CITATION_REFUSALS:
    register_refusal("citation", _name)

# ---------------------------------------------------------------------------
# Re-export public API
# ---------------------------------------------------------------------------
from citation_gate.sources import SourceRegistry
from citation_gate.measurer import CitationMeasurer
from citation_gate.claims import make_assertion_claim
from citation_gate.publish import PublishChecker, PublishDecision, check_publish
from citation_gate.scenarios import run_scenarios, DraftResult, AssertionResult

__all__ = [
    "SourceRegistry",
    "CitationMeasurer",
    "make_assertion_claim",
    "PublishChecker",
    "PublishDecision",
    "check_publish",
    "run_scenarios",
    "DraftResult",
    "AssertionResult",
]
