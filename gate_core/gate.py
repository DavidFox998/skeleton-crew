"""
gate_core.gate
~~~~~~~~~~~~~~
Provides ``adjudicate()``: the single composition function that runs the full
gate pipeline so that application code never has to re-derive the safety rules.

Pipeline
--------
1. Verify the mandate seal — raise ``MandateTamperError`` immediately if it fails.
   Nothing is appended to the chain on a tamper error.
2. Call ``measurer.measure(claim, sealed_mandate)`` inside ``try/except``.
   Any exception is caught; the result is treated as an absent measurement and
   the exception message is preserved as ``measurement_error``.
3. Produce a verdict:
   - No measurement  → ``Refused(name='unmeasured')``
   - ``passed=True``  → ``Pass()``
   - ``passed=False`` → ``Refused(name=<refusal_name>)`` where ``refusal_name``
     is taken from ``measurement.observations['refusal_name']``.  If that key is
     absent or the name is not registered for the domain, fall back to
     ``Refused(name='unmeasured')``.
4. Append a receipt to ``chain`` (mutates the list in-place) and return
   ``(verdict, receipt)``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from gate_core.claim import Claim
from gate_core.mandate import MandateTamperError, SealedMandate, verify_mandate
from gate_core.measure import MeasurementProtocol, MeasurementResult
from gate_core.receipt import Receipt, append_receipt
from gate_core.verdict import (
    Pass,
    Refused,
    Verdict,
    is_valid_refusal,
    make_pass,
    make_refused,
    unmeasured_refusal,
)


def _utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string (seconds precision)."""
    return datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def adjudicate(
    claim: Claim,
    sealed_mandate: SealedMandate,
    measurer: MeasurementProtocol,
    chain: list[Receipt],
    *,
    timestamp_utc: str | None = None,
) -> tuple[Verdict, Receipt]:
    """Run the full gate pipeline for a single claim.

    Args:
        claim:           The typed claim to adjudicate.
        sealed_mandate:  The mandate to verify and measure against.
        measurer:        A ``MeasurementProtocol`` implementor.
        chain:           The existing receipt chain (mutated: receipt is appended).
        timestamp_utc:   Optional ISO-8601 UTC timestamp; defaults to now.

    Returns:
        A ``(verdict, receipt)`` tuple.  The receipt has already been appended
        to ``chain``.

    Raises:
        MandateTamperError: If ``sealed_mandate``'s seal does not match its
                            content.  Nothing is appended to ``chain``.
    """
    ts = timestamp_utc if timestamp_utc is not None else _utc_now()

    # ── 1. Mandate verification ────────────────────────────────────────────
    if not verify_mandate(sealed_mandate):
        raise MandateTamperError(
            f"Mandate seal mismatch for domain '{sealed_mandate.domain}'. "
            "The mandate content may have been altered after sealing."
        )

    # ── 2. Measurement ─────────────────────────────────────────────────────
    measurement: MeasurementResult | None = None
    measurement_error: str | None = None
    try:
        measurement = measurer.measure(claim, sealed_mandate)
    except MandateTamperError:
        # A tamper error from inside the measurer is a hard error — it must
        # propagate to the caller rather than silently becoming unmeasured.
        # Nothing is appended to the chain.
        raise
    except Exception as exc:  # noqa: BLE001
        measurement_error = str(exc) or repr(exc)

    # ── 3. Verdict ─────────────────────────────────────────────────────────
    if measurement is None:
        # Measurer raised an exception — treat as absent measurement.
        verdict: Verdict = unmeasured_refusal()
    elif measurement.passed:
        verdict = make_pass()
    else:
        # Measurer says the claim failed.  Expect a 'refusal_name' key in
        # observations; fall back to 'unmeasured' if it is missing or unknown.
        refusal_name: str = measurement.observations.get('refusal_name', '')
        if refusal_name and is_valid_refusal(claim.domain, refusal_name):
            verdict = make_refused(claim.domain, refusal_name)
        else:
            verdict = unmeasured_refusal()

    # ── 4. Receipt ─────────────────────────────────────────────────────────
    receipt = append_receipt(
        chain,
        claim,
        measurement,
        measurement_error,
        verdict,
        ts,
    )
    chain.append(receipt)

    return verdict, receipt
