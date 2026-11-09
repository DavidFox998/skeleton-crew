"""
tests.test_executor_slots
~~~~~~~~~~~~~~~~~~~~~~~~~
Tests proving that the Executor measurer works correctly with non-zodiac
slot layouts carried inside the sealed mandate.

Synthetic will:
  testator:       "Monroe"
  slots:          ["House", "Residue", "Trust"]   (3 slots, MSB first)
  vector:         "101"                            (House=1, Residue=0, Trust=1)
  stated_popcount: 2
  bequests:       House → "Monroe Estate" → "Lee Strasberg"
                  Trust → "Personal Effects Trust" → "Aaron Frosch"
  empty_signs:    ["Residue"]

Three test cases:
  1. Faithful distribution (House + Trust)        → PASS
  2. Distribution paying Residue (unoccupied)     → REFUSED(sign_unoccupied)
  3. Mandate whose vector length differs from its
     slots length                                  → MeasurementResult(passed=False,
                                                     refusal_name='seal_broken',
                                                     reason='vector_length_mismatch')
"""

import unittest

import executor  # noqa: F401 — triggers refusal vocabulary registration
from executor import ExecutorMeasurer, make_distribution_claim
from gate_core import Pass, Refused, SealedMandate, seal_mandate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_monroe_death_record() -> SealedMandate:
    """Return a valid sealed death record for Monroe."""
    return seal_mandate(
        domain="executor",
        content={
            "deceased": "Monroe",
            "date_of_death": "1962-08-05",
        },
    )


def _make_monroe_will(vector: str = "101", slots: list | None = None) -> SealedMandate:
    """Return a sealed will for Monroe with the given vector and slots.

    Default slots = ["House", "Residue", "Trust"] (3 slots).
    Default vector = "101" → House occupied, Residue empty, Trust occupied.
    """
    if slots is None:
        slots = ["House", "Residue", "Trust"]
    content = {
        "testator": "Monroe",
        "sealed_date": "1961-01-14",
        "slots": slots,
        "vector": vector,
        "stated_popcount": vector.count("1"),
        "bequests": [
            {
                "sign": "House",
                "item": "Monroe Estate",
                "beneficiary": "Lee Strasberg",
            },
            {
                "sign": "Trust",
                "item": "Personal Effects Trust",
                "beneficiary": "Aaron Frosch",
            },
        ],
        "empty_signs": ["Residue"],
    }
    return seal_mandate(domain="executor", content=content)


class _MonroeRegistry:
    """Minimal registry holding one will and one death record for Monroe."""

    def __init__(self, will: SealedMandate, death_record: SealedMandate | None = None):
        self._will = will
        self._dr = death_record or _make_monroe_death_record()

    def death_record(self, name: str) -> SealedMandate | None:
        if self._dr.content.get("deceased") == name:
            return self._dr
        return None

    def latest_will(self, testator: str) -> SealedMandate | None:
        if self._will.content.get("testator") == testator:
            return self._will
        return None

    def all_wills(self, testator: str) -> list:
        if self._will.content.get("testator") == testator:
            return [self._will]
        return []

    def will_by_seal(self, seal: str) -> SealedMandate | None:
        if self._will.seal == seal:
            return self._will
        return None


# Canonical faithful distributions for the Monroe will (House + Trust).
MONROE_FAITHFUL = [
    {"sign": "House",  "item": "Monroe Estate",         "beneficiary": "Lee Strasberg"},
    {"sign": "Trust",  "item": "Personal Effects Trust", "beneficiary": "Aaron Frosch"},
]


# ---------------------------------------------------------------------------
# Test 1 — faithful distribution PASSes
# ---------------------------------------------------------------------------

class TestMonroeNonZodiacPass(unittest.TestCase):
    """A correct 2-bequest distribution under the Monroe (non-zodiac) will → PASS."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.will = _make_monroe_will()
        cls.registry = _MonroeRegistry(cls.will)
        cls.measurer = ExecutorMeasurer(cls.registry)

    def _measure(self, distributions):
        claim = make_distribution_claim(
            will_ref=self.will.seal,
            distributions=distributions,
        )
        return self.measurer.measure(claim, self.will)

    def test_faithful_distribution_passes(self):
        result = self._measure(MONROE_FAITHFUL)
        self.assertTrue(result.passed)

    def test_observations_contain_both_slots(self):
        result = self._measure(MONROE_FAITHFUL)
        self.assertIn("House",  result.observations["signs_verified"])
        self.assertIn("Trust",  result.observations["signs_verified"])
        self.assertEqual(len(result.observations["signs_verified"]), 2)

    def test_observations_testator_is_monroe(self):
        result = self._measure(MONROE_FAITHFUL)
        self.assertEqual(result.observations["testator"], "Monroe")

    def test_via_adjudicate(self):
        """Full adjudication path also yields PASS."""
        chain = []
        claim = make_distribution_claim(
            will_ref=self.will.seal,
            distributions=MONROE_FAITHFUL,
        )
        verdict, receipt = __import__("gate_core").adjudicate(
            claim, self.will, self.measurer, chain
        )
        self.assertIsInstance(verdict, Pass)
        self.assertEqual(len(chain), 1)


# ---------------------------------------------------------------------------
# Test 2 — paying Residue (unoccupied slot) → REFUSED(sign_unoccupied)
# ---------------------------------------------------------------------------

class TestMonroeResidueUnoccupied(unittest.TestCase):
    """Distributing Residue (vector bit = 0) → REFUSED(sign_unoccupied)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.will = _make_monroe_will()
        cls.registry = _MonroeRegistry(cls.will)
        cls.measurer = ExecutorMeasurer(cls.registry)

    def _measure(self, distributions):
        claim = make_distribution_claim(
            will_ref=self.will.seal,
            distributions=distributions,
        )
        return self.measurer.measure(claim, self.will)

    def test_residue_refused_sign_unoccupied(self):
        """Replace House with Residue — Residue bit is 0 → sign_unoccupied."""
        # Keep count at 2 by replacing House with Residue.
        dist = [
            {"sign": "Residue", "item": "Monroe Estate",         "beneficiary": "Lee Strasberg"},
            {"sign": "Trust",   "item": "Personal Effects Trust", "beneficiary": "Aaron Frosch"},
        ]
        result = self._measure(dist)
        self.assertFalse(result.passed)
        self.assertEqual(result.observations["refusal_name"], "sign_unoccupied")

    def test_residue_sign_in_observations(self):
        dist = [
            {"sign": "Residue", "item": "Monroe Estate",         "beneficiary": "Lee Strasberg"},
            {"sign": "Trust",   "item": "Personal Effects Trust", "beneficiary": "Aaron Frosch"},
        ]
        result = self._measure(dist)
        self.assertEqual(result.observations["sign"], "Residue")

    def test_zodiac_sign_also_unoccupied(self):
        """A zodiac sign like 'Aries' is not in slots → also sign_unoccupied."""
        dist = [
            {"sign": "Aries", "item": "Monroe Estate",          "beneficiary": "Lee Strasberg"},
            {"sign": "Trust", "item": "Personal Effects Trust",  "beneficiary": "Aaron Frosch"},
        ]
        result = self._measure(dist)
        self.assertFalse(result.passed)
        self.assertEqual(result.observations["refusal_name"], "sign_unoccupied")
        self.assertEqual(result.observations["sign"], "Aries")


# ---------------------------------------------------------------------------
# Test 3 — vector length ≠ slots length → seal_broken / vector_length_mismatch
# ---------------------------------------------------------------------------

class TestVectorLengthMismatch(unittest.TestCase):
    """A mandate whose vector length differs from its slots length →
    MeasurementResult(passed=False, refusal_name='seal_broken',
    reason='vector_length_mismatch').
    """

    @classmethod
    def setUpClass(cls) -> None:
        # slots has 3 entries but vector has 4 characters → mismatch
        cls.will = _make_monroe_will(vector="1010", slots=["House", "Residue", "Trust"])
        cls.registry = _MonroeRegistry(cls.will)
        cls.measurer = ExecutorMeasurer(cls.registry)

    def _measure(self, distributions):
        claim = make_distribution_claim(
            will_ref=self.will.seal,
            distributions=distributions,
        )
        return self.measurer.measure(claim, self.will)

    def test_refusal_is_seal_broken(self):
        result = self._measure(MONROE_FAITHFUL)
        self.assertFalse(result.passed)
        self.assertEqual(result.observations["refusal_name"], "seal_broken")

    def test_reason_is_vector_length_mismatch(self):
        result = self._measure(MONROE_FAITHFUL)
        self.assertEqual(result.observations["reason"], "vector_length_mismatch")

    def test_expected_length_equals_slots_count(self):
        result = self._measure(MONROE_FAITHFUL)
        # slots has 3 entries
        self.assertEqual(result.observations["expected_length"], 3)

    def test_actual_length_equals_vector_length(self):
        result = self._measure(MONROE_FAITHFUL)
        # vector "1010" has 4 characters
        self.assertEqual(result.observations["actual_length"], 4)

    def test_mismatch_short_vector(self):
        """slots has 3 entries, vector has 2 → also mismatch."""
        will = _make_monroe_will(vector="10", slots=["House", "Residue", "Trust"])
        registry = _MonroeRegistry(will)
        measurer = ExecutorMeasurer(registry)
        claim = make_distribution_claim(will_ref=will.seal, distributions=MONROE_FAITHFUL)
        result = measurer.measure(claim, will)
        self.assertFalse(result.passed)
        self.assertEqual(result.observations["refusal_name"], "seal_broken")
        self.assertEqual(result.observations["reason"], "vector_length_mismatch")
        self.assertEqual(result.observations["expected_length"], 3)
        self.assertEqual(result.observations["actual_length"], 2)


# ---------------------------------------------------------------------------
# Test 4 — legacy mandate without 'slots' field falls back to zodiac constant
# ---------------------------------------------------------------------------

class TestLegacyFallbackToZodiac(unittest.TestCase):
    """A mandate without 'slots' uses ZODIAC_MSB_TO_LSB as fallback.

    We construct a will whose content has no 'slots' key but whose vector and
    bequests match the zodiac layout, then verify the measurer still passes it.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # Build a minimal zodiac-layout will with no 'slots' key.
        content = {
            "testator": "LegacyTestator",
            "sealed_date": "2000-01-01",
            # No 'slots' key — legacy mandate.
            "vector": "000000000011",  # only Taurus (bit 10) and Aries (bit 11) occupied
            "stated_popcount": 2,
            "bequests": [
                {"sign": "Aries",  "item": "Old Watch", "beneficiary": "Heir A"},
                {"sign": "Taurus", "item": "Old Book",  "beneficiary": "Heir B"},
            ],
            "empty_signs": [
                "Pisces", "Aquarius", "Capricorn", "Sagittarius",
                "Scorpio", "Cancer", "Gemini", "Leo", "Virgo", "Libra",
            ],
        }
        cls.will = seal_mandate(domain="executor", content=content)
        dr = seal_mandate(
            domain="executor",
            content={"deceased": "LegacyTestator", "date_of_death": "2020-06-01"},
        )
        cls.registry = _MonroeRegistry(cls.will, death_record=dr)
        cls.measurer = ExecutorMeasurer(cls.registry)

    def test_legacy_will_without_slots_passes(self):
        distributions = [
            {"sign": "Aries",  "item": "Old Watch", "beneficiary": "Heir A"},
            {"sign": "Taurus", "item": "Old Book",  "beneficiary": "Heir B"},
        ]
        claim = make_distribution_claim(
            will_ref=self.will.seal,
            distributions=distributions,
        )
        result = self.measurer.measure(claim, self.will)
        self.assertTrue(result.passed)

    def test_legacy_will_unoccupied_sign_refused(self):
        """Pisces is unoccupied in the legacy will → sign_unoccupied."""
        distributions = [
            {"sign": "Pisces", "item": "Old Watch", "beneficiary": "Heir A"},
            {"sign": "Taurus", "item": "Old Book",  "beneficiary": "Heir B"},
        ]
        claim = make_distribution_claim(
            will_ref=self.will.seal,
            distributions=distributions,
        )
        result = self.measurer.measure(claim, self.will)
        self.assertFalse(result.passed)
        self.assertEqual(result.observations["refusal_name"], "sign_unoccupied")
        self.assertEqual(result.observations["sign"], "Pisces")


if __name__ == "__main__":
    unittest.main()
