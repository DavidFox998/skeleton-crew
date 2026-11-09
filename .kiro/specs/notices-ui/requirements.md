# Requirements — Notices Desk Web Skin

**Approved design brief:** `docs/DESIGN-BRIEF-NOTICES-SKIN.md` (Talitha, 2026-11-02, David's approval).  
Every decision in that brief is binding. These requirements translate it into verifiable acceptance criteria.

---

## 1. Scope and identity

**REQ-1.1** The feature adds a second desk — The Notices Desk — to the existing web house. The estate rooms (`/`, `/desk`, `/archive`) are unchanged.

**REQ-1.2** The Notices Desk title is **"The Notices Desk"**. The desk subtitle is **"Nothing is printed here unmeasured."** Both appear on every Notices room page.

**REQ-1.3** The implementation uses Python 3.11+ standard library only, extending `webui/`. No external packages, no JavaScript, no client-side frameworks. The dependency rule is unchanged: `webui` may import `citation_gate` and `gate_core`; `citation_gate` and `executor` are not modified by this feature.

**REQ-1.4** The canon fix (brief item 7) is applied in the same feature: the family record occupation fact becomes `self-professed Tree Wizard`, matching assertion text "He was a self-professed Tree Wizard." in scenarios N1 and N5.

### Acceptance criteria

- AC-1.1: The estate `GET /`, `GET /desk`, `GET /archive` routes continue to return HTTP 200 with unchanged content after the Notices Desk feature is added.
- AC-1.2: Every Notices room HTML response includes the text "The Notices Desk" and "Nothing is printed here unmeasured." in the document body.
- AC-1.3: No new third-party packages are required. `python run_webui.py --help` continues to exit cleanly.
- AC-1.4: `fixtures/family_record.json` contains `"occupation": "self-professed Tree Wizard"`.

---

## 2. Navigation

**REQ-2.1** The shared page header navigation links to all six rooms: the estate's Register (`/`), Desk (`/desk`), and Archive (`/archive`), and the Notices Desk's Sources (`/notices/sources`), Notices Desk (`/notices`), and Notice Archive (`/notices/archive`). The links appear on every page in the house.

**REQ-2.2** The navigation renders the two desks as visually distinct groups, so the clerk can see at a glance which desk each link belongs to.

### Acceptance criteria

- AC-2.1: Every HTML response — from both desks — contains anchor elements with `href` values `/`, `/desk`, `/archive`, `/notices/sources`, `/notices`, and `/notices/archive`.
- AC-2.2: The navigation on `GET /notices/sources` links back to `GET /` (the estate Register) without error.

---

## 3. Three-room structure — The Notices Desk

The Notices Desk has exactly three rooms:

| Room | Path | Purpose |
|------|------|---------|
| Sources | `GET /notices/sources` | The three sealed source records with seals and full fact tables. |
| Notices Desk | `GET /notices` | Workbench: six preset drafts N1–N6 plus the free assertion builder. |
| Notice Archive | `GET /notices/archive` | The notices chain's receipts in full, replay verification, and tamper demonstration. |

**REQ-3.1** `GET /notices/sources` is the Notices Desk's register equivalent.

**REQ-3.2** `GET /notices` is the Notices Desk workbench.

**REQ-3.3** `GET /notices/archive` is the notices chain archive.

### Acceptance criteria

- AC-3.1: `GET /notices/sources` returns HTTP 200 with the Sources content.
- AC-3.2: `GET /notices` returns HTTP 200 with the Notices Desk workbench content.
- AC-3.3: `GET /notices/archive` returns HTTP 200 with the Notice Archive content.

---

## 4. The Sources room

**REQ-4.1** The Sources room displays all three sealed source records held by the desk:

| Source ID | Fixture | Fact keys exposed |
|-----------|---------|-------------------|
| `death_record` | `fixtures/death_record.json` | `deceased`, `date_of_death`, `place`, `registrar` |
| `will_2024` | `fixtures/will_2024.json` | `bequest.<Sign>.item`, `bequest.<Sign>.beneficiary` (one pair per occupied sign) |
| `family_record` | `fixtures/family_record.json` | `person`, `born`, `birthplace`, `occupation`, `residence` |

**REQ-4.2** For each source record, the Sources room shows:
- The source ID as a heading.
- The source seal (abbreviated: first 12 hex characters followed by `…`).
- The full fact table as a two-column key/value listing. No facts are omitted or truncated.

**REQ-4.3** The Sources room is read-only. No forms, no submit buttons.

**REQ-4.4** The sealed mandates in the Sources room are the same objects the measurer uses for adjudication. The seal displayed is the actual SHA-256 hash of the fixture's canonical JSON.

### Acceptance criteria

- AC-4.1: `GET /notices/sources` response body contains all three source IDs: `death_record`, `will_2024`, `family_record`.
- AC-4.2: `GET /notices/sources` response body contains the seal prefix of each source (a substring of the actual SHA-256 hash followed by `…`).
- AC-4.3: `GET /notices/sources` response body contains every fact key for each source (e.g., `date_of_death`, `bequest.Taurus.item`, `occupation`).
- AC-4.4: `GET /notices/sources` response body contains `self-professed Tree Wizard` as the value for the `occupation` fact (after the canon fix).
- AC-4.5: `GET /notices/sources` contains no `<form>` or `<button>` elements.

---

## 5. The Notices Desk room — preset drafts

**REQ-5.1** The Notices Desk displays six preset drafts in the following narrative (casework) order. N5 runs both phases in a single action:

| Label | Scenario description | Expected publish outcome |
|-------|---------------------|--------------------------|
| N1 | Clean draft — all three assertions supported | PUBLISHABLE (all PASS) |
| N2 | Wrong Scorpio beneficiary — one `source_contradicts` refusal | REFUSED · source_contradicts |
| N3 | Bequest under empty sign Gemini — `unsupported_claim` | REFUSED · unsupported_claim |
| N4 | No citation provided — `missing_citation` | REFUSED · missing_citation |
| N5 | Two-phase: N5a wrong birthplace (refused), then N5b corrected (publishable) | Phase N5a: REFUSED · source_contradicts; Phase N5b: PUBLISHABLE |
| N6 | Unknown source id `parish_register` — `unsupported_claim` | REFUSED · unsupported_claim |

**REQ-5.2** Each preset button runs the entire draft: every assertion in that draft is adjudicated in sequence and appended to the notices chain. The draft's publish decision is stamped at the foot of the preset result block.

**REQ-5.3** Before adjudication, each preset's assertion list is rendered in ghost styling. After adjudication, each assertion is rendered in the appropriate verdict state (§8).

**REQ-5.4** Each preset is presented as a form with a single submit button. The assertion text and fact keys are read-only display; they are not editable on preset forms.

**REQ-5.5** Submitting a preset sends `POST /notices/preset` with a `preset` field containing the scenario label (`N1`–`N6`).

**REQ-5.6** For N5: pressing the N5 button runs N5a (three assertions, one refused) and immediately runs N5b (corrected assertion appended) in a single server action. The response shows both phases: N5a's publish decision (refused) and N5b's publish decision (publishable).

**REQ-5.7** All preset receipts are appended to the notices chain. The publish check for each draft evaluates only the draft's own assertion claim hashes against the chain; it does not evaluate the entire chain as a single draft.

### Acceptance criteria

- AC-5.1: `GET /notices` response body contains all six preset labels (N1 through N6) in document order.
- AC-5.2: `POST /notices/preset` with `preset=N1` returns HTTP 200 with a PUBLISHABLE stamp and all three assertion receipts.
- AC-5.3: `POST /notices/preset` with `preset=N2` returns HTTP 200 with `source_contradicts` and a REFUSED publish decision.
- AC-5.4: `POST /notices/preset` with `preset=N3` returns HTTP 200 with `unsupported_claim` and a REFUSED publish decision.
- AC-5.5: `POST /notices/preset` with `preset=N4` returns HTTP 200 with `missing_citation` and a REFUSED publish decision.
- AC-5.6: `POST /notices/preset` with `preset=N5` returns HTTP 200 showing both N5a (REFUSED · source_contradicts) and N5b (PUBLISHABLE) publish decisions.
- AC-5.7: `POST /notices/preset` with `preset=N6` returns HTTP 200 with `unsupported_claim` and a REFUSED publish decision.
- AC-5.8: After running N1 (3 assertions) and N2 (1 assertion), `GET /notices/archive` shows exactly 4 receipts in the chain.

---

## 6. The Notices Desk room — free assertion builder

**REQ-6.1** Below the presets, the Notices Desk provides a free-assertion builder form that allows the clerk to compose a draft assertion by assertion.

**REQ-6.2** The builder form provides the following fields:

| Field | Control | Notes |
|-------|---------|-------|
| Sentence text | `<textarea>` or `<input type="text">` | The assertion as it will print in the obituary. |
| Fact key | `<select>` | Every fact key the three sources expose, grouped or labelled by source. |
| Claimed value | `<input type="text">` | Free text. Typing the wrong value produces `source_contradicts`. |
| Citation | `<select>` | Options: `death_record`, `will_2024`, `family_record`, *no citation*. Choosing *no citation* produces `missing_citation`. |

**REQ-6.3** The fact key dropdown lists every key from all three sources, labelled with its source — e.g. `death_record — date_of_death`, `will_2024 — bequest.Taurus.item`, `family_record — occupation`. No fact key is omitted.

**REQ-6.4** The "Measure this assertion" button submits the form to `POST /notices/assertion`. The server adjudicates the assertion, appends the receipt to the notices chain (unless a hard tamper occurs), adds the assertion and its verdict to the working draft, evaluates the working draft's publish state via `check_publish`, and renders the full updated Notices Desk page.

**REQ-6.5** The working draft's current publish state — either `PUBLISHABLE (receipt IDs…)` or `REFUSED · <first refusal name>` — is displayed beneath the builder form after each assertion is measured.

**REQ-6.6** A "Begin a new draft" button sends `POST /notices/new-draft`. The server closes the current working draft (clears the working draft's assertion list from the register), but the notices chain is append-only — no receipts are ever removed. The archive keeps all receipts from all drafts. After this action the working draft is empty and its publish state is not yet evaluated.

**REQ-6.7** The builder sentence and value fields are not pre-filled with fixture data. They start empty or with a placeholder. The fact key and citation dropdowns are populated from fixture data but the clerk's typed input determines the claimed value.

### Acceptance criteria

- AC-6.1: `GET /notices` response body contains a `<select>` element whose options include every fact key from all three sources (e.g., `date_of_death`, `bequest.Scorpio.beneficiary`, `occupation`).
- AC-6.2: `GET /notices` response body contains citation options `death_record`, `will_2024`, `family_record`, and a "no citation" option.
- AC-6.3: `POST /notices/assertion` with `sentence=Elias+Vane+died+on+28+October+2026.&fact_key=date_of_death&value=2026-10-28&citation=death_record` returns HTTP 200 with a `PASS` verdict and the working draft's updated publish state.
- AC-6.4: `POST /notices/assertion` with `citation=` (no citation) returns HTTP 200 with `missing_citation` in the response.
- AC-6.5: `POST /notices/assertion` with a wrong value returns HTTP 200 with `source_contradicts` in the response.
- AC-6.6: `POST /notices/new-draft` returns HTTP 200; a subsequent `GET /notices` shows an empty working draft; `GET /notices/archive` still shows all previously appended receipts.
- AC-6.7: No `<input>` or `<textarea>` in the builder form has a `value` attribute pre-filled with fixture data.

---

## 7. Publish decision display

**REQ-7.1** A publishable draft is stamped: `PUBLISHABLE` followed by the receipt IDs (each `own_hash`, abbreviated or full) for all assertions in the draft, in assertion order.

**REQ-7.2** A refused draft is stamped: `REFUSED · <first refusal name>` in oxblood, matching the stamp format used for individual verdicts.

**REQ-7.3** The publish stamp for each preset draft appears at the foot of that draft's result block.

**REQ-7.4** For N5, the response shows two publish stamps: one for N5a (REFUSED · source_contradicts) and one for N5b (PUBLISHABLE with receipt IDs).

### Acceptance criteria

- AC-7.1: The response to `POST /notices/preset` with `preset=N1` contains the text `PUBLISHABLE` and at least three receipt ID substrings (own_hash values from the chain).
- AC-7.2: The response to `POST /notices/preset` with `preset=N2` contains `REFUSED · source_contradicts` as the publish stamp.
- AC-7.3: The response to `POST /notices/preset` with `preset=N5` contains both `REFUSED · source_contradicts` (N5a stamp) and `PUBLISHABLE` (N5b stamp) in the response body.

---

## 8. Verdict state styling

The same paper-ledger palette and stamp language used by the estate rooms governs the Notices Desk rooms. These rules are identical to §7 of the estate requirements.

**REQ-8.1 Ghost (unmeasured):** Assertions not yet adjudicated are rendered in ghost-gray (`#9a938a`) at reduced opacity. No verdict badge is shown.

**REQ-8.2 PASS:** The assertion block is rendered in full ink (`#1a1714`) with a seal-mark character (`✦`) adjacent to the PASS label.

**REQ-8.3 REFUSED:** The verdict block shows the refusal name as an oxblood stamp (`#7a2e2a`) in the format `REFUSED · <name>` with uppercase tracking.

**REQ-8.4 Animation:** The only permitted animation is the CSS transition from ghost to solid on verdict return. The transition applies to `color` and `opacity` on `.claim-block`. No `@keyframes` or `animation:` declarations.

**REQ-8.5** The same CSS block serves both desks' rooms. The Notices Desk rooms share the existing `render.css()` output — no duplicate style blocks.

### Acceptance criteria

- AC-8.1: Any Notices room HTML response body contains `color: #9a938a` for the ghost class (present in the shared CSS).
- AC-8.2: Any Notices room HTML response body contains `color: #7a2e2a` for the refused stamp class.
- AC-8.3: All occurrences of `REFUSED` in the notices rooms are accompanied by the refusal name in `REFUSED · <name>` format.
- AC-8.4: The CSS block in notices room responses contains no `@keyframes` and no `animation:` declarations.

---

## 9. Hard stops — seal tamper

**REQ-9.1** If a cited source's seal fails at adjudication time (i.e., the gate raises `MandateTamperError` for a source record), adjudication halts. Nothing is appended to the notices chain.

**REQ-9.2** The Notices Desk page presents the outcome as `REFUSED · seal_broken` in a `.seal-broken-notice` block, with the explanatory note: "Source seal verification failed. This assertion was not recorded in the notices chain."

**REQ-9.3** The hard tamper condition is distinct from a source-content refusal (`source_contradicts`). A `seal_broken` event means the source's content has been altered since sealing; it is not a receipt and not a verdict — it is a gate halt. The page makes this distinction explicit.

### Acceptance criteria

- AC-9.1: When `MandateTamperError` is raised during `POST /notices/assertion`, the response contains `seal_broken` and "was not recorded in the notices chain."
- AC-9.2: After a `seal_broken` event, `GET /notices/archive` shows no new receipt appended (chain length unchanged).
- AC-9.3: The `seal_broken` notice does not include `own_hash` or `previous_hash` fields, distinguishing it visually from a real receipt.

---

## 10. Notices chain semantics

**REQ-10.1** The notices desk maintains one append-only receipt chain in memory — the **notices chain** — separate from the estate desk's house chain. The two chains are never merged or cross-referenced.

**REQ-10.2** Every `gate_core.adjudicate()` call that returns normally (no `MandateTamperError`) appends the returned receipt to the notices chain. This includes assertions from presets and assertions from the free builder.

**REQ-10.3** When `MandateTamperError` is raised, the server catches it and does NOT append anything to the notices chain.

**REQ-10.4** No route or operation other than a successful `adjudicate()` call may append to the notices chain.

**REQ-10.5** `POST /notices/new-draft` does not alter the notices chain. It only clears the working draft's assertion list from the register.

**REQ-10.6** The notices chain is not persisted to disk. It lives only in the server process's memory.

### Acceptance criteria

- AC-10.1: On a fresh server start, `GET /notices/archive` shows an empty notices chain (0 receipts).
- AC-10.2: After running preset N1 (3 assertions), the notices chain has exactly 3 receipts.
- AC-10.3: A `MandateTamperError` during assertion adjudication does not increase the chain length.
- AC-10.4: `POST /notices/new-draft` does not change the notices chain length.
- AC-10.5: `GET /archive` (the estate archive) and `GET /notices/archive` (the notices archive) show independent chains that never share receipts.

---

## 11. Notice Archive room

**REQ-11.1** `GET /notices/archive` renders every receipt in the notices chain in append order (oldest first), each displaying all fields (claim, measurements, measurement_error, verdict, timestamp_utc, previous_hash, own_hash).

**REQ-11.2** The Notice Archive includes a "Verify chain integrity" control. Activating it triggers `POST /notices/archive/verify`, which calls `gate_core.verify_chain()` on the notices chain and renders the `ReplayResult`:
- If `ok=True`: "Chain intact — N receipts verified."
- If `ok=False`: the failure index and failure reason.

**REQ-11.3** The Notice Archive includes a "Tamper demonstration" section. Activating it sends `POST /notices/archive/tamper`. The server:
1. Makes a deep copy of the notices chain.
2. Mutates one field in a receipt in the copy (e.g., changes an assertion value in the claim dict of the last receipt).
3. Calls `gate_core.verify_chain()` on the mutated copy.
4. Renders the `ReplayResult` showing chain failure.
5. Does NOT modify the notices chain.

**REQ-11.4** The tamper demonstration result page includes the text "The notices chain was not modified." to make the demonstration semantics explicit.

### Acceptance criteria

- AC-11.1: `GET /notices/archive` response body contains all receipt `own_hash` values currently in the notices chain.
- AC-11.2: `POST /notices/archive/verify` on an unmodified chain returns HTTP 200 with "Chain intact".
- AC-11.3: `POST /notices/archive/tamper` returns HTTP 200 with a failure result from `verify_chain()` and the text "The notices chain was not modified."
- AC-11.4: After `POST /notices/archive/tamper`, `POST /notices/archive/verify` still returns "Chain intact" (notices chain was not mutated).

---

## 12. No decision logic in the web layer

**REQ-12.1** The web layer (`webui/`) contains no verdict logic, no measurement logic, and no mandate-verification logic. It calls `gate_core.adjudicate()` and `citation_gate.publish.check_publish()` and renders what returns.

**REQ-12.2** `MandateTamperError` is caught by the web layer solely to render the `seal_broken` notice and suppress the chain append. The web layer renders the fixed `seal_broken` label; it does not inspect the exception to alter any other behavior.

**REQ-12.3** The web layer does not filter, suppress, modify, or override any verdict returned by `adjudicate()` or any publish decision returned by `check_publish()`.

### Acceptance criteria

- AC-12.1: No function in `webui/` imports from `gate_core.gate` except to call `adjudicate()` and catch `MandateTamperError`.
- AC-12.2: No function in `webui/` calls `verify_mandate()`, `measure()`, `make_pass()`, or `make_refused()` directly.
- AC-12.3: Code review confirms zero conditional branches in `webui/` that alter a verdict value before rendering.

---

## 13. Input escaping

**REQ-13.1** All user-supplied strings inserted into HTML responses are escaped with `html.escape()` before rendering. This includes the sentence field, the claimed value, and any other form input from `POST /notices/assertion`.

**REQ-13.2** Fixture-sourced data (source record fact values, fact keys, seal prefixes) is also escaped when inserted into HTML, as a defense-in-depth measure.

### Acceptance criteria

- AC-13.1: Submitting `POST /notices/assertion` with `sentence=<script>alert(1)</script>` results in `&lt;script&gt;alert(1)&lt;/script&gt;` in the response body, not an executed script.
- AC-13.2: No raw f-string interpolation of form field values appears in `webui/render.py` without a wrapping `_e()` call.
