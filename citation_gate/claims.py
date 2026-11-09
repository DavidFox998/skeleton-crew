"""
citation_gate.claims
~~~~~~~~~~~~~~~~~~~~
Provides a thin factory function so callers can construct a
``factual_assertion`` claim from plain arguments without importing
``gate_core`` directly.
"""

from __future__ import annotations

from gate_core import Claim


def make_assertion_claim(
    text: str,
    fact_key: str,
    value: str,
    citation: str | None,
) -> Claim:
    """Build a gate_core.Claim for a factual assertion.

    Args:
        text:      The sentence exactly as it will appear in the published
                   obituary.
        fact_key:  The key being asserted (e.g. ``"date_of_death"``,
                   ``"bequest.Taurus.item"``).
        value:     The value being asserted for that key.
        citation:  Source id string (``"death_record"``, ``"will_2024"``, or
                   ``"family_record"``), or ``None`` if no citation was
                   provided.  ``None`` serialises to JSON ``null``.

    Returns:
        A ``gate_core.Claim`` with ``domain="citation"`` and
        ``claim_type="factual_assertion"``.
    """
    return Claim(
        domain="citation",
        claim_type="factual_assertion",
        payload={
            "text":      text,
            "fact_key":  fact_key,
            "value":     value,
            "citation":  citation,
        },
    )
