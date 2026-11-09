# Tasks — Notices Desk Web Skin

Implement the Notices Desk web skin as specified in:
- `.kiro/specs/notices-ui/requirements.md`
- `.kiro/specs/notices-ui/design.md`
- `docs/DESIGN-BRIEF-NOTICES-SKIN.md` (binding design brief)

All tasks are implementation tasks only. Do not write decision logic in `webui/`; call `gate_core.adjudicate()`, `citation_gate.publish.check_publish()`, and render what returns.

Tasks are ordered so each step depends only on completed prior steps. The canon fix (task 1) is applied first; all subsequent tasks build on it.

---

## 1. Canon fix — family record occupation

- [ ] In `fixtures/family_record.json`, change the `"occupation"` value from `"keeper of the Hollow Hill light (retired)"` to `"self-professed Tree Wizard"`.
- [ ] In `citation_gate/scenarios.py`, update `_SCENARIO_N1` assertion at index 2: set `"text"` to `"He was a self-professed Tree Wizard."` and `"value"` to `"self-professed Tree Wizard"`.
- [ ] In `citation_gate/scenarios.py`, update `_SCENARIO_N5A` assertion at index 2: set `"text"` to `"He was a self-professed Tree Wizard."` and `"value"` to `"self-professed Tree Wizard"`.
- [ ] In `tests/test_citation_gate.py`, update any string literals that reference `"keeper of the Hollow Hill light (retired)"` or the old assertion text to use the new wording.
- [ ] Run the full test suite (`python -m unittest discover -s tests`) and confirm it passes green with no failures or errors.

---

## 2. `state.py` — `NoticesRegister` and `NOTICES_SCENARIO_DEFINITIONS`

- [ ] Define the `AssertionEntry` dataclass in `webui/state.py` with fields: `text`, `fact_key`, `value`, `citation`, `claim_hash`, `verdict`, `receipt`.
- [ ] Define `NOTICES_SCENARIO_DEFINITIONS` as a module-level list of six scenario dicts (N1–N6 in order) with `label`, `description`, `phases` (each phase has `label` and `assertions`), and `expected_publish`. Populate all assertion data to match `citation_gate/scenarios.py` after the canon fix. N5 must have two phases (`N5a`, `N5b`).
- [ ] Implement `NoticesRegister.__init__`: construct `SourceRegistry` from the three fixture paths; construct `CitationMeasurer`; construct the desk mandate via `seal_mandate("citation", {...})`; initialise empty `_chain`, `_working_draft`, and `_lock`.
- [ ] Implement `adjudicate_preset(label)`: look up the scenario by label; iterate its phases; for each phase adjudicate all assertions via `gate_core.adjudicate()`, catch `MandateTamperError`; call `check_publish` after each phase; append receipts to `self._chain` (not to `self._working_draft`); return `(entries, decisions, tamper_error)`.
- [ ] Implement `adjudicate_assertion(text, fact_key, value, citation)`: build claim via `make_assertion_claim`; call `gate_core.adjudicate()`; catch `MandateTamperError`; on success append receipt to chain and `AssertionEntry` to `self._working_draft`; call `check_publish` on the working draft's claim hashes; return `(entry, publish_decision, tamper_error)`.
- [ ] Implement `new_draft()`: clear `self._working_draft` under lock; do not touch `self._chain`.
- [ ] Implement `working_draft_publish_state() -> PublishDecision | None`: if the working draft is empty return `None`; otherwise call `check_publish` on the draft's claim hashes and the chain snapshot; return the result.
- [ ] Implement `chain_snapshot()`: return `list(self._chain)` under lock.
- [ ] Implement `verify_notices_chain()`: call `gate_core.verify_chain()` on a locked snapshot.
- [ ] Implement `tamper_demo()`: deep-copy the chain under lock; mutate one assertion value in the last receipt's claim payload; construct a new `Receipt` with the mutated claim and the original `own_hash`; call `gate_core.verify_chain()` on the copy; do NOT modify `self._chain`; return `ReplayResult`.
- [ ] Expose `source_registry` property (read-only).
- [ ] Add the `_canonical_json`, `_claim_hash`, and `_utc_now` helper functions (or reuse existing module-level helpers already in `state.py`).
- [ ] Guard all mutations of `_chain` and `_working_draft` behind `self._lock`.

---

## 3. `render.py` — navigation update

- [ ] Update `page_shell(title, body_html)` to include all six navigation links: `/` (Register), `/desk` (Desk), `/archive` (Archive), `/notices/sources` (Sources), `/notices` (Notices), `/notices/archive` (Notice Archive).
- [ ] Group the two desks visually in the nav (e.g. a separator character between the two groups) without introducing new CSS classes beyond `nav-separator` and `nav-group`.
- [ ] Add `notices_page_shell(title, body_html) -> str` that renders the house header with title "The Notices Desk" and subtitle "Nothing is printed here unmeasured." and calls the updated `page_shell` or its own equivalent.
- [ ] Confirm the estate `page_shell` tests (if any) still pass after the nav change.

---

## 4. `render.py` — Sources room

- [ ] Implement `render_sources(source_registry) -> str`.
- [ ] Render each of the three source IDs (`death_record`, `will_2024`, `family_record`) in a fixed order as an `<h3>` heading, seal prefix in `<span class="hash">`, and a full key/value fact table (use `source_registry.fact_table(source_id)` for keys and values).
- [ ] Apply `_e()` to all fact keys and values inserted into HTML.
- [ ] Confirm no `<form>` or `<button>` elements appear in the output.

---

## 5. `render.py` — Notices Desk workbench functions

- [ ] Implement `render_assertion_builder(source_registry) -> str`.
  - `<input type="text" name="sentence">` with no pre-filled value.
  - `<select name="fact_key">` with one `<optgroup>` per source; each option value is the fact key, label is `{source_id} — {fact_key}`. Pull keys from `source_registry.fact_table(sid).keys()` for each source ID.
  - `<input type="text" name="value">` with no pre-filled value.
  - `<select name="citation">` with options `death_record`, `will_2024`, `family_record`, and `""` (display "No citation").
  - Submit button `"Measure this assertion"` posting to `POST /notices/assertion`.
- [ ] Implement `render_publish_decision(decision) -> str`.
  - If publishable: `<p class="verdict-pass">PUBLISHABLE</p>` followed by the list of receipt IDs.
  - If not publishable: `<p class="verdict-refused">REFUSED · {_e(decision.refusal_name)}</p>`.
- [ ] Implement `render_notices_desk(scenario_defs, source_registry, working_draft, publish_state) -> str`.
  - Render each scenario as a ghost preset block with description, assertion list (text + fact_key + citation in `.ghost`), and submit form posting to `POST /notices/preset`.
  - Render the working draft summary: list each `AssertionEntry` with its text and verdict badge (or ghost if not yet measured).
  - Render the current `publish_state` via `render_publish_decision` if not `None`.
  - Render the assertion builder form.
  - Render the "Begin a new draft" form posting to `POST /notices/new-draft`.
- [ ] Implement `render_notices_desk_with_preset_result(scenario_defs, source_registry, working_draft, publish_state, label, entries, decisions, tamper_error) -> str`.
  - Inject the full preset result block after the matched preset: each `AssertionEntry` in `entries` shown with its verdict badge (or `.seal-broken-notice` on tamper).
  - Each `PublishDecision` in `decisions` rendered via `render_publish_decision`.
  - The matched preset block transitions from `.ghost` to `.resolved`.
- [ ] Implement `render_notices_desk_with_assertion_result(scenario_defs, source_registry, working_draft, publish_state, entry, tamper_error) -> str`.
  - Show the latest assertion's verdict result beneath the builder form.
  - If `tamper_error`: show `.seal-broken-notice` with "REFUSED · seal_broken" and "Source seal verification failed. This assertion was not recorded in the notices chain."
  - Show the updated working draft and publish state.

---

## 6. `render.py` — Notice Archive room

- [ ] Implement `render_notices_archive(chain, replay_result=None, tamper_result=None, tamper_demo_ran=False) -> str`.
  - Header: "Notice Chain — N receipts."
  - Each receipt rendered via existing `render_receipt()`, in append order.
  - "Verify chain integrity" form posting to `POST /notices/archive/verify`.
  - If `replay_result` provided: render `ReplayResult` ("Chain intact — N receipts verified." or failure details).
  - "Tamper demonstration" section with form posting to `POST /notices/archive/tamper`.
  - If `tamper_demo_ran=True`: render `tamper_result` plus the text "The notices chain was not modified."

---

## 7. `server.py` — `HouseHandler` and notices routes

- [ ] Refactor `server.py` to use a single `HouseHandler(BaseHTTPRequestHandler)` class with both `register` (estate) and `notices_register` (notices) as class-level attributes. All existing estate routes must continue to work unchanged.
- [ ] Implement `do_GET` dispatch for all six GET paths (estate `/`, `/desk`, `/archive` plus notices `/notices/sources`, `/notices`, `/notices/archive`). Unknown paths return HTTP 404.
- [ ] Implement `do_POST` dispatch for all eight POST paths (estate four plus notices four). Unknown paths return HTTP 404.
- [ ] Implement `_get_sources()`: call `render.render_sources(self.notices_register.source_registry)` and send via `render.notices_page_shell`.
- [ ] Implement `_get_notices()`: call `render.render_notices_desk(...)` passing the working draft and `working_draft_publish_state()`.
- [ ] Implement `_get_notices_archive()`: call `render.render_notices_archive(chain)`.
- [ ] Implement `_post_preset()`: parse `preset` field; call `notices_register.adjudicate_preset(label)`; catch `KeyError` → HTTP 400; render result page.
- [ ] Implement `_post_assertion()`: parse `sentence`, `fact_key`, `value`, `citation` fields; validate `sentence` and `fact_key` non-empty (HTTP 400 if missing); call `notices_register.adjudicate_assertion(...)`; render result page.
- [ ] Implement `_post_new_draft()`: call `notices_register.new_draft()`; render the clean Notices Desk page.
- [ ] Implement `_post_notices_verify()`: call `verify_notices_chain()`; render Notice Archive with `replay_result`.
- [ ] Implement `_post_notices_tamper()`: call `tamper_demo()`; render Notice Archive with `tamper_result` and `tamper_demo_ran=True`.
- [ ] Update `run(host, port, register, notices_register)` to accept and set both registers on `HouseHandler`.
- [ ] All form values inserted into HTML are escaped via `_e()` before rendering.

---

## 8. `run_webui.py` update

- [ ] Update `run_webui.py` to construct a `NoticesRegister` with the three citation fixture paths (`death_record.json`, `will_2024.json`, `family_record.json`).
- [ ] Set `HouseHandler.notices_register = notices_register` before calling `run()`.
- [ ] Pass `notices_register` to `run()`.
- [ ] Confirm `python run_webui.py --help` exits cleanly.
- [ ] Confirm `python run_webui.py --port 8765` starts the server and all six GET routes return HTTP 200.

---

## 9. Unit tests — `tests/test_notices_ui.py`

Create a new file `tests/test_notices_ui.py`. Use the real `gate_core`, `citation_gate`, and fixture files with no mocking of gate logic. Mirror the style of `tests/test_webui.py`.

### State tests

- [ ] **Sources room renders**: call `render.render_sources(registry)` and assert the response contains `death_record`, `will_2024`, `family_record`, each source's seal prefix, and `self-professed Tree Wizard` as the occupation value.
- [ ] **Notices Desk room renders**: call `render.render_notices_desk(NOTICES_SCENARIO_DEFINITIONS, registry, [], None)` and assert all six labels N1–N6 appear in document order.
- [ ] **Notice Archive renders empty**: call `render.render_notices_archive([])` and assert "Notice Chain — 0 receipts" appears.
- [ ] **Preset N1 — all PASS, publishable**: call `notices_register.adjudicate_preset("N1")` and assert: `tamper_error=False`; all three assertion entries have `verdict["type"] == "pass"`; `decisions[0].publishable is True`; `decisions[0].receipt_ids` has length 3.
- [ ] **Preset N2 — source_contradicts, refused**: call `adjudicate_preset("N2")` and assert: the single entry's verdict is refused with `name="source_contradicts"`; `decisions[0].publishable is False`; `decisions[0].refusal_name == "source_contradicts"`.
- [ ] **Preset N3 — unsupported_claim, refused**: call `adjudicate_preset("N3")` and assert refusal name is `"unsupported_claim"`.
- [ ] **Preset N4 — missing_citation, refused**: call `adjudicate_preset("N4")` and assert refusal name is `"missing_citation"`.
- [ ] **Preset N5 — two phases**: call `adjudicate_preset("N5")` and assert: `len(decisions) == 2`; `decisions[0].publishable is False`; `decisions[0].refusal_name == "source_contradicts"`; `decisions[1].publishable is True`.
- [ ] **Preset N6 — unsupported_claim, refused**: call `adjudicate_preset("N6")` and assert refusal name is `"unsupported_claim"`.
- [ ] **Chain grows correctly**: run presets N1 (3 assertions) and N2 (1 assertion) in sequence; assert `chain_snapshot()` has exactly 4 receipts.
- [ ] **Custom assertion flow — PASS**: call `adjudicate_assertion("Elias Vane died on 28 October 2026.", "date_of_death", "2026-10-28", "death_record")` and assert `tamper_error=False`; entry verdict is `PASS`; publish decision is not None; chain length increased by 1.
- [ ] **Custom assertion flow — source_contradicts**: call `adjudicate_assertion("He bequeathed The Sealed Letter to Marta, the neighbor.", "bequest.Scorpio.beneficiary", "Marta, the neighbor", "will_2024")` and assert entry verdict is refused with `name="source_contradicts"`; `publish_decision.refusal_name == "source_contradicts"`.
- [ ] **Custom assertion flow — missing_citation**: call `adjudicate_assertion("He was born in Hollow Hill.", "birthplace", "Hollow Hill", None)` and assert entry verdict is refused with `name="missing_citation"`.
- [ ] **New draft resets working draft, chain only grows**: add one assertion to the working draft; call `new_draft()`; assert `working_draft` is empty; assert chain length is unchanged (not decreased).
- [ ] **Tamper demo does not mutate notices chain**: populate the chain with at least one receipt; call `tamper_demo()`; assert chain length unchanged; assert all own_hash values in `chain_snapshot()` are unchanged; assert the returned `ReplayResult` has `ok=False` (chain failure detected in the copy).
- [ ] **verify_notices_chain integrity**: after any sequence of successful adjudications, `verify_notices_chain()` returns `ok=True`.

### HTTP route tests

- [ ] **GET /notices/sources — HTTP 200**: assert response status 200 and body contains all three source IDs.
- [ ] **GET /notices — HTTP 200**: assert response status 200 and body contains "N1" through "N6".
- [ ] **GET /notices/archive — HTTP 200**: assert response status 200 and body contains "Notice Chain".
- [ ] **POST /notices/preset N1 — PUBLISHABLE**: assert HTTP 200 and body contains "PUBLISHABLE".
- [ ] **POST /notices/preset N2 — REFUSED publish**: assert HTTP 200 and body contains `source_contradicts`.
- [ ] **POST /notices/preset N5 — both phases**: assert HTTP 200 and body contains both `source_contradicts` (N5a) and `PUBLISHABLE` (N5b).
- [ ] **POST /notices/assertion — PASS**: send `sentence=Elias+Vane+died...&fact_key=date_of_death&value=2026-10-28&citation=death_record`; assert HTTP 200 and body contains `PASS`.
- [ ] **POST /notices/assertion — missing_citation**: send `citation=` (empty); assert HTTP 200 and body contains `missing_citation`.
- [ ] **POST /notices/new-draft — working draft cleared, chain unaffected**: add an assertion; POST to `/notices/new-draft`; assert HTTP 200; a subsequent `GET /notices` shows empty working draft; `GET /notices/archive` still shows previous receipts.
- [ ] **POST /notices/archive/verify — chain intact**: assert HTTP 200 with "Chain intact".
- [ ] **POST /notices/archive/tamper — failure shown, chain unmodified**: assert HTTP 200 with `hash_mismatch` (or equivalent failure reason) and "The notices chain was not modified."; a subsequent `/notices/archive/verify` still returns "Chain intact".
- [ ] **Input escaping**: POST `sentence=<script>alert(1)</script>` to `/notices/assertion`; assert response body contains `&lt;script&gt;` and does NOT contain `<script>alert`.
- [ ] **Estate routes unaffected**: `GET /`, `GET /desk`, `GET /archive` still return HTTP 200 after `NoticesHandler` integration.
- [ ] **Six-link navigation present**: any response from either desk contains `href="/notices/sources"` and `href="/"`.

---

## 10. CSS audit — notices rooms

- [ ] Render `GET /notices/sources` and confirm the response body contains the shared CSS with `--ghost: #9a938a` and `--oxblood: #7a2e2a`.
- [ ] Render `POST /notices/preset` with `preset=N1` and confirm the response body contains the text `PUBLISHABLE` and at least one `✦` character (PASS seal mark).
- [ ] Render `POST /notices/preset` with `preset=N2` and confirm the response body contains `REFUSED · source_contradicts` (middle-dot format) and the `verdict-refused` CSS class.
- [ ] Confirm no `@keyframes` and no `animation:` declarations appear in the CSS block of any notices room response.
- [ ] Confirm the only `transition:` in the CSS block applies to `.claim-block` for `color` and `opacity`.

---

## 11. Canon fix — verification

- [ ] Run `python -m unittest discover -s tests` after all tasks above are complete and confirm zero failures.
- [ ] Confirm `GET /notices/sources` response body contains `self-professed Tree Wizard` for the `occupation` fact.
- [ ] Confirm `POST /notices/preset` with `preset=N1` response body contains the assertion text "He was a self-professed Tree Wizard." and its verdict is `PASS`.

---

## 12. Manual smoke test

Perform after all implementation tasks are complete. Record pass/fail for each step.

- [ ] Start the server: `python run_webui.py --port 8765`. Server starts without errors.
- [ ] `curl -s http://localhost:8765/` returns HTTP 200 and body contains "The Estate Desk".
- [ ] `curl -s http://localhost:8765/notices/sources` returns HTTP 200 and body contains `death_record`, `will_2024`, `family_record`, and `self-professed Tree Wizard`.
- [ ] `curl -s http://localhost:8765/notices` returns HTTP 200 and body contains N1 through N6.
- [ ] `curl -s http://localhost:8765/notices/archive` returns HTTP 200 and body contains "Notice Chain — 0 receipts".
- [ ] `curl -s -X POST -d "preset=N1" http://localhost:8765/notices/preset` returns HTTP 200 and body contains `PUBLISHABLE`.
- [ ] `curl -s http://localhost:8765/notices/archive` now shows "Notice Chain — 3 receipts" and three `own_hash` values.
- [ ] `curl -s -X POST -d "preset=N2" http://localhost:8765/notices/preset` returns HTTP 200 and body contains `REFUSED · source_contradicts`.
- [ ] `curl -s -X POST -d "preset=N5" http://localhost:8765/notices/preset` returns HTTP 200 and body contains both `REFUSED · source_contradicts` and `PUBLISHABLE`.
- [ ] `curl -s -X POST -d "sentence=test&fact_key=date_of_death&value=2026-10-28&citation=death_record" http://localhost:8765/notices/assertion` returns HTTP 200 and body contains `PASS`.
- [ ] `curl -s -X POST -d "sentence=test&fact_key=date_of_death&value=wrong&citation=death_record" http://localhost:8765/notices/assertion` returns HTTP 200 and body contains `source_contradicts`.
- [ ] `curl -s -X POST http://localhost:8765/notices/new-draft` returns HTTP 200; a subsequent `GET /notices` shows empty working draft; `GET /notices/archive` still shows all receipts.
- [ ] `curl -s -X POST http://localhost:8765/notices/archive/verify` returns HTTP 200 with "Chain intact".
- [ ] `curl -s -X POST http://localhost:8765/notices/archive/tamper` returns HTTP 200 with a failure result and "The notices chain was not modified."
- [ ] After the tamper demo, `curl -s -X POST http://localhost:8765/notices/archive/verify` still returns "Chain intact".
- [ ] `curl -s http://localhost:8765/` still returns the estate Register without error (estate unaffected by notices feature).
- [ ] Navigation on `GET /notices/sources` contains links to both `/` and `/notices`.
