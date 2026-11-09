"""
executor.scenarios
~~~~~~~~~~~~~~~~~~
Defines the seven demo scenarios A–G as structured data and provides a runner
that adjudicates each against a fresh receipt chain.

Each scenario uses its own fresh receipt chain so that demo scenarios are
independent and auditable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gate_core
from gate_core import (
    MandateTamperError,
    Receipt,
    SealedMandate,
    Verdict,
    adjudicate,
    seal_mandate,
)

from executor.claims import make_distribution_claim
from executor.measurer import ExecutorMeasurer
from executor.registry import ExecutorRegistry


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    """The outcome of running a single demo scenario.

    Attributes:
        label:       Single-letter identifier, e.g. "A".
        description: Human-readable description of the scenario.
        verdict:     The gate_core Verdict (Pass or Refused), or None if
                     MandateTamperError was raised.
        receipt:     The Receipt appended to the chain, or None on tamper.
        chain:       The receipt chain after adjudication (length 0 on tamper).
        tamper_error: The MandateTamperError if raised; else None.
    """

    label: str
    description: str
    verdict: Verdict | None
    receipt: Receipt | None
    chain: list[Receipt]
    tamper_error: MandateTamperError | None = None


# ---------------------------------------------------------------------------
# Canonical 2024 distributions (Scenario A baseline)
# ---------------------------------------------------------------------------

_DISTRIBUTIONS_2024: list[dict] = [
    {"sign": "Aries",    "item": "The Iron Key",
     "beneficiary": "whoever first knocks thrice on the chapel door after midnight on All Hallows' Eve"},
    {"sign": "Taurus",   "item": "The Stone Bull",
     "beneficiary": "Marta, the neighbor"},
    {"sign": "Leo",      "item": "The Brass Telescope",
     "beneficiary": "the child who mapped the lion's heart from the hilltop in the summer of the comet"},
    {"sign": "Scorpio",  "item": "The Sealed Letter",
     "beneficiary": "the one who knows what happened at the millpond in '87"},
    {"sign": "Capricorn","item": "The Goat Bell",
     "beneficiary": "the town itself"},
    {"sign": "Aquarius", "item": "The Water Jar",
     "beneficiary": "the well-keeper's daughter"},
    {"sign": "Pisces",   "item": "The Two Fishhooks",
     "beneficiary": "Silas Vane, brother of the testator"},
]

# Canonical 2019 distributions
_DISTRIBUTIONS_2019: list[dict] = [
    {"sign": "Aries",    "item": "The Iron Key",
     "beneficiary": "whoever first knocks thrice on the chapel door after midnight on All Hallows' Eve"},
    {"sign": "Taurus",   "item": "The Stone Bull",
     "beneficiary": "Marta, the neighbor"},
    {"sign": "Leo",      "item": "The Brass Telescope",
     "beneficiary": "the child who mapped the lion's heart from the hilltop in the summer of the comet"},
    {"sign": "Capricorn","item": "The Goat Bell",
     "beneficiary": "the town itself"},
    {"sign": "Aquarius", "item": "The Water Jar",
     "beneficiary": "the well-keeper's daughter"},
    {"sign": "Pisces",   "item": "The Two Fishhooks",
     "beneficiary": "Silas Vane, brother of the testator"},
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_scenarios(
    registry: ExecutorRegistry,
) -> list[ScenarioResult]:
    """Adjudicate all seven demo scenarios and return their results.

    Each scenario uses its own fresh receipt chain.

    Args:
        registry: An ExecutorRegistry populated with both Vane wills and the
                  death record.

    Returns:
        List of ScenarioResult, one per scenario A–G, in order.
    """
    results: list[ScenarioResult] = []

    # Resolve will mandates once.
    will_2024 = registry.latest_will("Elias Vane")  # most recent = 2024
    # The 2019 will is the oldest one.
    all_vane_wills = registry.all_wills("Elias Vane")
    will_2019 = all_vane_wills[0] if len(all_vane_wills) >= 2 else None

    # ── Scenario A — Correct 7-bequest distribution under 2024 will → PASS ──
    results.append(_run_standard(
        label="A",
        description="Correct 7-bequest distribution under the 2024 will → PASS",
        mandate=will_2024,
        distributions=_DISTRIBUTIONS_2024,
        registry=registry,
    ))

    # ── Scenario B — Any distribution under 2019 will → REFUSED will_superseded ──
    results.append(_run_standard(
        label="B",
        description="Any distribution under the 2019 will → REFUSED(will_superseded)",
        mandate=will_2019,
        distributions=_DISTRIBUTIONS_2019,
        registry=registry,
    ))

    # ── Scenario C — 8-entry distribution → REFUSED share_mismatch ───────
    extra_dist = list(_DISTRIBUTIONS_2024) + [
        {"sign": "Taurus", "item": "The Stone Bull", "beneficiary": "an interloper"}
    ]
    results.append(_run_standard(
        label="C",
        description="2024 distribution plus an eighth bequest → REFUSED(share_mismatch)",
        mandate=will_2024,
        distributions=extra_dist,
        registry=registry,
    ))

    # ── Scenario D — Scorpio wrong beneficiary → REFUSED beneficiary_unknown ──
    dist_d = [
        d if d["sign"] != "Scorpio"
        else {**d, "beneficiary": "an unknown claimant"}
        for d in _DISTRIBUTIONS_2024
    ]
    results.append(_run_standard(
        label="D",
        description="Correct sign and item, wrong beneficiary for Scorpio → REFUSED(beneficiary_unknown)",
        mandate=will_2024,
        distributions=dist_d,
        registry=registry,
    ))

    # ── Scenario E — Includes a Gemini entry → REFUSED sign_unoccupied ───
    # Replace one entry with a Gemini entry to keep count at 7.
    dist_e = [
        d if d["sign"] != "Taurus"
        else {"sign": "Gemini", "item": "The Stone Bull", "beneficiary": "Marta, the neighbor"}
        for d in _DISTRIBUTIONS_2024
    ]
    results.append(_run_standard(
        label="E",
        description="Bequest under Gemini (bit=0 in 2024 vector) → REFUSED(sign_unoccupied)",
        mandate=will_2024,
        distributions=dist_e,
        registry=registry,
    ))

    # ── Scenario F — No death record → REFUSED death_unverified ──────────
    # Build a registry without the death record.
    all_will_paths: list[str] = []
    # We need paths — reconstruct by collecting all will seals and finding them.
    # Since the runner doesn't have paths directly, we build a _NoDeathRegistry.
    no_death_registry = _NoDeathRecordRegistry(registry)
    results.append(_run_standard(
        label="F",
        description="Death record removed from registry → REFUSED(death_unverified)",
        mandate=will_2024,
        distributions=_DISTRIBUTIONS_2024,
        registry=no_death_registry,
    ))

    # ── Scenario G — Tampered will passed to adjudicate → MandateTamperError ──
    # Construct a SealedMandate with original seal but modified content.
    tampered_content = dict(will_2024.content)
    # Alter one beneficiary to simulate tampering after sealing.
    tampered_bequests = [
        {**b, "beneficiary": "TAMPERED"} if b["sign"] == "Aries" else b
        for b in will_2024.content["bequests"]
    ]
    tampered_content = {**will_2024.content, "bequests": tampered_bequests}
    tampered_mandate = SealedMandate(
        domain=will_2024.domain,
        content=tampered_content,
        seal=will_2024.seal,  # original seal — no longer matches content
    )
    chain_g: list[Receipt] = []
    measurer_g = ExecutorMeasurer(registry)
    claim_g = make_distribution_claim(
        will_ref=will_2024.seal,
        distributions=_DISTRIBUTIONS_2024,
    )
    try:
        verdict_g, receipt_g = adjudicate(claim_g, tampered_mandate, measurer_g, chain_g)
        results.append(ScenarioResult(
            label="G",
            description="Will bytes altered after sealing → MandateTamperError",
            verdict=verdict_g,
            receipt=receipt_g,
            chain=chain_g,
            tamper_error=None,
        ))
    except MandateTamperError as exc:
        results.append(ScenarioResult(
            label="G",
            description="Will bytes altered after sealing → MandateTamperError",
            verdict=None,
            receipt=None,
            chain=chain_g,
            tamper_error=exc,
        ))

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_standard(
    label: str,
    description: str,
    mandate: SealedMandate | None,
    distributions: list[dict],
    registry: Any,
) -> ScenarioResult:
    """Run a single standard (non-tamper) scenario."""
    chain: list[Receipt] = []
    measurer = ExecutorMeasurer(registry)
    claim = make_distribution_claim(
        will_ref=mandate.seal if mandate is not None else "",
        distributions=distributions,
    )
    verdict, receipt = adjudicate(claim, mandate, measurer, chain)
    return ScenarioResult(
        label=label,
        description=description,
        verdict=verdict,
        receipt=receipt,
        chain=chain,
    )


class _NoDeathRecordRegistry:
    """A thin wrapper around ExecutorRegistry that always returns None for death records.

    Used for Scenario F to simulate a missing death record without rebuilding
    the registry from scratch.
    """

    def __init__(self, real_registry: ExecutorRegistry) -> None:
        self._real = real_registry

    def death_record(self, name: str):  # type: ignore[override]
        return None

    def latest_will(self, testator: str):
        return self._real.latest_will(testator)

    def all_wills(self, testator: str):
        return self._real.all_wills(testator)

    def will_by_seal(self, seal: str):
        return self._real.will_by_seal(seal)
