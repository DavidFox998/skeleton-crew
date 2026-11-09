# Tasks — Executor Web Skin

Implement the Executor web skin as specified in:
- `.kiro/specs/web-ui/requirements.md`
- `.kiro/specs/web-ui/design.md`
- `docs/DESIGN-BRIEF-WEB-SKIN.md` (binding design brief)

All tasks below are implementation tasks only. Do not write decision logic in `webui/`; call `gate_core.adjudicate()` and render what returns.

---

## 1. Package scaffold

- [x] Create `webui/__init__.py` (empty package marker).
- [x] Create `webui/state.py`, `webui/render.py`, `webui/server.py` as empty module stubs.
- [x] Create `run_webui.py` at the repository root with the entry-point skeleton (argument parsing, fixture path resolution, `HouseRegister` construction, `EstateHandler.register` assignment, `server.run()` call).
- [x] Verify `python -m webui.server` and `python run_webui.py --help` both exit without import errors.

---

## 2. `state.py` — HouseRegister

- [x] Define `SCENARIO_DEFINITIONS`: a module-level list of seven dicts (labels A–G in casework order) with keys `label`, `description`, `will_selector`, `distributions`, `registry_variant`. Populate each dict with the correct distribution data matching the executor scenarios.
- [x] Implement `HouseRegister.__init__`: construct `ExecutorRegistry` (full), `ExecutorRegistry` (no death record), `ExecutorMeasurer` for each, empty chain list, `threading.Lock`.
- [x] Implement `adjudicate_preset(label)`: resolve scenario definition; call `gate_core.adjudicate()` with the appropriate registry/measurer; catch `MandateTamperError` for Scenario G; append receipt to chain for all non-tamper results; return `(verdict, receipt, tamper_error)`.
- [x] Implement `adjudicate_custom(will_seal, distributions)`: look up will by seal; build claim via `make_distribution_claim`; call `gate_core.adjudicate()`; catch `MandateTamperError`; append receipt; return `(verdict, receipt, tamper_error)`.
- [x] Implement `chain_snapshot()`: return `list(self._chain)` under lock.
- [x] Implement `verify_house_chain()`: call `gate_core.verify_chain()` under lock.
- [x] Implement `tamper_demo()`: deep-copy the chain under lock; mutate one field in the last receipt's `claim` dict (constructing a new `Receipt` with `own_hash` unchanged); call `gate_core.verify_chain()` on the mutated copy; return the `ReplayResult`; confirm `self._chain` is unchanged.
- [x] Expose `registry` property.

---

## 3. `render.py` — CSS and page shell

- [x] Implement `render.css() -> str`: return the full CSS block with palette variables `--paper #faf7f0`, `--ink #1a1714`, `--ghost #9a938a`, `--oxblood #7a2e2a`, `--hairline #d8d2c4`; serif font stack `Georgia, 'Times New Roman', serif`; all classes from the design spec (`.ghost`, `.resolved`, `.verdict-pass`, `.verdict-refused`, `.seal-broken-notice`, `.hash`, `.will-columns`, `.will-column.superseded`, `.vector-bit.changed`, `.claim-block`).
- [x] Confirm no `@keyframes` and no `animation:` declarations exist in the CSS output; the only `transition:` is on `.claim-block` for `color` and `opacity`.
- [x] Implement `page_shell(title, body_html) -> str`: full `<!DOCTYPE html>` document with embedded CSS, navigation bar (links to `/`, `/desk`, `/archive`), title "The Estate Desk", subtitle "Nothing leaves this house unmeasured.", and `<main>` containing `body_html`.

---

## 4. `render.py` — Register room

- [x] Implement `render_register(registry) -> str`.
- [x] Render testator heading, death record status (seal prefix if present, "absent" if not).
- [x] Render `.will-columns` with two `.will-column` divs: 2019 with `.ghost .superseded`, 2024 without.
- [x] For each will, render the bit vector as individual `.vector-bit` spans; compute the differing bit positions between the 2019 and 2024 vectors and mark each differing span with `.changed`.
- [x] For each will, render the bequest table of occupied signs (sign, item, beneficiary).
- [x] Apply `_e()` escaping to all fixture values inserted into HTML.

---

## 5. `render.py` — Desk room

- [x] Implement `render_desk(scenario_defs, registry) -> str`.
- [x] Render each scenario in order A–G as a `.claim-block.ghost` section: description, claim summary, submit form with hidden `preset` field.
- [x] Implement `render_desk_with_result(scenario_defs, registry, label_or_builder, verdict, receipt, tamper_error) -> str`.
- [x] For the matched preset: replace `.ghost` with `.resolved` on the `.claim-block`; inject the verdict result block immediately after its form.
- [x] For `tamper_error=True`: inject a `.seal-broken-notice` with "REFUSED · seal_broken" and "Mandate seal verification failed. This event was not recorded in the house chain."
- [x] For normal verdicts: call `render_receipt(receipt)` to inject the full receipt.
- [x] Implement `render_verdict_badge(verdict_dict) -> str`: `PASS` → `<span class="verdict-pass">`, refused → `<span class="verdict-refused">REFUSED · {name}</span>`.

---

## 6. `render.py` — builder form

- [x] Implement `render_builder_form(registry, selected_will_seal, row_count) -> str`.
- [x] Render will picker `<select name="will_seal">` with options for all wills (value = seal, label = `"{sealed_date} — {seal[:12]}…"`).
- [x] Render row-count `<input type="number" name="row_count">` with a "Set rows" submit button to `POST /desk/builder-rows`.
- [x] Render `row_count` distribution rows, each with `<select name="sign_{i}">` and `<select name="item_{i}">` populated from the selected will's occupied bequests, and `<input type="text" name="beneficiary_{i}">` with no pre-filled value.
- [x] Include hidden `<input type="hidden" name="builder" value="1">` and "Submit for adjudication" button to `POST /adjudicate`.
- [x] Confirm no beneficiary `<input>` element has a `value` attribute from fixture data.

---

## 7. `render.py` — receipt and Archive room

- [x] Implement `render_receipt(receipt) -> str`: render all fields (claim, measurements, measurement_error, verdict, timestamp_utc, previous_hash, own_hash) in a `<dl>`; hashes in `<span class="hash">`; no truncation.
- [x] Implement `render_archive(chain, replay_result, tamper_result, tamper_demo_ran) -> str`.
- [x] Render chain summary "House Chain — N receipts."
- [x] Render each receipt via `render_receipt()` separated by `.rule` dividers.
- [x] Render "Verify chain integrity" form (`POST /archive/verify`); if `replay_result` provided, render result.
- [x] Render "Tamper demonstration" form (`POST /archive/tamper-demo`); if `tamper_demo_ran=True`, render `tamper_result` and the text "The house chain was not modified."

---

## 8. `server.py` — routes

- [x] Implement `EstateHandler(BaseHTTPRequestHandler)` with class-level `register` attribute.
- [x] Implement `do_GET` dispatch via `match`/`case`: `/` → `_get_register`, `/desk` → `_get_desk`, `/archive` → `_get_archive`, default → `_send_404`.
- [x] Implement `do_POST` dispatch: `/adjudicate` → `_post_adjudicate`, `/desk/builder-rows` → `_post_builder_rows`, `/archive/verify` → `_post_archive_verify`, `/archive/tamper-demo` → `_post_tamper_demo`, default → `_send_404`.
- [x] Implement `_read_form() -> dict[str, list[str]]`: read `Content-Length` bytes, decode UTF-8, parse with `urllib.parse.parse_qs`.
- [x] Implement `_send_html(html, status=200)`.
- [x] Implement `_get_register`, `_get_desk`, `_get_archive` calling the corresponding render functions.
- [x] Implement `_post_adjudicate`: branch on `builder` field; call `adjudicate_preset` or `adjudicate_custom`; render result page.
- [x] Implement `_post_builder_rows`: extract `will_seal` and `row_count`; render Desk with reloaded builder.
- [x] Implement `_post_archive_verify`: call `verify_house_chain()`; render Archive with `replay_result`.
- [x] Implement `_post_tamper_demo`: call `tamper_demo()`; render Archive with `tamper_result` and `tamper_demo_ran=True`.
- [x] Add HTTP 400 / 500 error handling: unknown preset, missing will seal, unhandled exceptions (traceback to stderr only, not response body).
- [x] Implement `run(host, port, register)`.

---

## 9. CSS — per-brief audit

- [x] Audit rendered HTML from `GET /` against the brief: paper background `#faf7f0` present, ink `#1a1714` present, hairline borders `#d8d2c4` present.
- [x] Audit `GET /desk`: ghost color `#9a938a` present on unmeasured preset blocks.
- [x] Audit a PASS verdict response: `#1a1714` ink color and seal-mark character (`✦`) present.
- [x] Audit a REFUSED verdict response: oxblood `#7a2e2a` stamp with `REFUSED · {name}` format and `letter-spacing` present.
- [x] Confirm the only transition in the CSS is on `.claim-block` color/opacity; confirm no `@keyframes` and no `animation:` declarations.
- [x] Confirm the 2019 will column carries the `.ghost` class in `GET /` response.

---

## 10. Unit tests — handler and state

All tests in `tests/test_webui.py`. Tests must use the real `gate_core` and `executor` libraries with the fixture files; no mocking of gate logic.

- [x] **Preset verdicts match direct adjudication (all seven scenarios):** For each label A–G, call `register.adjudicate_preset(label)` and compare the verdict type and refusal name (or tamper flag) to the expected outcome from the scenario table.
- [x] **Chain append semantics:** After adjudicating A through F in order, `chain_snapshot()` has exactly 6 receipts. After G, still 6.
- [x] **Builder submission path — PASS:** Construct a correct 7-bequest distribution for the 2024 will, call `adjudicate_custom(will_seal, distributions)`, assert verdict is `PASS` and receipt is appended.
- [x] **Builder submission path — beneficiary_unknown:** Construct a distribution with one wrong beneficiary name, call `adjudicate_custom`, assert verdict is `REFUSED('beneficiary_unknown')`.
- [x] **Tamper demo does not mutate house chain:** Populate the chain, call `tamper_demo()`, verify chain length and all own_hash values unchanged.
- [x] **verify_house_chain integrity:** After any sequence of successful adjudications, `verify_house_chain()` returns `ok=True`.
- [x] **Input escaping:** Submit a builder form with `beneficiary_0=<script>alert(1)</script>` via HTTP POST; assert `&lt;script&gt;` present; bare `<script>` absent.
- [x] **Route smoke tests:** `GET /`, `GET /desk`, `GET /archive` all return HTTP 200. `POST /adjudicate` with `preset=A` returns HTTP 200 containing `PASS`.

---

## 11. README

- [x] Add `webui/README.md` covering:
  - How to start the server: `python run_webui.py [--port N]`.
  - The three rooms and their URLs.
  - How the house chain works and what Scenario G demonstrates.
  - How to run the tests: `python -m unittest discover -s tests`.

---

## 12. Manual smoke test

Perform after implementation is complete. Record pass/fail for each step.

- [x] Start the server: `python run_webui.py --port 8765`. Server starts without errors.
- [x] `curl -s http://localhost:8765/` returns HTTP 200; response body contains "The Estate Desk" and "Nothing leaves this house unmeasured."
- [x] `curl -s http://localhost:8765/desk` returns HTTP 200; response body contains all seven scenario labels A through G in order.
- [x] `curl -s http://localhost:8765/archive` returns HTTP 200; response body contains "House Chain — 0 receipts."
- [x] `curl -s -X POST -d "preset=A" http://localhost:8765/adjudicate` returns HTTP 200; response body contains "PASS".
- [x] `curl -s http://localhost:8765/archive` now shows "House Chain — 1 receipts." and a 64-character `own_hash`.
- [x] `curl -s -X POST -d "preset=G" http://localhost:8765/adjudicate` returns HTTP 200; response body contains "seal_broken" and "was not recorded in the house chain."
- [x] `curl -s http://localhost:8765/archive` still shows "House Chain — 1 receipts." (G did not append).
- [x] `curl -s -X POST http://localhost:8765/archive/verify` returns HTTP 200 with "Chain intact".
- [x] `curl -s -X POST http://localhost:8765/archive/tamper-demo` returns HTTP 200 with a failure result and "The house chain was not modified."
- [x] After the tamper demo, `curl -s -X POST http://localhost:8765/archive/verify` still returns "Chain intact".
