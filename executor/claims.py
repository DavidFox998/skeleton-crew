"""
executor.claims
~~~~~~~~~~~~~~~
Thin factory for estate_distribution Claims.

Application code that submits claims should not need to know gate_core's
Claim constructor signature.  The domain and claim_type values belong to the
executor domain, not to the caller.
"""

from __future__ import annotations

from gate_core import Claim


def make_distribution_claim(
    will_ref: str,
    distributions: list[dict],
) -> Claim:
    """Build a gate_core.Claim for an estate distribution.

    Args:
        will_ref:      Hex SHA-256 seal of the target will.
        distributions: List of {"sign": str, "item": str, "beneficiary": str}.

    Returns:
        gate_core.Claim with domain="executor", claim_type="estate_distribution".
    """
    return Claim(
        domain="executor",
        claim_type="estate_distribution",
        payload={
            "will_ref": will_ref,
            "distributions": distributions,
        },
    )
