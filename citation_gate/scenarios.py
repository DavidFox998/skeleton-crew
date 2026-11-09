"""
citation_gate.scenarios
~~~~~~~~~~~~~~~~~~~~~~~
Defines the six demo scenarios N1–N6 as structured data and provides a runner
that adjudicates each against a receipt chain and evaluates the publish rule.

Scenario N5 is split into two phases:
  N5a — the original three-assertion draft with one wrong assertion.
  N5b — the corrected assertion appended to N5a's chain.
Both phases share a single chain, modelling the real clerk workflow of
correcting one assertion without re-adjudicating the others.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import gate_core
from gate_core import (
    MandateTamperError,
    Receipt,
    SealedMandate,
    Verdict,
    adjudicate,
    seal_mandate,
    verify_chain,
)

from citation_gate.claims import make_assertion_claim
from citation_gate.measurer import CitationMeasurer
from citation_gate.publish import PublishDecision, check_publish
from citation_gate.sources import SourceRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


def _claim_hash(claim: gate_core.Claim) -> str:
    return hashlib.sha256(_canonical_json(claim.to_dict()).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class AssertionResult:
    """The outcome of adjudicating a single factual assertion.

    Attributes:
        text:      The assertion text as it would appear in the obituary.
        fact_key:  The fact key that was asserted.
        verdict:   The gate verdict (Pass or Refused).
        receipt:   The receipt appended to the chain (or None on tamper).
    """

    text: str
    fact_key: str
    verdict: Verdict | None
    receipt: Receipt | None


@dataclass
class DraftResult:
    """The outcome of running a full scenario (draft adjudication + publish check).

    Attributes:
        label:             e.g. "N1", "N5a", "N5b".
        description:       Human-readable description.
        assertion_results: One AssertionResult per assertion adjudicated.
        chain:             The receipt chain after all adjudications.
        publish_decision:  The publish check result.
    """

    label: str
    description: str
    assertion_results: list[AssertionResult] = field(default_factory=list)
    chain: list[Receipt] = field(default_factory=list)
    publish_decision: PublishDecision | None = None


# ---------------------------------------------------------------------------
# Scenario data
# ---------------------------------------------------------------------------

_SCENARIO_N1 = {
    "label": "N1",
    "description": "Clean draft — all assertions supported → all PASS, publishable",
    "assertions": [
        {
            "text":     "Elias Vane died on 28 October 2026.",
            "fact_key": "date_of_death",
            "value":    "2026-10-28",
            "citation": "death_record",
        },
        {
            "text":     "He bequeathed The Stone Bull to Marta, the neighbor.",
            "fact_key": "bequest.Taurus.item",
            "value":    "The Stone Bull",
            "citation": "will_2024",
        },
        {
            "text":     "He was a self-professed Tree Wizard.",
            "fact_key": "occupation",
            "value":    "self-professed Tree Wizard",
            "citation": "family_record",
        },
    ],
}

_SCENARIO_N2 = {
    "label": "N2",
    "description": (
        "Wrong Scorpio beneficiary → REFUSED(source_contradicts)"
    ),
    "assertions": [
        {
            "text":     "He bequeathed The Sealed Letter to Marta, the neighbor.",
            "fact_key": "bequest.Scorpio.beneficiary",
            "value":    "Marta, the neighbor",
            "citation": "will_2024",
        },
    ],
}

_SCENARIO_N3 = {
    "label": "N3",
    "description": (
        "Bequest under empty sign Gemini → REFUSED(unsupported_claim)"
    ),
    "assertions": [
        {
            "text":     "He left The Twin Lanterns to the two apprentices.",
            "fact_key": "bequest.Gemini.item",
            "value":    "The Twin Lanterns",
            "citation": "will_2024",
        },
    ],
}

_SCENARIO_N4 = {
    "label": "N4",
    "description": "No citation provided → REFUSED(missing_citation)",
    "assertions": [
        {
            "text":     "He was born in Hollow Hill.",
            "fact_key": "birthplace",
            "value":    "Hollow Hill",
            "citation": None,
        },
    ],
}

_SCENARIO_N5A = {
    "label": "N5a",
    "description": (
        "Mixed draft (wrong birthplace) → publish refused; "
        "phase 1 of N5"
    ),
    "assertions": [
        {
            "text":     "Elias Vane died on 28 October 2026.",
            "fact_key": "date_of_death",
            "value":    "2026-10-28",
            "citation": "death_record",
        },
        {
            "text":     "He was born in Galway.",
            "fact_key": "birthplace",
            "value":    "Galway",
            "citation": "family_record",
        },
        {
            "text":     "He was a self-professed Tree Wizard.",
            "fact_key": "occupation",
            "value":    "self-professed Tree Wizard",
            "citation": "family_record",
        },
    ],
}

# Corrected assertion 2 for N5b — replaces the "Galway" assertion.
_N5B_CORRECTED_ASSERTION = {
    "text":     "He was born in Hollow Hill.",
    "fact_key": "birthplace",
    "value":    "Hollow Hill",
    "citation": "family_record",
}

_SCENARIO_N6 = {
    "label": "N6",
    "description": (
        "Unknown source id 'parish_register' → REFUSED(unsupported_claim)"
    ),
    "assertions": [
        {
            "text":     "He was known to the parish register.",
            "fact_key": "person",
            "value":    "Elias Vane",
            "citation": "parish_register",
        },
    ],
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_scenarios(
    registry: SourceRegistry,
    desk_mandate: SealedMandate,
) -> list[DraftResult]:
    """Adjudicate all six demo scenarios and return their results.

    Each scenario (except N5) uses its own fresh receipt chain.  N5 runs in
    two phases — N5a adjudicates the original draft (with one wrong assertion),
    then N5b appends the corrected assertion to the same chain.

    Args:
        registry:      A SourceRegistry populated with the three fixture files.
        desk_mandate:  The desk's governing SealedMandate.  This is the
                       ``mandate`` argument passed to each
                       ``gate_core.adjudicate()`` call and is distinct from
                       the per-source mandates the measurer checks internally.

    Returns:
        List of DraftResult objects, one per scenario/phase, in order:
        N1, N2, N3, N4, N5a, N5b, N6.
    """
    measurer = CitationMeasurer(registry)
    results: list[DraftResult] = []

    # ── Standard single-phase scenarios ──────────────────────────────────
    for spec in (_SCENARIO_N1, _SCENARIO_N2, _SCENARIO_N3, _SCENARIO_N4, _SCENARIO_N6):
        chain: list[Receipt] = []
        assertion_results: list[AssertionResult] = []
        claim_hashes: list[str] = []

        for a in spec["assertions"]:
            claim = make_assertion_claim(
                text=a["text"],
                fact_key=a["fact_key"],
                value=a["value"],
                citation=a["citation"],
            )
            claim_hashes.append(_claim_hash(claim))
            verdict, receipt = adjudicate(claim, desk_mandate, measurer, chain)
            assertion_results.append(AssertionResult(
                text=a["text"],
                fact_key=a["fact_key"],
                verdict=verdict,
                receipt=receipt,
            ))

        decision = check_publish(spec["label"], claim_hashes, chain)
        results.append(DraftResult(
            label=spec["label"],
            description=spec["description"],
            assertion_results=assertion_results,
            chain=chain,
            publish_decision=decision,
        ))

    # ── Scenario N5 — two-phase mixed draft ───────────────────────────────
    n5_chain: list[Receipt] = []

    # Phase N5a: three assertions, one of which is wrong.
    n5a_assertion_results: list[AssertionResult] = []
    n5a_claim_hashes: list[str] = []

    for a in _SCENARIO_N5A["assertions"]:
        claim = make_assertion_claim(
            text=a["text"],
            fact_key=a["fact_key"],
            value=a["value"],
            citation=a["citation"],
        )
        n5a_claim_hashes.append(_claim_hash(claim))
        verdict, receipt = adjudicate(claim, desk_mandate, measurer, n5_chain)
        n5a_assertion_results.append(AssertionResult(
            text=a["text"],
            fact_key=a["fact_key"],
            verdict=verdict,
            receipt=receipt,
        ))

    n5a_decision = check_publish("N5a", n5a_claim_hashes, n5_chain)
    results.append(DraftResult(
        label="N5a",
        description=_SCENARIO_N5A["description"],
        assertion_results=n5a_assertion_results,
        chain=n5_chain,
        publish_decision=n5a_decision,
    ))

    # Phase N5b: adjudicate the corrected assertion 2 into the same chain.
    corrected_claim = make_assertion_claim(
        text=_N5B_CORRECTED_ASSERTION["text"],
        fact_key=_N5B_CORRECTED_ASSERTION["fact_key"],
        value=_N5B_CORRECTED_ASSERTION["value"],
        citation=_N5B_CORRECTED_ASSERTION["citation"],
    )
    corrected_hash = _claim_hash(corrected_claim)
    verdict_corr, receipt_corr = adjudicate(corrected_claim, desk_mandate, measurer, n5_chain)

    # The publish check for N5b uses three claim hashes:
    #   - assertion 1: original hash (still PASS)
    #   - assertion 2: corrected hash (now PASS)
    #   - assertion 3: original hash (still PASS)
    n5b_claim_hashes = [
        n5a_claim_hashes[0],  # assertion 1 (PASS, unchanged)
        corrected_hash,       # assertion 2 corrected (PASS)
        n5a_claim_hashes[2],  # assertion 3 (PASS, unchanged)
    ]
    n5b_decision = check_publish("N5b", n5b_claim_hashes, n5_chain)

    results.append(DraftResult(
        label="N5b",
        description="Corrected birthplace assertion → all PASS, publishable; phase 2 of N5",
        assertion_results=[AssertionResult(
            text=_N5B_CORRECTED_ASSERTION["text"],
            fact_key=_N5B_CORRECTED_ASSERTION["fact_key"],
            verdict=verdict_corr,
            receipt=receipt_corr,
        )],
        chain=n5_chain,
        publish_decision=n5b_decision,
    ))

    # Re-order results so the list is N1, N2, N3, N4, N5a, N5b, N6.
    # Currently: N1, N2, N3, N4, N6, N5a, N5b — swap N6 to the end.
    n6_result = results.pop(4)  # index 4 is N6 (inserted after N4)
    results.append(n6_result)

    return results
