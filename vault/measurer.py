"""
vault.measurer
~~~~~~~~~~~~~~
VaultMeasurer — implements gate_core.MeasurementProtocol for bundle_release.

Order:
  1. Lock record self-check.  A lock that does not recompute (seal or
     certificate) raises MandateTamperError — a hard error, never a refusal.
  2. Census comparison against the lock record.  The first difference wins,
     by precedence file_changed > file_missing > file_added, then by path
     in canonical order.
  3. Otherwise the bundle passes.

The measurer observes and reports; the gate decides.
"""

from __future__ import annotations

from gate_core import Claim, MandateTamperError, MeasurementResult, SealedMandate

from vault.lock import lock_recomputes


class VaultMeasurer:
    """Measures a bundle_release claim against a bundle lock record."""

    def measure(self, claim: Claim, mandate: SealedMandate) -> MeasurementResult:
        # ── 1. Lock record self-check ─────────────────────────────────────
        if not lock_recomputes(mandate):
            raise MandateTamperError(
                "Lock record does not recompute to its own seal/certificate. "
                "The lock record has been altered."
            )

        locked: dict[str, str] = mandate.content["files"]
        certificate: str = mandate.content["certificate"]
        bundle_id: str = mandate.content["bundle_id"]

        presented: dict[str, str] = claim.payload["files"]
        if claim.payload["bundle_id"] != bundle_id:
            raise ValueError(
                f"Claim is for bundle '{claim.payload['bundle_id']}', "
                f"lock record is for '{bundle_id}'."
            )

        changed = sorted(p for p in locked if p in presented and presented[p] != locked[p])
        missing = sorted(p for p in locked if p not in presented)
        added = sorted(p for p in presented if p not in locked)

        base = {
            "bundle_id": bundle_id,
            "certificate": certificate,
            "changed": changed,
            "missing": missing,
            "added": added,
        }

        # ── 2. First difference ───────────────────────────────────────────
        if changed:
            path = changed[0]
            return MeasurementResult(
                observations={**base, "refusal_name": "file_changed", "path": path,
                              "expected_sha256": locked[path], "found_sha256": presented[path]},
                passed=False,
            )
        if missing:
            path = missing[0]
            return MeasurementResult(
                observations={**base, "refusal_name": "file_missing", "path": path,
                              "expected_sha256": locked[path]},
                passed=False,
            )
        if added:
            path = added[0]
            return MeasurementResult(
                observations={**base, "refusal_name": "file_added", "path": path,
                              "found_sha256": presented[path]},
                passed=False,
            )

        # ── 3. Untouched ──────────────────────────────────────────────────
        return MeasurementResult(
            observations={
                "bundle_id": bundle_id,
                "certificate": certificate,
                "file_count": len(locked),
                "files_verified": sorted(locked),
            },
            passed=True,
        )
