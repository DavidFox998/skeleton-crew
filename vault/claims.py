"""
vault.claims
~~~~~~~~~~~~
Factory for bundle_release Claims.
"""

from __future__ import annotations

from gate_core import Claim

from vault.lock import census


def make_release_claim(bundle_id: str, files: dict[str, str]) -> Claim:
    """Build a bundle_release claim from a presented bundle manifest.

    Args:
        bundle_id: Identifier of the bundle asking to leave the house.
        files:     Presented manifest {relative path: sha256}.
    """
    return Claim(
        domain="vault",
        claim_type="bundle_release",
        payload={"bundle_id": bundle_id, "files": dict(files)},
    )


def present_bundle(bundle_id: str, root: str) -> Claim:
    """Take the census of *root* and build the bundle_release claim for it."""
    return make_release_claim(bundle_id, census(root))
