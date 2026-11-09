"""
tests.test_citation_gate
~~~~~~~~~~~~~~~~~~~~~~~~
Unittest suite for the Citation Gate desk.

Test inventory:
  Scenario N1 — clean three-assertion draft → all PASS, publishable
  Scenario N2 — wrong Scorpio beneficiary → REFUSED(source_contradicts)
  Scenario N3 — bequest under empty sign Gemini → REFUSED(unsupported_claim)
  Scenario N4 — no citation provided → REFUSED(missing_citation)
  Scenario N5 — mixed draft: publish refused; corrected → publishable
  Scenario N6 — unknown source id → REFUSED(unsupported_claim)
  Fact table  — shape tests for all three source records
  Tamper      — tampered cited source → MandateTamperError, chain length 0
  Publish     — publishable only when every assertion receipt is PASS
"""

import hashlib
import json
import os
import unittest

import citation_gate  # triggers refusal vocabulary registration
from citation_gate import (
    AssertionResult,
    CitationMeasurer,
    DraftResult,
    PublishDecision,
    SourceRegistry,
    check_publish,
    make_assertion_claim,
    run_scenarios,
)

from gate_core import (
    MandateTamperError,
    Pass,
    Refused,
    SealedMandate,
    adjudicate,
    seal_mandate,
    verify_chain,
    verify_mandate,
)

# ---------------------------------------------------------------------------
# Fixture paths (relative to this file → project root)
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(__file__)
_ROOT = os.path.dirname(_HERE)
_DEATH_RECORD_PATH = os.path.join(_ROOT, "fixtures", "death_record.json")
_WILL_2024_PATH    = os.path.join(_ROOT, "fixtures", "will_2024.json")
_FAMILY_RECORD_PATH = os.path.join(_ROOT, "fixtures", "family_record.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry() -> SourceRegistry:
    """Return a fresh SourceRegistry from the standard fixture paths."""
    return SourceRegistry(
        death_record_path=_DEATH_RECORD_PATH,
        will_path=_WILL_2024_PATH,
        family_record_path=_FAMILY_RECORD_PATH,
    )


def _make_desk_mandate() -> SealedMandate:
    """Return the desk's governing SealedMandate (distinct from source records)."""
    return seal_mandate(
        "citation",
        {"desk": "citation", "authority": "Hollow Hill Mortuary Notices Desk"},
    )


def _canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


def _claim_hash(claim) -> str:
    return hashlib.sha256(
        _canonical_json(claim.to_dict()).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Base class that sets up a registry + desk mandate for all test cases
# ---------------------------------------------------------------------------

class _CitationBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = _make_registry()
        cls.desk_mandate = _make_desk_mandate()
        cls.measurer = CitationMeasurer(cls.registry)


# ---------------------------------------------------------------------------
# Scenario N1 — clean three-assertion draft → all PASS, publishable
# ---------------------------------------------------------------------------

class TestScenarioN1(unittest.TestCase):
    """N1: Three assertions covering all three sources → all PASS, publishable."""

    def setUp(self) -> None:
        self.registry = _make_registry()
        self.desk_mandate = _make_desk_mandate()
        self.measurer = CitationMeasurer(self.registry)

        self.assertions_spec = [
            dict(text="Elias Vane died on 28 October 2026.",
                 fact_key="date_of_death", value="2026-10-28",
                 citation="death_record"),
            dict(text="He bequeathed The Stone Bull to Marta, the neighbor.",
                 fact_key="bequest.Taurus.item", value="The Stone Bull",
                 citation="will_2024"),
            dict(text="He was a self-professed Tree Wizard.",
                 fact_key="occupation",
                 value="self-professed Tree Wizard",
                 citation="family_record"),
        ]
        self.chain = []
        self.claim_hashes = []
        self.verdicts = []
        for a in self.assertions_spec:
            claim = make_assertion_claim(**a)
            self.claim_hashes.append(_claim_hash(claim))
            verdict, receipt = adjudicate(
                claim, self.desk_mandate, self.measurer, self.chain
            )
            self.verdicts.append(verdict)

    def test_all_verdicts_pass(self):
        for i, v in enumerate(self.verdicts):
            with self.subTest(assertion=i):
                self.assertIsInstance(v, Pass, f"Assertion {i} should be Pass, got {v!r}")

    def test_chain_length_is_3(self):
        self.assertEqual(len(self.chain), 3)

    def test_verify_chain_ok(self):
        result = verify_chain(self.chain)
        self.assertTrue(result.ok, f"verify_chain failed: {result}")

    def test_publish_decision_publishable(self):
        decision = check_publish("N1", self.claim_hashes, self.chain)
        self.assertTrue(decision.publishable)
        self.assertIsNone(decision.refusal_name)
        self.assertIsNotNone(decision.receipt_ids)
        self.assertEqual(len(decision.receipt_ids), 3)

    def test_publish_receipt_ids_match_chain(self):
        decision = check_publish("N1", self.claim_hashes, self.chain)
        chain_hashes = [r.own_hash for r in self.chain]
        for rid in decision.receipt_ids:
            self.assertIn(rid, chain_hashes)


# ---------------------------------------------------------------------------
# Scenario N2 — wrong Scorpio beneficiary → REFUSED(source_contradicts)
# ---------------------------------------------------------------------------

class TestScenarioN2(unittest.TestCase):
    """N2: Wrong Scorpio beneficiary → source_contradicts."""

    def setUp(self) -> None:
        self.registry = _make_registry()
        self.desk_mandate = _make_desk_mandate()
        self.measurer = CitationMeasurer(self.registry)

        claim = make_assertion_claim(
            text="He bequeathed The Sealed Letter to Marta, the neighbor.",
            fact_key="bequest.Scorpio.beneficiary",
            value="Marta, the neighbor",
            citation="will_2024",
        )
        self.chain = []
        self.claim_hashes = [_claim_hash(claim)]
        self.verdict, self.receipt = adjudicate(
            claim, self.desk_mandate, self.measurer, self.chain
        )

    def test_verdict_refused_source_contradicts(self):
        self.assertIsInstance(self.verdict, Refused)
        self.assertEqual(self.verdict.name, "source_contradicts")

    def test_observations_include_fact_key(self):
        obs = self.receipt.measurements
        self.assertEqual(obs["fact_key"], "bequest.Scorpio.beneficiary")

    def test_observations_include_asserted_value(self):
        obs = self.receipt.measurements
        self.assertEqual(obs["asserted_value"], "Marta, the neighbor")

    def test_observations_include_stored_value(self):
        obs = self.receipt.measurements
        self.assertEqual(
            obs["stored_value"],
            "the one who knows what happened at the millpond in '87",
        )

    def test_publish_refused_source_contradicts(self):
        decision = check_publish("N2", self.claim_hashes, self.chain)
        self.assertFalse(decision.publishable)
        self.assertEqual(decision.refusal_name, "source_contradicts")


# ---------------------------------------------------------------------------
# Scenario N3 — bequest under empty sign Gemini → REFUSED(unsupported_claim)
# ---------------------------------------------------------------------------

class TestScenarioN3(unittest.TestCase):
    """N3: Bequest under empty sign Gemini → unsupported_claim."""

    def setUp(self) -> None:
        self.registry = _make_registry()
        self.desk_mandate = _make_desk_mandate()
        self.measurer = CitationMeasurer(self.registry)

        claim = make_assertion_claim(
            text="He left The Twin Lanterns to the two apprentices.",
            fact_key="bequest.Gemini.item",
            value="The Twin Lanterns",
            citation="will_2024",
        )
        self.chain = []
        self.claim_hashes = [_claim_hash(claim)]
        self.verdict, self.receipt = adjudicate(
            claim, self.desk_mandate, self.measurer, self.chain
        )

    def test_verdict_refused_unsupported_claim(self):
        self.assertIsInstance(self.verdict, Refused)
        self.assertEqual(self.verdict.name, "unsupported_claim")

    def test_observations_include_fact_key(self):
        obs = self.receipt.measurements
        self.assertEqual(obs["fact_key"], "bequest.Gemini.item")

    def test_observations_include_reason(self):
        obs = self.receipt.measurements
        self.assertEqual(obs["reason"], "fact_key_not_in_source")

    def test_publish_refused_unsupported_claim(self):
        decision = check_publish("N3", self.claim_hashes, self.chain)
        self.assertFalse(decision.publishable)
        self.assertEqual(decision.refusal_name, "unsupported_claim")


# ---------------------------------------------------------------------------
# Scenario N4 — no citation → REFUSED(missing_citation)
# ---------------------------------------------------------------------------

class TestScenarioN4(unittest.TestCase):
    """N4: No citation provided → missing_citation."""

    def setUp(self) -> None:
        self.registry = _make_registry()
        self.desk_mandate = _make_desk_mandate()
        self.measurer = CitationMeasurer(self.registry)

        claim = make_assertion_claim(
            text="He was born in Hollow Hill.",
            fact_key="birthplace",
            value="Hollow Hill",
            citation=None,
        )
        self.chain = []
        self.claim_hashes = [_claim_hash(claim)]
        self.verdict, self.receipt = adjudicate(
            claim, self.desk_mandate, self.measurer, self.chain
        )

    def test_verdict_refused_missing_citation(self):
        self.assertIsInstance(self.verdict, Refused)
        self.assertEqual(self.verdict.name, "missing_citation")

    def test_observations_include_fact_key(self):
        obs = self.receipt.measurements
        self.assertEqual(obs["fact_key"], "birthplace")

    def test_publish_refused_missing_citation(self):
        decision = check_publish("N4", self.claim_hashes, self.chain)
        self.assertFalse(decision.publishable)
        self.assertEqual(decision.refusal_name, "missing_citation")


# ---------------------------------------------------------------------------
# Scenario N5 — mixed draft; correction → publishable
# ---------------------------------------------------------------------------

class TestScenarioN5(unittest.TestCase):
    """N5: Mixed draft initially refused; corrected assertion makes it publishable."""

    def setUp(self) -> None:
        self.registry = _make_registry()
        self.desk_mandate = _make_desk_mandate()
        self.measurer = CitationMeasurer(self.registry)

        # Phase N5a: three assertions (date_of_death PASS, wrong birthplace
        # REFUSED, occupation PASS).
        assertions_spec = [
            dict(text="Elias Vane died on 28 October 2026.",
                 fact_key="date_of_death", value="2026-10-28",
                 citation="death_record"),
            dict(text="He was born in Galway.",
                 fact_key="birthplace", value="Galway",
                 citation="family_record"),
            dict(text="He was a self-professed Tree Wizard.",
                 fact_key="occupation",
                 value="self-professed Tree Wizard",
                 citation="family_record"),
        ]
        self.chain = []
        self.n5a_hashes = []
        self.n5a_verdicts = []
        for a in assertions_spec:
            claim = make_assertion_claim(**a)
            self.n5a_hashes.append(_claim_hash(claim))
            verdict, _ = adjudicate(
                claim, self.desk_mandate, self.measurer, self.chain
            )
            self.n5a_verdicts.append(verdict)

        # N5b: adjudicate corrected assertion 2 into the same chain.
        corrected = make_assertion_claim(
            text="He was born in Hollow Hill.",
            fact_key="birthplace",
            value="Hollow Hill",
            citation="family_record",
        )
        self.corrected_hash = _claim_hash(corrected)
        self.corrected_verdict, _ = adjudicate(
            corrected, self.desk_mandate, self.measurer, self.chain
        )

    def test_n5a_verdicts(self):
        self.assertIsInstance(self.n5a_verdicts[0], Pass)
        self.assertIsInstance(self.n5a_verdicts[1], Refused)
        self.assertEqual(self.n5a_verdicts[1].name, "source_contradicts")
        self.assertIsInstance(self.n5a_verdicts[2], Pass)

    def test_n5a_publish_refused(self):
        decision = check_publish("N5a", self.n5a_hashes, self.chain)
        self.assertFalse(decision.publishable)
        self.assertEqual(decision.refusal_name, "source_contradicts")

    def test_n5b_corrected_verdict_pass(self):
        self.assertIsInstance(self.corrected_verdict, Pass)

    def test_n5b_publish_publishable(self):
        # Use assertion 1 (original hash), corrected assertion 2, assertion 3
        # (original hash).
        n5b_hashes = [
            self.n5a_hashes[0],
            self.corrected_hash,
            self.n5a_hashes[2],
        ]
        decision = check_publish("N5b", n5b_hashes, self.chain)
        self.assertTrue(decision.publishable)
        self.assertIsNone(decision.refusal_name)
        self.assertIsNotNone(decision.receipt_ids)
        self.assertEqual(len(decision.receipt_ids), 3)

    def test_full_chain_length_is_4(self):
        # N5a appended 3 receipts; N5b appended 1 more.
        self.assertEqual(len(self.chain), 4)

    def test_full_chain_verify_ok(self):
        result = verify_chain(self.chain)
        self.assertTrue(result.ok, f"verify_chain failed: {result}")


# ---------------------------------------------------------------------------
# Scenario N6 — unknown source id → REFUSED(unsupported_claim)
# ---------------------------------------------------------------------------

class TestScenarioN6(unittest.TestCase):
    """N6: Unknown source id 'parish_register' → unsupported_claim."""

    def setUp(self) -> None:
        self.registry = _make_registry()
        self.desk_mandate = _make_desk_mandate()
        self.measurer = CitationMeasurer(self.registry)

        claim = make_assertion_claim(
            text="He was known to the parish register.",
            fact_key="person",
            value="Elias Vane",
            citation="parish_register",
        )
        self.chain = []
        self.claim_hashes = [_claim_hash(claim)]
        self.verdict, self.receipt = adjudicate(
            claim, self.desk_mandate, self.measurer, self.chain
        )

    def test_verdict_refused_unsupported_claim(self):
        self.assertIsInstance(self.verdict, Refused)
        self.assertEqual(self.verdict.name, "unsupported_claim")

    def test_observations_include_citation(self):
        obs = self.receipt.measurements
        self.assertEqual(obs["citation"], "parish_register")

    def test_observations_include_reason_source_not_registered(self):
        obs = self.receipt.measurements
        self.assertEqual(obs["reason"], "source_not_registered")

    def test_publish_refused_unsupported_claim(self):
        decision = check_publish("N6", self.claim_hashes, self.chain)
        self.assertFalse(decision.publishable)
        self.assertEqual(decision.refusal_name, "unsupported_claim")


# ---------------------------------------------------------------------------
# Fact table shape tests
# ---------------------------------------------------------------------------

class TestFactTableShape(unittest.TestCase):
    """Verify the structure and completeness of every source's fact table."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = _make_registry()

    def test_death_record_has_exactly_4_keys(self):
        table = self.registry.fact_table("death_record")
        self.assertIsNotNone(table)
        self.assertEqual(set(table.keys()), {"deceased", "date_of_death", "place", "registrar"})

    def test_family_record_has_exactly_5_keys(self):
        table = self.registry.fact_table("family_record")
        self.assertIsNotNone(table)
        self.assertEqual(
            set(table.keys()),
            {"person", "born", "birthplace", "occupation", "residence"},
        )

    def test_will_2024_has_exactly_14_keys(self):
        table = self.registry.fact_table("will_2024")
        self.assertIsNotNone(table)
        self.assertEqual(len(table), 14)

    def test_will_2024_occupied_sign_taurus_item_present(self):
        table = self.registry.fact_table("will_2024")
        self.assertIn("bequest.Taurus.item", table)
        self.assertEqual(table["bequest.Taurus.item"], "The Stone Bull")

    def test_will_2024_occupied_sign_taurus_beneficiary_present(self):
        table = self.registry.fact_table("will_2024")
        self.assertIn("bequest.Taurus.beneficiary", table)
        self.assertEqual(table["bequest.Taurus.beneficiary"], "Marta, the neighbor")

    def test_will_2024_empty_sign_gemini_absent(self):
        table = self.registry.fact_table("will_2024")
        self.assertNotIn("bequest.Gemini.item", table)
        self.assertNotIn("bequest.Gemini.beneficiary", table)

    def test_will_2024_no_empty_sign_keys(self):
        table = self.registry.fact_table("will_2024")
        empty_signs = {"Gemini", "Cancer", "Virgo", "Libra", "Sagittarius"}
        for key in table.keys():
            for sign in empty_signs:
                self.assertNotIn(
                    sign, key,
                    f"Key '{key}' contains empty sign '{sign}'",
                )

    def test_will_2024_all_7_occupied_signs_present(self):
        table = self.registry.fact_table("will_2024")
        occupied_signs = {"Aries", "Taurus", "Leo", "Scorpio", "Capricorn", "Aquarius", "Pisces"}
        for sign in occupied_signs:
            with self.subTest(sign=sign):
                self.assertIn(f"bequest.{sign}.item", table)
                self.assertIn(f"bequest.{sign}.beneficiary", table)

    def test_unknown_source_returns_none(self):
        self.assertIsNone(self.registry.fact_table("unknown_source"))
        self.assertIsNone(self.registry.source("unknown_source"))


# ---------------------------------------------------------------------------
# Tampered cited source — hard error: MandateTamperError propagates
# ---------------------------------------------------------------------------

class TestTamperedCitedSource(unittest.TestCase):
    """A tampered cited source record causes MandateTamperError to propagate.

    gate_core.adjudicate() now re-raises MandateTamperError (Approach A) so
    tampering in the measurer surfaces as a hard error rather than silently
    becoming REFUSED('unmeasured').  The chain length remains 0.
    """

    def test_tampered_source_raises_mandate_tamper_error(self):
        registry = _make_registry()
        desk_mandate = _make_desk_mandate()
        measurer = CitationMeasurer(registry)

        # Tamper the death_record's SealedMandate: replace content with a
        # modified dict while the seal remains the original (hash mismatch).
        original_mandate = registry.source("death_record")
        tampered_content = dict(original_mandate.content)
        tampered_content["deceased"] = "TAMPERED NAME"

        from gate_core import SealedMandate
        tampered_mandate = SealedMandate(
            domain=original_mandate.domain,
            content=tampered_content,
            seal=original_mandate.seal,  # stale seal — will not match new content
        )

        # Inject the tampered mandate back into the registry's internal dict.
        registry._sources["death_record"] = tampered_mandate

        chain: list = []
        claim = make_assertion_claim(
            text="Elias Vane died on 28 October 2026.",
            fact_key="date_of_death",
            value="2026-10-28",
            citation="death_record",
        )

        with self.assertRaises(MandateTamperError):
            adjudicate(claim, desk_mandate, measurer, chain)

        # No receipt was appended because the error propagated before receipt creation.
        self.assertEqual(
            len(chain), 0,
            "Chain must remain empty when MandateTamperError propagates",
        )


# ---------------------------------------------------------------------------
# Publish checker — publishable only when every assertion receipt is PASS
# ---------------------------------------------------------------------------

class TestPublishChecker(unittest.TestCase):
    """Direct unit tests for check_publish logic."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = _make_registry()
        cls.desk_mandate = _make_desk_mandate()
        cls.measurer = CitationMeasurer(cls.registry)

    def _run_assertion(self, chain, **kwargs):
        claim = make_assertion_claim(**kwargs)
        verdict, receipt = adjudicate(
            claim, self.desk_mandate, self.measurer, chain
        )
        return claim, verdict, receipt

    def test_empty_draft_not_publishable(self):
        decision = check_publish("empty", [], [])
        self.assertFalse(decision.publishable)

    def test_single_pass_is_publishable(self):
        chain = []
        claim = make_assertion_claim(
            text="Elias Vane died on 28 October 2026.",
            fact_key="date_of_death",
            value="2026-10-28",
            citation="death_record",
        )
        adjudicate(claim, self.desk_mandate, self.measurer, chain)
        decision = check_publish("single", [_claim_hash(claim)], chain)
        self.assertTrue(decision.publishable)
        self.assertEqual(len(decision.receipt_ids), 1)

    def test_single_refused_not_publishable(self):
        chain = []
        claim = make_assertion_claim(
            text="He was born in Hollow Hill.",
            fact_key="birthplace",
            value="Hollow Hill",
            citation=None,
        )
        adjudicate(claim, self.desk_mandate, self.measurer, chain)
        decision = check_publish("single-refused", [_claim_hash(claim)], chain)
        self.assertFalse(decision.publishable)
        self.assertEqual(decision.refusal_name, "missing_citation")

    def test_unadjudicated_assertion_not_publishable(self):
        chain = []
        # Adjudicate one claim but check publish with two hashes.
        claim1 = make_assertion_claim(
            text="Elias Vane died on 28 October 2026.",
            fact_key="date_of_death",
            value="2026-10-28",
            citation="death_record",
        )
        adjudicate(claim1, self.desk_mandate, self.measurer, chain)

        claim2 = make_assertion_claim(
            text="He was born in Hollow Hill.",
            fact_key="birthplace",
            value="Hollow Hill",
            citation="family_record",
        )
        # claim2 is NOT adjudicated — no receipt in chain.
        decision = check_publish(
            "partial", [_claim_hash(claim1), _claim_hash(claim2)], chain
        )
        self.assertFalse(decision.publishable)
        self.assertEqual(decision.refusal_name, "unmeasured")

    def test_mixed_pass_and_refused_not_publishable(self):
        chain = []
        claim_pass = make_assertion_claim(
            text="Elias Vane died on 28 October 2026.",
            fact_key="date_of_death",
            value="2026-10-28",
            citation="death_record",
        )
        claim_refused = make_assertion_claim(
            text="He was born in Galway.",
            fact_key="birthplace",
            value="Galway",
            citation="family_record",
        )
        adjudicate(claim_pass, self.desk_mandate, self.measurer, chain)
        adjudicate(claim_refused, self.desk_mandate, self.measurer, chain)

        hashes = [_claim_hash(claim_pass), _claim_hash(claim_refused)]
        decision = check_publish("mixed", hashes, chain)
        self.assertFalse(decision.publishable)
        self.assertEqual(decision.refusal_name, "source_contradicts")

    def test_all_pass_receipt_ids_are_own_hashes(self):
        chain = []
        claims = []
        specs = [
            dict(text="Elias Vane died on 28 October 2026.",
                 fact_key="date_of_death", value="2026-10-28",
                 citation="death_record"),
            dict(text="He was a self-professed Tree Wizard.",
                 fact_key="occupation",
                 value="self-professed Tree Wizard",
                 citation="family_record"),
        ]
        for s in specs:
            c = make_assertion_claim(**s)
            claims.append(c)
            adjudicate(c, self.desk_mandate, self.measurer, chain)

        hashes = [_claim_hash(c) for c in claims]
        decision = check_publish("all-pass", hashes, chain)
        self.assertTrue(decision.publishable)
        expected_own_hashes = [r.own_hash for r in chain]
        self.assertEqual(decision.receipt_ids, expected_own_hashes)


# ---------------------------------------------------------------------------
# run_scenarios integration smoke-test
# ---------------------------------------------------------------------------

class TestRunScenarios(unittest.TestCase):
    """Integration test: run_scenarios returns correctly labelled results."""

    @classmethod
    def setUpClass(cls) -> None:
        registry = _make_registry()
        desk_mandate = _make_desk_mandate()
        cls.results = run_scenarios(registry, desk_mandate)
        cls.by_label = {r.label: r for r in cls.results}

    def test_labels_present(self):
        expected_labels = {"N1", "N2", "N3", "N4", "N5a", "N5b", "N6"}
        self.assertEqual(set(self.by_label.keys()), expected_labels)

    def test_n1_publishable(self):
        self.assertTrue(self.by_label["N1"].publish_decision.publishable)

    def test_n2_source_contradicts(self):
        r = self.by_label["N2"]
        self.assertFalse(r.publish_decision.publishable)
        self.assertEqual(r.publish_decision.refusal_name, "source_contradicts")

    def test_n3_unsupported_claim(self):
        r = self.by_label["N3"]
        self.assertFalse(r.publish_decision.publishable)
        self.assertEqual(r.publish_decision.refusal_name, "unsupported_claim")

    def test_n4_missing_citation(self):
        r = self.by_label["N4"]
        self.assertFalse(r.publish_decision.publishable)
        self.assertEqual(r.publish_decision.refusal_name, "missing_citation")

    def test_n5a_refused_n5b_publishable(self):
        self.assertFalse(self.by_label["N5a"].publish_decision.publishable)
        self.assertTrue(self.by_label["N5b"].publish_decision.publishable)

    def test_n6_unsupported_claim(self):
        r = self.by_label["N6"]
        self.assertFalse(r.publish_decision.publishable)
        self.assertEqual(r.publish_decision.refusal_name, "unsupported_claim")


if __name__ == "__main__":
    unittest.main()
