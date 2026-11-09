"""
gate_core.mandate
~~~~~~~~~~~~~~~~~
Defines SealedMandate and the seal/verify helpers.

A mandate's content is hashed at sealing time.  Any subsequent modification
of the content dict is detectable via verify_mandate().
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MandateTamperError(Exception):
    """Raised when a mandate's seal does not match its recomputed hash.

    This is a hard error, not a gate refusal.  It indicates that the mandate
    content has been altered after sealing.
    """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_json(obj: dict) -> str:
    """Return canonical JSON: sorted keys, no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SealedMandate:
    """A mandate whose content is protected by a SHA-256 seal.

    Attributes:
        domain:  Must match the domain of claims submitted against this mandate.
        content: The mandate's terms.  Must be JSON-serialisable.
        seal:    Hex SHA-256 of canonical_json(content).
    """

    domain: str
    content: dict
    seal: str

    def __post_init__(self) -> None:
        if not self.domain or not self.domain.strip():
            raise ValueError("SealedMandate.domain must be a non-empty string.")
        try:
            _canonical_json(self.content)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"SealedMandate.content is not JSON-serialisable: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def seal_mandate(domain: str, content: dict) -> SealedMandate:
    """Create a SealedMandate by hashing *content* with SHA-256.

    Args:
        domain:  The desk identifier for this mandate.
        content: Mandate terms dict.  Must be JSON-serialisable.

    Returns:
        A new SealedMandate with the computed seal.
    """
    seal = _sha256_hex(_canonical_json(content))
    return SealedMandate(domain=domain, content=content, seal=seal)


def verify_mandate(mandate: SealedMandate) -> bool:
    """Return True iff the mandate's seal matches its recomputed hash."""
    expected = _sha256_hex(_canonical_json(mandate.content))
    return expected == mandate.seal
