"""
gate_core.measure
~~~~~~~~~~~~~~~~~
Defines the MeasurementProtocol structural protocol and the MeasurementResult
value object returned by domain-specific measurers.

Measurers observe and report facts; they do not decide verdicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from gate_core.claim import Claim
    from gate_core.mandate import SealedMandate


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MeasurementResult:
    """The output of a domain-specific measurer.

    Attributes:
        observations: Stable-keyed observed values that influenced or could
                      influence the verdict.  Must be JSON-serialisable.
        passed:       Advisory opinion: True if the claim satisfies the mandate.
                      The gate passes this through directly in the base policy
                      (True → Pass, False → Refused), but domain extensions may
                      apply additional rules.
    """

    observations: dict
    passed: bool


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class MeasurementProtocol(Protocol):
    """Structural protocol for all domain-specific measurers.

    Any object with a ``measure`` method matching this signature satisfies the
    protocol.  No base-class inheritance is required.
    """

    def measure(
        self,
        claim: "Claim",
        mandate: "SealedMandate",
    ) -> MeasurementResult:
        """Measure *claim* against *mandate* and return a MeasurementResult.

        Must not raise intentionally; the gate catches all exceptions and
        treats them as an absent measurement.
        """
        ...
