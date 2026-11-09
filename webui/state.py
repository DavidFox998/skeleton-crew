"""
webui.state
~~~~~~~~~~~
Owns all mutable server state and all calls into gate_core and executor.
No HTML, no HTTP logic.

The HouseRegister class:
- Holds a single append-only house chain (list[Receipt]) for the server session.
- Guards all chain mutations behind a threading.Lock for ThreadingHTTPServer safety.
- Exposes adjudicate_preset(), adjudicate_custom(), chain_snapshot(),
  verify_house_chain(), tamper_demo(), and a registry property.

SCENARIO_DEFINITIONS is a module-level list of dicts defining the seven
demo scenarios A–G in casework order.
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from gate_core.gate import adjudicate
from gate_core.mandate import MandateTamperError, SealedMandate
from gate_core.receipt import Receipt, ReplayResult, verify_chain
from gate_core.verdict import Verdict

from executor.claims import make_distribution_claim
from executor.measurer import ExecutorMeasurer
from executor.registry import ExecutorRegistry

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Canonical 2024 distributions (Scenario A baseline)
# ---------------------------------------------------------------------------

_DISTRIBUTIONS_2024: list[dict] = [
    {
        "sign": "Aries",
        "item": "The Iron Key",
        "beneficiary": "whoever first knocks thrice on the chapel door after midnight on All Hallows' Eve",
    },
    {
        "sign": "Taurus",
        "item": "The Stone Bull",
        "beneficiary": "Marta, the neighbor",
    },
    {
        "sign": "Leo",
        "item": "The Brass Telescope",
        "beneficiary": "the child who mapped the lion's heart from the hilltop in the summer of the comet",
    },
    {
        "sign": "Scorpio",
        "item": "The Sealed Letter",
        "beneficiary": "the one who knows what happened at the millpond in '87",
    },
    {
        "sign": "Capricorn",
        "item": "The Goat Bell",
        "beneficiary": "the town itself",
    },
    {
        "sign": "Aquarius",
        "item": "The Water Jar",
        "beneficiary": "the well-keeper's daughter",
    },
    {
        "sign": "Pisces",
        "item": "The Two Fishhooks",
        "beneficiary": "Silas Vane, brother of the testator",
    },
]

# Canonical 2019 distributions (6 bequests — no Scorpio)
_DISTRIBUTIONS_2019: list[dict] = [
    {
        "sign": "Aries",
        "item": "The Iron Key",
        "beneficiary": "whoever first knocks thrice on the chapel door after midnight on All Hallows' Eve",
    },
    {
        "sign": "Taurus",
        "item": "The Stone Bull",
        "beneficiary": "Marta, the neighbor",
    },
    {
        "sign": "Leo",
        "item": "The Brass Telescope",
        "beneficiary": "the child who mapped the lion's heart from the hilltop in the summer of the comet",
    },
    {
        "sign": "Capricorn",
        "item": "The Goat Bell",
        "beneficiary": "the town itself",
    },
    {
        "sign": "Aquarius",
        "item": "The Water Jar",
        "beneficiary": "the well-keeper's daughter",
    },
    {
        "sign": "Pisces",
        "item": "The Two Fishhooks",
        "beneficiary": "Silas Vane, brother of the testator",
    },
]


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIO_DEFINITIONS: list[dict] = [
    {
        "label": "A",
        "description": "Correct 7-bequest distribution under the 2024 will",
        "will_selector": "2024",
        "distributions": _DISTRIBUTIONS_2024,
        "registry_variant": "full",
        "expected_verdict": "PASS",
    },
    {
        "label": "B",
        "description": "Correct distribution under the superseded 2019 will",
        "will_selector": "2019",
        "distributions": _DISTRIBUTIONS_2019,
        "registry_variant": "full",
        "expected_verdict": "REFUSED · will_superseded",
    },
    {
        "label": "C",
        "description": "2024 will with one extra bequest (8 total)",
        "will_selector": "2024",
        "distributions": list(_DISTRIBUTIONS_2024) + [
            {"sign": "Taurus", "item": "The Stone Bull", "beneficiary": "an interloper"}
        ],
        "registry_variant": "full",
        "expected_verdict": "REFUSED · share_mismatch",
    },
    {
        "label": "D",
        "description": "2024 will with a wrong beneficiary on one sign",
        "will_selector": "2024",
        "distributions": [
            d if d["sign"] != "Scorpio"
            else {**d, "beneficiary": "an unknown claimant"}
            for d in _DISTRIBUTIONS_2024
        ],
        "registry_variant": "full",
        "expected_verdict": "REFUSED · beneficiary_unknown",
    },
    {
        "label": "E",
        "description": "2024 will with an unoccupied sign included (Gemini, bit=0)",
        "will_selector": "2024",
        "distributions": [
            d if d["sign"] != "Taurus"
            else {"sign": "Gemini", "item": "The Stone Bull", "beneficiary": "Marta, the neighbor"}
            for d in _DISTRIBUTIONS_2024
        ],
        "registry_variant": "full",
        "expected_verdict": "REFUSED · sign_unoccupied",
    },
    {
        "label": "F",
        "description": "2024 will, correct distribution, but no death record in the registry view",
        "will_selector": "2024",
        "distributions": _DISTRIBUTIONS_2024,
        "registry_variant": "no_death_record",
        "expected_verdict": "REFUSED · death_unverified",
    },
    {
        "label": "G",
        "description": "2024 will with tampered mandate (altered page)",
        "will_selector": "tampered_2024",
        "distributions": _DISTRIBUTIONS_2024,
        "registry_variant": "full",
        "expected_verdict": "REFUSED · seal_broken",
    },
]


# ---------------------------------------------------------------------------
# HouseRegister
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class HouseRegister:
    """Owns all mutable server state and all calls to gate_core / executor.

    Args:
        will_paths:         List of file paths to will JSON fixtures.
        death_record_paths: List of file paths to death record JSON fixtures.
    """

    def __init__(
        self,
        will_paths: list[str],
        death_record_paths: list[str],
    ) -> None:
        self._registry = ExecutorRegistry(will_paths, death_record_paths)
        self._registry_no_death = ExecutorRegistry(will_paths, [])
        self._measurer = ExecutorMeasurer(self._registry)
        self._measurer_no_death = ExecutorMeasurer(self._registry_no_death)
        self._chain: list[Receipt] = []
        self._lock = threading.Lock()

    # ── Public read-only property ─────────────────────────────────────────

    @property
    def registry(self) -> ExecutorRegistry:
        """Expose the full registry (read-only) for render helpers."""
        return self._registry

    # ── Chain accessors ───────────────────────────────────────────────────

    def chain_snapshot(self) -> list[Receipt]:
        """Return a shallow copy of the house chain under lock."""
        with self._lock:
            return list(self._chain)

    def verify_house_chain(self) -> ReplayResult:
        """Run verify_chain on the house chain and return the result."""
        with self._lock:
            snapshot = list(self._chain)
        return verify_chain(snapshot)

    # ── Adjudication ──────────────────────────────────────────────────────

    def adjudicate_preset(
        self,
        label: str,
    ) -> tuple[Verdict | None, Receipt | None, bool]:
        """Adjudicate a preset scenario by its label (A–G).

        Returns:
            (verdict, receipt, tamper_error)
            - For normal verdicts: (Verdict, Receipt, False) — receipt appended.
            - For Scenario G (MandateTamperError): (None, None, True) — nothing appended.

        Raises:
            KeyError: if label is not in SCENARIO_DEFINITIONS.
        """
        defn = next((d for d in SCENARIO_DEFINITIONS if d["label"] == label), None)
        if defn is None:
            raise KeyError(f"Unknown scenario label: {label!r}")

        with self._lock:
            testator = "Elias Vane"

            # Resolve mandate
            if defn["will_selector"] == "2024":
                mandate = self._registry.latest_will(testator)
            elif defn["will_selector"] == "2019":
                all_wills = self._registry.all_wills(testator)
                mandate = all_wills[0] if all_wills else None
            elif defn["will_selector"] == "tampered_2024":
                # Build a tampered SealedMandate: original seal, mutated content
                real = self._registry.latest_will(testator)
                tampered_bequests = [
                    {**b, "beneficiary": "TAMPERED"} if b["sign"] == "Aries" else b
                    for b in real.content["bequests"]
                ]
                tampered_content = {**real.content, "bequests": tampered_bequests}
                mandate = SealedMandate(
                    domain=real.domain,
                    content=tampered_content,
                    seal=real.seal,  # original seal — no longer matches content
                )
            else:
                mandate = self._registry.latest_will(testator)

            # Resolve measurer
            if defn["registry_variant"] == "no_death_record":
                measurer = self._measurer_no_death
            else:
                measurer = self._measurer

            # Build claim
            claim = make_distribution_claim(
                will_ref=mandate.seal if mandate is not None else "",
                distributions=defn["distributions"],
            )

            # Adjudicate
            try:
                verdict, receipt = adjudicate(
                    claim,
                    mandate,
                    measurer,
                    self._chain,
                    timestamp_utc=_utc_now(),
                )
                return verdict, receipt, False
            except MandateTamperError:
                return None, None, True

    def adjudicate_custom(
        self,
        will_seal: str,
        distributions: list[dict],
    ) -> tuple[Verdict | None, Receipt | None, bool]:
        """Adjudicate a free-builder distribution claim.

        Returns:
            (verdict, receipt, tamper_error)
            - (Verdict, Receipt, False) on success — receipt appended.
            - (None, None, True) if MandateTamperError (defensive).

        Raises:
            ValueError: if no will is found for the given seal.
        """
        with self._lock:
            mandate = self._registry.will_by_seal(will_seal)
            if mandate is None:
                raise ValueError(
                    f"No will found for seal {will_seal[:12]}…"
                )

            claim = make_distribution_claim(
                will_ref=will_seal,
                distributions=distributions,
            )

            try:
                verdict, receipt = adjudicate(
                    claim,
                    mandate,
                    self._measurer,
                    self._chain,
                    timestamp_utc=_utc_now(),
                )
                return verdict, receipt, False
            except MandateTamperError:
                return None, None, True

    # ── Archive operations ────────────────────────────────────────────────

    def tamper_demo(self) -> ReplayResult:
        """Run the tamper demonstration on a COPY of the house chain.

        Does NOT modify self._chain.

        Returns:
            ReplayResult — will show ok=True (empty chain) or a failure
            indicating hash_mismatch at the tampered receipt position.
        """
        with self._lock:
            chain_copy = copy.deepcopy(self._chain)

        if not chain_copy:
            # Nothing to demonstrate — return ok=True (empty chain verified clean)
            return ReplayResult(ok=True, failure_index=None, failure_reason=None)

        # Mutate the last receipt in the copy: replace own_hash unchanged,
        # but alter the claim payload to simulate a real tamper.
        last = chain_copy[-1]
        mutated_claim = copy.deepcopy(last.claim)

        # Navigate to payload and alter a value
        if "payload" in mutated_claim and isinstance(mutated_claim["payload"], dict):
            payload = mutated_claim["payload"]
            if "distributions" in payload and payload["distributions"]:
                dists = list(payload["distributions"])
                first = dict(dists[0])
                first["beneficiary"] = "TAMPERED_FOR_DEMO"
                dists[0] = first
                payload["distributions"] = dists
            elif "will_ref" in payload:
                payload["will_ref"] = "0" * 64
        else:
            # Fallback: mutate at top level
            mutated_claim["_tampered"] = True

        # Build a new Receipt with the mutated claim but the ORIGINAL own_hash
        # (this simulates real tampering: content changed, hash not updated)
        tampered_receipt = Receipt(
            claim=mutated_claim,
            measurements=last.measurements,
            measurement_error=last.measurement_error,
            verdict=last.verdict,
            timestamp_utc=last.timestamp_utc,
            previous_hash=last.previous_hash,
            own_hash=last.own_hash,  # original hash — now stale
        )
        chain_copy[-1] = tampered_receipt

        return verify_chain(chain_copy)


# ---------------------------------------------------------------------------
# NoticesRegister — module-level helpers
# ---------------------------------------------------------------------------

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from gate_core.gate import adjudicate as _adjudicate_gate
from gate_core.mandate import MandateTamperError as _MandateTamperError, SealedMandate as _SealedMandate
from gate_core.mandate import seal_mandate as _seal_mandate
from gate_core.receipt import Receipt as _Receipt, ReplayResult as _ReplayResult, verify_chain as _verify_chain

from citation_gate.claims import make_assertion_claim as _make_assertion_claim
from citation_gate.measurer import CitationMeasurer as _CitationMeasurer
from citation_gate.publish import PublishDecision as _PublishDecision, check_publish as _check_publish
from citation_gate.sources import SourceRegistry as _SourceRegistry


def _notices_canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


def _notices_claim_hash(claim) -> str:
    return hashlib.sha256(
        _notices_canonical_json(claim.to_dict()).encode("utf-8")
    ).hexdigest()


def _notices_utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# NOTICES_SCENARIO_DEFINITIONS
# ---------------------------------------------------------------------------

NOTICES_SCENARIO_DEFINITIONS: list[dict] = [
    {
        "label": "N1",
        "description": "Clean draft — all assertions supported → all PASS, publishable",
        "phases": [
            {
                "label": "N1",
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
            },
        ],
        "expected_publish": "PUBLISHABLE",
    },
    {
        "label": "N2",
        "description": "Wrong Scorpio beneficiary → REFUSED(source_contradicts)",
        "phases": [
            {
                "label": "N2",
                "assertions": [
                    {
                        "text":     "He bequeathed The Sealed Letter to Marta, the neighbor.",
                        "fact_key": "bequest.Scorpio.beneficiary",
                        "value":    "Marta, the neighbor",
                        "citation": "will_2024",
                    },
                ],
            },
        ],
        "expected_publish": "REFUSED · source_contradicts",
    },
    {
        "label": "N3",
        "description": "Bequest under empty sign Gemini → REFUSED(unsupported_claim)",
        "phases": [
            {
                "label": "N3",
                "assertions": [
                    {
                        "text":     "He left The Twin Lanterns to the two apprentices.",
                        "fact_key": "bequest.Gemini.item",
                        "value":    "The Twin Lanterns",
                        "citation": "will_2024",
                    },
                ],
            },
        ],
        "expected_publish": "REFUSED · unsupported_claim",
    },
    {
        "label": "N4",
        "description": "No citation provided → REFUSED(missing_citation)",
        "phases": [
            {
                "label": "N4",
                "assertions": [
                    {
                        "text":     "He was born in Hollow Hill.",
                        "fact_key": "birthplace",
                        "value":    "Hollow Hill",
                        "citation": None,
                    },
                ],
            },
        ],
        "expected_publish": "REFUSED · missing_citation",
    },
    {
        "label": "N5",
        "description": "Two-phase draft: wrong birthplace corrected",
        "phases": [
            {
                "label": "N5a",
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
            },
            {
                "label": "N5b",
                "assertions": [
                    {
                        "text":     "He was born in Hollow Hill.",
                        "fact_key": "birthplace",
                        "value":    "Hollow Hill",
                        "citation": "family_record",
                    },
                ],
            },
        ],
        "expected_publish": "N5a: REFUSED · source_contradicts; N5b: PUBLISHABLE",
    },
    {
        "label": "N6",
        "description": "Unknown source id 'parish_register' → REFUSED(unsupported_claim)",
        "phases": [
            {
                "label": "N6",
                "assertions": [
                    {
                        "text":     "He was known to the parish register.",
                        "fact_key": "person",
                        "value":    "Elias Vane",
                        "citation": "parish_register",
                    },
                ],
            },
        ],
        "expected_publish": "REFUSED · unsupported_claim",
    },
]


# ---------------------------------------------------------------------------
# AssertionEntry
# ---------------------------------------------------------------------------

@dataclass
class AssertionEntry:
    """One assertion in the working draft, after adjudication."""

    text: str
    fact_key: str
    value: str
    citation: str | None
    claim_hash: str            # canonical-JSON SHA-256 of the Claim dict
    verdict: dict | None       # receipt.verdict or None on tamper
    receipt: _Receipt | None   # None on tamper


# ---------------------------------------------------------------------------
# NoticesRegister
# ---------------------------------------------------------------------------

class NoticesRegister:
    """Owns all mutable server state for the Notices Desk.

    Mirrors the structure of HouseRegister but governs the citation gate
    domain. No HTML, no HTTP logic.

    Args:
        death_record_path: File path to the death record JSON fixture.
        will_path:         File path to the will JSON fixture.
        family_record_path: File path to the family record JSON fixture.
    """

    def __init__(
        self,
        death_record_path: str,
        will_path: str,
        family_record_path: str,
    ) -> None:
        self._source_registry = _SourceRegistry(
            death_record_path=death_record_path,
            will_path=will_path,
            family_record_path=family_record_path,
        )
        self._measurer = _CitationMeasurer(self._source_registry)
        self._desk_mandate: _SealedMandate = _seal_mandate(
            "citation",
            {
                "desk": "notices",
                "mandate": "Adjudicate factual assertions for obituary publication.",
            },
        )
        self._chain: list[_Receipt] = []
        self._working_draft: list[AssertionEntry] = []
        self._lock = threading.Lock()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def source_registry(self) -> _SourceRegistry:
        """Expose the SourceRegistry (read-only) for render helpers."""
        return self._source_registry

    @property
    def working_draft(self) -> list[AssertionEntry]:
        """Return a shallow copy of the current working draft under lock."""
        with self._lock:
            return list(self._working_draft)

    # ── Chain accessors ───────────────────────────────────────────────────

    def chain_snapshot(self) -> list[_Receipt]:
        """Return a shallow copy of the notices chain under lock."""
        with self._lock:
            return list(self._chain)

    def verify_notices_chain(self) -> _ReplayResult:
        """Run verify_chain on the notices chain and return the result."""
        with self._lock:
            snapshot = list(self._chain)
        return _verify_chain(snapshot)

    # ── Working draft publish state ───────────────────────────────────────

    def working_draft_publish_state(self) -> _PublishDecision | None:
        """Return the current publish state for the working draft, or None if empty."""
        with self._lock:
            if not self._working_draft:
                return None
            draft_hashes = [e.claim_hash for e in self._working_draft]
            chain_snapshot = list(self._chain)
        return _check_publish("working_draft", draft_hashes, chain_snapshot)

    # ── Adjudication ──────────────────────────────────────────────────────

    def adjudicate_preset(
        self,
        label: str,
    ) -> tuple[list[AssertionEntry], list[_PublishDecision], bool]:
        """Adjudicate a full preset draft by label (N1–N6).

        For N5, runs both phases (N5a and N5b) against the same chain segment.

        Preset adjudications append receipts to the notices chain but do NOT
        modify the working draft.

        Returns:
            (assertion_entries, publish_decisions, tamper_error)
            - assertion_entries: all AssertionEntry objects across all phases.
            - publish_decisions: one PublishDecision per phase.
            - tamper_error: True if MandateTamperError was raised.

        Raises:
            KeyError: if label is not in NOTICES_SCENARIO_DEFINITIONS.
        """
        spec = next(
            (d for d in NOTICES_SCENARIO_DEFINITIONS if d["label"] == label), None
        )
        if spec is None:
            raise KeyError(f"Unknown notices scenario label: {label!r}")

        with self._lock:
            entries: list[AssertionEntry] = []
            decisions: list[_PublishDecision] = []

            for phase in spec["phases"]:
                phase_hashes: list[str] = []
                for a in phase["assertions"]:
                    claim = _make_assertion_claim(
                        text=a["text"],
                        fact_key=a["fact_key"],
                        value=a["value"],
                        citation=a["citation"],
                    )
                    ch = _notices_claim_hash(claim)
                    phase_hashes.append(ch)
                    try:
                        verdict, receipt = _adjudicate_gate(
                            claim,
                            self._desk_mandate,
                            self._measurer,
                            self._chain,
                            timestamp_utc=_notices_utc_now(),
                        )
                        entries.append(AssertionEntry(
                            text=a["text"],
                            fact_key=a["fact_key"],
                            value=a["value"],
                            citation=a["citation"],
                            claim_hash=ch,
                            verdict=receipt.verdict,
                            receipt=receipt,
                        ))
                    except _MandateTamperError:
                        entries.append(AssertionEntry(
                            text=a["text"],
                            fact_key=a["fact_key"],
                            value=a["value"],
                            citation=a["citation"],
                            claim_hash=ch,
                            verdict=None,
                            receipt=None,
                        ))
                        return entries, decisions, True

                decision = _check_publish(phase["label"], phase_hashes, self._chain)
                decisions.append(decision)

            return entries, decisions, False

    def adjudicate_assertion(
        self,
        text: str,
        fact_key: str,
        value: str,
        citation: str | None,
    ) -> tuple[AssertionEntry, _PublishDecision, bool]:
        """Adjudicate a single free-builder assertion.

        On success: appends receipt to self._chain; appends AssertionEntry to
        self._working_draft.

        On MandateTamperError: returns (entry_with_none_receipt,
        seal_broken_decision, True) — nothing appended.

        Returns:
            (assertion_entry, publish_decision, tamper_error)
        """
        with self._lock:
            claim = _make_assertion_claim(
                text=text,
                fact_key=fact_key,
                value=value,
                citation=citation,
            )
            ch = _notices_claim_hash(claim)
            try:
                verdict, receipt = _adjudicate_gate(
                    claim,
                    self._desk_mandate,
                    self._measurer,
                    self._chain,
                    timestamp_utc=_notices_utc_now(),
                )
                entry = AssertionEntry(
                    text=text,
                    fact_key=fact_key,
                    value=value,
                    citation=citation,
                    claim_hash=ch,
                    verdict=receipt.verdict,
                    receipt=receipt,
                )
                self._working_draft.append(entry)
                draft_hashes = [e.claim_hash for e in self._working_draft]
                decision = _check_publish("working_draft", draft_hashes, self._chain)
                return entry, decision, False
            except _MandateTamperError:
                entry = AssertionEntry(
                    text=text,
                    fact_key=fact_key,
                    value=value,
                    citation=citation,
                    claim_hash=ch,
                    verdict=None,
                    receipt=None,
                )
                refused = _PublishDecision(
                    publishable=False,
                    receipt_ids=None,
                    refusal_name="seal_broken",
                )
                return entry, refused, True

    # ── Draft management ──────────────────────────────────────────────────

    def new_draft(self) -> None:
        """Clear the working draft. Does not touch the notices chain."""
        with self._lock:
            self._working_draft = []

    # ── Archive operations ────────────────────────────────────────────────

    def tamper_demo(self) -> _ReplayResult:
        """Run the tamper demonstration on a COPY of the notices chain.

        Does NOT modify self._chain.

        Returns:
            ReplayResult — ok=True for an empty chain, or failure indicating
            hash_mismatch at the tampered receipt position.
        """
        with self._lock:
            chain_copy = copy.deepcopy(self._chain)

        if not chain_copy:
            return _ReplayResult(ok=True, failure_index=None, failure_reason=None)

        # Mutate the last receipt in the copy: alter the claim payload while
        # leaving own_hash unchanged, to simulate real tampering.
        last = chain_copy[-1]
        mutated_claim = copy.deepcopy(last.claim)

        if "payload" in mutated_claim and isinstance(mutated_claim["payload"], dict):
            payload = mutated_claim["payload"]
            if "value" in payload:
                payload["value"] = "TAMPERED_FOR_DEMO"
            elif "fact_key" in payload:
                payload["fact_key"] = "TAMPERED_FOR_DEMO"
            else:
                payload["_tampered"] = True
        else:
            mutated_claim["_tampered"] = True

        tampered_receipt = _Receipt(
            claim=mutated_claim,
            measurements=last.measurements,
            measurement_error=last.measurement_error,
            verdict=last.verdict,
            timestamp_utc=last.timestamp_utc,
            previous_hash=last.previous_hash,
            own_hash=last.own_hash,  # original hash — now stale
        )
        chain_copy[-1] = tampered_receipt

        return _verify_chain(chain_copy)


# ===========================================================================
# The Vault — register and preset definitions
# ===========================================================================

import os as _os
import shutil as _shutil
import tempfile as _tempfile

from vault.claims import present_bundle as _present_bundle
from vault.lock import lock_bundle as _lock_bundle
from vault.measurer import VaultMeasurer as _VaultMeasurer
from vault.scenarios import (
    BUNDLE_ID as _VAULT_BUNDLE_ID,
    DEFAULT_FIXTURES as _VAULT_DEFAULT_FIXTURES,
    build_bundle as _build_vault_bundle,
)


VAULT_SCENARIO_DEFINITIONS: list[dict] = [
    {
        "label": "B1",
        "description": "The bundle presented untouched",
        "situation": "untouched",
        "expected_verdict": "PASS",
    },
    {
        "label": "B2",
        "description": "One paper altered — an inventory figure",
        "situation": "inventory figure altered",
        "expected_verdict": "REFUSED · file_changed",
    },
    {
        "label": "B3",
        "description": "A stray paper added to the bundle",
        "situation": "stray paper added",
        "expected_verdict": "REFUSED · file_added",
    },
    {
        "label": "B4",
        "description": "A paper removed — the death record",
        "situation": "death record removed",
        "expected_verdict": "REFUSED · file_missing",
    },
    {
        "label": "B5",
        "description": "The bundle restored, presented again under the original certificate",
        "situation": "death record removed, then restored",
        "expected_verdict": "PASS",
    },
    {
        "label": "B6",
        "description": "The lock record itself altered after sealing",
        "situation": "lock record altered",
        "expected_verdict": "REFUSED · seal_broken",
    },
]


def _vault_alter_inventory(root: str) -> None:
    path = _os.path.join(root, "inventory.json")
    with open(path, "rb") as fh:
        data = fh.read()
    with open(path, "wb") as fh:
        fh.write(data.replace(b'"appraised_value":520', b'"appraised_value":5200'))


def _vault_add_stray(root: str) -> None:
    with open(_os.path.join(root, "stray_note.txt"), "w", encoding="utf-8") as fh:
        fh.write("a paper nobody sealed")


def _vault_remove_death_record(root: str) -> None:
    _os.remove(_os.path.join(root, "death_record.json"))


def _vault_remove_then_restore(root: str) -> None:
    path = _os.path.join(root, "death_record.json")
    with open(path, "rb") as fh:
        original = fh.read()
    _os.remove(path)
    with open(path, "wb") as fh:
        fh.write(original)


# How each preset leaves the papers on the table.  These only arrange the
# papers; every judgement is made by the gate.
_VAULT_ARRANGEMENTS = {
    "B1": None,
    "B2": _vault_alter_inventory,
    "B3": _vault_add_stray,
    "B4": _vault_remove_death_record,
    "B5": _vault_remove_then_restore,
    "B6": None,  # papers untouched; the lock record is the thing altered
}


class VaultRegister:
    """Owns all mutable server state for The Vault.

    Holds the sealed lock record of the house bundle and ONE append-only
    vault chain.  No HTML, no HTTP logic, no verdict logic: every verdict
    comes from ``gate_core.adjudicate()`` with the ``VaultMeasurer``.

    Args:
        fixtures_dir: Directory holding the four papers of the estate file.
    """

    def __init__(self, fixtures_dir: str = _VAULT_DEFAULT_FIXTURES) -> None:
        self._fixtures_dir = fixtures_dir
        with _tempfile.TemporaryDirectory() as tmp:
            root = _os.path.join(tmp, "bundle")
            _build_vault_bundle(root, fixtures_dir)
            self._lock_record: _SealedMandate = _lock_bundle(_VAULT_BUNDLE_ID, root)
        self._measurer = _VaultMeasurer()
        self._chain: list[_Receipt] = []
        self._mutex = threading.Lock()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def lock_record(self) -> _SealedMandate:
        """The sealed lock record (read-only use by render helpers)."""
        return self._lock_record

    @property
    def bundle_id(self) -> str:
        return _VAULT_BUNDLE_ID

    def papers(self) -> list[tuple[str, str]]:
        """Return [(path, sha256)] from the lock record, in canonical order."""
        return list(self._lock_record.content["files"].items())

    # ── Chain accessors ───────────────────────────────────────────────────

    def chain_snapshot(self) -> list[_Receipt]:
        with self._mutex:
            return list(self._chain)

    def verify_vault_chain(self) -> _ReplayResult:
        with self._mutex:
            snapshot = list(self._chain)
        return _verify_chain(snapshot)

    # ── Adjudication ──────────────────────────────────────────────────────

    def adjudicate_preset(
        self,
        label: str,
    ) -> tuple[Verdict | None, _Receipt | None, bool]:
        """Present the bundle for release in the situation of preset B1–B6.

        Returns:
            (verdict, receipt, tamper_error)
            - Normal verdicts: (Verdict, Receipt, False) — receipt appended.
            - Hard tamper (lock record does not recompute):
              (None, None, True) — nothing appended.

        Raises:
            KeyError: if label is not in VAULT_SCENARIO_DEFINITIONS.
        """
        if not any(d["label"] == label for d in VAULT_SCENARIO_DEFINITIONS):
            raise KeyError(f"Unknown vault scenario label: {label!r}")

        with self._mutex:
            lock = self._lock_record
            if label == "B6":
                # Same alteration vault.scenarios applies: original seal,
                # altered table.
                forged_files = {**lock.content["files"], "inventory.json": "0" * 64}
                lock = _SealedMandate(
                    domain=lock.domain,
                    content={**lock.content, "files": forged_files},
                    seal=lock.seal,
                )

            with _tempfile.TemporaryDirectory() as tmp:
                root = _os.path.join(tmp, "bundle")
                _build_vault_bundle(root, self._fixtures_dir)
                arrange = _VAULT_ARRANGEMENTS[label]
                if arrange is not None:
                    arrange(root)
                claim = _present_bundle(_VAULT_BUNDLE_ID, root)

            try:
                verdict, receipt = _adjudicate_gate(
                    claim,
                    lock,
                    self._measurer,
                    self._chain,
                    timestamp_utc=_notices_utc_now(),
                )
                return verdict, receipt, False
            except _MandateTamperError:
                return None, None, True

    # ── Archive operations ────────────────────────────────────────────────

    def tamper_demo(self) -> _ReplayResult:
        """Run the tamper demonstration on a COPY of the vault chain.

        Does NOT modify self._chain.
        """
        with self._mutex:
            chain_copy = copy.deepcopy(self._chain)

        if not chain_copy:
            return _ReplayResult(ok=True, failure_index=None, failure_reason=None)

        last = chain_copy[-1]
        mutated_claim = copy.deepcopy(last.claim)
        payload = mutated_claim.get("payload")
        if isinstance(payload, dict):
            payload["bundle_id"] = "TAMPERED_FOR_DEMO"
        else:
            mutated_claim["_tampered"] = True

        chain_copy[-1] = _Receipt(
            claim=mutated_claim,
            measurements=last.measurements,
            measurement_error=last.measurement_error,
            verdict=last.verdict,
            timestamp_utc=last.timestamp_utc,
            previous_hash=last.previous_hash,
            own_hash=last.own_hash,  # original hash — now stale
        )
        return _verify_chain(chain_copy)
