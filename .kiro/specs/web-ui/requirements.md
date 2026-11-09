# Requirements — Executor Web Skin

**Approved design brief:** `docs/DESIGN-BRIEF-WEB-SKIN.md` (David, 2026-11-02).  
Every decision in that brief is binding. These requirements translate it into verifiable acceptance criteria.

---

## 1. Scope and identity

**REQ-1.1** The application is titled "The Estate Desk". The subtitle "Nothing leaves this house unmeasured." appears on every page beneath the title.

**REQ-1.2** The skin wraps the Executor domain only. The Citation Gate skin is out of scope for this feature.

**REQ-1.3** The implementation uses Python 3.11+ standard library only (`http.server`, `html`, `json`, `hashlib`, `datetime`, etc.). No external packages, no JavaScript, no client-side frameworks.

### Acceptance criteria

- AC-1.1: `GET /` returns an HTML page whose `<title>` element reads "The Estate Desk".
- AC-1.2: Every rendered page includes the subtitle "Nothing leaves this house unmeasured." in the document body.
- AC-1.3: `pip install` is not required; `python -m webui.server` starts the application with no import errors from third-party packages.

---

## 2. Three-room structure

The application has exactly three rooms, navigable by links present on every page.

| Room | Path | Purpose |
|------|------|---------|
| Register | `GET /` | Case file: testator identity, death record status, both wills side by side. |
| Desk | `GET /desk` | Workbench: seven preset claims plus a free builder. |
| Archive | `GET /archive` | The house receipt chain, chain-integrity replay, tamper demonstration. |

**REQ-2.1** Navigation links to all three rooms appear on every page.

**REQ-2.2** The Register (`GET /`) is the default landing page.

### Acceptance criteria

- AC-2.1: Every HTML response contains anchor elements whose `href` values are `/`, `/desk`, and `/archive`.
- AC-2.2: `GET /` returns HTTP 200 with the Register content.
- AC-2.3: `GET /desk` returns HTTP 200 with the Desk content.
- AC-2.4: `GET /archive` returns HTTP 200 with the Archive content.

---

## 3. The Register room

**REQ-3.1** The Register displays the testator's name as a heading.

**REQ-3.2** The Register shows the sealed death record status: whether a death record is present and, if so, its seal (abbreviated to the first 12 hex characters followed by `…`).

**REQ-3.3** The Register displays both wills side by side (or stacked on narrow viewports):
- The 2019 will rendered in grayscale (ghost styling — see §7) with its sealed date and seal prefix.
- The 2024 will rendered in full ink with its sealed date and seal prefix.
- The one-bit vector difference between the two wills is visually distinguishable: the bit position(s) that differ between the 2019 vector and the 2024 vector are marked with a hairline underline or equivalent contrast treatment.

**REQ-3.4** Each will's bequest table lists sign, item, and beneficiary for every occupied bit (bit value `"1"` in the vector).

### Acceptance criteria

- AC-3.1: `GET /` response body contains the testator name from the 2024 will fixture.
- AC-3.2: `GET /` response body contains the death record seal prefix.
- AC-3.3: `GET /` response body contains both `sealed_date` values from the two will fixtures.
- AC-3.4: The 2019 will section carries the ghost CSS class; the 2024 will section does not.
- AC-3.5: The bit position that differs between the two will vectors is visually distinguished (carries a CSS class or inline style marking the difference).

---

## 4. The Desk room — preset claims

**REQ-4.1** The Desk displays seven preset claims in the following narrative (casework) order:

| Label | Scenario | Expected verdict |
|-------|----------|------------------|
| A | Correct 7-bequest distribution under the 2024 will | `PASS` |
| B | Correct distribution under the superseded 2019 will | `REFUSED · will_superseded` |
| C | 2024 will with one extra bequest (8 total) | `REFUSED · share_mismatch` |
| D | 2024 will with a wrong beneficiary on one sign | `REFUSED · beneficiary_unknown` |
| E | 2024 will with an unoccupied sign included | `REFUSED · sign_unoccupied` |
| F | 2024 will, correct distribution, but no death record in the registry view | `REFUSED · death_unverified` |
| G | 2024 will with tampered mandate (altered page) | Presented as `REFUSED · seal_broken`; nothing appended |

**REQ-4.2** Each preset is presented as a form with a single submit button. No distribution data is editable on preset forms; they are read-only displays of the claim that will be submitted.

**REQ-4.3** Before adjudication, each preset claim is rendered in ghost styling (§7). After adjudication, the verdict is rendered in the appropriate verdict styling (§7) directly beneath its preset form. This state transition is the only visual animation permitted: a CSS transition on the ghost → solid resolution.

**REQ-4.4** Submitting a preset sends `POST /adjudicate` with a `preset` field containing the scenario label (`A`–`G`).

**REQ-4.5** For Scenario F: the server adjudicates using a restricted `ExecutorRegistry` view that omits the death record. The resulting receipt (verdict `REFUSED · death_unverified`) is appended to the house chain normally.

**REQ-4.6** For Scenario G: the server catches `MandateTamperError` from `gate_core.adjudicate()`. Nothing is appended to the house chain. The Desk renders the outcome as `REFUSED · seal_broken` with an explanatory note: "Mandate seal verification failed. This event was not recorded in the house chain."

### Acceptance criteria

- AC-4.1: `GET /desk` response body contains all seven scenario labels (A through G) in document order A → G.
- AC-4.2: `POST /adjudicate` with `preset=A` returns HTTP 200 and a response body containing a `PASS` verdict indicator.
- AC-4.3: `POST /adjudicate` with `preset=B` returns HTTP 200 and a response body containing `will_superseded`.
- AC-4.4: `POST /adjudicate` with `preset=C` returns HTTP 200 and a response body containing `share_mismatch`.
- AC-4.5: `POST /adjudicate` with `preset=D` returns HTTP 200 and a response body containing `beneficiary_unknown`.
- AC-4.6: `POST /adjudicate` with `preset=E` returns HTTP 200 and a response body containing `sign_unoccupied`.
- AC-4.7: `POST /adjudicate` with `preset=F` returns HTTP 200 and a response body containing `death_unverified`; a subsequent `GET /archive` shows one additional receipt at the tail of the chain.
- AC-4.8: `POST /adjudicate` with `preset=G` returns HTTP 200 and a response body containing `seal_broken`; the house chain length does NOT increase; the note about nothing being appended is present in the response body.

---

## 5. The Desk room — free builder

**REQ-5.1** Below the presets, the Desk provides a free-builder form that allows the user to compose an arbitrary distribution claim.

**REQ-5.2** The builder form includes:
- A will picker: a `<select>` element listing all wills held by the registry, identified by sealed date and seal prefix. Changing the selected will repopulates the sign/item dropdowns (via a plain HTML form reload, not JavaScript).
- For each distribution row: a sign `<select>` and item `<select>` populated from the bequests of the selected will (occupied signs only, in vector order), and a beneficiary `<input type="text">` (free text — typing the wrong name is how `beneficiary_unknown` occurs in real casework).
- An "Add row" mechanism. Because no JavaScript is required, this may be implemented as a numeric `<input>` for "number of distributions" that, on form submission to a helper route, reloads the builder with that many rows pre-populated.
- A "Submit for adjudication" button that posts to `POST /adjudicate`.

**REQ-5.3** The builder submission sends `POST /adjudicate` with a `builder` field set to `1` (to distinguish from a preset submission) plus `will_seal`, `row_count`, and per-row fields `sign_N`, `item_N`, `beneficiary_N` (where N is a zero-based integer).

**REQ-5.4** The server constructs a `Claim` via `make_distribution_claim(will_ref, distributions)`, calls `gate_core.adjudicate()`, appends the receipt to the house chain (unless `MandateTamperError` is raised), and renders the full receipt on the response page.

**REQ-5.5** The builder may not pre-fill beneficiary fields with values from the fixture. Sign and item dropdowns are populated from fixture data; the beneficiary is always typed by the user.

### Acceptance criteria

- AC-5.1: `GET /desk` response body contains a `<select>` element whose options include the 2019 and 2024 will seal prefixes.
- AC-5.2: The builder sign dropdowns for the 2024 will contain exactly the seven occupied signs in vector order.
- AC-5.3: `POST /adjudicate` with valid `builder=1` parameters for a correct distribution returns a `PASS` receipt.
- AC-5.4: `POST /adjudicate` with `builder=1` and a wrong beneficiary returns a `beneficiary_unknown` refusal.
- AC-5.5: No beneficiary input in the builder form has a `value` attribute pre-filled from fixture data.

---

## 6. Receipt rendering

**REQ-6.1** Every adjudication response renders the complete receipt. No fields are truncated or omitted for aesthetic reasons. The following fields must all appear:

- `claim` (domain, claim\_type, payload in full)
- `measurements` (all observations, or `null` if unmeasured)
- `measurement_error` (if present)
- `verdict` (type and refusal name if refused)
- `timestamp_utc`
- `previous_hash` (64 hex characters)
- `own_hash` (64 hex characters)

**REQ-6.2** Hashes are rendered as monospaced text. They are not truncated.

**REQ-6.3** For `MandateTamperError` (Scenario G), no receipt object exists. The server renders a synthetic refusal notice — distinct from a real receipt — with the label `seal_broken` and the note "Mandate seal verification failed. This event was not recorded in the house chain." The notice must not include `previous_hash` or `own_hash` fields, making it visually distinguishable from a real receipt.

### Acceptance criteria

- AC-6.1: The response to `POST /adjudicate?preset=A` contains the 64-character own_hash.
- AC-6.2: The response to `POST /adjudicate?preset=A` contains the full `previous_hash` (64 hex chars or `"0" * 64` for the first receipt).
- AC-6.3: The response to `POST /adjudicate?preset=G` does NOT contain `own_hash` or `previous_hash` fields; it contains the text "seal_broken".

---

## 7. Verdict state styling

These rules are binding. They apply everywhere a claim or verdict is displayed.

**REQ-7.1 Ghost (unmeasured):** Claims that have not yet been adjudicated are rendered in ghost-gray (`#9a938a`). Text is set at reduced opacity in the paper-ledger serif; no verdict badge is shown.

**REQ-7.2 PASS:** The verdict block is rendered in full ink (`#1a1714`). A seal-mark character (e.g. `✦` or a Unicode seal glyph) appears adjacent to the PASS label. No color other than ink is used.

**REQ-7.3 REFUSED:** The verdict block displays the refusal name styled as a stamp in muted oxblood (`#7a2e2a`). The format is `REFUSED · <refusal_name>` (middle dot separator). The stamp uses uppercase tracking (CSS `letter-spacing`).

**REQ-7.4 Animation:** The only permitted animation is the CSS transition from ghost styling to solid ink styling at the moment a verdict returns. This transition must be implemented as a CSS `transition` on `color` and `opacity`. No other animation, keyframe, or motion effect is used anywhere in the application.

**REQ-7.5** The 2019 will in the Register is displayed in ghost styling regardless of adjudication state, as it is the superseded document.

### Acceptance criteria

- AC-7.1: The CSS block in any rendered page contains `color: #9a938a` for the ghost class.
- AC-7.2: The CSS block contains `color: #7a2e2a` for the refused/stamp class.
- AC-7.3: All occurrences of `REFUSED` in the rendered HTML are accompanied by the refusal name in the format `REFUSED · <name>`.
- AC-7.4: The only `@keyframes` or `animation:` declarations in the CSS are absent; `transition:` declarations are limited to color/opacity on the verdict-state class.
- AC-7.5: The 2019 will section in `GET /` carries the ghost CSS class.

---

## 8. House chain semantics

**REQ-8.1** The server maintains one append-only house chain in memory (a `list[Receipt]`). It is initialised empty at server startup.

**REQ-8.2** Every call to `gate_core.adjudicate()` that returns normally (i.e., does not raise `MandateTamperError`) appends the returned receipt to the house chain. This includes all scenarios A–F.

**REQ-8.3** When `MandateTamperError` is raised (Scenario G), the server catches it and does NOT append anything to the house chain. The chain length is unchanged.

**REQ-8.4** No route or operation other than a successful `adjudicate()` call may append to the house chain.

**REQ-8.5** The house chain is not persisted to disk in this version. It lives only in the server process's memory.

### Acceptance criteria

- AC-8.1: After a fresh server start with no adjudications, `GET /archive` shows an empty chain.
- AC-8.2: After `POST /adjudicate` with `preset=A`, the chain has exactly one receipt; after `preset=B`, exactly two; after all presets A–F run, exactly six receipts (G produces none).
- AC-8.3: `POST /adjudicate` with `preset=G` does not increase the chain length.
- AC-8.4: `GET /archive` always shows exactly the receipts produced by adjudication calls in the order they were appended.

---

## 9. Archive room

**REQ-9.1** `GET /archive` renders every receipt in the house chain in append order (oldest first), each displaying all fields specified in §6.

**REQ-9.2** The Archive includes a "Verify chain integrity" control. Activating it triggers `POST /archive/verify` (a plain HTML form), which calls `gate_core.verify_chain()` on the house chain and renders the `ReplayResult`:
- If `ok=True`: a clean notice "Chain intact — N receipts verified."
- If `ok=False`: the failure index and failure reason displayed clearly.

**REQ-9.3** The Archive includes a "Tamper demonstration" section. Activating it sends `POST /archive/tamper-demo`. The server:
1. Makes a deep copy of the house chain.
2. Mutates one field in a receipt in the copy (e.g., changes a beneficiary name in the `claim` dict of the last receipt).
3. Calls `gate_core.verify_chain()` on the mutated copy.
4. Renders the `ReplayResult` showing chain failure.
5. Does NOT modify the house chain. The house chain is unchanged by this demonstration.

**REQ-9.4** The tamper demonstration result page includes the text "The house chain was not modified." to make the demonstration semantics explicit.

### Acceptance criteria

- AC-9.1: `GET /archive` response body contains all receipt `own_hash` values currently in the house chain.
- AC-9.2: `POST /archive/verify` on an unmodified chain returns HTTP 200 with "Chain intact".
- AC-9.3: `POST /archive/tamper-demo` returns HTTP 200 with a failure result from `verify_chain()` and the text "The house chain was not modified."
- AC-9.4: After `POST /archive/tamper-demo`, `POST /archive/verify` still returns "Chain intact" (confirming the house chain was not mutated).

---

## 10. No decision logic in the web layer

**REQ-10.1** The web layer (all code in `webui/`) contains no verdict logic, no measurement logic, and no mandate-verification logic. It may not replicate, shadow, or short-circuit any behavior implemented in `gate_core` or `executor`.

**REQ-10.2** All adjudication is performed by calling `gate_core.adjudicate(claim, sealed_mandate, measurer, chain, timestamp_utc=...)`. The web layer passes the arguments and renders what returns.

**REQ-10.3** `MandateTamperError` is caught by the web layer solely for the purpose of rendering the `seal_broken` notice (§6.3) and suppressing the chain append. The web layer does not inspect the exception to make any decision; it renders the fixed `seal_broken` label.

**REQ-10.4** The web layer does not filter, suppress, modify, or override any verdict returned by `adjudicate()`.

### Acceptance criteria

- AC-10.1: No function in `webui/` imports from `gate_core.gate` except to call `adjudicate()` and catch `MandateTamperError`.
- AC-10.2: No function in `webui/` calls `verify_mandate()`, `measure()`, or `make_pass()`/`make_refused()` directly.
- AC-10.3: Code review confirms zero conditional branches in `webui/` that alter a verdict value.

---

## 11. Input escaping

**REQ-11.1** All user-supplied strings inserted into HTML responses are escaped with `html.escape()` before rendering. This includes beneficiary names from builder form submissions, will seal values from form fields, and any other form input.

**REQ-11.2** Fixture-sourced data (will content, death record content, scenario descriptions) is also escaped when inserted into HTML, as a defense-in-depth measure.

### Acceptance criteria

- AC-11.1: No raw `str.format()` or f-string interpolation of form field values appears in `webui/render.py` without a wrapping `html.escape()` call.
- AC-11.2: Submitting a beneficiary name containing `<script>alert(1)</script>` via the builder results in the literal text `&lt;script&gt;alert(1)&lt;/script&gt;` appearing in the response body, not an executed script.
