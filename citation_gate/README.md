# Citation Gate Desk

The Citation Gate desk processes factual assertions in an obituary draft
against sealed source records — a death record, the governing will, and a
family record.  It is an application built on top of `gate_core`: it reuses
`gate_core.adjudicate()` without modification and registers its
domain-specific source registry, measurement logic, and refusal vocabulary
within the framework `gate_core` defines.  A claim — one sentence as it will
appear in print — may not enter the published obituary until its verdict is
`PASS`.  Every verdict, pass or refused, produces a hash-chained receipt that
makes the full adjudication history tamper-evident.

---

## Initialise the Source Registry

```python
from citation_gate import SourceRegistry

registry = SourceRegistry(
    death_record_path="fixtures/death_record.json",
    will_path="fixtures/will_2024.json",
    family_record_path="fixtures/family_record.json",
)
```

`SourceRegistry` reads each fixture at construction time, seals it as a
`gate_core.SealedMandate` under domain `"citation"`, and caches a flat fact
table derived from the record's content.  Fixture paths are injected; none
are hard-coded in the library.

---

## Construct and Adjudicate a Factual Assertion

```python
from gate_core import adjudicate, seal_mandate
from citation_gate import CitationMeasurer, make_assertion_claim

# The desk's governing mandate — distinct from the per-source records.
desk_mandate = seal_mandate(
    "citation",
    {"desk": "citation", "authority": "Hollow Hill Mortuary Notices Desk"},
)

measurer = CitationMeasurer(registry)
chain = []

claim = make_assertion_claim(
    text="Elias Vane died on 28 October 2026.",
    fact_key="date_of_death",
    value="2026-10-28",
    citation="death_record",  # or "will_2024" / "family_record" / None
)

verdict, receipt = adjudicate(claim, desk_mandate, measurer, chain)
# verdict is gate_core.Pass() or gate_core.Refused(name=<refusal_name>)
# receipt is appended to chain
```

---

## Run the Publish Check for a Draft

```python
import hashlib, json
from citation_gate import check_publish

def claim_hash(claim):
    data = json.dumps(claim.to_dict(), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(data.encode()).hexdigest()

assertion_claim_hashes = [claim_hash(c) for c in my_claims]
decision = check_publish("draft-001", assertion_claim_hashes, chain)

if decision.publishable:
    print("Ready to publish.  Receipt ids:", decision.receipt_ids)
else:
    print("Not publishable.  First refusal:", decision.refusal_name)
```

`check_publish` is a pure function — it never calls `adjudicate()` and never
mutates the chain.  A draft with zero assertions returns `publishable=False`.

---

## Run the Demo Scenarios

```python
from citation_gate import run_scenarios

results = run_scenarios(registry, desk_mandate)
for r in results:
    pd = r.publish_decision
    print(f"{r.label}: publishable={pd.publishable}  refusal={pd.refusal_name}")
```

`run_scenarios` returns one `DraftResult` per scenario label in order:
N1, N2, N3, N4, N5a, N5b, N6.  Each `DraftResult` carries the full receipt
chain for that scenario and the publish decision.

---

## Verify the Receipt Chain

```python
from gate_core import verify_chain

result = verify_chain(chain)
if result.ok:
    print("Chain is intact.")
else:
    print(f"Chain failure at index {result.failure_index}: {result.failure_reason}")
```

`verify_chain` replays every receipt, recomputes each `own_hash`, and
confirms that each receipt's `previous_hash` matches its predecessor.

---

## Refusal Vocabulary

| Refusal name       | Meaning |
|--------------------|---------|
| `missing_citation` | The assertion names no source (`citation` is `null` or empty). |
| `unsupported_claim`| The cited source exists but does not contain the asserted `fact_key`; or the cited source id is not in the registry. |
| `source_contradicts`| The cited source contains the `fact_key` but its stored value differs from the asserted `value`. |
| `unmeasured`       | *(reserved by gate_core)* Measurement did not complete. |

---

## Source Records and Fact Tables

Three sealed source records are admitted to the desk at initialisation:

| Source id       | Keys in fact table |
|-----------------|--------------------|
| `death_record`  | `deceased`, `date_of_death`, `place`, `registrar` |
| `family_record` | `person`, `born`, `birthplace`, `occupation`, `residence` |
| `will_2024`     | `bequest.<Sign>.item` and `bequest.<Sign>.beneficiary` for each **occupied** sign |

The 2024 will has seven occupied signs (Aries, Taurus, Leo, Scorpio,
Capricorn, Aquarius, Pisces), yielding 14 fact keys.  The five empty signs —
Gemini, Cancer, Virgo, Libra, Sagittarius — produce no entries.  A claim
asserting a fact under an empty sign will be refused with `unsupported_claim`.
