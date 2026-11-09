"""
vault.scenarios
~~~~~~~~~~~~~~~
The six demo scenarios B1–B6 as a runner.

Each scenario builds its own bundle directory (copies of the house papers) in
a temporary directory and adjudicates against its own fresh receipt chain.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass

from gate_core import (
    MandateTamperError,
    Receipt,
    SealedMandate,
    Verdict,
    adjudicate,
)

from vault.claims import present_bundle
from vault.lock import lock_bundle
from vault.measurer import VaultMeasurer

BUNDLE_ID = "vane-estate-file"

#: The papers of the estate file: (name in bundle, fixture file name).
PAPERS: list[tuple[str, str]] = [
    ("will_2024.json", "will_2024.json"),
    ("death_record.json", "death_record.json"),
    ("family_record.json", "family_record.json"),
    ("inventory.json", "inventory.json"),
]

DEFAULT_FIXTURES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures"
)


@dataclass
class ScenarioResult:
    """Outcome of one scenario (same shape as executor.ScenarioResult).

    ``tamper_error`` is set, and verdict/receipt are None, on a hard tamper.
    ``certificate`` is the original lock certificate for the bundle.
    """

    label: str
    description: str
    verdict: Verdict | None
    receipt: Receipt | None
    chain: list[Receipt]
    certificate: str = ""
    tamper_error: MandateTamperError | None = None


def build_bundle(root: str, fixtures_dir: str = DEFAULT_FIXTURES) -> None:
    """Copy the house papers into *root*."""
    os.makedirs(root, exist_ok=True)
    for name, fixture in PAPERS:
        shutil.copyfile(os.path.join(fixtures_dir, fixture), os.path.join(root, name))


def _adjudicate(label: str, description: str, root: str,
                lock: SealedMandate) -> ScenarioResult:
    chain: list[Receipt] = []
    claim = present_bundle(BUNDLE_ID, root)
    cert = lock.content.get("certificate", "")
    try:
        verdict, receipt = adjudicate(claim, lock, VaultMeasurer(), chain)
    except MandateTamperError as exc:
        return ScenarioResult(label, description, None, None, chain, cert, exc)
    return ScenarioResult(label, description, verdict, receipt, chain, cert)


def run_scenarios(fixtures_dir: str = DEFAULT_FIXTURES) -> list[ScenarioResult]:
    """Run B1–B6 and return their results in order."""
    results: list[ScenarioResult] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "bundle")
        build_bundle(root, fixtures_dir)
        lock = lock_bundle(BUNDLE_ID, root)

        results.append(_adjudicate(
            "B1", "Untouched bundle → PASS (lock holds, receipt issued)", root, lock))

        inv = os.path.join(root, "inventory.json")
        with open(inv, "rb") as fh:
            original_inv = fh.read()
        with open(inv, "wb") as fh:
            fh.write(original_inv.replace(b'"appraised_value":520', b'"appraised_value":5200'))
        results.append(_adjudicate(
            "B2", "One paper altered (an inventory figure) → REFUSED(file_changed)", root, lock))
        with open(inv, "wb") as fh:
            fh.write(original_inv)

        stray = os.path.join(root, "stray_note.txt")
        with open(stray, "w", encoding="utf-8") as fh:
            fh.write("a paper nobody sealed")
        results.append(_adjudicate(
            "B3", "A stray paper added → REFUSED(file_added)", root, lock))
        os.remove(stray)

        death = os.path.join(root, "death_record.json")
        with open(death, "rb") as fh:
            original_death = fh.read()
        os.remove(death)
        results.append(_adjudicate(
            "B4", "A paper removed (the death record) → REFUSED(file_missing)", root, lock))

        with open(death, "wb") as fh:
            fh.write(original_death)
        results.append(_adjudicate(
            "B5", "Bundle restored → PASS under the original certificate", root, lock))

        forged_files = {**lock.content["files"], "inventory.json": "0" * 64}
        forged = SealedMandate(
            domain=lock.domain,
            content={**lock.content, "files": forged_files},
            seal=lock.seal,  # original seal — no longer matches content
        )
        results.append(_adjudicate(
            "B6", "Lock record itself altered → hard tamper, nothing appended", root, forged))
    return results
