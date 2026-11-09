"""
citation_gate.measurer
~~~~~~~~~~~~~~~~~~~~~~
CitationMeasurer — implements gate_core.MeasurementProtocol.

Performs all five precedence checks in deterministic order and returns a
MeasurementResult.  Has no knowledge of verdicts; it only observes and
reports.

On step 3 (source seal check), if the cited source's seal is broken, this
measurer raises ``gate_core.MandateTamperError`` explicitly so that tampering
surfaces as a hard error rather than the silently generic ``unmeasured``
refusal that gate_core would produce if the exception were swallowed.

Note: gate_core.adjudicate() wraps measure() in ``except Exception``, which
catches MandateTamperError.  The re-raise here is intentional per the
design's Approach A specification; if gate_core is updated to re-raise
MandateTamperError before the generic handler the error will propagate to the
caller.  Until then, gate_core converts it to REFUSED('unmeasured').
"""

from __future__ import annotations

from gate_core import (
    Claim,
    MandateTamperError,
    MeasurementResult,
    SealedMandate,
    verify_mandate,
)

from citation_gate.sources import SourceRegistry


class CitationMeasurer:
    """Measures a factual_assertion claim against the citation source registry.

    Args:
        registry: A SourceRegistry instance providing access to the three
                  sealed source records and their derived fact tables.
    """

    def __init__(self, registry: SourceRegistry) -> None:
        self._registry = registry

    def measure(
        self,
        claim: Claim,
        mandate: SealedMandate,
    ) -> MeasurementResult:
        """Measure *claim* against the source registry.

        The *mandate* argument is the desk's governing SealedMandate (passed
        through from gate_core.adjudicate); it is not directly used here
        because seal verification of the desk mandate is already performed by
        gate_core before this method is called.  The per-source seal checks
        are performed by this method against the cited source retrieved from
        the registry.

        Precedence (first failing check wins):
            1. Citation present?    → missing_citation
            2. Source known?        → unsupported_claim (source_not_registered)
            3. Source seal intact?  → raise MandateTamperError
            4. Fact key in table?   → unsupported_claim (fact_key_not_in_source)
            5. Value matches?       → source_contradicts
            6. All pass             → passed=True
        """
        citation: str | None = claim.payload.get("citation")
        fact_key: str = claim.payload["fact_key"]
        value: str = claim.payload["value"]

        # ── 1. Citation present? ─────────────────────────────────────────
        if not citation:
            return MeasurementResult(
                observations={
                    "refusal_name": "missing_citation",
                    "fact_key": fact_key,
                },
                passed=False,
            )

        # ── 2. Source known? ─────────────────────────────────────────────
        if citation not in self._registry.known_source_ids():
            return MeasurementResult(
                observations={
                    "refusal_name": "unsupported_claim",
                    "citation": citation,
                    "reason": "source_not_registered",
                    "fact_key": fact_key,
                },
                passed=False,
            )

        # ── 3. Source seal intact? ───────────────────────────────────────
        source_mandate: SealedMandate = self._registry.source(citation)  # type: ignore[assignment]
        if not verify_mandate(source_mandate):
            raise MandateTamperError(
                f"Source record '{citation}' seal verification failed"
            )

        # ── 4. Fact key in table? ────────────────────────────────────────
        table: dict[str, str] = self._registry.fact_table(citation)  # type: ignore[assignment]
        if fact_key not in table:
            return MeasurementResult(
                observations={
                    "refusal_name": "unsupported_claim",
                    "source_id": citation,
                    "fact_key": fact_key,
                    "reason": "fact_key_not_in_source",
                },
                passed=False,
            )

        # ── 5. Value matches? ────────────────────────────────────────────
        stored_value: str = table[fact_key]
        if stored_value != value:
            return MeasurementResult(
                observations={
                    "refusal_name": "source_contradicts",
                    "source_id": citation,
                    "fact_key": fact_key,
                    "asserted_value": value,
                    "stored_value": stored_value,
                },
                passed=False,
            )

        # ── 6. All checks passed ─────────────────────────────────────────
        return MeasurementResult(
            observations={
                "source_id": citation,
                "fact_key": fact_key,
                "asserted_value": value,
                "stored_value": stored_value,
                "source_seal": source_mandate.seal,
            },
            passed=True,
        )
