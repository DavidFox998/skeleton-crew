# Technical Design — The Vault Desk

## Constraints

- Python 3.11+, standard library only; depends on `gate_core` only (not `executor`, `citation_gate`, `webui`).
- `gate_core` is unmodified and imports nothing from `vault`.
- Seals are SHA-256 over canonical JSON (product steering, hard rule 4).
- No UI, no network. File I/O is limited to reading bundle files (`census`, `hash_file`) and the scenario runner's temp directories.

## Package Layout

```
vault/
    __init__.py    — registers vault refusal vocabulary; re-exports public API
    lock.py        — hash_file, census, bundle_certificate, lock_bundle, lock_recomputes
    claims.py      — make_release_claim, present_bundle (census → bundle_release Claim)
    measurer.py    — VaultMeasurer implementing gate_core MeasurementProtocol
    scenarios.py   — B1–B6 runner, ScenarioResult
    README.md
fixtures/inventory.json   — the fourth paper of the Vane estate file
tests/test_vault.py
```

## Data Flow

```
lock_bundle(id, root) ──► SealedMandate(domain="vault", content{kind,bundle_id,files,certificate})
present_bundle(id, root) ─► Claim(vault, bundle_release, {bundle_id, files})
adjudicate(claim, lock, VaultMeasurer(), chain)
   1. verify_mandate(lock)            → MandateTamperError (gate)
   2. VaultMeasurer.measure:
        lock_recomputes(lock)?        → MandateTamperError (hard; nothing appended)
        bundle_id match?              → else ValueError → unmeasured
        compare tables                → refusal_name observation or pass
   3. verdict + chained receipt
```

## Measurer Precedence

1. Lock record: seal and certificate recompute (else hard tamper).
2. `file_changed` → `file_missing` → `file_added`; first path in sorted order per category.
3. Pass.

The measurer only reports `refusal_name` in observations; `adjudicate()` maps it to a verdict via the registered vocabulary.

## Design Decisions

- **Two-layer lock check.** The mandate seal catches content altered after sealing. The certificate check additionally catches a table edited and re-sealed without recomputing the certificate; the measurer therefore verifies both itself rather than relying only on the gate.
- **Census by directory walk.** `file_added` requires discovering unsealed papers, so the census walks the bundle root rather than a caller-supplied list. Paths are relative and posix-style so certificates are portable.
- **Hash of bytes.** Files are hashed as raw bytes, so any change at all is detected.
- **Scenarios copy fixtures to a temp dir** (will_2024, death_record, family_record, inventory) so the house's own fixtures are never mutated; the bundle overlaps the other desks' sources on purpose.

## Testing Strategy

`tests/test_vault.py` mirrors `tests/test_executor.py`: a base class, one class per scenario B1–B6, extras (certificate-only tamper, precedence, wrong bundle → unmeasured, malformed claim → unmeasured, chain integrity), a `run_scenarios` shape test, and an import-boundary test.
