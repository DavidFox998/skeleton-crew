# Tasks — Executor Desk

## Implementation

- [x] 1. **Registry** — implement `executor/registry.py`
  - Define `ExecutorRegistry.__init__(will_paths, death_record_paths)`: read each JSON file, call `gate_core.seal_mandate(domain="executor", content=data)`, store results.
  - Group sealed wills by `content["testator"]`, sorted by `content["sealed_date"]` ascending.
  - Store sealed death records by `content["deceased"]`.
  - Implement `latest_will(testator) -> SealedMandate | None`.
  - Implement `all_wills(testator) -> list[SealedMandate]`.
  - Implement `will_by_seal(seal) -> SealedMandate | None`.
  - Implement `death_record(name) -> SealedMandate | None`.

- [x] 2. **Measurer** — implement `executor/measurer.py`
  - Define module-level `ZODIAC_MSB_TO_LSB` constant (12-sign list, MSB=Pisces to LSB=Aries); verify against both fixture files before finalising.
  - Implement `ExecutorMeasurer.__init__(registry)`.
  - Implement `ExecutorMeasurer.measure(claim, mandate) -> MeasurementResult` with the full precedence chain:
    1. Death record check → `death_unverified`
    2. Will seal check → `seal_broken`
    3. Supersession check → `will_superseded` (include `governing_seal` in observations)
    4. `stated_popcount` vs actual popcount → `share_mismatch`
    5. Distribution count vs actual popcount → `share_mismatch`
    6. Per-distribution: sign occupied → `sign_unoccupied`; duplicate sign → `share_mismatch`; item mismatch → `share_mismatch`; beneficiary mismatch → `beneficiary_unknown`
    7. All pass → `passed=True` with full observations

- [x] 3. **Claims helper** — implement `executor/claims.py`
  - Implement `make_distribution_claim(will_ref, distributions) -> gate_core.Claim`.
  - `domain="executor"`, `claim_type="estate_distribution"`.

- [x] 4. **Scenarios and runner** — implement `executor/scenarios.py`
  - Define `ScenarioResult` dataclass: `label`, `description`, `verdict`, `receipt`, `chain`.
  - Define the seven scenario data dicts (A–G) with `will_selector`, `distributions`, `registry_variant`, `description`.
  - Implement `run_scenarios(registry) -> list[ScenarioResult]`:
    - Resolve `will_selector` to the correct `SealedMandate`.
    - Construct claim via `make_distribution_claim`.
    - Construct a fresh `ExecutorMeasurer(registry)` per scenario.
    - Start a new empty `chain: list[Receipt]` per scenario.
    - Call `gate_core.adjudicate(claim, mandate, measurer, chain)`.
    - For Scenario G: catch `MandateTamperError` and record it in the result.

- [x] 5. **Package init** — implement `executor/__init__.py`
  - Call `gate_core.verdict.register_refusal("executor", name)` for all six executor refusal names at import time.
  - Re-export: `ExecutorRegistry`, `ExecutorMeasurer`, `make_distribution_claim`, `run_scenarios`, `ScenarioResult`.

---

## Tests

- [x] 6. **Scenario A test** — correct 7-bequest 2024 distribution → verdict is `Pass`; chain length is 1; `verify_chain` returns `ok=True`; observations contain all 7 signs.

- [x] 7. **Scenario B test** — 2019 distribution → verdict is `Refused(name='will_superseded')`; observations include `governing_seal` matching the 2024 will's seal.

- [x] 8. **Scenario C test** — 8-entry distribution → verdict is `Refused(name='share_mismatch')`; observations include `reason='distribution_count_mismatch'`.

- [x] 9. **Scenario D test** — Scorpio with wrong beneficiary → verdict is `Refused(name='beneficiary_unknown')`; observations include `sign='Scorpio'`.

- [x] 10. **Scenario E test** — distribution including Gemini → verdict is `Refused(name='sign_unoccupied')`; observations include `sign='Gemini'`.

- [x] 11. **Scenario F test** — no death record in registry → verdict is `Refused(name='death_unverified')`; observations include `death_record_present=False`.

- [x] 12. **Scenario G test** — tampered mandate passed to `adjudicate()` → `MandateTamperError` raised; chain length remains 0. Separate sub-case: tampered mandate passed directly to `measure()` → `MeasurementResult(passed=False)` with `refusal_name='seal_broken'`.

- [x] 13. **Popcount mismatch test** — construct a will `SealedMandate` whose `stated_popcount` does not equal the count of `1` bits in `vector`; measure against it → `Refused(name='share_mismatch')` with `reason='stated_popcount_mismatch'`.

- [x] 14. **Duplicate sign test** — distribution where the same sign appears twice (and total count still equals popcount by reducing another sign) → `Refused(name='share_mismatch')` with `reason='duplicate_sign'`.

---

## Documentation

- [x] 15. **Package README** — write `executor/README.md`:
  - One-paragraph description of the executor desk and its relationship to gate_core.
  - How to initialise the registry with fixture paths.
  - How to run the demo scenarios (`run_scenarios`).
  - How to verify the receipt chain (`gate_core.verify_chain`).
  - Refusal vocabulary table (copy from requirements).
  - Note on the two Elias Vane wills and the supersession rule.
