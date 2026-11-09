# Technical Design — Citation Gate Desk

## Constraints

- Python 3.11+, standard library only.
- No external dependencies beyond `gate_core`.
- `citation_gate` imports from `gate_core`; it does not import from `executor` or `webui`.
- `gate_core` imports nothing from `citation_gate`.
- Fixture file paths are injected at registry construction time; no paths are hard-coded in logic modules.
- All measurement and adjudication logic lives in `citation_gate`; no UI or network access.

---

## Package Layout

```
citation_gate/
    __init__.py    — re-exports public API; registers citation refusal vocabulary
    sources.py     — loads fixture JSON, seals source records, builds fact tables, answers registry queries
    measurer.py    — CitationMeasurer implementing gate_core MeasurementProtocol
    claims.py      — helper to build factual_assertion Claims from plain arguments
    publish.py     — PublishChecker: inspects receipt chain for a draft and returns publish/refuse decision
    scenarios.py   — six demo scenarios N1-N6 as data + runner
```

This package lives beside `gate_core/` and `executor/` at the same directory level:

```
skeleton-crew/
    gate_core/
        ...
    executor/
        ...
    citation_gate/
        ...
    fixtures/
        death_record.json
        will_2024.json
        family_record.json
```

---

## Dependency Graph

```
sources.py    ← gate_core.mandate (seal_mandate, verify_mandate)
measurer.py   ← gate_core.measure (MeasurementResult)
              ← gate_core.mandate (verify_mandate, MandateTamperError)
              ← sources.py
claims.py     ← gate_core.claim (Claim)
publish.py    ← gate_core.receipt (Receipt)
              ← gate_core.verdict (Pass, Refused)
scenarios.py  ← gate_core.gate (adjudicate)
              ← gate_core.receipt (verify_chain)
              ← sources.py
              ← measurer.py
              ← claims.py
              ← publish.py
__init__.py   ← gate_core.verdict (register_refusal)
              ← all submodules
```

No circular dependencies. `gate_core` has no import from `citation_gate`. `citation_gate` has no import from `executor`.

---

## `sources.py`

### Purpose

Loads the three source record fixtures from JSON files, seals each as a `gate_core.SealedMandate`, derives a flat fact table from each, and answers queries needed by the measurer.

### Public API

```python
class SourceRegistry:
    def __init__(
        self,
        death_record_path: str,
        will_path: str,
        family_record_path: str,
    ) -> None: ...

    def source(self, source_id: str) -> SealedMandate | None: ...
    def fact_table(self, source_id: str) -> dict[str, str] | None: ...
    def known_source_ids(self) -> frozenset[str]: ...
```

### Construction

`__init__` reads each path with `json.load`, calls `gate_core.seal_mandate(domain="citation", content=data)` for each, and stores the returned `SealedMandate` objects in an internal dict keyed by source id. It also calls the appropriate extractor function for each source and caches the resulting fact table.

```python
_sources: dict[str, SealedMandate] = {
    "death_record": seal_mandate("citation", death_record_data),
    "will_2024":    seal_mandate("citation", will_data),
    "family_record": seal_mandate("citation", family_record_data),
}
_fact_tables: dict[str, dict[str, str]] = {
    "death_record": _extract_death_record_facts(death_record_data),
    "will_2024":    _extract_will_facts(will_data),
    "family_record": _extract_family_record_facts(family_record_data),
}
```

### `source(source_id)`

Returns the `SealedMandate` for `source_id`, or `None` if not registered.

### `fact_table(source_id)`

Returns the cached flat fact table for `source_id`, or `None` if not registered.

### `known_source_ids()`

Returns a `frozenset` of the registered source id strings. Used by the measurer at step (2) to check whether a citation names a known source before attempting further lookup.

### Extractor Functions (module-private)

```python
def _extract_death_record_facts(data: dict) -> dict[str, str]:
    return {
        "deceased":      data["deceased"],
        "date_of_death": data["date_of_death"],
        "place":         data["place"],
        "registrar":     data["registrar"],
    }

def _extract_family_record_facts(data: dict) -> dict[str, str]:
    return {
        "person":     data["person"],
        "born":       data["born"],
        "birthplace": data["birthplace"],
        "occupation": data["occupation"],
        "residence":  data["residence"],
    }

def _extract_will_facts(data: dict) -> dict[str, str]:
    facts: dict[str, str] = {}
    for bequest in data.get("bequests", []):
        sign = bequest["sign"]
        facts[f"bequest.{sign}.item"]        = bequest["item"]
        facts[f"bequest.{sign}.beneficiary"] = bequest["beneficiary"]
    return facts
    # empty_signs produce no keys; the loop only iterates over bequests that exist
```

All extractor functions return plain string-to-string dicts. No type conversion is required; the fixture JSON values are already strings.

### Notes

- The registry does not validate source content semantics. That is the measurer's job.
- Fact tables are built from the raw JSON data at construction time, before sealing, so they always reflect the content that was sealed. If the `SealedMandate` is later found to have a broken seal, it means the stored bytes diverge from what was originally hashed — but the in-memory fact table remains the pre-seal snapshot, which is correct for audit purposes.
- Fixture paths are injected; the registry has no knowledge of where `fixtures/` is located on disk.

---

## `measurer.py`

### Purpose

Implements `gate_core.MeasurementProtocol`. Performs all precedence checks in deterministic order and returns a `MeasurementResult`. Has no knowledge of verdicts; it only observes and reports.

### Class

```python
class CitationMeasurer:
    def __init__(self, registry: SourceRegistry) -> None: ...

    def measure(
        self,
        claim: Claim,
        mandate: SealedMandate,
    ) -> MeasurementResult: ...
```

`mandate` passed to `measure()` is the desk's governing `SealedMandate` (the same object passed to `gate_core.adjudicate()`). The measurer also retrieves cited-source mandates from the registry for its own seal check at step (3).

### Measurement Algorithm

All observations are collected in a plain dict and included in the returned `MeasurementResult.observations`. On any failure the function returns immediately with `passed=False` and `observations["refusal_name"]` set. The function never returns without setting `refusal_name` when `passed=False`.

```
citation  = claim.payload.get("citation")
fact_key  = claim.payload["fact_key"]
value     = claim.payload["value"]

1. CITATION PRESENT?
   if not citation:                    # None, "", or any falsy string
       return MeasurementResult(
           observations={
               "refusal_name": "missing_citation",
               "fact_key": fact_key,
           },
           passed=False,
       )

2. SOURCE KNOWN?
   if citation not in registry.known_source_ids():
       return MeasurementResult(
           observations={
               "refusal_name": "unsupported_claim",
               "citation": citation,
               "reason": "source_not_registered",
               "fact_key": fact_key,
           },
           passed=False,
       )

3. SOURCE SEAL INTACT?
   source_mandate = registry.source(citation)
   if not verify_mandate(source_mandate):
       raise MandateTamperError(
           f"Source record '{citation}' seal verification failed"
       )
   # MandateTamperError propagates; gate_core.adjudicate() does NOT catch it
   # (the gate catches generic Exception but re-raises MandateTamperError)

4. FACT KEY IN TABLE?
   table = registry.fact_table(citation)
   if fact_key not in table:
       return MeasurementResult(
           observations={
               "refusal_name": "unsupported_claim",
               "source_id": citation,
               "fact_key": fact_key,
               "reason": "fact_key_not_in_source",
           },
           passed=False,
       )

5. VALUE MATCHES?
   stored_value = table[fact_key]
   if stored_value != value:
       return MeasurementResult(
           observations={
               "refusal_name": "source_contradicts",
               "source_id": citation,
               "fact_key": fact_key,
               "asserted_value": value,
               "stored_value": stored_value,
           },
           passed=False,
       )

6. PASS
   return MeasurementResult(
       observations={
           "source_id": citation,
           "fact_key": fact_key,
           "asserted_value": value,
           "stored_value": stored_value,
           "source_seal": source_mandate.seal,
       },
       passed=True,
   )
```

### Notes on `MandateTamperError` Propagation

`gate_core.adjudicate()` wraps `measurer.measure()` in a `try/except Exception`. `MandateTamperError` is a subclass of `Exception`. The gate's intent (per gate_core design) is to catch measurer exceptions and produce `REFUSED('unmeasured')`. However, the citation gate explicitly wants tamper events to surface as hard errors, not silent `unmeasured` refusals. Two approaches are available:

**Approach A (preferred):** `gate_core.adjudicate()` re-raises `MandateTamperError` specifically before falling back to `unmeasured`. This requires a small addition to gate_core's `adjudicate()` implementation: `except MandateTamperError: raise` before `except Exception`.

**Approach B (fallback):** The citiation gate measurer wraps its own seal check in a way that produces a distinctive `unmeasured` receipt, and the unit tests accept `REFUSED('unmeasured')` for the tamper case. This approach is weaker from an audit standpoint.

The design **specifies Approach A**. If gate_core is not yet updated, the citation gate unit test for this case documents the expected behaviour and is marked as pending gate_core update.

---

## `claims.py`

### Purpose

Provides a thin factory function so callers can construct a `factual_assertion` claim from plain arguments without importing `gate_core` directly.

### Public API

```python
def make_assertion_claim(
    text: str,
    fact_key: str,
    value: str,
    citation: str | None,
) -> Claim:
    """
    Build a gate_core.Claim for a factual assertion.

    Args:
        text:      The sentence exactly as it will appear in the published obituary.
        fact_key:  The key being asserted (e.g. "date_of_death", "bequest.Taurus.item").
        value:     The value being asserted for that key.
        citation:  Source id string ("death_record", "will_2024", "family_record"),
                   or None if no citation is provided.

    Returns:
        gate_core.Claim with domain="citation", claim_type="factual_assertion".
    """
```

### Implementation

```python
from gate_core.claim import Claim

def make_assertion_claim(
    text: str,
    fact_key: str,
    value: str,
    citation: str | None,
) -> Claim:
    return Claim(
        domain="citation",
        claim_type="factual_assertion",
        payload={
            "text": text,
            "fact_key": fact_key,
            "value": value,
            "citation": citation,
        },
    )
```

`None` is JSON-serialisable (it serialises to `null`). No additional validation beyond what `gate_core.Claim.__post_init__` performs.

---

## `publish.py`

### Purpose

Implements the publish check: given a draft id and the desk's receipt chain, decides whether the draft is publishable or names the first failing refusal.

### Public API

```python
from dataclasses import dataclass
from gate_core.receipt import Receipt

@dataclass(frozen=True)
class PublishDecision:
    publishable: bool
    receipt_ids: list[str] | None    # own_hash values in assertion order; None if not publishable
    refusal_name: str | None         # first failing refusal name; None if publishable

def check_publish(
    draft_id: str,
    assertion_claim_hashes: list[str],
    chain: list[Receipt],
) -> PublishDecision:
    """
    Inspect the receipt chain to determine if a draft is publishable.

    Args:
        draft_id:               Logical identifier for the draft (used only for labelling).
        assertion_claim_hashes: Ordered list of canonical JSON hashes of each assertion's
                                Claim, in draft assertion order. Used to locate each
                                assertion's receipt in the chain.
        chain:                  The desk's receipt chain (list of Receipt objects).

    Returns:
        PublishDecision.
    """
```

### Algorithm

```
if not assertion_claim_hashes:
    return PublishDecision(publishable=False, receipt_ids=None, refusal_name="missing_citation")
    # A draft with no assertions is not publishable; "missing_citation" is the closest
    # available refusal, but implementations may choose a dedicated empty-draft path.

receipt_by_claim = {
    canonical_json(r.claim): r
    for r in chain
}

pass_ids: list[str] = []

for claim_hash in assertion_claim_hashes:
    receipt = receipt_by_claim.get(claim_hash)
    if receipt is None:
        # Assertion was never adjudicated
        return PublishDecision(publishable=False, receipt_ids=None, refusal_name="unmeasured")
    if receipt.verdict["type"] != "pass":
        refusal = receipt.verdict.get("name", "unmeasured")
        return PublishDecision(publishable=False, receipt_ids=None, refusal_name=refusal)
    pass_ids.append(receipt.own_hash)

return PublishDecision(publishable=True, receipt_ids=pass_ids, refusal_name=None)
```

### Notes

- `assertion_claim_hashes` is a list of SHA-256 hex strings computed as `hashlib.sha256(canonical_json(claim.__dict__).encode()).hexdigest()`. In practice the scenarios module computes these from the claim objects it constructs, so callers do not need to hash manually.
- The publish check is a pure function. It does not call `adjudicate()` or modify the chain.
- An alternative design indexes receipts by draft id stored in the claim payload. Either approach is valid; the hash-based lookup is chosen here because it requires no changes to the claim payload schema and works naturally with the hash-chained receipt structure gate_core provides.

---

## `scenarios.py`

### Purpose

Defines the six demo scenarios N1–N6 as structured data and provides a runner that adjudicates each against a fresh receipt chain and evaluates the publish rule.

### Data Structures

```python
from dataclasses import dataclass, field
from gate_core.receipt import Receipt
from gate_core.verdict import Verdict

@dataclass
class AssertionResult:
    text: str
    fact_key: str
    verdict: Verdict
    receipt: Receipt

@dataclass
class DraftResult:
    label: str              # e.g. "N1"
    description: str
    assertion_results: list[AssertionResult]
    chain: list[Receipt]
    publish_decision: PublishDecision
```

### Scenario Definitions

Each scenario is expressed as a plain dict with an `assertions` list and a `description`:

```python
{
    "label": "N1",
    "description": "Clean draft — all assertions supported → PASS, publishable",
    "assertions": [
        {
            "text":     "Elias Vane died on 28 October 2026.",
            "fact_key": "date_of_death",
            "value":    "2026-10-28",
            "citation": "death_record",
        },
        {
            "text":     "He bequeathed The Stone Bull to Marta, the neighbor.",
            "fact_key": "bequest.Taurus.item",
            "value":    "The Stone Bull",
            "citation": "will_2024",
        },
        {
            "text":     "He served as keeper of the Hollow Hill light (retired).",
            "fact_key": "occupation",
            "value":    "keeper of the Hollow Hill light (retired)",
            "citation": "family_record",
        },
    ],
}
```

Scenario N5 (mixed draft corrected) is represented as two runs: `N5a` with the original incorrect assertion and `N5b` with the corrected assertion, both sharing the same logical draft id. The runner appends `N5b`'s receipt to the chain from `N5a`.

### Runner

```python
def run_scenarios(
    registry: SourceRegistry,
    desk_mandate: SealedMandate,
) -> list[DraftResult]:
    """
    Adjudicate all six demo scenarios and return their results.
    Each scenario (except N5) uses its own fresh receipt chain.
    N5 runs in two phases: first the original draft, then the corrected draft
    continuing in the same chain.
    """
```

The runner constructs a `CitationMeasurer(registry)`, iterates over the scenario's assertions, calls `make_assertion_claim(...)` for each, calls `gate_core.adjudicate(claim, desk_mandate, measurer, chain)`, collects `AssertionResult` objects, then calls `check_publish(...)` on the completed chain. Each scenario except N5 starts with an empty `chain = []`. N5 starts fresh, adjudicates three assertions (one of which will be `REFUSED`), then continues in the same chain with the corrected assertion 2 appended.

### Desk Mandate

The runner receives a `desk_mandate: SealedMandate` as an argument. This is a `SealedMandate` constructed from a minimal desk-authority content dict (e.g. `{"desk": "citation", "authority": "Hollow Hill Mortuary Notices Desk"}`) sealed under domain `"citation"`. It is the object passed as `mandate` to `gate_core.adjudicate()`. It is distinct from the per-source mandates that the measurer checks internally. This separation keeps the gate_core contract (every `adjudicate()` call has a mandate) without conflating the desk's authority mandate with the source records.

### Scenario Inventory

| Label | Assertions | Expected per-assertion verdicts | Expected publish decision |
|---|---|---|---|
| N1 | 3 (death date+place, Taurus item, occupation) | All `PASS` | `publishable=True`, 3 receipt ids |
| N2 | 1 (Scorpio beneficiary → "Marta, the neighbor") | `REFUSED('source_contradicts')` | `publishable=False, refusal_name='source_contradicts'` |
| N3 | 1 (Gemini item → anything) | `REFUSED('unsupported_claim')` | `publishable=False, refusal_name='unsupported_claim'` |
| N4 | 1 (birthplace, citation=None) | `REFUSED('missing_citation')` | `publishable=False, refusal_name='missing_citation'` |
| N5a | 3 (date_of_death PASS, birthplace wrong REFUSED, occupation PASS) | Mixed | `publishable=False, refusal_name='source_contradicts'` |
| N5b | N5a chain + corrected birthplace assertion | `PASS` | `publishable=True`, 3 receipt ids |
| N6 | 1 (person, citation="parish_register") | `REFUSED('unsupported_claim')` | `publishable=False, refusal_name='unsupported_claim'` |

---

## `__init__.py`

Registers the citation refusal vocabulary at import time and re-exports the public API.

```python
from gate_core.verdict import register_refusal

_CITATION_REFUSALS = [
    "missing_citation",
    "unsupported_claim",
    "source_contradicts",
]

for _name in _CITATION_REFUSALS:
    register_refusal("citation", _name)

from citation_gate.sources import SourceRegistry
from citation_gate.measurer import CitationMeasurer
from citation_gate.claims import make_assertion_claim
from citation_gate.publish import PublishChecker, PublishDecision, check_publish
from citation_gate.scenarios import run_scenarios, DraftResult, AssertionResult
```

Registration at import time ensures the vocabulary is in place before any `make_refused("citation", ...)` call.

---

## Error Handling Summary

| Situation | Behaviour |
|---|---|
| `citation` is `None` or `""` | Measurer returns `passed=False, refusal_name='missing_citation'` |
| `citation` names unknown source | Measurer returns `passed=False, refusal_name='unsupported_claim'` |
| Cited source seal fails | Measurer raises `MandateTamperError`; propagates from `adjudicate()`; no receipt appended |
| `fact_key` not in source's fact table | Measurer returns `passed=False, refusal_name='unsupported_claim'` |
| Source's stored value ≠ asserted value | Measurer returns `passed=False, refusal_name='source_contradicts'` |
| All checks pass | Measurer returns `passed=True`; verdict is `PASS` |
| Desk mandate tampered (passed to `adjudicate()`) | `MandateTamperError` raised by gate_core; no receipt appended |
| Measurer raises unhandled non-tamper exception | gate_core catches it; `REFUSED('unmeasured')`; receipt appended |
| Draft has no assertions | `check_publish` returns `publishable=False` |
| Draft has an unadjudicated assertion | `check_publish` returns `publishable=False, refusal_name='unmeasured'` |

---

## Design Decisions

**Why a separate desk mandate distinct from the source records?**
`gate_core.adjudicate()` requires a `SealedMandate` as its second argument. The executor passes the will directly because the will is the operative document being adjudicated against. In the citation gate, individual assertions are measured against source records retrieved inside the measurer, but no single source record is "the" mandate for all claims. A lightweight desk-authority mandate keeps the gate_core interface satisfied without overloading the role of `mandate` with source-record semantics.

**Why does `check_publish` take `assertion_claim_hashes` rather than claim objects?**
The publish checker is a pure read operation on the receipt chain. Passing hashes rather than claim objects means the checker has no dependency on `Claim` construction logic; it only needs to match receipts by their stored claim content. This also makes the function easier to call from contexts that already have the hash values (e.g. a UI that stored them when the draft was composed).

**Why are fact table values always strings?**
The fixture JSON files store all values as JSON strings. Keeping the fact table as `dict[str, str]` makes equality comparison unambiguous (no type coercion surprises) and keeps the table independent of how different sources might represent numerics or dates in other fixture schemas.

**Why does `__init__.py` register the vocabulary at import time?**
Identical reasoning to the executor: vocabulary must exist before any `make_refused("citation", ...)` call, and centralising registration in `__init__.py` ensures exactly-once execution without requiring a separate `setup()` call.

**Why does N5 continue in the same chain rather than start fresh?**
Scenario N5 models the real workflow: a clerk corrects a draft and re-adjudicates only the offending assertion. The corrected assertion's `PASS` receipt is appended to the chain that already contains the original refused receipt. The publish checker finds three `PASS` receipts for the three canonical assertions and returns `publishable=True`. This demonstrates that the chain faithfully records the full correction history, not just the final state.
