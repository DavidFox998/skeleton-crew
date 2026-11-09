"""
vault
~~~~~
The Vault desk — seals a client's whole estate file as one bundle under a
single chain certificate and re-measures it before it may leave the house.

Built on top of gate_core (unmodified).  Registers the vault refusal
vocabulary at import time.

Disclosure: the bundle-certificate METHOD is the author's own prior work
(Appendix G chain certificate); every line here is written fresh in this
repository and imports nothing from any external project.
"""

from gate_core import register_refusal

_VAULT_REFUSALS = [
    "file_changed",
    "file_missing",
    "file_added",
]

for _name in _VAULT_REFUSALS:
    register_refusal("vault", _name)

from vault.lock import (
    bundle_certificate,
    census,
    hash_file,
    lock_bundle,
    lock_recomputes,
)
from vault.claims import make_release_claim, present_bundle
from vault.measurer import VaultMeasurer
from vault.scenarios import ScenarioResult, build_bundle, run_scenarios

__all__ = [
    "bundle_certificate",
    "census",
    "hash_file",
    "lock_bundle",
    "lock_recomputes",
    "make_release_claim",
    "present_bundle",
    "VaultMeasurer",
    "ScenarioResult",
    "build_bundle",
    "run_scenarios",
]
