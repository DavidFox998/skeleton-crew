# Tasks — Citation Gate Desk

## Implementation

- [x] 1. **Source Registry** — implement `citation_gate/sources.py`
  - Define `SourceRegistry.__init__(death_record_path, will_path, family_record_path)`: read each JSON file with `json.load`, call `gate_core.seal_mandate(domain="citation", content=data)` for each, store results keyed by source id.
  - Implement module-private `_extract_death_record_facts(data) -> dict[str, str]`: returns `{deceased, date_of_death, place, registrar}`.
  - Implement module-private `_extract_family_record_facts(data) -> dict[str, str]`: returns `{person, born, birthplace, occupation, residence}`.
  - Implement module-private `_extract_will_facts(data) -> dict[str, str]`: iterates `data["bequests"]`, emitting `bequest.<Sign>.item` and `bequest.<Sign>.beneficiary` per bequest entry. Empty signs (not present in `bequests`) produce no keys.
  - Cache all three fact tables in `_fact_tables` dict at construction time.
  - Implement `source(source_id) -> SealedMandate | None`.
  - Implement `fact_table(source_id) -> dict[str, str] | None`.
  - Implement `known_source_ids() -> frozenset[str]`.

- [x] 2. **Measurer** — implement `citation_gate/measurer.py`
  - Implement `CitationMeasurer.__init__(registry: SourceRegistry)`.
  - Implement `CitationMeasurer.measure(claim, mandate) -> MeasurementResult` with the full five-step precedence chain:
    1. Citation present? (`None` or empty string) → `missing_citation`
    2. Source known? (citation not in `registry.known_source_ids()`) → `unsupported_claim` with `reason='source_not_registered'`
    3. Source seal intact? (`gate_core.verify_mandate` on cited source's `SealedMandate`) → raise `MandateTamperError` if seal fails
    4. Fact key in table? (`fact_key not in registry.fact_table(citation)`) → `unsupported_claim` with `reason='fact_key_not_in_source'`
    5. Value matches? (`stored_value != asserted_value`) → `source_contradicts` with `asserted_value` and `stored_value` in observations
    6. All pass → `passed=True` with `source_id`, `fact_key`, `asserted_value`, `stored_value`, `source_seal` in observations
  - Include `refusal_name` in observations for every `passed=False` result.
  - Never return without `observations["refusal_name"]` when `passed=False`.

- [x] 3. **Claims helper** — implement `citation_gate/claims.py`
  - Implement `make_assertion_claim(text, fact_key, value, citation) -> gate_core.Claim`.
  - `domain="citation"`, `claim_type="factual_assertion"`.
  - `citation` accepts `str | None`; `None` encodes as JSON `null` in the payload.

- [x] 4. **Publish checker** — implement `citation_gate/publish.py`
  - Define `PublishDecision` frozen dataclass: `publishable: bool`, `receipt_ids: list[str] | None`, `refusal_name: str | None`.
  - Implement `check_publish(draft_id, assertion_claim_hashes, chain) -> PublishDecision`:
    - Return `publishable=False` immediately if `assertion_claim_hashes` is empty.
    - Build an index of receipts by canonical JSON of `receipt.claim`.
    - For each hash in `assertion_claim_hashes` (in order): look up the receipt; if absent return `publishable=False, refusal_name='unmeasured'`; if verdict type is not `'pass'` return `publishable=False` with the verdict's `name`; otherwise collect `receipt.own_hash`.
    - If all assertions pass return `publishable=True, receipt_ids=[...]`.
  - The function is pure: no calls to `adjudicate()`, no chain mutations.

- [x] 5. **Scenarios and runner** — implement `citation_gate/scenarios.py`
  - Define `AssertionResult` dataclass: `text`, `fact_key`, `verdict`, `receipt`.
  - Define `DraftResult` dataclass: `label`, `description`, `assertion_results`, `chain`, `publish_decision`.
  - Define the six scenario data dicts (N1–N6) as module-level constants, each with `label`, `description`, `assertions` list. Scenario N5 is split into `N5a` (original draft, one wrong assertion) and `N5b` (corrected assertion appended to `N5a`'s chain).
  - Implement `run_scenarios(registry: SourceRegistry, desk_mandate: SealedMandate) -> list[DraftResult]`:
    - Construct `CitationMeasurer(registry)` once.
    - For each scenario except N5: start `chain = []`; iterate assertions; call `make_assertion_claim(...)`; call `gate_core.adjudicate(claim, desk_mandate, measurer, chain)`; append receipt to chain; collect `AssertionResult`; call `check_publish(...)`.
    - For N5: adjudicate the three-assertion draft (including the wrong birthplace assertion) into a fresh chain; run `check_publish` to confirm `publishable=False`; then adjudicate the corrected birthplace assertion into the same chain; run `check_publish` again using only the three canonical assertion hashes (original good assertion 1, corrected assertion 2, assertion 3); return both phases as a single `DraftResult` with the full chain.

- [x] 6. **Package init** — implement `citation_gate/__init__.py`
  - Call `gate_core.verdict.register_refusal("citation", name)` for `missing_citation`, `unsupported_claim`, `source_contradicts` at import time.
  - Re-export: `SourceRegistry`, `CitationMeasurer`, `make_assertion_claim`, `PublishDecision`, `check_publish`, `run_scenarios`, `DraftResult`, `AssertionResult`.

---

## Tests

- [x] 7. **Scenario N1 test** — clean three-assertion draft → all verdicts `Pass`; chain length 3; `gate_core.verify_chain` returns `ok=True`; `check_publish` returns `publishable=True` with three receipt ids.

- [x] 8. **Scenario N2 test** — Scorpio beneficiary claimed as `"Marta, the neighbor"` citing `will_2024` → verdict `Refused(name='source_contradicts')`; observations include `fact_key='bequest.Scorpio.beneficiary'`, `asserted_value='Marta, the neighbor'`, `stored_value="the one who knows what happened at the millpond in '87"`; `check_publish` returns `publishable=False, refusal_name='source_contradicts'`.

- [x] 9. **Scenario N3 test** — bequest asserted under Gemini citing `will_2024` → verdict `Refused(name='unsupported_claim')`; observations include `fact_key='bequest.Gemini.item'`, `reason='fact_key_not_in_source'`; `check_publish` returns `publishable=False, refusal_name='unsupported_claim'`.

- [x] 10. **Scenario N4 test** — assertion with `citation=None` → verdict `Refused(name='missing_citation')`; observations include `fact_key`; `check_publish` returns `publishable=False, refusal_name='missing_citation'`.

- [x] 11. **Scenario N5 test** — mixed draft phase 1: `check_publish` returns `publishable=False, refusal_name='source_contradicts'` (assertion 2 is wrong); phase 2 after correcting assertion 2: `check_publish` returns `publishable=True` with three receipt ids; full chain contains four receipts (three from phase 1, one corrected from phase 2); `gate_core.verify_chain` returns `ok=True` on the full chain.

- [x] 12. **Scenario N6 test** — assertion citing unknown source id `"parish_register"` → verdict `Refused(name='unsupported_claim')`; observations include `citation='parish_register'`, `reason='source_not_registered'`; `check_publish` returns `publishable=False, refusal_name='unsupported_claim'`.

- [x] 13. **Tampered cited source test** — construct a `SourceRegistry` where the death record's `SealedMandate` has its `content` dict modified after sealing (seal field left intact); submit an assertion citing `"death_record"`; expect `gate_core.MandateTamperError` to propagate from `adjudicate()`; chain length remains 0 after the error.

- [x] 14. **Fact table shape tests** — construct `SourceRegistry` from the three fixture paths and verify:
  - `fact_table("death_record")` has exactly 4 keys: `deceased`, `date_of_death`, `place`, `registrar`.
  - `fact_table("family_record")` has exactly 5 keys: `person`, `born`, `birthplace`, `occupation`, `residence`.
  - `fact_table("will_2024")` has exactly 14 keys (7 occupied signs × 2 fact types); none of the keys contain `Gemini`, `Cancer`, `Virgo`, `Libra`, or `Sagittarius`.
  - `fact_table("unknown_source")` returns `None`.

---

## Documentation

- [x] 15. **Package README** — write `citation_gate/README.md`:
  - One-paragraph description of the citation gate desk and its relationship to `gate_core`.
  - How to initialise the source registry with fixture paths.
  - How to construct and adjudicate a factual assertion.
  - How to run the publish check for a draft.
  - How to run the demo scenarios (`run_scenarios`).
  - How to verify the receipt chain (`gate_core.verify_chain`).
  - Refusal vocabulary table (copy from requirements).
  - Note on the three source records, the fact table derivation, and the empty-sign rule for the will.
