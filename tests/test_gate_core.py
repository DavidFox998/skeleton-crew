"""
tests/test_gate_core.py
~~~~~~~~~~~~~~~~~~~~~~~
Unittest suite for the gate_core package.

Run with:
    python3 -m unittest discover -s tests -v
"""

import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import replace

from gate_core import (
    Claim,
    MandateTamperError,
    MeasurementResult,
    Pass,
    Refused,
    ReplayResult,
    SealedMandate,
    UnknownRefusalError,
    append_receipt,
    is_valid_refusal,
    load_chain,
    make_pass,
    make_refused,
    receipt_from_dict,
    receipt_to_dict,
    register_refusal,
    save_chain,
    seal_mandate,
    unmeasured_refusal,
    verify_chain,
    verify_mandate,
)


# ---------------------------------------------------------------------------
# Helpers shared across test cases
# ---------------------------------------------------------------------------

DOMAIN = "test_domain"
TIMESTAMP = "2026-11-01T22:00:00Z"


def _register_domain_refusals() -> None:
    """Register a standard set of refusal names for DOMAIN (idempotent)."""
    for name in ("violates_terms", "insufficient_evidence"):
        if not is_valid_refusal(DOMAIN, name):
            register_refusal(DOMAIN, name)


def _make_claim(payload: dict | None = None) -> Claim:
    return Claim(
        domain=DOMAIN,
        claim_type="test_assertion",
        payload=payload or {"key": "value"},
    )


def _make_mandate(content: dict | None = None) -> SealedMandate:
    return seal_mandate(DOMAIN, content or {"rule": "must_be_true"})


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


# ---------------------------------------------------------------------------
# 1. Claim construction
# ---------------------------------------------------------------------------

class TestClaimConstruction(unittest.TestCase):

    def test_valid_claim(self) -> None:
        c = _make_claim()
        self.assertEqual(c.domain, DOMAIN)
        self.assertEqual(c.claim_type, "test_assertion")
        self.assertEqual(c.payload, {"key": "value"})

    def test_blank_domain_raises(self) -> None:
        with self.assertRaises(ValueError):
            Claim(domain="", claim_type="t", payload={})

    def test_whitespace_domain_raises(self) -> None:
        with self.assertRaises(ValueError):
            Claim(domain="   ", claim_type="t", payload={})

    def test_blank_claim_type_raises(self) -> None:
        with self.assertRaises(ValueError):
            Claim(domain="d", claim_type="", payload={})

    def test_non_serialisable_payload_raises(self) -> None:
        with self.assertRaises(ValueError):
            Claim(domain="d", claim_type="t", payload={"bad": object()})

    def test_claim_is_immutable(self) -> None:
        c = _make_claim()
        with self.assertRaises((AttributeError, TypeError)):
            c.domain = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 2. Mandate seal / verify round-trip
# ---------------------------------------------------------------------------

class TestMandateSealVerify(unittest.TestCase):

    def test_seal_produces_hex_sha256(self) -> None:
        mandate = _make_mandate()
        expected = hashlib.sha256(
            _canonical(mandate.content).encode('utf-8')
        ).hexdigest()
        self.assertEqual(mandate.seal, expected)
        self.assertEqual(len(mandate.seal), 64)

    def test_verify_returns_true_for_intact_mandate(self) -> None:
        mandate = _make_mandate()
        self.assertTrue(verify_mandate(mandate))

    def test_tampered_mandate_fails_verification(self) -> None:
        mandate = _make_mandate({"rule": "must_be_true"})
        # Bypass frozen dataclass to simulate tampering via object.__setattr__
        tampered = SealedMandate(
            domain=mandate.domain,
            content={"rule": "tampered"},   # content changed
            seal=mandate.seal,              # seal NOT updated
        )
        self.assertFalse(verify_mandate(tampered))

    def test_mandate_is_immutable(self) -> None:
        mandate = _make_mandate()
        with self.assertRaises((AttributeError, TypeError)):
            mandate.seal = "deadbeef"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 3. MandateTamperError raised by gate logic
# ---------------------------------------------------------------------------

class TestMandateTamperError(unittest.TestCase):
    """Demonstrates that gate code raises MandateTamperError on tampered mandate."""

    def test_raise_on_tampered_mandate(self) -> None:
        mandate = _make_mandate()
        tampered = SealedMandate(
            domain=mandate.domain,
            content={"rule": "altered"},
            seal=mandate.seal,
        )
        with self.assertRaises(MandateTamperError):
            if not verify_mandate(tampered):
                raise MandateTamperError("Mandate seal mismatch.")


# ---------------------------------------------------------------------------
# 4. Verdict construction
# ---------------------------------------------------------------------------

class TestVerdictConstruction(unittest.TestCase):

    def setUp(self) -> None:
        _register_domain_refusals()

    def test_make_pass(self) -> None:
        v = make_pass()
        self.assertIsInstance(v, Pass)

    def test_make_refused_known_name(self) -> None:
        v = make_refused(DOMAIN, "violates_terms")
        self.assertIsInstance(v, Refused)
        self.assertEqual(v.name, "violates_terms")

    def test_make_refused_unknown_name_raises(self) -> None:
        with self.assertRaises(UnknownRefusalError):
            make_refused(DOMAIN, "does_not_exist")

    def test_unmeasured_refusal(self) -> None:
        v = unmeasured_refusal()
        self.assertIsInstance(v, Refused)
        self.assertEqual(v.name, "unmeasured")

    def test_unmeasured_is_valid_for_any_domain(self) -> None:
        self.assertTrue(is_valid_refusal(DOMAIN, "unmeasured"))
        self.assertTrue(is_valid_refusal("brand_new_domain", "unmeasured"))

    def test_register_reserved_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            register_refusal(DOMAIN, "unmeasured")

    def test_verdict_immutable(self) -> None:
        v = make_pass()
        with self.assertRaises((AttributeError, TypeError)):
            v.nonexistent = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 5. PASS verdict for a satisfying claim
# ---------------------------------------------------------------------------

class TestPassVerdict(unittest.TestCase):

    def setUp(self) -> None:
        _register_domain_refusals()

    def test_pass_for_satisfying_measurement(self) -> None:
        claim = _make_claim({"amount": 100})
        mandate = _make_mandate({"max_amount": 200})
        self.assertTrue(verify_mandate(mandate))

        measurement = MeasurementResult(
            observations={"amount": 100, "max_amount": 200},
            passed=True,
        )
        # Gate policy: passed=True → make_pass()
        verdict = make_pass() if measurement.passed else make_refused(DOMAIN, "violates_terms")
        self.assertIsInstance(verdict, Pass)


# ---------------------------------------------------------------------------
# 6. REFUSED verdict for a violating claim
# ---------------------------------------------------------------------------

class TestRefusedVerdict(unittest.TestCase):

    def setUp(self) -> None:
        _register_domain_refusals()

    def test_refused_for_violating_measurement(self) -> None:
        claim = _make_claim({"amount": 300})
        mandate = _make_mandate({"max_amount": 200})
        self.assertTrue(verify_mandate(mandate))

        measurement = MeasurementResult(
            observations={"amount": 300, "max_amount": 200},
            passed=False,
        )
        verdict = make_pass() if measurement.passed else make_refused(DOMAIN, "violates_terms")
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "violates_terms")


# ---------------------------------------------------------------------------
# 7. Unmeasured claim is refused with 'unmeasured'
# ---------------------------------------------------------------------------

class TestUnmeasuredRefusal(unittest.TestCase):

    def test_no_measurement_produces_unmeasured_refused(self) -> None:
        # Simulate: measurement is None (no measurer registered / exception raised)
        measurement: MeasurementResult | None = None
        verdict = make_pass() if (measurement is not None and measurement.passed) \
            else unmeasured_refusal()
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "unmeasured")

    def test_unmeasured_refusal_is_valid_in_every_domain(self) -> None:
        for domain in (DOMAIN, "executor", "citation_gate", "brand_new"):
            with self.subTest(domain=domain):
                self.assertTrue(is_valid_refusal(domain, "unmeasured"))


# ---------------------------------------------------------------------------
# 8. Receipt construction and hash
# ---------------------------------------------------------------------------

class TestReceiptConstruction(unittest.TestCase):

    def setUp(self) -> None:
        _register_domain_refusals()

    def _make_first_receipt(self) -> object:
        claim = _make_claim()
        mandate = _make_mandate()
        measurement = MeasurementResult(observations={"ok": True}, passed=True)
        verdict = make_pass()
        return append_receipt([], claim, measurement, None, verdict, TIMESTAMP)

    def test_first_receipt_has_sentinel_previous_hash(self) -> None:
        r = self._make_first_receipt()
        self.assertEqual(r.previous_hash, "0" * 64)

    def test_own_hash_is_64_hex_chars(self) -> None:
        r = self._make_first_receipt()
        self.assertEqual(len(r.own_hash), 64)
        int(r.own_hash, 16)  # must be valid hex

    def test_own_hash_is_reproducible(self) -> None:
        """Recompute own_hash independently and compare."""
        r = self._make_first_receipt()
        fields = {
            'claim': r.claim,
            'measurements': r.measurements,
            'measurement_error': r.measurement_error,
            'verdict': r.verdict,
            'timestamp_utc': r.timestamp_utc,
            'previous_hash': r.previous_hash,
        }
        expected = hashlib.sha256(
            _canonical(fields).encode('utf-8')
        ).hexdigest()
        self.assertEqual(r.own_hash, expected)

    def test_receipt_is_immutable(self) -> None:
        r = self._make_first_receipt()
        with self.assertRaises((AttributeError, TypeError)):
            r.own_hash = "bad"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 9. Receipt chain — each receipt references previous hash
# ---------------------------------------------------------------------------

class TestReceiptChain(unittest.TestCase):

    def setUp(self) -> None:
        _register_domain_refusals()

    def _build_chain(self, length: int = 3) -> list:
        chain = []
        for i in range(length):
            claim = _make_claim({"index": i})
            measurement = MeasurementResult(observations={"i": i}, passed=True)
            verdict = make_pass()
            r = append_receipt(chain, claim, measurement, None, verdict, TIMESTAMP)
            chain.append(r)
        return chain

    def test_chain_links_are_correct(self) -> None:
        chain = self._build_chain(3)
        self.assertEqual(chain[0].previous_hash, "0" * 64)
        self.assertEqual(chain[1].previous_hash, chain[0].own_hash)
        self.assertEqual(chain[2].previous_hash, chain[1].own_hash)

    def test_chain_length(self) -> None:
        chain = self._build_chain(5)
        self.assertEqual(len(chain), 5)

    def test_unmeasured_receipt_in_chain(self) -> None:
        chain = []
        claim = _make_claim()
        verdict = unmeasured_refusal()
        r = append_receipt(chain, claim, None, "measurer crashed", verdict, TIMESTAMP)
        chain.append(r)
        self.assertIsNone(r.measurements)
        self.assertEqual(r.measurement_error, "measurer crashed")
        self.assertEqual(r.verdict, {"type": "refused", "name": "unmeasured"})


# ---------------------------------------------------------------------------
# 10. Replay — clean chain
# ---------------------------------------------------------------------------

class TestVerifyChainPass(unittest.TestCase):

    def setUp(self) -> None:
        _register_domain_refusals()

    def test_replay_clean_chain(self) -> None:
        chain = []
        for i in range(4):
            claim = _make_claim({"n": i})
            m = MeasurementResult(observations={"n": i}, passed=True)
            r = append_receipt(chain, claim, m, None, make_pass(), TIMESTAMP)
            chain.append(r)

        result = verify_chain(chain)
        self.assertTrue(result.ok)
        self.assertIsNone(result.failure_index)
        self.assertIsNone(result.failure_reason)

    def test_replay_empty_chain(self) -> None:
        result = verify_chain([])
        self.assertTrue(result.ok)

    def test_replay_single_receipt(self) -> None:
        claim = _make_claim()
        m = MeasurementResult(observations={}, passed=True)
        r = append_receipt([], claim, m, None, make_pass(), TIMESTAMP)
        result = verify_chain([r])
        self.assertTrue(result.ok)


# ---------------------------------------------------------------------------
# 11. Replay — tampered receipt detected
# ---------------------------------------------------------------------------

class TestVerifyChainTampered(unittest.TestCase):

    def setUp(self) -> None:
        _register_domain_refusals()

    def _build_chain(self, length: int = 3) -> list:
        chain = []
        for i in range(length):
            claim = _make_claim({"index": i})
            m = MeasurementResult(observations={"i": i}, passed=True)
            r = append_receipt(chain, claim, m, None, make_pass(), TIMESTAMP)
            chain.append(r)
        return chain

    def test_tampered_own_hash_detected(self) -> None:
        chain = self._build_chain(3)
        # Tamper: replace receipt at index 1 with a fake own_hash
        from gate_core.receipt import Receipt
        bad = Receipt(
            claim=chain[1].claim,
            measurements=chain[1].measurements,
            measurement_error=chain[1].measurement_error,
            verdict=chain[1].verdict,
            timestamp_utc=chain[1].timestamp_utc,
            previous_hash=chain[1].previous_hash,
            own_hash="deadbeef" * 8,   # 64 chars, wrong value
        )
        tampered_chain = [chain[0], bad, chain[2]]
        result = verify_chain(tampered_chain)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_index, 1)
        self.assertEqual(result.failure_reason, 'hash_mismatch')

    def test_tampered_payload_detected(self) -> None:
        chain = self._build_chain(3)
        # Tamper: change the claim payload of receipt[1] (own_hash won't match)
        from gate_core.receipt import Receipt
        bad = Receipt(
            claim={"domain": DOMAIN, "claim_type": "test_assertion", "payload": {"index": 99}},
            measurements=chain[1].measurements,
            measurement_error=chain[1].measurement_error,
            verdict=chain[1].verdict,
            timestamp_utc=chain[1].timestamp_utc,
            previous_hash=chain[1].previous_hash,
            own_hash=chain[1].own_hash,   # own_hash not updated → mismatch
        )
        tampered_chain = [chain[0], bad, chain[2]]
        result = verify_chain(tampered_chain)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_index, 1)
        self.assertEqual(result.failure_reason, 'hash_mismatch')

    def test_broken_link_detected(self) -> None:
        """Detect when receipt[i].previous_hash doesn't match receipt[i-1].own_hash."""
        chain = self._build_chain(3)
        # Build a separate, valid receipt with the right own_hash but wrong previous_hash
        from gate_core.receipt import Receipt, _compute_own_hash  # noqa: PLC2701

        # Reconstruct receipt[1] with a wrong previous_hash but correct own_hash
        # for the *altered* fields (so own_hash check passes but chain check fails).
        bad_fields = {
            'claim': chain[1].claim,
            'measurements': chain[1].measurements,
            'measurement_error': chain[1].measurement_error,
            'verdict': chain[1].verdict,
            'timestamp_utc': chain[1].timestamp_utc,
            'previous_hash': "a" * 64,   # wrong previous_hash
        }
        bad_own_hash = _compute_own_hash(bad_fields)
        bad = Receipt(
            claim=chain[1].claim,
            measurements=chain[1].measurements,
            measurement_error=chain[1].measurement_error,
            verdict=chain[1].verdict,
            timestamp_utc=chain[1].timestamp_utc,
            previous_hash="a" * 64,
            own_hash=bad_own_hash,
        )
        tampered_chain = [chain[0], bad, chain[2]]
        result = verify_chain(tampered_chain)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_index, 1)
        self.assertEqual(result.failure_reason, 'chain_broken')

    def test_replay_stops_at_first_failure(self) -> None:
        """Only the first broken receipt is reported."""
        chain = self._build_chain(4)
        from gate_core.receipt import Receipt
        # Corrupt receipts 1 and 2; only index 1 should be reported.
        def corrupt(r: object) -> object:
            return Receipt(
                claim=r.claim,
                measurements=r.measurements,
                measurement_error=r.measurement_error,
                verdict=r.verdict,
                timestamp_utc=r.timestamp_utc,
                previous_hash=r.previous_hash,
                own_hash="eeeeeeee" * 8,
            )
        tampered = [chain[0], corrupt(chain[1]), corrupt(chain[2]), chain[3]]
        result = verify_chain(tampered)
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_index, 1)


# ---------------------------------------------------------------------------
# 12. Serialisation round-trip (receipt_to_dict / receipt_from_dict)
# ---------------------------------------------------------------------------

class TestReceiptSerialisation(unittest.TestCase):

    def setUp(self) -> None:
        _register_domain_refusals()

    def test_round_trip(self) -> None:
        claim = _make_claim({"x": 1})
        m = MeasurementResult(observations={"x": 1}, passed=True)
        r = append_receipt([], claim, m, None, make_pass(), TIMESTAMP)
        d = receipt_to_dict(r)
        r2 = receipt_from_dict(d)
        self.assertEqual(r, r2)

    def test_round_trip_unmeasured(self) -> None:
        claim = _make_claim()
        r = append_receipt([], claim, None, "boom", unmeasured_refusal(), TIMESTAMP)
        d = receipt_to_dict(r)
        r2 = receipt_from_dict(d)
        self.assertEqual(r, r2)
        self.assertIsNone(r2.measurements)
        self.assertEqual(r2.measurement_error, "boom")


# ---------------------------------------------------------------------------
# 13. save_chain / load_chain I/O helpers
# ---------------------------------------------------------------------------

class TestChainIO(unittest.TestCase):

    def setUp(self) -> None:
        _register_domain_refusals()

    def test_save_and_load_round_trip(self) -> None:
        chain = []
        for i in range(3):
            claim = _make_claim({"i": i})
            m = MeasurementResult(observations={"i": i}, passed=True)
            r = append_receipt(chain, claim, m, None, make_pass(), TIMESTAMP)
            chain.append(r)

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode='w'
        ) as tf:
            path = tf.name

        try:
            save_chain(chain, path)
            loaded = load_chain(path)
            self.assertEqual(chain, loaded)
            # Verify the loaded chain is still valid
            self.assertTrue(verify_chain(loaded).ok)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 14. adjudicate() — end-to-end composition
# ---------------------------------------------------------------------------

class TestAdjudicate(unittest.TestCase):
    """End-to-end tests for gate_core.gate.adjudicate()."""

    ADJ_DOMAIN = "adj_test_domain"
    TIMESTAMP = "2026-11-01T23:00:00Z"

    def setUp(self) -> None:
        for name in ("violates_rule", "over_limit"):
            if not is_valid_refusal(self.ADJ_DOMAIN, name):
                register_refusal(self.ADJ_DOMAIN, name)

    def _claim(self, payload: dict | None = None) -> Claim:
        return Claim(
            domain=self.ADJ_DOMAIN,
            claim_type="adjudication_test",
            payload=payload or {"value": 42},
        )

    def _mandate(self, content: dict | None = None) -> SealedMandate:
        return seal_mandate(self.ADJ_DOMAIN, content or {"limit": 100})

    # -- helpers: simple measurer factories ---------------------------------

    @staticmethod
    def _passing_measurer():
        """Returns a measurer that always passes."""
        class _Measurer:
            def measure(self, claim, mandate):
                return MeasurementResult(
                    observations={"checked": True},
                    passed=True,
                )
        return _Measurer()

    @staticmethod
    def _refusing_measurer(refusal_name: str):
        """Returns a measurer that always refuses with *refusal_name*."""
        class _Measurer:
            def measure(self, claim, mandate):
                return MeasurementResult(
                    observations={"checked": True, "refusal_name": refusal_name},
                    passed=False,
                )
        return _Measurer()

    @staticmethod
    def _crashing_measurer(msg: str = "boom"):
        """Returns a measurer that always raises RuntimeError."""
        class _Measurer:
            def measure(self, claim, mandate):
                raise RuntimeError(msg)
        return _Measurer()

    # -- tests --------------------------------------------------------------

    def test_pass_returns_pass_verdict(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        verdict, receipt = adjudicate(
            self._claim(), self._mandate(),
            self._passing_measurer(), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertIsInstance(verdict, Pass)

    def test_pass_appends_receipt_to_chain(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        verdict, receipt = adjudicate(
            self._claim(), self._mandate(),
            self._passing_measurer(), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertEqual(len(chain), 1)
        self.assertIs(chain[0], receipt)

    def test_pass_receipt_is_chained_correctly(self) -> None:
        """Second adjudication links to first receipt's hash."""
        from gate_core import adjudicate
        chain: list = []
        _, first = adjudicate(
            self._claim({"n": 1}), self._mandate(),
            self._passing_measurer(), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        _, second = adjudicate(
            self._claim({"n": 2}), self._mandate(),
            self._passing_measurer(), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertEqual(second.previous_hash, first.own_hash)
        self.assertTrue(verify_chain(chain).ok)

    def test_pass_receipt_verdict_is_pass(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        _, receipt = adjudicate(
            self._claim(), self._mandate(),
            self._passing_measurer(), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertEqual(receipt.verdict, {"type": "pass"})

    def test_refusal_returns_refused_verdict(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        verdict, _ = adjudicate(
            self._claim(), self._mandate(),
            self._refusing_measurer("violates_rule"), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "violates_rule")

    def test_refusal_receipt_carries_domain_refusal_name(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        _, receipt = adjudicate(
            self._claim(), self._mandate(),
            self._refusing_measurer("over_limit"), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertEqual(receipt.verdict, {"type": "refused", "name": "over_limit"})

    def test_refusal_appends_receipt_to_chain(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        adjudicate(
            self._claim(), self._mandate(),
            self._refusing_measurer("violates_rule"), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertEqual(len(chain), 1)

    def test_crashing_measurer_produces_unmeasured_refused(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        verdict, _ = adjudicate(
            self._claim(), self._mandate(),
            self._crashing_measurer("exploded"), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "unmeasured")

    def test_crashing_measurer_still_appends_receipt(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        adjudicate(
            self._claim(), self._mandate(),
            self._crashing_measurer(), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertEqual(len(chain), 1)

    def test_crashing_measurer_records_error_in_receipt(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        _, receipt = adjudicate(
            self._claim(), self._mandate(),
            self._crashing_measurer("exploded"), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertIsNone(receipt.measurements)
        self.assertIn("exploded", receipt.measurement_error)

    def test_crashing_measurer_receipt_is_valid_in_chain(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        adjudicate(
            self._claim(), self._mandate(),
            self._crashing_measurer(), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertTrue(verify_chain(chain).ok)

    def test_tampered_mandate_raises_mandate_tamper_error(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        mandate = self._mandate()
        tampered = SealedMandate(
            domain=mandate.domain,
            content={"limit": 9999},  # content changed
            seal=mandate.seal,        # seal NOT updated
        )
        with self.assertRaises(MandateTamperError):
            adjudicate(
                self._claim(), tampered,
                self._passing_measurer(), chain,
                timestamp_utc=self.TIMESTAMP,
            )

    def test_tampered_mandate_appends_nothing_to_chain(self) -> None:
        from gate_core import adjudicate
        chain: list = []
        mandate = self._mandate()
        tampered = SealedMandate(
            domain=mandate.domain,
            content={"limit": 9999},
            seal=mandate.seal,
        )
        try:
            adjudicate(
                self._claim(), tampered,
                self._passing_measurer(), chain,
                timestamp_utc=self.TIMESTAMP,
            )
        except MandateTamperError:
            pass
        self.assertEqual(len(chain), 0)

    def test_unknown_refusal_name_falls_back_to_unmeasured(self) -> None:
        """A measurer returning an unregistered refusal name falls back gracefully."""
        from gate_core import adjudicate

        class _BadMeasurer:
            def measure(self, claim, mandate):
                return MeasurementResult(
                    observations={"refusal_name": "not_registered_ever"},
                    passed=False,
                )

        chain: list = []
        verdict, _ = adjudicate(
            self._claim(), self._mandate(),
            _BadMeasurer(), chain,
            timestamp_utc=self.TIMESTAMP,
        )
        self.assertIsInstance(verdict, Refused)
        self.assertEqual(verdict.name, "unmeasured")


if __name__ == '__main__':
    unittest.main()
