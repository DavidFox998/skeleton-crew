"""
vault.lock
~~~~~~~~~~
Seals a directory of papers as one bundle under a single chain certificate.

The lock record is a gate_core.SealedMandate (domain "vault") whose content is:

    {
      "kind":        "bundle_lock",
      "bundle_id":   <str>,
      "files":       {<relative posix path>: <sha256 hex of file bytes>, ...},
      "certificate": <sha256 hex of the canonical JSON of "files">
    }

The mandate seal covers the whole content (including the certificate); the
certificate covers the path:hash table.  A lock record is intact only when
BOTH recompute.
"""

from __future__ import annotations

import hashlib
import json
import os

from gate_core import SealedMandate, seal_mandate, verify_mandate

DOMAIN = "vault"
LOCK_KIND = "bundle_lock"


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: str) -> str:
    """Return the hex SHA-256 of the raw bytes of the file at *path*."""
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def census(root: str) -> dict[str, str]:
    """Return {relative posix path: sha256} for every file under *root*.

    Keys are in canonical (sorted) order.  This only observes; it decides nothing.
    """
    table: dict[str, str] = {}
    for dirpath, _dirs, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, '/')
            table[rel] = hash_file(full)
    return dict(sorted(table.items()))


def bundle_certificate(files: dict[str, str]) -> str:
    """Return the chain certificate: SHA-256 of the canonical path:hash table."""
    return _sha256_hex(_canonical_json(files).encode('utf-8'))


def lock_bundle(bundle_id: str, root: str) -> SealedMandate:
    """Seal every file under *root* as one bundle and return the lock record."""
    if not bundle_id or not bundle_id.strip():
        raise ValueError("bundle_id must be a non-empty string.")
    files = census(root)
    if not files:
        raise ValueError("Cannot lock an empty bundle.")
    content = {
        "kind": LOCK_KIND,
        "bundle_id": bundle_id,
        "files": files,
        "certificate": bundle_certificate(files),
    }
    return seal_mandate(DOMAIN, content)


def lock_recomputes(lock: SealedMandate) -> bool:
    """Return True iff the lock record's seal AND certificate both recompute."""
    if not verify_mandate(lock):
        return False
    try:
        return lock.content["certificate"] == bundle_certificate(lock.content["files"])
    except (KeyError, TypeError):
        return False
