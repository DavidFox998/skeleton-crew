"""
tests.test_executor
~~~~~~~~~~~~~~~~~~~
Unittest suite for the Executor desk.

Test inventory:
  Scenario A  — correct 7-bequest 2024 distribution → Pass
  Scenario B  — any distribution under 2019 will → Refused(will_superseded)
  Scenario C  — 8-entry distribution → Refused(share_mismatch, distribution_count_mismatch)
  Scenario D  — wrong Scorpio beneficiary → Refused(beneficiary_unknown)
  Scenario E  — Gemini entry (unoccupied) → Refused(sign_unoccupied)
  Scenario F  — no death record → Refused(death_unverified)
  Scenario G  — tampered will → MandateTamperError; measurer path → seal_broken
  Extra 1     — stated_popcount ≠ vector popcount → Refused(share_mismatch, stated_popcount_mismatch)
  Extra 2     — duplicate sign in distribution → Refused(share_mismatch, duplicate_sign)
  Extra 3     — precedence: 2019 will + wrong beneficiary → Refused(will_superseded) not beneficiary_unknown
  Extra 4     — precedence: no death record + 2019 will → Refused(death_unverified) not will_superseded
"""

import copy
import json
import os
import tempfile
import unittest

import executor  # triggers refusal vocabulary registration
from executor import (
    ExecutorMeasurer,
    ExecutorRegistry,
    ScenarioResult,
    make_distribution_claim,
    run_scenarios,
)

from gate_core import (
    MandateTamperError,
    Pass,
    Refused,
    SealedMandate,
    seal_mandate,
    verify_chain,
    verify_mandate,
)

# ---------------------------------------------------------------------------
# Fixture paths (relative to this file → project root)
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(__file__)
_ROOT = os.path.dirname(_HERE)
_WILL_2024_PATH = os.path.join(_ROOT, "fixtures", "will_2024.json")
_WILL_2019_PATH = os.path.join(_ROOT, "fixtures", "will_2019.json")
_DEATH_RECORD_PATH = os.path.join(_ROOT, "fixtures", "death_record.json")

# ---------------------------------------------------------------------------
# Canonical distribution data (matches will_2024.json bequests exactly)
# ---------------------------------------------------------------------------

DISTRIBUTIONS_2024 = [
    {"sign": "Aries",     "item": "The Iron Key",
     "beneficiary": "whoever first knocks thrice on the chapel door after midnight on All Hallows' Eve"},
    {"sign": "Taurus",    "item": "The Stone Bull",
     "beneficiary": "Marta, the neighbor"},
    {"sign": "Leo",       "item": "The Brass Telescope",
     "beneficiary": "the child who mapped the lion's heart from the hilltop in the summer of the comet"},
    {"sign": "Scorpio",   "item": "The Sealed Letter",
     "beneficiary": "the one who knows what happened at the millpond in '87"},
    {"sign": "Capricorn", "item": "The Goat Bell",
     "beneficiary": "the town itself"},
    {"sign": "Aquarius",  "item": "The Water Jar",
     "beneficiary": "the well-keeper's daughter"},
    {"sign": "Pisces",    "item": "The Two Fishhooks",
     "beneficiary": "Silas Vane, brother of the testator"},
]

DISTRIBUTIONS_2019 = [
    {"sign": "Aries",     "item": "The Iron Key",
     "beneficiary": "whoever first knocks thrice on the chapel door after midnight on All Hallows' Eve"},
    {"sign": "Taurus",    "item": "The Stone Bull",
     "beneficiary": "Marta, the neighbor"},
    {"sign": "Leo",       "item": "The Brass Telescope",
     "beneficiary": "the child who mapped the lion's heart from the hilltop in the summer of the comet"},
    {"sign": "Capricorn", "item": "The Goat Bell",
     "beneficiary": "the town itself"},
    {"sign": "Aquarius",  "item": "The Water Jar",
     "beneficiary": "the well-keeper's daughter"},
    {"sign": "Pisces",    "item": "The Two Fishhooks",
     "beneficiary": "Silas Vane, brother of the testator"},
]


# ---------------------------------------------------------------------------
# Base test class — builds the full registry once per test class
# ---------------------------------------------------------------------------

class ExecutorTestBase(unittest.TestCase):
    """Shared fixture setup for executor tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = ExecutorRegistry(
            will_paths=[_WILL_2019_PATH, _WILL_2024_PATH],
            death_record_paths=[_DEATH_RECORD_PATH],
        )
        cls.will_2024 = cls.registry.latest_will("Elias Vane")
        all_wills = cls.registry.all_wills("Elias Vane")
        cls.will_2019 = all_wills[0]  # oldest = 2019

    def _adjudicate(self, mandate, distributions, registry=None):
        """Convenience: build a claim, adjudicate, return (verdict, receipt, chain)."""
        reg = registry if registry is not None else self.registry
        chain = []
        measurer = ExecutorMeasurer(reg)
        claim = make_distribution_claim(
            will_ref=mandate.seal,
            distributions=distributions,
        )
        verdict, receipt = __import__("gate_core").adjudicate(claim, mandate, measurer, chain)
        return verdict, receipt, chain

    def _measure(self, mandate, distributions, registry=None):
        """Convenience: run measure() directly without going through adjudicate()."""
        reg = registry if registry is not None else self.registry
        measurer = ExecutorMeasurer(reg)
        claim = make_distribution_claim(
            will_ref=mandate.seal,
            distributions=distributions,
        )
        return measurer.measure(claim, mandate)


# ===========================================================================
# Scenario tests
# ===========================================================================

class TestScenarioA(ExecutorTestBase):
    """Scenario A — correct 7-bequest 2024 distribution → PASS."""

    def test_verdict_is_pass(self):
        verdict, receipt, chain = self._adjudicate(self.will_2024, DISTRIBUTIONS_2024)
        self.assertIsInstance(verdict, Pass)

    def test_chain_length_is_one(self):
        _, _, chain = self._adjudicate(self.will_2024, DISTRIBUTIONS_2024)
        self.assertEqual(len(chain), 1)

    def test_verify_chain_ok(self):
        _, _, chain = self._adjudicate(self.will_2024, DISTRIBUTIONS_2024)
        result = verify_chain(chain)
        self.assertTrue(result.ok)

    def test_observations_contain_all_seven_signs(self):
        verdict, receipt, chain = self._adjudicate(self.will_2024, DISTRIBUTIONS_2024)
        signs_verified = receipt.measurements["signs_verified"]
        expected = {d["sign"] for d in DISTRIBUTIONS_2024}
        self.assertEqual(set(signs_verified), expected)
        self.assertEqual(len(signs_verified), 7)


class TestScenarioB(ExecutorTestBase):
    """Scenario B — distribution under 2019 will → REFUSED(will_superseded)."""

    def test_verdict_is_refused_will_superseded(self):
        verdict, receipt, chain = self._adjudicate(self.will_2019, DISTRIBUTIONS_2019)
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "will_superseded")

    def test_observations_include_governing_seal(self):
        verdict, receipt, chain = self._adjudicate(self.will_2019, DISTRIBUTIONS_2019)
        governing_seal = receipt.measurements["governing_seal"]
        self.assertEqual(governing_seal, self.will_2024.seal)

    def test_chain_length_is_one(self):
        _, _, chain = self._adjudicate(self.will_2019, DISTRIBUTIONS_2019)
        self.assertEqual(len(chain), 1)


class TestScenarioC(ExecutorTestBase):
    """Scenario C — 8-entry distribution → REFUSED(share_mismatch)."""

    def setUp(self):
        self.extra_dist = list(DISTRIBUTIONS_2024) + [
            {"sign": "Taurus", "item": "The Stone Bull", "beneficiary": "an interloper"}
        ]

    def test_verdict_is_refused_share_mismatch(self):
        verdict, receipt, chain = self._adjudicate(self.will_2024, self.extra_dist)
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "share_mismatch")

    def test_observations_reason_distribution_count_mismatch(self):
        verdict, receipt, chain = self._adjudicate(self.will_2024, self.extra_dist)
        self.assertEqual(receipt.measurements["reason"], "distribution_count_mismatch")


class TestScenarioD(ExecutorTestBase):
    """Scenario D — Scorpio with wrong beneficiary → REFUSED(beneficiary_unknown)."""

    def setUp(self):
        self.dist_d = [
            d if d["sign"] != "Scorpio"
            else {**d, "beneficiary": "an unknown claimant"}
            for d in DISTRIBUTIONS_2024
        ]

    def test_verdict_is_refused_beneficiary_unknown(self):
        verdict, receipt, chain = self._adjudicate(self.will_2024, self.dist_d)
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "beneficiary_unknown")

    def test_observations_sign_is_scorpio(self):
        verdict, receipt, chain = self._adjudicate(self.will_2024, self.dist_d)
        self.assertEqual(receipt.measurements["sign"], "Scorpio")


class TestScenarioE(ExecutorTestBase):
    """Scenario E — Gemini entry in distribution → REFUSED(sign_unoccupied)."""

    def setUp(self):
        # Replace Taurus with Gemini to keep count at 7.
        self.dist_e = [
            d if d["sign"] != "Taurus"
            else {"sign": "Gemini", "item": "The Stone Bull", "beneficiary": "Marta, the neighbor"}
            for d in DISTRIBUTIONS_2024
        ]

    def test_verdict_is_refused_sign_unoccupied(self):
        verdict, receipt, chain = self._adjudicate(self.will_2024, self.dist_e)
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "sign_unoccupied")

    def test_observations_sign_is_gemini(self):
        verdict, receipt, chain = self._adjudicate(self.will_2024, self.dist_e)
        self.assertEqual(receipt.measurements["sign"], "Gemini")


class TestScenarioF(ExecutorTestBase):
    """Scenario F — no death record in registry → REFUSED(death_unverified)."""

    class _NoDeathRegistry:
        """Wraps an ExecutorRegistry but always returns None for death records."""
        def __init__(self, real):
            self._real = real
        def death_record(self, name):
            return None
        def latest_will(self, testator):
            return self._real.latest_will(testator)
        def all_wills(self, testator):
            return self._real.all_wills(testator)
        def will_by_seal(self, seal):
            return self._real.will_by_seal(seal)

    def test_verdict_is_refused_death_unverified(self):
        no_death = self._NoDeathRegistry(self.registry)
        verdict, receipt, chain = self._adjudicate(
            self.will_2024, DISTRIBUTIONS_2024, registry=no_death
        )
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "death_unverified")

    def test_observations_death_record_present_false(self):
        no_death = self._NoDeathRegistry(self.registry)
        verdict, receipt, chain = self._adjudicate(
            self.will_2024, DISTRIBUTIONS_2024, registry=no_death
        )
        self.assertFalse(receipt.measurements["death_record_present"])


class TestScenarioG(ExecutorTestBase):
    """Scenario G — tampered will mandate.

    Two sub-cases:
    (a) Tampered mandate passed to adjudicate() → MandateTamperError; chain stays empty.
    (b) Tampered mandate passed directly to measure() → MeasurementResult(passed=False,
        refusal_name='seal_broken').
    """

    def _make_tampered_mandate(self):
        """Return a SealedMandate whose content differs from what was sealed."""
        tampered_bequests = [
            {**b, "beneficiary": "TAMPERED"} if b["sign"] == "Aries" else b
            for b in self.will_2024.content["bequests"]
        ]
        tampered_content = {**self.will_2024.content, "bequests": tampered_bequests}
        return SealedMandate(
            domain=self.will_2024.domain,
            content=tampered_content,
            seal=self.will_2024.seal,  # original seal — no longer matches
        )

    def test_adjudicate_raises_mandate_tamper_error(self):
        """adjudicate() raises MandateTamperError on tampered mandate."""
        tampered = self._make_tampered_mandate()
        chain = []
        measurer = ExecutorMeasurer(self.registry)
        claim = make_distribution_claim(
            will_ref=self.will_2024.seal,
            distributions=DISTRIBUTIONS_2024,
        )
        with self.assertRaises(MandateTamperError):
            __import__("gate_core").adjudicate(claim, tampered, measurer, chain)

    def test_chain_remains_empty_on_tamper(self):
        """No receipt is appended when MandateTamperError is raised."""
        tampered = self._make_tampered_mandate()
        chain = []
        measurer = ExecutorMeasurer(self.registry)
        claim = make_distribution_claim(
            will_ref=self.will_2024.seal,
            distributions=DISTRIBUTIONS_2024,
        )
        try:
            __import__("gate_core").adjudicate(claim, tampered, measurer, chain)
        except MandateTamperError:
            pass
        self.assertEqual(len(chain), 0)

    def test_measure_directly_returns_seal_broken(self):
        """measure() called directly with tampered mandate returns seal_broken."""
        tampered = self._make_tampered_mandate()
        result = self._measure(self.will_2024, DISTRIBUTIONS_2024)  # intact mandate
        # Now measure with tampered mandate directly.
        measurer = ExecutorMeasurer(self.registry)
        claim = make_distribution_claim(
            will_ref=tampered.seal,
            distributions=DISTRIBUTIONS_2024,
        )
        result = measurer.measure(claim, tampered)
        self.assertFalse(result.passed)
        self.assertEqual(result.observations["refusal_name"], "seal_broken")


# ===========================================================================
# Extra test cases
# ===========================================================================

class _SingleWillRegistry:
    """A minimal in-memory registry holding exactly one will and one death record.

    Used in tests that need to bypass the supersession check by making the
    test will the only/latest will for its testator.
    """

    def __init__(self, will: SealedMandate, death_record: SealedMandate | None):
        self._will = will
        self._death_record = death_record

    def death_record(self, name):
        if self._death_record and self._death_record.content.get("deceased") == name:
            return self._death_record
        return None

    def latest_will(self, testator):
        if self._will.content.get("testator") == testator:
            return self._will
        return None

    def all_wills(self, testator):
        if self._will.content.get("testator") == testator:
            return [self._will]
        return []

    def will_by_seal(self, seal):
        if self._will.seal == seal:
            return self._will
        return None


class TestStatedPopcountLiesAboutVector(ExecutorTestBase):
    """Extra — stated_popcount does not equal count of '1' bits in vector
    → Refused(share_mismatch, reason='stated_popcount_mismatch').

    The bad-popcount will is placed in a _SingleWillRegistry so that it IS
    the latest will for the testator (bypassing the supersession check),
    allowing the stated_popcount check to fire first.
    """

    def _make_bad_popcount_registry(self):
        """Return (bad_will, registry_with_only_that_will)."""
        with open(_WILL_2024_PATH, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        # Lie: claim 8 bequests when there are actually 7.
        data["stated_popcount"] = 8
        bad_will = seal_mandate(domain="executor", content=data)
        death_record = self.registry.death_record("Elias Vane")
        reg = _SingleWillRegistry(bad_will, death_record)
        return bad_will, reg

    def test_refused_share_mismatch_stated_popcount(self):
        bad_will, reg = self._make_bad_popcount_registry()
        result = self._measure(bad_will, DISTRIBUTIONS_2024, registry=reg)
        self.assertFalse(result.passed)
        self.assertEqual(result.observations["refusal_name"], "share_mismatch")
        self.assertEqual(result.observations["reason"], "stated_popcount_mismatch")

    def test_stated_and_actual_values_in_observations(self):
        bad_will, reg = self._make_bad_popcount_registry()
        result = self._measure(bad_will, DISTRIBUTIONS_2024, registry=reg)
        self.assertEqual(result.observations["stated"], 8)
        self.assertEqual(result.observations["actual"], 7)


class TestDuplicateSign(ExecutorTestBase):
    """Extra — same sign appears twice in distribution
    → Refused(share_mismatch, reason='duplicate_sign').

    The total count still equals popcount by using two Aries entries and
    omitting Taurus.
    """

    def _make_duplicate_dist(self):
        """Return a 7-entry distribution with Aries appearing twice (no Taurus)."""
        aries_entry = next(d for d in DISTRIBUTIONS_2024 if d["sign"] == "Aries")
        return [
            d if d["sign"] != "Taurus" else dict(aries_entry)
            for d in DISTRIBUTIONS_2024
        ]

    def test_refused_share_mismatch_duplicate_sign(self):
        dist = self._make_duplicate_dist()
        # Verify duplicate exists.
        signs = [d["sign"] for d in dist]
        self.assertEqual(signs.count("Aries"), 2)

        result = self._measure(self.will_2024, dist)
        self.assertFalse(result.passed)
        self.assertEqual(result.observations["refusal_name"], "share_mismatch")
        self.assertEqual(result.observations["reason"], "duplicate_sign")

    def test_duplicate_sign_in_observations(self):
        dist = self._make_duplicate_dist()
        result = self._measure(self.will_2024, dist)
        self.assertEqual(result.observations["sign"], "Aries")


class TestPrecedence(ExecutorTestBase):
    """Extra — precedence: earlier check wins over later check.

    Case 1: Distribution under 2019 will that also names a wrong beneficiary
            → Refused(will_superseded), not beneficiary_unknown.

    Case 2: Distribution with no death record and the 2019 (superseded) will
            → Refused(death_unverified), not will_superseded.
    """

    class _NoDeathRegistry:
        def __init__(self, real):
            self._real = real
        def death_record(self, name):
            return None
        def latest_will(self, testator):
            return self._real.latest_will(testator)
        def all_wills(self, testator):
            return self._real.all_wills(testator)
        def will_by_seal(self, seal):
            return self._real.will_by_seal(seal)

    def test_will_superseded_beats_beneficiary_unknown(self):
        """2019 will + wrong beneficiary → will_superseded (not beneficiary_unknown)."""
        # Use 2019 distributions but corrupt one beneficiary.
        dist_wrong_benef = [
            d if d["sign"] != "Aries"
            else {**d, "beneficiary": "wrong person"}
            for d in DISTRIBUTIONS_2019
        ]
        verdict, receipt, chain = self._adjudicate(self.will_2019, dist_wrong_benef)
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "will_superseded",
                         "will_superseded must take precedence over beneficiary_unknown")

    def test_death_unverified_beats_will_superseded(self):
        """No death record + 2019 will → death_unverified (not will_superseded)."""
        no_death = self._NoDeathRegistry(self.registry)
        verdict, receipt, chain = self._adjudicate(
            self.will_2019, DISTRIBUTIONS_2019, registry=no_death
        )
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "death_unverified",
                         "death_unverified must take precedence over will_superseded")


# ===========================================================================
# Scenario runner integration test
# ===========================================================================

class TestRunScenarios(ExecutorTestBase):
    """Smoke-test the run_scenarios() helper; verifies all 7 labels appear."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.results = run_scenarios(cls.registry)
        cls.by_label = {r.label: r for r in cls.results}

    def test_returns_seven_results(self):
        self.assertEqual(len(self.results), 7)

    def test_all_labels_present(self):
        self.assertEqual(set(self.by_label.keys()), {"A", "B", "C", "D", "E", "F", "G"})

    def test_scenario_a_pass(self):
        self.assertIsInstance(self.by_label["A"].verdict, Pass)

    def test_scenario_b_will_superseded(self):
        self.assertIsInstance(self.by_label["B"].verdict, Refused)
        self.assertEqual(self.by_label["B"].verdict.name, "will_superseded")

    def test_scenario_c_share_mismatch(self):
        self.assertIsInstance(self.by_label["C"].verdict, Refused)
        self.assertEqual(self.by_label["C"].verdict.name, "share_mismatch")

    def test_scenario_d_beneficiary_unknown(self):
        self.assertIsInstance(self.by_label["D"].verdict, Refused)
        self.assertEqual(self.by_label["D"].verdict.name, "beneficiary_unknown")

    def test_scenario_e_sign_unoccupied(self):
        self.assertIsInstance(self.by_label["E"].verdict, Refused)
        self.assertEqual(self.by_label["E"].verdict.name, "sign_unoccupied")

    def test_scenario_f_death_unverified(self):
        self.assertIsInstance(self.by_label["F"].verdict, Refused)
        self.assertEqual(self.by_label["F"].verdict.name, "death_unverified")

    def test_scenario_g_tamper_error(self):
        r = self.by_label["G"]
        self.assertIsInstance(r.tamper_error, MandateTamperError)
        self.assertIsNone(r.verdict)
        self.assertEqual(len(r.chain), 0)


if __name__ == "__main__":
    unittest.main()
