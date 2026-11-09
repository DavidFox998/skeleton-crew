"""
gate_core.receipt
~~~~~~~~~~~~~~~~~
Defines the Receipt value object, the chain-append operation, chain replay,
and the only I/O helpers in the core library (save_chain / load_chain).

Hash computation
----------------
own_hash = SHA-256 of canonical_json of the receipt fields excluding own_hash.
previous_hash is "0" * 64 for the first receipt in a chain.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gate_core.claim import Claim
    from gate_core.measure import MeasurementResult
    from gate_core.verdict import Verdict

from gate_core.claim import Claim
from gate_core.measure import MeasurementResult
from gate_core.verdict import Pass, Refused, Verdict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTINEL_HASH = "0" * 64


def _canonical_json(obj: dict) -> str:
    """Return canonical JSON: sorted keys, no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


def _compute_own_hash(fields: dict) -> str:
    """Compute SHA-256 hex digest over the canonical JSON of *fields*."""
    return hashlib.sha256(_canonical_json(fields).encode('utf-8')).hexdigest()


def _verdict_to_dict(verdict: Verdict) -> dict:
    match verdict:
        case Pass():
            return {'type': 'pass'}
        case Refused(name=n):
            return {'type': 'refused', 'name': n}
        case _:
            raise TypeError(f"Unknown verdict type: {type(verdict)!r}")


def _verdict_from_dict(d: dict) -> Verdict:
    if d['type'] == 'pass':
        return Pass()
    if d['type'] == 'refused':
        return Refused(name=d['name'])
    raise ValueError(f"Unknown verdict type in dict: {d!r}")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Receipt:
    """An immutable, hash-chained record of a single gate decision.

    Attributes:
        claim:             Plain-dict snapshot of the claim.
        measurements:      Plain-dict snapshot of MeasurementResult.observations,
                           or None if the claim was unmeasured.
        measurement_error: Exception message if measurement raised; else None.
        verdict:           Plain-dict form of the verdict.
        timestamp_utc:     ISO-8601 UTC timestamp string.
        previous_hash:     own_hash of the preceding receipt, or "0"*64.
        own_hash:          SHA-256 over canonical fields (excluding own_hash).
    """

    claim: dict
    measurements: dict | None
    measurement_error: str | None
    verdict: dict
    timestamp_utc: str
    previous_hash: str
    own_hash: str


# ---------------------------------------------------------------------------
# Chain append
# ---------------------------------------------------------------------------

def append_receipt(
    chain: list[Receipt],
    claim: Claim,
    measurement: MeasurementResult | None,
    measurement_error: str | None,
    verdict: Verdict,
    timestamp_utc: str,
) -> Receipt:
    """Build and return a new Receipt to append to *chain*.

    Does not mutate *chain*.  The caller is responsible for appending the
    returned receipt to their chain list.

    Args:
        chain:             The existing chain (may be empty).
        claim:             The Claim being recorded.
        measurement:       The MeasurementResult, or None if unmeasured.
        measurement_error: Exception message if measurement failed, else None.
        verdict:           The gate verdict.
        timestamp_utc:     ISO-8601 UTC timestamp string.

    Returns:
        A new Receipt with own_hash computed.
    """
    previous_hash = chain[-1].own_hash if chain else _SENTINEL_HASH

    fields: dict = {
        'claim': claim.to_dict(),
        'measurements': measurement.observations if measurement is not None else None,
        'measurement_error': measurement_error,
        'verdict': _verdict_to_dict(verdict),
        'timestamp_utc': timestamp_utc,
        'previous_hash': previous_hash,
    }
    own_hash = _compute_own_hash(fields)

    return Receipt(
        claim=fields['claim'],
        measurements=fields['measurements'],
        measurement_error=fields['measurement_error'],
        verdict=fields['verdict'],
        timestamp_utc=fields['timestamp_utc'],
        previous_hash=fields['previous_hash'],
        own_hash=own_hash,
    )


# ---------------------------------------------------------------------------
# Chain replay
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReplayResult:
    """Result of a chain verification run.

    Attributes:
        ok:             True iff every receipt in the chain is intact.
        failure_index:  Index of the first failing receipt; None if ok=True.
        failure_reason: 'hash_mismatch' or 'chain_broken'; None if ok=True.
    """

    ok: bool
    failure_index: int | None
    failure_reason: str | None


def verify_chain(receipts: list[Receipt]) -> ReplayResult:
    """Replay *receipts* and return a ReplayResult.

    Stops at the first failure (AC-6.5).

    Checks per receipt:
    1. Recompute own_hash; if mismatch → failure_reason='hash_mismatch'.
    2. For i > 0, verify previous_hash matches receipts[i-1].own_hash;
       if mismatch → failure_reason='chain_broken'.
    """
    for i, receipt in enumerate(receipts):
        # Recompute own_hash from stored fields (excluding own_hash itself).
        fields = {
            'claim': receipt.claim,
            'measurements': receipt.measurements,
            'measurement_error': receipt.measurement_error,
            'verdict': receipt.verdict,
            'timestamp_utc': receipt.timestamp_utc,
            'previous_hash': receipt.previous_hash,
        }
        recomputed = _compute_own_hash(fields)
        if recomputed != receipt.own_hash:
            return ReplayResult(ok=False, failure_index=i, failure_reason='hash_mismatch')

        if i > 0 and receipt.previous_hash != receipts[i - 1].own_hash:
            return ReplayResult(ok=False, failure_index=i, failure_reason='chain_broken')

    return ReplayResult(ok=True, failure_index=None, failure_reason=None)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def receipt_to_dict(receipt: Receipt) -> dict:
    """Return a plain dict representation of *receipt*."""
    return {
        'claim': receipt.claim,
        'measurements': receipt.measurements,
        'measurement_error': receipt.measurement_error,
        'verdict': receipt.verdict,
        'timestamp_utc': receipt.timestamp_utc,
        'previous_hash': receipt.previous_hash,
        'own_hash': receipt.own_hash,
    }


def receipt_from_dict(data: dict) -> Receipt:
    """Reconstruct a Receipt from a plain dict (as stored in a JSON file)."""
    return Receipt(
        claim=data['claim'],
        measurements=data.get('measurements'),
        measurement_error=data.get('measurement_error'),
        verdict=data['verdict'],
        timestamp_utc=data['timestamp_utc'],
        previous_hash=data['previous_hash'],
        own_hash=data['own_hash'],
    )


# ---------------------------------------------------------------------------
# I/O helpers  (only I/O permitted in the core library)
# ---------------------------------------------------------------------------

def save_chain(receipts: list[Receipt], path: str) -> None:
    """Write *receipts* as a JSON array to *path*.

    This is one of only two I/O operations permitted in the gate core library.
    """
    data = [receipt_to_dict(r) for r in receipts]
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def load_chain(path: str) -> list[Receipt]:
    """Read a JSON array from *path* and return a list of Receipt objects.

    This is one of only two I/O operations permitted in the gate core library.
    """
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    return [receipt_from_dict(item) for item in data]
