# Tasks — The Vault Desk

## Implementation

- [x] 1. **Spec** — `requirements.md`, `design.md`, `tasks.md` in `.kiro/specs/vault/`.
- [x] 2. **Fixture** — add `fixtures/inventory.json` (fourth paper of the estate file).
- [x] 3. **Lock** — implement `vault/lock.py`: `hash_file`, `census`, `bundle_certificate`, `lock_bundle`, `lock_recomputes`.
- [x] 4. **Claims helper** — implement `vault/claims.py`: `make_release_claim`, `present_bundle` (`domain="vault"`, `claim_type="bundle_release"`).
- [x] 5. **Measurer** — implement `vault/measurer.py`: lock self-check (hard `MandateTamperError`), then `file_changed` → `file_missing` → `file_added`, else pass.
- [x] 6. **Scenarios and runner** — implement `vault/scenarios.py`: `ScenarioResult`, `build_bundle`, `run_scenarios` for B1–B6 with a fresh chain each.
- [x] 7. **Package init** — register `file_changed`, `file_missing`, `file_added` for domain `vault`; re-export public API; `vault/README.md`.

## Tests (`tests/test_vault.py`)

- [x] 8. **Lock tests** — certificate is hash of table; deterministic; empty bundle / blank id rejected.
- [x] 9. **B1** — untouched → `Pass`; chain length 1; `verify_chain` ok; certificate in observations.
- [x] 10. **B2** — altered inventory figure → `Refused(file_changed)` naming `inventory.json`.
- [x] 11. **B3** — stray paper → `Refused(file_added)` naming it.
- [x] 12. **B4** — death record removed → `Refused(file_missing)` naming it.
- [x] 13. **B5** — restored → `Pass` under the original certificate; lock unchanged by refusals.
- [x] 14. **B6** — altered lock → `MandateTamperError`, chain length 0; certificate-only tamper also hard.
- [x] 15. **Extras** — precedence, wrong bundle / malformed claim → `unmeasured`, chain integrity, `run_scenarios`, import boundary.

## Verification

- [x] 16. Full suite `python -m unittest discover -s tests` green; existing tests untouched.

## Out of scope

- Web skin for the Vault (separate, later task). Film/story documents under `docs/`.
