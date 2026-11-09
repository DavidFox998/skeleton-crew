# gate_core

Pure-Python library implementing the Skeleton Crew gate pattern.  No external
dependencies; Python 3.11+ standard library only.

---

## Module map

```
gate_core/
    claim.py      — Claim dataclass
    mandate.py    — SealedMandate, seal_mandate(), verify_mandate()
    measure.py    — MeasurementProtocol, MeasurementResult
    verdict.py    — Verdict (Pass | Refused), refusal vocabulary registry
    receipt.py    — Receipt, append_receipt(), verify_chain(), save/load helpers
    gate.py       — adjudicate(): the claim → measure → verdict → receipt composition
```

All public names are re-exported from `gate_core/__init__.py`.

---

## Canonical JSON

Every SHA-256 hash in the library is computed over the same canonical
serialisation:

```python
import json

def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))
```

`sort_keys=True` makes key order deterministic.  `separators=(',', ':')`
removes all whitespace.  This two-liner is duplicated in each module that
needs it to keep the dependency graph acyclic.

---

## Error taxonomy

| Exception            | Raised by              | Meaning                                              |
|----------------------|------------------------|------------------------------------------------------|
| `MandateTamperError` | `gate.py`, `mandate.py`| Mandate seal does not match recomputed hash          |
| `UnknownRefusalError`| `verdict.py`           | Refusal name not registered for the domain           |
| `ValueError`         | `claim.py`             | Blank field or non-JSON-serialisable payload         |
| `ValueError`         | `mandate.py`           | Non-JSON-serialisable mandate content                |

`MandateTamperError` is a hard error, not a gate refusal.  It means the chain
of custody is already broken.  `adjudicate()` raises it before appending
anything to the chain.

---

## Minimal end-to-end example

```python
from gate_core import (
    Claim,
    MandateTamperError,
    MeasurementResult,
    Pass,
    Refused,
    adjudicate,
    register_refusal,
    seal_mandate,
    verify_chain,
)

# ── 1. Define the domain ────────────────────────────────────────────────────
DOMAIN = "executor"
register_refusal(DOMAIN, "exceeds_estate_value")

# ── 2. Seal the mandate (done once, at admission time) ──────────────────────
mandate = seal_mandate(DOMAIN, {"max_distribution_usd": 500_000})

# ── 3. Implement a domain-specific measurer ─────────────────────────────────
class DistributionMeasurer:
    def measure(self, claim, sealed_mandate):
        proposed = claim.payload["amount_usd"]
        limit    = sealed_mandate.content["max_distribution_usd"]
        passed   = proposed <= limit
        observations = {"proposed": proposed, "limit": limit}
        if not passed:
            observations["refusal_name"] = "exceeds_estate_value"
        return MeasurementResult(observations=observations, passed=passed)

measurer = DistributionMeasurer()

# ── 4. Submit claims through the gate ───────────────────────────────────────
chain = []

claim_a = Claim(domain=DOMAIN, claim_type="asset_distribution",
                payload={"amount_usd": 200_000})
verdict_a, receipt_a = adjudicate(claim_a, mandate, measurer, chain)
# verdict_a → Pass()

claim_b = Claim(domain=DOMAIN, claim_type="asset_distribution",
                payload={"amount_usd": 600_000})
verdict_b, receipt_b = adjudicate(claim_b, mandate, measurer, chain)
# verdict_b → Refused(name='exceeds_estate_value')

# ── 5. Inspect results ──────────────────────────────────────────────────────
for verdict in (verdict_a, verdict_b):
    match verdict:
        case Pass():
            print("PASS — distribution approved")
        case Refused(name=name):
            print(f"REFUSED — {name}")

# ── 6. Verify the chain is intact ───────────────────────────────────────────
result = verify_chain(chain)
assert result.ok, f"Chain broken at index {result.failure_index}: {result.failure_reason}"
print(f"Chain of {len(chain)} receipts verified.")
```

Expected output:

```
PASS — distribution approved
REFUSED — exceeds_estate_value
Chain of 2 receipts verified.
```

---

## Running the tests

```sh
python3 -m unittest discover -s tests -v
```
