# Requirements — The Vault Desk

## Overview

The Vault is the third desk of Skeleton Crew, specified by `docs/BUNDLE-DESK-PLAN.md` (name ratified 2026-11-07). At intake the house seals a client's whole estate file — will, death record, family record, inventory — as **one bundle** under a single chain certificate. When anyone asks for the file to leave the house, the desk re-measures the presented bundle against its lock record. A changed, added, or missing paper is refused by name.

It is built on `gate_core` (unmodified), reusing `adjudicate()`, `seal_mandate()`, `verify_mandate()`, `register_refusal()` and `verify_chain()`. Python standard library only; nothing is imported from any external project.

**Disclosure.** The bundle-certificate method is the author's own prior work (Appendix G chain certificate; a production version shipped in the ZeroBeacon trust harness on 2026-11-05). All code in this repository is written fresh; no ZeroBeacon code or API is imported.

## Domain Model

### The Lock Record (the mandate)

A `gate_core.SealedMandate`, domain `"vault"`, with content:

| Field | Meaning |
|---|---|
| `kind` | `"bundle_lock"` |
| `bundle_id` | Identifier of the sealed bundle |
| `files` | Table `{relative posix path: SHA-256 hex of file bytes}` in canonical (sorted) order |
| `certificate` | SHA-256 of the canonical JSON of `files` — the one bundle certificate |

Canonical JSON is `json.dumps(sort_keys=True, separators=(',', ':'))`. The mandate seal covers the whole content, certificate included.

### The Claim

`domain="vault"`, `claim_type="bundle_release"`, payload `{"bundle_id": str, "files": {path: sha256}}` — the presented bundle manifest (the census of the papers actually present).

### Refusal Vocabulary (domain `vault`)

`file_changed`, `file_missing`, `file_added`. Core `unmeasured` applies when the measurer cannot run (e.g. malformed claim, claim for a different bundle).

## Requirements

### R1 — Locking
1. `lock_bundle(bundle_id, root)` seals every file under `root` (recursive) as one lock record with per-file SHA-256 and one certificate.
2. Locking is deterministic: same bytes → same certificate and seal.
3. An empty bundle or blank `bundle_id` is rejected with `ValueError`.

### R2 — Lock record self-check (first, always)
1. The measurer first verifies the lock record: the mandate seal AND the certificate must recompute.
2. If either fails the measurer raises `MandateTamperError` — a hard tamper, never a refusal. `adjudicate()` propagates it; **nothing is appended to the chain**.
3. This check precedes any census comparison, so a tampered lock never yields a refusal verdict even when the bundle is also wrong.

### R3 — Census comparison
1. Compare the presented manifest to the lock table and name the first difference. Precedence: `file_changed` (path present in both with different hash), then `file_missing` (locked, not present), then `file_added` (present, not locked). Within a category, the first path in canonical order.
2. Observations name the path and carry `expected_sha256`/`found_sha256` where applicable, the full `changed`/`missing`/`added` lists, the `bundle_id`, and the `certificate`.
3. If there is no difference the measurement passes, observations carrying `certificate`, `file_count`, `files_verified`.

### R4 — Verdict and receipt
1. PASS issues a hash-chained receipt; the bundle may leave. Every refusal also produces a chained receipt.
2. A restored bundle passes again under the **original** certificate; refusals never alter the lock record.

### R5 — Scenarios B1–B6 (from the plan)
| # | Situation | Outcome |
|---|---|---|
| B1 | Untouched bundle | PASS, receipt issued |
| B2 | One paper's contents altered (an inventory figure) | REFUSED `file_changed`, naming it |
| B3 | A stray paper added | REFUSED `file_added`, naming it |
| B4 | A paper removed (the death record) | REFUSED `file_missing`, naming it |
| B5 | Bundle restored | PASS with the original certificate |
| B6 | Lock record itself altered | hard tamper (`MandateTamperError`), chain length 0 |

Each scenario uses its own fresh receipt chain, as in the Executor desk.

### R6 — Boundaries
1. `gate_core` is not modified. `vault` imports only the standard library and `gate_core`.
2. Interfaces display verdicts and never decide them; all decisional logic is in the measurer and gate.
3. No web skin in this phase (a separate, later task). The film/story documents are untouched.
