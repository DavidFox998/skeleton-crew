# Technical Design — Gate Core Library

## Constraints

- Python 3.11+, standard library only.
- No external dependencies.
- No I/O in the core except explicit `load` / `save` helpers inside `receipt.py`.
- No network access anywhere in the library.

---

## Module Map

```
gate_core/
    claim.py      — Claim dataclass
    mandate.py    — SealedMandate, seal(), verify()
    measure.py    — MeasurementProtocol, MeasurementResult
    verdict.py    — Verdict (Pass | Refused), refusal vocabulary
    receipt.py    — Receipt, chain append, chain replay/verify
    gate.py       — adjudicate(): the claim → measure → verdict → receipt composition
```

---

## Canonical JSON

All hashing in this library uses the same canonical serialization:

```python
import json

def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))
```

`sort_keys=True` ensures key order is deterministic. `separators=(',', ':')` removes all whitespace. This function is a private helper duplicated in any module that needs it, keeping modules free of circular imports.

---

## `claim.py`

### Purpose

Defines the typed, immutable `Claim` value object. A `Claim` is the unit of work submitted to the gate.

### Data Model

```python
@dataclass(frozen=True)
class Claim:
    domain: str          # e.g. "executor", "citation_gate"
    claim_type: str      # e.g. "asset_distribution", "factual_assertion"
    payload: dict        # domain-specific structured data (must be JSON-serialisable)
```

`frozen=True` ensures immutability after construction.

### Notes

- `payload` must be JSON-serialisable. The gate validates this at claim construction time by attempting `canonical_json(payload)` and raising `ValueError` on failure.
- `domain` and `claim_type` are non-empty strings; the constructor raises `ValueError` on blank values.

---

## `mandate.py`

### Purpose

Defines a `SealedMandate`: a mandate whose content has been hashed so any post-hoc modification is detectable.

### Data Model

```python
@dataclass(frozen=True)
class SealedMandate:
    domain: str          # must match the domain of claims submitted against it
    content: dict        # the mandate's terms; must be JSON-serialisable
    seal: str            # hex SHA-256 of canonical_json(content)
```

### Functions

```python
def seal_mandate(domain: str, content: dict) -> SealedMandate:
    ...

def verify_mandate(mandate: SealedMandate) -> bool:
    ...
```

### Sealing Algorithm

```
seal = hashlib.sha256(canonical_json(content).encode('utf-8')).hexdigest()
```

`verify_mandate` recomputes this value and returns `True` iff it equals `mandate.seal`.

### Notes

- The gate raises `MandateTamperError` (a subclass of `Exception`) if `verify_mandate` returns `False` before processing a claim. This is a hard error, not a refusal verdict.

---

## `measure.py`

### Purpose

Defines the `MeasurementProtocol` that all domain-specific measurers must implement, and the `MeasurementResult` they return.

### Data Model

```python
@dataclass(frozen=True)
class MeasurementResult:
    observations: dict   # stable-keyed observed values; must be JSON-serialisable
    passed: bool         # measurer's opinion: does the claim satisfy the mandate?
```

### Protocol

```python
from typing import Protocol

class MeasurementProtocol(Protocol):
    def measure(self, claim: Claim, mandate: SealedMandate) -> MeasurementResult:
        ...
```

Any callable object (class instance, function, lambda) that has a `measure` method with this signature satisfies the protocol. No base class inheritance is required.

### Notes

- The gate catches all exceptions raised inside `measure()`. On exception, the result is treated as an absent measurement (see `verdict.py` and `receipt.py`).
- `MeasurementResult` does not produce a verdict. `passed` is an advisory opinion; the gate may define additional domain rules on top of it.
- In the current design, the gate passes through `passed` directly: `passed=True` → `PASS`, `passed=False` → `REFUSED` with a domain-specific name. Domain extensions may override this mapping.

---

## `verdict.py`

### Purpose

Defines the `Verdict` type and the per-domain refusal vocabulary registry.

### Verdict Type

```python
from dataclasses import dataclass
from typing import Union

@dataclass(frozen=True)
class Pass:
    pass

@dataclass(frozen=True)
class Refused:
    name: str            # must be in the domain's refusal vocabulary

Verdict = Union[Pass, Refused]
```

`Pass` and `Refused` are distinct types. Pattern-matching (`match`/`case`) is the preferred dispatch mechanism in calling code.

### Refusal Vocabulary

```python
# Module-level registry: domain -> set of registered refusal names
_VOCABULARIES: dict[str, set[str]] = {}
_RESERVED = frozenset({'unmeasured'})

def register_refusal(domain: str, name: str) -> None:
    ...

def is_valid_refusal(domain: str, name: str) -> bool:
    ...
```

- `'unmeasured'` is pre-registered for every domain and cannot be overridden.
- `register_refusal` raises `ValueError` if `name` collides with a reserved name.
- The gate raises `UnknownRefusalError` (subclass of `Exception`) if a verdict attempts to use a name not in the domain's vocabulary.

### Factory Helpers

```python
def make_pass() -> Pass:
    return Pass()

def make_refused(domain: str, name: str) -> Refused:
    # validates name against vocabulary before constructing
    ...

def unmeasured_refusal() -> Refused:
    return Refused(name='unmeasured')
```

---

## `receipt.py`

### Purpose

Defines the `Receipt` value object, the chain-append operation, and the chain-replay verifier.

### Data Model

```python
@dataclass(frozen=True)
class Receipt:
    claim: dict          # canonical_json-serialisable snapshot of the claim
    measurements: dict | None   # canonical_json-serialisable snapshot; None if unmeasured
    measurement_error: str | None  # exception message if measurement raised; else None
    verdict: dict        # {'type': 'pass'} or {'type': 'refused', 'name': '...'}
    timestamp_utc: str   # ISO-8601 UTC, e.g. "2026-11-01T22:38:05Z"
    previous_hash: str   # 64 hex chars; "0"*64 for the first receipt in a chain
    own_hash: str        # SHA-256 of canonical_json of this receipt excluding own_hash
```

### Hash Computation

The `own_hash` field is computed over a dict that is identical to the receipt's fields except `own_hash` is omitted:

```python
def _compute_hash(fields_without_own_hash: dict) -> str:
    return hashlib.sha256(
        canonical_json(fields_without_own_hash).encode('utf-8')
    ).hexdigest()
```

### Chain Append

```python
def append_receipt(
    chain: list[Receipt],
    claim: Claim,
    measurement: MeasurementResult | None,
    measurement_error: str | None,
    verdict: Verdict,
    timestamp_utc: str,
) -> Receipt:
    ...
```

- `previous_hash` is `chain[-1].own_hash` if `chain` is non-empty, else `"0" * 64`.
- Returns a new `Receipt`; does not mutate `chain`. The caller is responsible for appending it to the chain list.

### Chain Replay

```python
@dataclass(frozen=True)
class ReplayResult:
    ok: bool
    failure_index: int | None   # None if ok=True
    failure_reason: str | None  # None if ok=True

def verify_chain(receipts: list[Receipt]) -> ReplayResult:
    ...
```

Algorithm:

1. For each receipt at index `i`:
   a. Recompute `own_hash` from stored fields (excluding `own_hash`). If mismatch → `ReplayResult(ok=False, failure_index=i, failure_reason='hash_mismatch')`.
   b. If `i > 0`, check `receipt.previous_hash == receipts[i-1].own_hash`. If mismatch → `ReplayResult(ok=False, failure_index=i, failure_reason='chain_broken')`.
2. If all receipts pass → `ReplayResult(ok=True, failure_index=None, failure_reason=None)`.

Replay stops at the first failure (AC-6.5).

### Load / Save Helpers

```python
def receipt_to_dict(receipt: Receipt) -> dict:
    ...

def receipt_from_dict(data: dict) -> Receipt:
    ...

def save_chain(receipts: list[Receipt], path: str) -> None:
    # writes JSON array to path; only I/O allowed in the core
    ...

def load_chain(path: str) -> list[Receipt]:
    # reads JSON array from path; validates each receipt
    ...
```

These are the only functions in the core that perform filesystem I/O. All other functions are pure.

---

## `gate.py`

### Purpose

Provides `adjudicate()`: the single function that composes the full gate pipeline — mandate verification, measurement, verdict, and receipt — so that application code never has to re-derive the safety rules.

### Signature

```python
def adjudicate(
    claim: Claim,
    sealed_mandate: SealedMandate,
    measurer: MeasurementProtocol,
    chain: list[Receipt],
    *,
    timestamp_utc: str | None = None,
) -> tuple[Verdict, Receipt]:
    ...
```

`timestamp_utc` defaults to `datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')` when `None`.

### Algorithm

1. **Mandate verification** — call `verify_mandate(sealed_mandate)`.  If it returns `False`, raise `MandateTamperError` immediately.  Nothing is appended to the chain.
2. **Measurement** — call `measurer.measure(claim, sealed_mandate)` inside `try/except Exception`.  On success, store the `MeasurementResult`; on any exception, store `None` and record the exception message as `measurement_error`.
3. **Verdict** — if measurement is `None`, call `unmeasured_refusal()`.  Otherwise, if `measurement.passed` is `True`, call `make_pass()`; if `False`, call `make_refused(claim.domain, measurement.refusal_name)` where `refusal_name` is taken from `measurement.observations.get('refusal_name')` — the measurer is expected to include it when `passed=False`.  If no `refusal_name` key is present, fall back to `unmeasured_refusal()`.
4. **Receipt** — call `append_receipt(chain, claim, measurement, measurement_error, verdict, timestamp_utc)` and append the returned receipt to `chain`.
5. **Return** `(verdict, receipt)`.

### Notes

- `MandateTamperError` propagates without appending a receipt.  This is intentional: a tampered mandate means the chain of custody is already broken, so recording a receipt would be misleading.
- All other errors (measurer exceptions, unknown refusal names) are contained inside the function: the measurer exception becomes an `unmeasured` refusal, and an unknown refusal name would only arise if the measurer returned a `refusal_name` not registered for the domain, which is treated the same way.
- `gate.py` is the only module that imports from all other modules; it is the composition root.

---

## Error Taxonomy

| Exception               | Raised by        | Meaning                                              |
|-------------------------|------------------|------------------------------------------------------|
| `MandateTamperError`    | gate, mandate.py | Mandate seal does not match recomputed hash          |
| `UnknownRefusalError`   | verdict.py       | Refusal name not in domain vocabulary                |
| `ValueError`            | claim.py         | Claim payload not JSON-serialisable, or blank fields |
| `ValueError`            | mandate.py       | Mandate content not JSON-serialisable                |

---

## Dependency Graph

```
claim.py       ← no internal imports
mandate.py     ← no internal imports
measure.py     ← claim.py, mandate.py
verdict.py     ← no internal imports
receipt.py     ← claim.py, measure.py, verdict.py
gate.py        ← claim.py, mandate.py, measure.py, verdict.py, receipt.py
```

No circular dependencies.

---

## Design Decisions

**Why `Union[Pass, Refused]` instead of an `Enum`?**  
`Pass` carries no data; `Refused` carries a name. An enum cannot hold per-variant data cleanly in Python without awkward payloads. Frozen dataclasses give immutability, structural equality, and clear type-narrowing in `match`/`case`.

**Why duplicate `canonical_json` across modules?**  
A shared `utils.py` would create a fan-in dependency that makes the graph harder to read and test in isolation. The function is two lines; duplication is the lesser cost.

**Why store `measurements` as `dict | None` rather than `MeasurementResult | None`?**  
Receipts must survive serialization and deserialization. Storing a plain dict avoids coupling the receipt format to the `MeasurementResult` class and allows future schema evolution without breaking existing receipt files.

**Why is `passed` advisory in `MeasurementResult`?**  
Measurement observes facts; the gate decides verdicts. Keeping these roles separate means a domain can register additional rules (e.g., mandatory secondary review) without changing the measurer.
