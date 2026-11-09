"""
tests.test_vault
~~~~~~~~~~~~~~~~
Unittest suite for the Vault desk.

Test inventory:
  B1 — untouched bundle → Pass; lock holds; receipt issued
  B2 — one paper altered → Refused(file_changed), naming it
  B3 — stray paper added → Refused(file_added), naming it
  B4 — paper removed → Refused(file_missing), naming it
  B5 — restored → Pass under the original certificate
  B6 — lock record altered → MandateTamperError, chain length zero
  Extras — certificate-only tamper, precedence, wrong bundle (unmeasured),
           malformed claim (unmeasured), lock determinism, runner shape,
           chain integrity across a mixed history.
"""

import os
import shutil
import tempfile
import unittest

import vault  # triggers refusal vocabulary registration
from vault import (
    ScenarioResult,
    VaultMeasurer,
    build_bundle,
    bundle_certificate,
    census,
    lock_bundle,
    lock_recomputes,
    make_release_claim,
    present_bundle,
    run_scenarios,
)
from vault.scenarios import BUNDLE_ID

from gate_core import (
    MandateTamperError,
    Pass,
    Refused,
    SealedMandate,
    adjudicate,
    seal_mandate,
    verify_chain,
)


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def _write(path, data):
    with open(path, "wb") as fh:
        fh.write(data)


class VaultTestBase(unittest.TestCase):
    """Builds a fresh bundle directory and lock record per test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.join(self._tmp.name, "bundle")
        build_bundle(self.root)
        self.lock = lock_bundle(BUNDLE_ID, self.root)
        self.chain = []

    def release(self, lock=None):
        claim = present_bundle(BUNDLE_ID, self.root)
        return adjudicate(claim, lock or self.lock, VaultMeasurer(), self.chain)

    def measure(self):
        return VaultMeasurer().measure(present_bundle(BUNDLE_ID, self.root), self.lock)


class TestLock(VaultTestBase):
    def test_lock_covers_four_papers(self):
        self.assertEqual(
            sorted(self.lock.content["files"]),
            ["death_record.json", "family_record.json", "inventory.json", "will_2024.json"],
        )

    def test_certificate_is_hash_of_table(self):
        self.assertEqual(self.lock.content["certificate"],
                         bundle_certificate(self.lock.content["files"]))

    def test_lock_recomputes(self):
        self.assertTrue(lock_recomputes(self.lock))

    def test_lock_is_deterministic(self):
        again = lock_bundle(BUNDLE_ID, self.root)
        self.assertEqual(again.seal, self.lock.seal)
        self.assertEqual(again.content["certificate"], self.lock.content["certificate"])

    def test_lock_domain_is_vault(self):
        self.assertEqual(self.lock.domain, "vault")

    def test_empty_bundle_cannot_be_locked(self):
        empty = os.path.join(self._tmp.name, "empty")
        os.makedirs(empty)
        with self.assertRaises(ValueError):
            lock_bundle(BUNDLE_ID, empty)

    def test_blank_bundle_id_rejected(self):
        with self.assertRaises(ValueError):
            lock_bundle("  ", self.root)

    def test_census_matches_lock_when_untouched(self):
        self.assertEqual(census(self.root), self.lock.content["files"])


class TestScenarioB1(VaultTestBase):
    def setUp(self):
        super().setUp()
        self.verdict, self.receipt = self.release()

    def test_verdict_is_pass(self):
        self.assertIsInstance(self.verdict, Pass)

    def test_chain_length_is_one(self):
        self.assertEqual(len(self.chain), 1)

    def test_verify_chain_ok(self):
        self.assertTrue(verify_chain(self.chain).ok)

    def test_observations_carry_certificate_and_files(self):
        obs = self.receipt.measurements
        self.assertEqual(obs["certificate"], self.lock.content["certificate"])
        self.assertEqual(obs["file_count"], 4)
        self.assertEqual(obs["files_verified"], sorted(self.lock.content["files"]))


class TestScenarioB2(VaultTestBase):
    def setUp(self):
        super().setUp()
        path = os.path.join(self.root, "inventory.json")
        _write(path, _read(path).replace(b'"appraised_value":520', b'"appraised_value":5200'))
        self.verdict, self.receipt = self.release()

    def test_verdict_is_file_changed(self):
        self.assertEqual(self.verdict, Refused(name="file_changed"))

    def test_names_the_paper(self):
        obs = self.receipt.measurements
        self.assertEqual(obs["path"], "inventory.json")
        self.assertEqual(obs["changed"], ["inventory.json"])
        self.assertEqual(obs["expected_sha256"], self.lock.content["files"]["inventory.json"])
        self.assertNotEqual(obs["found_sha256"], obs["expected_sha256"])

    def test_receipt_chained(self):
        self.assertEqual(len(self.chain), 1)
        self.assertTrue(verify_chain(self.chain).ok)


class TestScenarioB3(VaultTestBase):
    def setUp(self):
        super().setUp()
        _write(os.path.join(self.root, "stray_note.txt"), b"unsealed")
        self.verdict, self.receipt = self.release()

    def test_verdict_is_file_added(self):
        self.assertEqual(self.verdict, Refused(name="file_added"))

    def test_names_the_paper(self):
        self.assertEqual(self.receipt.measurements["path"], "stray_note.txt")
        self.assertEqual(self.receipt.measurements["added"], ["stray_note.txt"])

    def test_added_in_subdirectory_is_seen(self):
        os.remove(os.path.join(self.root, "stray_note.txt"))
        os.makedirs(os.path.join(self.root, "sub"))
        _write(os.path.join(self.root, "sub", "x.txt"), b"x")
        verdict, receipt = self.release()
        self.assertEqual(verdict, Refused(name="file_added"))
        self.assertEqual(receipt.measurements["path"], "sub/x.txt")


class TestScenarioB4(VaultTestBase):
    def setUp(self):
        super().setUp()
        os.remove(os.path.join(self.root, "death_record.json"))
        self.verdict, self.receipt = self.release()

    def test_verdict_is_file_missing(self):
        self.assertEqual(self.verdict, Refused(name="file_missing"))

    def test_names_the_paper(self):
        self.assertEqual(self.receipt.measurements["path"], "death_record.json")
        self.assertEqual(self.receipt.measurements["missing"], ["death_record.json"])


class TestScenarioB5(VaultTestBase):
    def test_restored_bundle_passes_under_original_certificate(self):
        death = os.path.join(self.root, "death_record.json")
        original = _read(death)
        os.remove(death)
        v1, _ = self.release()
        self.assertEqual(v1, Refused(name="file_missing"))
        _write(death, original)
        v2, r2 = self.release()
        self.assertIsInstance(v2, Pass)
        self.assertEqual(r2.measurements["certificate"], self.lock.content["certificate"])
        self.assertEqual(len(self.chain), 2)
        self.assertTrue(verify_chain(self.chain).ok)

    def test_lock_unchanged_by_refusals(self):
        before = self.lock.seal
        os.remove(os.path.join(self.root, "inventory.json"))
        self.release()
        self.assertEqual(self.lock.seal, before)
        self.assertTrue(lock_recomputes(self.lock))


class TestScenarioB6(VaultTestBase):
    def setUp(self):
        super().setUp()
        files = {**self.lock.content["files"], "inventory.json": "0" * 64}
        self.forged = SealedMandate(
            domain=self.lock.domain,
            content={**self.lock.content, "files": files},
            seal=self.lock.seal,
        )

    def test_raises_mandate_tamper_error(self):
        with self.assertRaises(MandateTamperError):
            self.release(self.forged)

    def test_chain_length_zero(self):
        with self.assertRaises(MandateTamperError):
            self.release(self.forged)
        self.assertEqual(len(self.chain), 0)

    def test_measurer_itself_raises_tamper(self):
        with self.assertRaises(MandateTamperError):
            VaultMeasurer().measure(present_bundle(BUNDLE_ID, self.root), self.forged)

    def test_consistently_resealed_but_certificate_stale_is_tamper(self):
        # Table edited and re-sealed, but certificate not recomputed: the
        # measurer's own check must catch what the seal check cannot.
        files = {**self.lock.content["files"], "inventory.json": "0" * 64}
        resealed = seal_mandate("vault", {**self.lock.content, "files": files})
        self.assertFalse(lock_recomputes(resealed))
        with self.assertRaises(MandateTamperError):
            self.release(resealed)
        self.assertEqual(len(self.chain), 0)

    def test_tamper_is_not_a_refusal_even_for_a_bad_bundle(self):
        os.remove(os.path.join(self.root, "death_record.json"))
        with self.assertRaises(MandateTamperError):
            self.release(self.forged)
        self.assertEqual(self.chain, [])


class TestPrecedenceAndEdges(VaultTestBase):
    def test_changed_beats_missing_and_added(self):
        _write(os.path.join(self.root, "will_2024.json"), b"{}")
        os.remove(os.path.join(self.root, "death_record.json"))
        _write(os.path.join(self.root, "stray.txt"), b"s")
        verdict, receipt = self.release()
        self.assertEqual(verdict, Refused(name="file_changed"))
        self.assertEqual(receipt.measurements["missing"], ["death_record.json"])
        self.assertEqual(receipt.measurements["added"], ["stray.txt"])

    def test_missing_beats_added(self):
        os.remove(os.path.join(self.root, "death_record.json"))
        _write(os.path.join(self.root, "stray.txt"), b"s")
        verdict, _ = self.release()
        self.assertEqual(verdict, Refused(name="file_missing"))

    def test_first_changed_in_path_order(self):
        _write(os.path.join(self.root, "will_2024.json"), b"{}")
        _write(os.path.join(self.root, "family_record.json"), b"{}")
        _, receipt = self.release()
        self.assertEqual(receipt.measurements["path"], "family_record.json")

    def test_wrong_bundle_id_is_unmeasured(self):
        claim = make_release_claim("some-other-bundle", census(self.root))
        verdict, receipt = adjudicate(claim, self.lock, VaultMeasurer(), self.chain)
        self.assertEqual(verdict, Refused(name="unmeasured"))
        self.assertIsNotNone(receipt.measurement_error)

    def test_malformed_claim_is_unmeasured(self):
        from gate_core import Claim
        claim = Claim(domain="vault", claim_type="bundle_release", payload={})
        verdict, _ = adjudicate(claim, self.lock, VaultMeasurer(), self.chain)
        self.assertEqual(verdict, Refused(name="unmeasured"))

    def test_claim_domain_and_type(self):
        claim = present_bundle(BUNDLE_ID, self.root)
        self.assertEqual((claim.domain, claim.claim_type), ("vault", "bundle_release"))

    def test_mixed_history_chain_verifies(self):
        self.release()
        os.remove(os.path.join(self.root, "inventory.json"))
        self.release()
        self.assertEqual(len(self.chain), 2)
        self.assertTrue(verify_chain(self.chain).ok)

    def test_tampering_a_receipt_is_detected(self):
        from dataclasses import replace
        self.release()
        self.release()
        self.chain[0] = replace(self.chain[0], verdict={"type": "refused", "name": "file_added"})
        self.assertFalse(verify_chain(self.chain).ok)


class TestRunScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = run_scenarios()
        cls.by = {r.label: r for r in cls.results}

    def test_six_results_in_order(self):
        self.assertEqual([r.label for r in self.results],
                         ["B1", "B2", "B3", "B4", "B5", "B6"])
        self.assertTrue(all(isinstance(r, ScenarioResult) for r in self.results))

    def test_expected_verdicts(self):
        expected = {
            "B1": Pass(),
            "B2": Refused("file_changed"),
            "B3": Refused("file_added"),
            "B4": Refused("file_missing"),
            "B5": Pass(),
            "B6": None,
        }
        for label, verdict in expected.items():
            self.assertEqual(self.by[label].verdict, verdict, label)

    def test_named_papers(self):
        self.assertEqual(self.by["B2"].receipt.measurements["path"], "inventory.json")
        self.assertEqual(self.by["B3"].receipt.measurements["path"], "stray_note.txt")
        self.assertEqual(self.by["B4"].receipt.measurements["path"], "death_record.json")

    def test_b5_original_certificate(self):
        b1, b5 = self.by["B1"], self.by["B5"]
        self.assertEqual(b5.receipt.measurements["certificate"],
                         b1.receipt.measurements["certificate"])
        self.assertEqual(b5.receipt.measurements["certificate"], b5.certificate)

    def test_b6_hard_tamper_chain_zero(self):
        b6 = self.by["B6"]
        self.assertIsInstance(b6.tamper_error, MandateTamperError)
        self.assertIsNone(b6.receipt)
        self.assertEqual(len(b6.chain), 0)

    def test_non_tamper_scenarios_have_one_verified_receipt(self):
        for label in ["B1", "B2", "B3", "B4", "B5"]:
            r = self.by[label]
            self.assertEqual(len(r.chain), 1, label)
            self.assertTrue(verify_chain(r.chain).ok, label)
            self.assertIsNone(r.tamper_error, label)


class TestBoundaries(unittest.TestCase):
    def test_vault_imports_only_stdlib_and_gate_core(self):
        import ast
        import sys
        pkg = os.path.dirname(vault.__file__)
        allowed = set(sys.stdlib_module_names) | {"gate_core", "vault", "__future__"}
        for name in os.listdir(pkg):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(pkg, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    mods = [node.module]
                for m in mods:
                    self.assertIn(m.split(".")[0], allowed, f"{name} imports {m}")


if __name__ == "__main__":
    unittest.main()
