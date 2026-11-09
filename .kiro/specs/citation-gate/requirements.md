# Requirements — Citation Gate Desk

## Overview

The Citation Gate desk processes factual assertions in an obituary draft against sealed source records — a death record, the governing will, and a family record. It is an application built on top of the gate_core library; it reuses `adjudicate()` without modification and registers its domain-specific source registry, measurement logic, and refusal vocabulary within the framework gate_core defines.

A sealed source record is the mandate. A factual assertion — one sentence as it will appear in print — is the claim. No assertion may appear in the published obituary until its verdict is `PASS`. Every verdict — pass or refused — produces a hash-chained receipt. An obituary draft may not be published until every one of its assertions has a `PASS` receipt in the desk's chain.

---

## Domain Model

### The Source Records

The desk holds three sealed source records. Each is sealed as a `gate_core.SealedMandate` under domain `"citation"`. Each exposes a flat fact table of key-value pairs derived from its content.

#### Death Record

| Fixture field | Fact key | Example value |
|---|---|---|
| `deceased` | `deceased` | `"Elias Vane"` |
| `date_of_death` | `date_of_death` | `"2026-10-28"` |
| `place` | `place` | `"Hollow Hill"` |
| `registrar` | `registrar` | `"Registrar of Hollow Hill County"` |

Source id: `"death_record"`.

#### Family Record

| Fixture field | Fact key | Example value |
|---|---|---|
| `person` | `person` | `"Elias Vane"` |
| `born` | `born` | `"1941-03-14"` |
| `birthplace` | `birthplace` | `"Hollow Hill"` |
| `occupation` | `occupation` | `"keeper of the Hollow Hill light (retired)"` |
| `residence` | `residence` | `"the cottage on Hollow Hill"` |

Source id: `"family_record"`.

#### Will (2024)

One fact is produced per bequest field, **only for occupied signs**. Empty signs have no fact table entries.

| Fact key pattern | Example key | Example value |
|---|---|---|
| `bequest.<Sign>.item` | `bequest.Taurus.item` | `"The Stone Bull"` |
| `bequest.<Sign>.beneficiary` | `bequest.Taurus.beneficiary` | `"Marta, the neighbor"` |

Source id: `"will_2024"`.

The occupied signs in the Elias Vane 2024 will are: Aries, Taurus, Leo, Scorpio, Capricorn, Aquarius, Pisces. The empty signs — Gemini, Cancer, Virgo, Libra, Sagittarius — produce no fact keys. A claim asserting a fact under an empty sign citing `will_2024` will fail at step (4) of measurement with refusal `unsupported_claim`.

### The Claim

A factual assertion is the unit of work submitted to the gate.

| Field | Type | Notes |
|---|---|---|
| `domain` | string | Always `"citation"`. |
| `claim_type` | string | Always `"factual_assertion"`. |
| `payload.text` | string | The sentence exactly as it will appear in the published obituary. |
| `payload.fact_key` | string | The key being asserted (e.g. `"date_of_death"`, `"bequest.Taurus.item"`). |
| `payload.value` | string | The value being asserted for that key. |
| `payload.citation` | string or null | Source id string: `"death_record"`, `"will_2024"`, or `"family_record"`. `null` or empty string means no citation was provided. |

### The Obituary Draft

An obituary draft is an ordered list of factual assertions. Each assertion is submitted to the gate independently; each produces its own receipt in the desk's chain. The draft as a whole has a logical draft id used by the publish checker to locate its receipts.

---

## Refusal Vocabulary

The citation gate registers the following names for domain `"citation"`. The gate_core reserved name `"unmeasured"` is also present in the vocabulary without explicit registration.

| Refusal name | Meaning |
|---|---|
| `missing_citation` | The assertion names no source (`citation` is `null` or empty). |
| `unsupported_claim` | The cited source exists but does not contain the asserted `fact_key`; or the cited source id is not in the registry. |
| `source_contradicts` | The cited source contains the `fact_key` but its stored value differs from the asserted `value`. |
| `unmeasured` | *(reserved by gate_core)* Measurement did not complete. |

---

## Measurement Precedence

Measurement of one factual assertion is deterministic. The **first** failing check names the refusal and measurement stops. Subsequent checks are not reported.

1. **Citation present?** — if `payload.citation` is `null` or an empty string, return `passed=False, refusal_name='missing_citation'`.
2. **Source known?** — if `payload.citation` does not name a registered source id, return `passed=False, refusal_name='unsupported_claim'`.
3. **Source seal intact?** — call `gate_core.verify_mandate` on the cited source's `SealedMandate`. If it returns `False`, raise `gate_core.MandateTamperError`. This is a hard error, not a refusal verdict; it propagates from `adjudicate()` without appending a receipt.
4. **Fact key in table?** — look up `payload.fact_key` in the cited source's fact table. If the key is absent, return `passed=False, refusal_name='unsupported_claim'`.
5. **Value matches?** — compare the fact table's value for `payload.fact_key` to `payload.value`. If they differ, return `passed=False, refusal_name='source_contradicts'`.
6. **Pass** — all checks satisfied; return `passed=True`.

> **Note on step 3 vs. the mandate passed to `adjudicate()`:** `gate_core.adjudicate()` calls `verify_mandate` on the `SealedMandate` it receives as its `mandate` argument. In the citation gate, the mandate argument is the desk's governing mandate (a registry-wide sealed record representing the desk's authority), not the individual cited source. The seal check in step 3 is performed by the measurer on the *cited source's* `SealedMandate` retrieved from the source registry. These are two distinct checks. A tamper on the desk's governing mandate causes `MandateTamperError` from the gate before measurement begins; a tamper on a cited source record causes `MandateTamperError` from inside `measure()`, which gate_core catches and converts to `REFUSED('unmeasured')` — unless the measurer deliberately re-raises it, which is the preferred design here so tampering is surfaced as a hard error rather than silently becoming `unmeasured`.

---

## Publish Rule

An obituary draft may be published only when every assertion in the draft has been adjudicated with a `PASS` verdict and each `PASS` receipt is present in the desk's chain.

The publish check is performed by a `PublishChecker` function that accepts a draft id and the desk's receipt chain. It returns either:

- `{'publishable': True, 'receipt_ids': [...]}` — a list of the `own_hash` values of the `PASS` receipts for all assertions in the draft, in assertion order; or
- `{'publishable': False, 'refusal_name': '...'}` — the refusal name of the **first** assertion that is not `PASS`.

A draft with zero assertions is not publishable.

---

## Rendering Rule (State Language)

Per the product steering, the rendering state of each assertion in a draft follows this progression:

| Verdict state | Display form |
|---|---|
| Not yet submitted / pending | Ghost text (unresolved) |
| `REFUSED(any name)` | Marked clearly; the refusal name is visible; ghost text treatment preserved |
| `PASS` | Resolves to solid type |

No assertion transitions to solid type without a `PASS` receipt in the desk's chain. The UI reads verdicts from receipts; it never sets them.

---

## User Stories and Acceptance Criteria

### US-CG-1 — Seal and Register a Source Record

**As a** clerk admitting a source record to the desk,
**I want to** seal the source record's JSON content and store it in the registry,
**so that** any subsequent alteration of the record is detectable before measurement.

**Acceptance Criteria**

- AC-CG-1.1: Sealing a source record calls `gate_core.seal_mandate` with domain `"citation"` and the record's JSON content. The returned `SealedMandate` is stored in the registry under the record's source id.
- AC-CG-1.2: The registry holds exactly three source records at initialisation: `"death_record"`, `"will_2024"`, and `"family_record"`. Fixture paths are injected, not hard-coded.
- AC-CG-1.3: The registry exposes a `source(source_id: str) -> SealedMandate | None` operation that returns the sealed record for the given id, or `None` if not registered.
- AC-CG-1.4: The registry exposes a `fact_table(source_id: str) -> dict[str, str] | None` operation that returns the flat fact table derived from the source's content, or `None` if the source id is not registered.

---

### US-CG-2 — Derive a Flat Fact Table from Each Source Record

**As a** measurer,
**I want to** look up any fact key in a source's flat table,
**so that** I can compare the asserted value to the record's stored value without parsing the source's internal structure at measure time.

**Acceptance Criteria**

- AC-CG-2.1: The death record's fact table contains exactly four keys: `deceased`, `date_of_death`, `place`, `registrar`.
- AC-CG-2.2: The family record's fact table contains exactly five keys: `person`, `born`, `birthplace`, `occupation`, `residence`.
- AC-CG-2.3: The 2024 will's fact table contains exactly two keys per occupied sign: `bequest.<Sign>.item` and `bequest.<Sign>.beneficiary`. With seven occupied signs, the table has 14 keys.
- AC-CG-2.4: Empty signs (Gemini, Cancer, Virgo, Libra, Sagittarius in the 2024 will) produce no keys in the fact table.
- AC-CG-2.5: Fact table values are strings. The extractor converts non-string primitive values (e.g. dates stored as strings in the fixture JSON) directly; no type coercion beyond what `json.load` already performs.

---

### US-CG-3 — Submit a Factual Assertion Claim

**As a** notices clerk drafting an obituary,
**I want to** submit each factual sentence as a typed claim,
**so that** the gate can adjudicate whether the sentence is supported by a source record.

**Acceptance Criteria**

- AC-CG-3.1: The claim has `domain="citation"`, `claim_type="factual_assertion"`, and a payload containing `text`, `fact_key`, `value`, and `citation`.
- AC-CG-3.2: The `claims` helper constructs a valid `gate_core.Claim` from plain arguments without the caller needing to import gate_core directly.
- AC-CG-3.3: The claim is immutable after construction (inherits `frozen=True` from `gate_core.Claim`).
- AC-CG-3.4: `citation` may be `null` (Python `None`); the helper encodes this as `None` in the payload dict, which is JSON-serialisable.

---

### US-CG-4 — Adjudicate a Factual Assertion

**As a** notices desk,
**I want to** adjudicate each factual assertion against the sealed source records,
**so that** no sentence enters the published obituary without documented support.

**Acceptance Criteria**

- AC-CG-4.1: Adjudication calls `gate_core.adjudicate(claim, desk_mandate, measurer, chain)` exactly once per assertion. No citation gate code re-derives the mandate-verification or receipt-chaining logic.
- AC-CG-4.2: The `CitationMeasurer` performs the precedence checks in the order defined in the Measurement Precedence section above.
- AC-CG-4.3: On `PASS`, the verdict is `gate_core.Pass`. The receipt records the source id, the fact key, the asserted value, and the stored value as observations.
- AC-CG-4.4: On `REFUSED`, the verdict is `gate_core.Refused` with exactly one name from the citation refusal vocabulary. The receipt records the refusal name and the observation that triggered it.
- AC-CG-4.5: A tampered cited source (bytes altered after sealing) causes `gate_core.MandateTamperError` to propagate from the measurer. Because gate_core catches all measurer exceptions and converts them to `REFUSED('unmeasured')`, a tampered source results in `REFUSED('unmeasured')` unless the measurer explicitly re-raises `MandateTamperError` — which it does, so that source tampering is never silent. The receipt for a tampered-source case is therefore absent from the chain (the error propagates before receipt append).

---

### US-CG-5 — Check Whether a Draft Is Publishable

**As a** notices clerk,
**I want to** ask the desk whether an obituary draft is ready for publication,
**so that** I know at a glance whether all sentences have been verified and can release the text.

**Acceptance Criteria**

- AC-CG-5.1: The publish check accepts a draft id and the desk's receipt chain and inspects the receipts associated with that draft.
- AC-CG-5.2: If every assertion in the draft has a `PASS` receipt, the check returns `publishable=True` and the list of receipt `own_hash` values, in assertion order.
- AC-CG-5.3: If any assertion in the draft has a `REFUSED` receipt, or has not yet been adjudicated, the check returns `publishable=False` and the refusal name of the **first** non-passing assertion.
- AC-CG-5.4: A draft with zero assertions returns `publishable=False`.
- AC-CG-5.5: The publish check does not call `adjudicate()`. It only inspects existing receipts in the chain.

---

### US-CG-6 — Produce a Hash-Chained Receipt for Every Verdict

**As a** compliance officer,
**I want** every citation gate verdict to be recorded in a hash-chained receipt,
**so that** the full adjudication history for an obituary draft is tamper-evident.

**Acceptance Criteria**

- AC-CG-6.1: Each call to `adjudicate` appends exactly one receipt to the chain (unless `MandateTamperError` is raised or propagates from the measurer).
- AC-CG-6.2: The receipt chain can be verified by `gate_core.verify_chain` and returns `ok=True` for a chain of legitimately issued receipts.
- AC-CG-6.3: Each receipt's observations include at minimum: `source_id`, `fact_key`, `asserted_value`; on `PASS` also `stored_value`; on refusal also `refusal_name` and enough context to explain the failure.

---

## Acceptance Scenarios (Demo)

These six scenarios are the concrete acceptance tests for the citation gate desk. They use the Elias Vane fixtures.

---

**Scenario N1 — Clean draft, all assertions supported → all PASS, publishable**

A three-assertion draft citing each of the three source records.

```
Assertions:
  1. text: "Elias Vane died on 28 October 2026."
     fact_key: "date_of_death"
     value:    "2026-10-28"
     citation: "death_record"

  2. text: "He bequeathed The Stone Bull to Marta, the neighbor."
     fact_key: "bequest.Taurus.item"
     value:    "The Stone Bull"
     citation: "will_2024"

  3. text: "He served as keeper of the Hollow Hill light (retired)."
     fact_key: "occupation"
     value:    "keeper of the Hollow Hill light (retired)"
     citation: "family_record"
```

Expected: all three verdicts `PASS`; chain length 3; `verify_chain` returns `ok=True`; publish check returns `publishable=True` with three receipt ids.

---

**Scenario N2 — Wrong beneficiary for Scorpio → REFUSED `source_contradicts`**

```
Assertion:
  text:     "He bequeathed The Sealed Letter to Marta, the neighbor."
  fact_key: "bequest.Scorpio.beneficiary"
  value:    "Marta, the neighbor"
  citation: "will_2024"
```

The will's stored value for `bequest.Scorpio.beneficiary` is `"the one who knows what happened at the millpond in '87"`. The asserted value differs.

Expected: verdict `REFUSED('source_contradicts')`; observations include `fact_key`, `asserted_value`, `stored_value`.

---

**Scenario N3 — Bequest claimed under empty sign Gemini → REFUSED `unsupported_claim`**

```
Assertion:
  text:     "He left The Twin Lanterns to the two apprentices."
  fact_key: "bequest.Gemini.item"
  value:    "The Twin Lanterns"
  citation: "will_2024"
```

Gemini is an empty sign; the will's fact table has no key `bequest.Gemini.item`.

Expected: verdict `REFUSED('unsupported_claim')`; observations include `fact_key` and `source_id`.

---

**Scenario N4 — No citation provided → REFUSED `missing_citation`**

```
Assertion:
  text:     "He was born in Hollow Hill."
  fact_key: "birthplace"
  value:    "Hollow Hill"
  citation: null
```

Expected: verdict `REFUSED('missing_citation')`; observations include `fact_key`.

---

**Scenario N5 — Mixed draft: one contradicted assertion among good ones → publish refused; after correction, publishable**

A draft with two good assertions and one contradicted assertion.

```
Assertions:
  1. text: "Elias Vane died on 28 October 2026."
     fact_key: "date_of_death"
     value:    "2026-10-28"
     citation: "death_record"
     → expected PASS

  2. text: "He was born in Galway."
     fact_key: "birthplace"
     value:    "Galway"
     citation: "family_record"
     → expected REFUSED('source_contradicts')  [stored value is "Hollow Hill"]

  3. text: "He served as keeper of the Hollow Hill light (retired)."
     fact_key: "occupation"
     value:    "keeper of the Hollow Hill light (retired)"
     citation: "family_record"
     → expected PASS
```

After adjudicating all three: publish check returns `publishable=False, refusal_name='source_contradicts'` (the first non-passing assertion is assertion 2).

Then correct assertion 2:

```
  2. text: "He was born in Hollow Hill."
     fact_key: "birthplace"
     value:    "Hollow Hill"
     citation: "family_record"
     → expected PASS
```

Adjudicate the corrected assertion and append its receipt to the chain. Publish check with the updated receipts returns `publishable=True` with three receipt ids.

---

**Scenario N6 — Unknown source id → REFUSED `unsupported_claim`**

```
Assertion:
  text:     "He was known to the parish register."
  fact_key: "person"
  value:    "Elias Vane"
  citation: "parish_register"
```

`"parish_register"` is not a registered source id.

Expected: verdict `REFUSED('unsupported_claim')`; observations include `citation` value and note that the source is not registered.
