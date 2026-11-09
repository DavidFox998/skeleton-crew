# Technical Design — Executor Desk

## Constraints

- Python 3.11+, standard library only.
- No external dependencies beyond `gate_core`.
- `executor` imports from `gate_core`; `gate_core` imports nothing from `executor`.
- Fixture file paths are injected at registry construction time; no paths are hard-coded in logic modules.
- All measurement and adjudication logic lives in `executor`; no UI or network access.

---

## Package Layout

```
executor/
    __init__.py    — re-exports public API; registers executor refusal vocabulary
    registry.py   — loads fixture JSON, seals mandates, answers registry queries
    measurer.py   — ExecutorMeasurer implementing gate_core MeasurementProtocol
    claims.py     — helper to build estate_distribution Claims from plain dicts
    scenarios.py  — seven demo scenarios A-G as data + runner
```

This package lives beside `gate_core/` at the same directory level:

```
skeleton-crew/
    gate_core/
        ...
    executor/
        ...
    fixtures/
        will_2024.json
        will_2019.json
        death_record.json
```

---

## Dependency Graph

```
registry.py   ← gate_core.mandate (seal_mandate, verify_mandate)
measurer.py   ← gate_core.measure (MeasurementResult)
              ← gate_core.mandate (verify_mandate)
              ← registry.py
claims.py     ← gate_core.claim (Claim)
scenarios.py  ← gate_core.gate (adjudicate)
              ← gate_core.receipt (verify_chain)
              ← registry.py
              ← measurer.py
              ← claims.py
__init__.py   ← gate_core.verdict (register_refusal)
              ← all submodules
```

No circular dependencies. `gate_core` has no import from `executor`.

---

## `registry.py`

### Purpose

Loads will and death-record fixtures from JSON files, seals each as a `gate_core.SealedMandate`, and answers queries needed by the measurer.

### Public API

```python
class ExecutorRegistry:
    def __init__(
        self,
        will_paths: list[str],
        death_record_paths: list[str],
    ) -> None: ...

    def latest_will(self, testator: str) -> SealedMandate | None: ...
    def all_wills(self, testator: str) -> list[SealedMandate]: ...
    def will_by_seal(self, seal: str) -> SealedMandate | None: ...
    def death_record(self, name: str) -> SealedMandate | None: ...
```

### Construction

`__init__` reads each path with `json.load`, calls `gate_core.seal_mandate(domain="executor", content=data)` for each, and stores the results. Wills are grouped by `content["testator"]` and sorted by `content["sealed_date"]` ascending. Death records are stored by `content["deceased"]`.

### `latest_will`

Returns the `SealedMandate` with the greatest `sealed_date` for `testator`, or `None`.

### `all_wills`

Returns the list of sealed wills for `testator`, oldest first.

### `will_by_seal`

Returns the `SealedMandate` whose `seal` field equals the given hex string, or `None`. Used by the measurer to locate the will referenced by `will_ref` in the claim payload.

### `death_record`

Returns the sealed death record for `name`, or `None`.

### Notes

- The registry does not validate fixture semantics (e.g. vector/popcount consistency). That is the measurer's job.
- A registry may hold wills for multiple testators. The Vane demo uses two will paths and one death record path.

---

## `measurer.py`

### Purpose

Implements `gate_core.MeasurementProtocol`. Performs all precedence checks and returns a `MeasurementResult`. Has no knowledge of verdicts; it only observes and reports.

### Class

```python
class ExecutorMeasurer:
    def __init__(self, registry: ExecutorRegistry) -> None: ...

    def measure(
        self,
        claim: Claim,
        mandate: SealedMandate,
    ) -> MeasurementResult: ...
```

`mandate` passed to `measure()` is the `SealedMandate` for the specific will being adjudicated (the one whose seal matches `claim.payload["will_ref"]`).

### Measurement Algorithm

All observations are collected in a plain dict and included in the returned `MeasurementResult.observations`. On any failure the function returns immediately with `passed=False` and `observations["refusal_name"]` set.

```
1. DEATH RECORD CHECK
   dr = registry.death_record(mandate.content["testator"])
   if dr is None or not verify_mandate(dr):
       return MeasurementResult(
           observations={
               "refusal_name": "death_unverified",
               "testator": mandate.content["testator"],
               "death_record_present": dr is not None,
           },
           passed=False,
       )

2. WILL SEAL CHECK
   if not verify_mandate(mandate):
       return MeasurementResult(
           observations={
               "refusal_name": "seal_broken",
               "will_seal": mandate.seal,
           },
           passed=False,
       )

3. SUPERSESSION CHECK
   latest = registry.latest_will(mandate.content["testator"])
   if latest is not None and latest.seal != mandate.seal:
       return MeasurementResult(
           observations={
               "refusal_name": "will_superseded",
               "submitted_seal": mandate.seal,
               "governing_seal": latest.seal,
               "governing_sealed_date": latest.content["sealed_date"],
           },
           passed=False,
       )

4. PER-DISTRIBUTION CHECKS
   Derive sign_to_bit: read mandate.content["vector_order"] to get ordered sign list;
   zip with mandate.content["vector"] characters to build {sign: bit_char} dict.
   actual_popcount = mandate.content["vector"].count("1")

   a. Check stated_popcount == actual_popcount:
      if mandate.content["stated_popcount"] != actual_popcount:
          return MeasurementResult(
              observations={
                  "refusal_name": "share_mismatch",
                  "reason": "stated_popcount_mismatch",
                  "stated": mandate.content["stated_popcount"],
                  "actual": actual_popcount,
              },
              passed=False,
          )

   b. Check len(distributions) == actual_popcount:
      distributions = claim.payload["distributions"]
      if len(distributions) != actual_popcount:
          return MeasurementResult(
              observations={
                  "refusal_name": "share_mismatch",
                  "reason": "distribution_count_mismatch",
                  "expected": actual_popcount,
                  "received": len(distributions),
              },
              passed=False,
          )

   c. For each entry in distributions (in order):
      sign = entry["sign"]

      i.  Sign occupied?
          if sign_to_bit.get(sign) != "1":
              return MeasurementResult(
                  observations={
                      "refusal_name": "sign_unoccupied",
                      "sign": sign,
                  },
                  passed=False,
              )

      ii. Duplicate sign?
          if sign already seen in this distribution:
              return MeasurementResult(
                  observations={
                      "refusal_name": "share_mismatch",
                      "reason": "duplicate_sign",
                      "sign": sign,
                  },
                  passed=False,
              )

      iii. Item match?
           will_bequest = bequest_map[sign]  # built from mandate.content["bequests"]
           if entry["item"] != will_bequest["item"]:
               return MeasurementResult(
                   observations={
                       "refusal_name": "share_mismatch",
                       "reason": "item_mismatch",
                       "sign": sign,
                       "expected_item": will_bequest["item"],
                       "received_item": entry["item"],
                   },
                   passed=False,
               )

      iv. Beneficiary match?
          if entry["beneficiary"] != will_bequest["beneficiary"]:
              return MeasurementResult(
                  observations={
                      "refusal_name": "beneficiary_unknown",
                      "sign": sign,
                      "expected_beneficiary": will_bequest["beneficiary"],
                      "received_beneficiary": entry["beneficiary"],
                  },
                  passed=False,
              )

      Mark sign as seen.

5. PASS
   return MeasurementResult(
       observations={
           "signs_verified": [e["sign"] for e in distributions],
           "items_verified": [e["item"] for e in distributions],
           "testator": mandate.content["testator"],
           "will_seal": mandate.seal,
           "death_record_seal": dr.seal,
       },
       passed=True,
   )
```

### Deriving `sign_to_bit` and `bequest_map`

`vector_order` in the fixture is a human-readable string of the form `"MSB=Pisces ... LSB=Aries"`. The implementation parses the list of sign names from `mandate.content["vector_order"]` by extracting the `MSB=X` and `LSB=Y` endpoints and relying on the known fixed 12-sign zodiac order. A safer approach (and the one preferred here) is to store the full ordered sign list as a separate field in the fixture, or to hard-code the canonical 12-sign sequence as a module-level constant in `measurer.py` and validate it against `vector_order` at measure time.

**Canonical 12-sign sequence (MSB → LSB):**

```python
ZODIAC_MSB_TO_LSB = [
    "Pisces", "Aquarius", "Capricorn", "Sagittarius",
    "Scorpio", "Leo", "Cancer", "Gemini",
    "Virgo", "Libra", "Taurus", "Aries",
]
```

> The exact sequence must be verified against both fixture files before implementation. The sequence above is derived from the 2024 fixture vector `"111010010011"` and the 7 occupied signs (Pisces, Aquarius, Capricorn, Scorpio, Gemini, Taurus, Aries). Implementors must cross-check the 2019 fixture to confirm consistency.

`bequest_map` is built as `{b["sign"]: b for b in mandate.content["bequests"]}`.

### Notes

- `ExecutorMeasurer` holds a reference to the registry but reads it only through its public API.
- The measurer never raises intentionally. If a key is missing from a fixture, a `KeyError` propagates to `adjudicate()`, which catches it and issues `REFUSED('unmeasured')`.

---

## `claims.py`

### Purpose

Provides a thin factory function so callers can construct an `estate_distribution` claim from a plain dict without importing `gate_core` directly.

### Public API

```python
def make_distribution_claim(
    will_ref: str,
    distributions: list[dict],
) -> Claim:
    """
    Build a gate_core.Claim for an estate distribution.

    Args:
        will_ref: hex SHA-256 seal of the target will.
        distributions: list of {"sign": str, "item": str, "beneficiary": str}.

    Returns:
        gate_core.Claim with domain="executor", claim_type="estate_distribution".
    """
```

### Implementation

```python
from gate_core.claim import Claim

def make_distribution_claim(will_ref: str, distributions: list[dict]) -> Claim:
    return Claim(
        domain="executor",
        claim_type="estate_distribution",
        payload={
            "will_ref": will_ref,
            "distributions": distributions,
        },
    )
```

No validation beyond what `gate_core.Claim.__post_init__` already performs (JSON-serialisability, non-blank fields).

---

## `scenarios.py`

### Purpose

Defines the seven demo scenarios A–G as structured data and provides a runner that adjudicates each against a fresh receipt chain and collects results.

### Scenario Data Structure

```python
from dataclasses import dataclass
from gate_core.receipt import Receipt
from gate_core.verdict import Verdict

@dataclass
class ScenarioResult:
    label: str          # e.g. "A"
    description: str
    verdict: Verdict
    receipt: Receipt
    chain: list[Receipt]
```

### Scenario Definitions

Each scenario is expressed as a plain dict:

```python
{
    "label": "A",
    "description": "Correct 7-bequest distribution under the 2024 will → PASS",
    "will_selector": "2024",          # "2024" | "2019" | tampered
    "distributions": [...],           # list of {sign, item, beneficiary}
    "registry_variant": "full",       # "full" | "no_death_record"
}
```

The runner resolves `will_selector` to a `SealedMandate` from the registry, constructs the claim via `make_distribution_claim`, constructs a fresh `ExecutorMeasurer(registry)`, starts a new empty chain, and calls `gate_core.adjudicate`.

### Runner

```python
def run_scenarios(
    registry: ExecutorRegistry,
) -> list[ScenarioResult]:
    """
    Adjudicate all seven demo scenarios and return their results.
    Each scenario uses its own fresh receipt chain.
    """
```

For Scenario G (tampered will), the runner constructs a `SealedMandate` with the original seal but with `content` modified (e.g. a beneficiary name changed). This is passed directly as the `mandate` argument to `adjudicate()`. Because `gate_core.adjudicate()` calls `verify_mandate()` first and will raise `MandateTamperError` before measurement runs, Scenario G's runner catches `MandateTamperError` and records it distinctly in the result. If the test intent is to exercise the measurer's `seal_broken` path, the tampered mandate is passed only to `measure()` directly (not to `adjudicate()`), per the note in requirements Scenario G.

### Scenario Inventory

| Label | Will | Registry | Distributions | Expected verdict |
|---|---|---|---|---|
| A | 2024 | full | All 7 correct | `PASS` |
| B | 2019 | full | 2019's 6 correct | `REFUSED('will_superseded')` |
| C | 2024 | full | 7 correct + 1 extra | `REFUSED('share_mismatch')` |
| D | 2024 | full | 7 entries, Scorpio wrong beneficiary | `REFUSED('beneficiary_unknown')` |
| E | 2024 | full | Includes a Gemini entry | `REFUSED('sign_unoccupied')` |
| F | 2024 | no death record | All 7 correct | `REFUSED('death_unverified')` |
| G | 2024 (tampered) | full | All 7 correct | `MandateTamperError` (or `REFUSED('seal_broken')` via measurer path) |

---

## `__init__.py`

Registers the executor refusal vocabulary at import time and re-exports the public API.

```python
from gate_core.verdict import register_refusal

_EXECUTOR_REFUSALS = [
    "death_unverified",
    "seal_broken",
    "will_superseded",
    "sign_unoccupied",
    "share_mismatch",
    "beneficiary_unknown",
]

for _name in _EXECUTOR_REFUSALS:
    register_refusal("executor", _name)

from executor.registry import ExecutorRegistry
from executor.measurer import ExecutorMeasurer
from executor.claims import make_distribution_claim
from executor.scenarios import run_scenarios, ScenarioResult
```

Registration at import time ensures the vocabulary is in place before any adjudication call, even if only a subset of submodules is imported by the caller.

---

## Error Handling Summary

| Situation | Behaviour |
|---|---|
| Death record missing or seal fails | Measurer returns `passed=False, refusal_name='death_unverified'` |
| Will seal fails inside measurer | Measurer returns `passed=False, refusal_name='seal_broken'` |
| Later will exists | Measurer returns `passed=False, refusal_name='will_superseded'` |
| Distribution count wrong | Measurer returns `passed=False, refusal_name='share_mismatch'` |
| Sign unoccupied | Measurer returns `passed=False, refusal_name='sign_unoccupied'` |
| Item mismatch / duplicate sign | Measurer returns `passed=False, refusal_name='share_mismatch'` |
| Beneficiary mismatch | Measurer returns `passed=False, refusal_name='beneficiary_unknown'` |
| Tampered mandate passed to `adjudicate()` | `MandateTamperError` raised by gate_core; no receipt appended |
| Measurer raises unhandled exception | gate_core catches it; `REFUSED('unmeasured')` verdict; receipt appended |

---

## Design Decisions

**Why does the registry sort wills by `sealed_date` as a string?**
ISO-8601 date strings (`YYYY-MM-DD`) sort lexicographically in the same order as chronologically. No date parsing is needed for comparison, which keeps the registry dependency-free.

**Why does `__init__.py` register the vocabulary at import time?**
The vocabulary must exist before any `make_refused("executor", ...)` call. Centralising registration in `__init__.py` ensures it runs exactly once and before any submodule can issue a verdict, without requiring a separate `setup()` call from application code.

**Why is `sign_to_bit` derived from a module-level constant rather than parsed from `vector_order`?**
`vector_order` is a human-readable annotation string, not a machine-readable encoding. Parsing it at measure time adds fragility with no benefit; the canonical sequence is fixed by the zodiac and can be validated against the fixtures once during development.

**Why does each scenario use a fresh receipt chain?**
Demo scenarios are independent. A shared chain would mean Scenario B's receipt appears before Scenario A's in a single chain, which is misleading for demo purposes. Auditable production use would chain all claims for a single estate sequentially.

**Why does `claims.py` exist if it is only two lines?**
It enforces the domain boundary: application code that submits claims should not need to know gate_core's `Claim` constructor signature, and the `domain` and `claim_type` values are facts that belong to the executor domain, not to the caller.

---

## Amendment 2026-11-02 — slot generalization

### Motivation

A historical control case — a real 1961 will (Monroe) whose bequest keys are not
zodiac signs — exposed a structural coupling in the original design: the measurer
hard-coded a 12-element zodiac constant (`ZODIAC_MSB_TO_LSB`) as the slot layout
for every will, so any mandate whose vector length differed from 12, or whose
bequest keys fell outside the zodiac vocabulary, could never produce a correct
measurement.

### Change summary

**Slots are now part of the sealed mandate content.**  Every new mandate includes
a `"slots"` field — an ordered list of slot names (MSB first) whose length equals
the length of `"vector"`.  Because `"slots"` lives inside `content`, it is covered
by the SHA-256 seal: the slot order is itself tamper-evident.

**The measurer reads `slots` from the mandate.**  The logic in `ExecutorMeasurer.measure`
derives the slot list as:

```python
slots = mandate.content.get("slots", ZODIAC_MSB_TO_LSB)
```

`ZODIAC_MSB_TO_LSB` is retained as a legacy fallback for any mandate sealed before
this amendment that does not carry a `"slots"` field.

**The vector-length check is unchanged in semantics**, but now compares
`len(vector)` against `len(slots)` (which equals 12 for all current fixtures,
and equals the actual slot count for new mandates).  A mismatch still produces
`REFUSED('seal_broken')` with `reason='vector_length_mismatch'` and
`expected_length=len(slots)` / `actual_length=len(vector)` in the observations.

**`sign_to_bit` is built by zipping `slots` with `vector`.**  A distribution sign
not present in `slots` is handled identically to today: `sign_to_bit.get(sign)`
returns `None`, which is not `"1"`, so the check fires `sign_unoccupied`.

### Fixture updates

`will_2024.json` and `will_2019.json` each received a `"slots"` field whose value
is the `ZODIAC_MSB_TO_LSB` list verbatim.  The seals for these fixtures are
recomputed at load time by `ExecutorRegistry` (they are not stored in the JSON),
so no stored seal needed updating.

### Invariants preserved

- All measurement logic, check precedence, and refusal names are unchanged.
- Scenario A–G verdicts are identical to pre-amendment results.
- The webui is unaffected: it renders the Vane fixtures, whose slot order equals
  the legacy list.
- `gate_core` and `citation_gate` are unmodified.
