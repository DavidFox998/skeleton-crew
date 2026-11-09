"""
gate_core.claim
~~~~~~~~~~~~~~~
Defines the immutable Claim value object submitted to the gate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


def _canonical_json(obj: dict) -> str:
    """Return canonical JSON: sorted keys, no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


@dataclass(frozen=True)
class Claim:
    """A typed, immutable unit of work submitted to the gate.

    Attributes:
        domain:     Identifies the desk (e.g. "executor", "citation_gate").
        claim_type: Identifies the kind of claim (e.g. "asset_distribution").
        payload:    Domain-specific structured data.  Must be JSON-serialisable.
    """

    domain: str
    claim_type: str
    payload: dict

    def __post_init__(self) -> None:
        if not self.domain or not self.domain.strip():
            raise ValueError("Claim.domain must be a non-empty string.")
        if not self.claim_type or not self.claim_type.strip():
            raise ValueError("Claim.claim_type must be a non-empty string.")
        # Validate payload is JSON-serialisable.
        try:
            _canonical_json(self.payload)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Claim.payload is not JSON-serialisable: {exc}"
            ) from exc

    def to_dict(self) -> dict:
        """Return a plain-dict snapshot suitable for receipt storage."""
        return {
            "domain": self.domain,
            "claim_type": self.claim_type,
            "payload": self.payload,
        }
