# Executor Desk

The Executor desk processes estate distribution claims against sealed wills. It is one of the two application desks in the Skeleton Crew project, built on top of the `gate_core` library without modifying it. The desk reuses `gate_core`'s `adjudicate()`, `seal_mandate()`, `verify_mandate()`, `register_refusal()`, and `verify_chain()` directly. All decisional logic — checking death records, verifying will seals, detecting supersession, and validating distributions — lives in this package.

A sealed will is the mandate. A proposed distribution of estate assets is the claim. No asset may be released without a `PASS` verdict. Every verdict — pass or refused — produces a hash-chained receipt that makes the full distribution history tamper-evident.

---

## Package Layout

```
executor/
    __init__.py    — registers executor refusal vocabulary; re-exports public API
    registry.py    — loads fixture JSON, seals mandates, answers registry queries
    measurer.py    — ExecutorMeasurer implementing gate_core MeasurementProtocol
    claims.py      — factory to build estate_distribution Claims from plain dicts
    scenarios.py   — seven demo scenarios A–G and runner
```

---

## Quick Start

### 1. Initialise the Registry

Provide paths to will fixture files and death-record fixture files. The registry reads and seals each at construction time.

```python
from executor import ExecutorRegistry

registry = ExecutorRegistry(
    will_paths=[
        "fixtures/will_2019.json",
        "fixtures/will_2024.json",
    ],
    death_record_paths=[
        "fixtures/death_record.json",
    ],
)
```

Fixture paths are injected; nothing is hard-coded in the logic modules.

### 2. Submit a Distribution Claim

```python
from executor import ExecutorMeasurer, make_distribution_claim
import gate_core

# Resolve the target will from the registry.
will = registry.latest_will("Elias Vane")

# Build the claim.
claim = make_distribution_claim(
    will_ref=will.seal,
    distributions=[
        {"sign": "Aries",    "item": "The Iron Key",       "beneficiary": "..."},
        {"sign": "Taurus",   "item": "The Stone Bull",     "beneficiary": "Marta, the neighbor"},
        # ... one entry per occupied sign in the will
    ],
)

# Adjudicate against a fresh chain.
chain = []
measurer = ExecutorMeasurer(registry)
verdict, receipt = gate_core.adjudicate(claim, will, measurer, chain)
print(verdict)  # Pass() or Refused(name='...')
```

### 3. Run the Demo Scenarios

```python
from executor import ExecutorRegistry, run_scenarios

registry = ExecutorRegistry(
    will_paths=["fixtures/will_2019.json", "fixtures/will_2024.json"],
    death_record_paths=["fixtures/death_record.json"],
)

results = run_scenarios(registry)
for r in results:
    verdict_str = (
        "PASS" if r.verdict is not None and r.verdict.__class__.__name__ == "Pass"
        else f"REFUSED({r.verdict.name})" if r.verdict is not None
        else f"MandateTamperError: {r.tamper_error}"
    )
    print(f"Scenario {r.label}: {verdict_str}")
```

### 4. Verify the Receipt Chain

```python
from gate_core import verify_chain

replay = verify_chain(chain)
if replay.ok:
    print("Chain intact.")
else:
    print(f"Chain failure at index {replay.failure_index}: {replay.failure_reason}")
```

---

## Refusal Vocabulary

The executor desk registers the following names for domain `"executor"`. The gate_core reserved name `"unmeasured"` is also present without explicit registration.

| Refusal name        | Meaning |
|---------------------|---------|
| `death_unverified`  | No sealed death record exists for the testator, or the death record's seal fails verification. |
| `seal_broken`       | The will's own seal fails verification — the will bytes were altered after sealing. |
| `will_superseded`   | A later-sealed will for the same testator exists in the registry. |
| `sign_unoccupied`   | A distribution entry names a sign whose bit in the will's vector is `0`. |
| `share_mismatch`    | Distribution count mismatch, wrong item, duplicate sign, or stated_popcount inconsistency. |
| `beneficiary_unknown` | The sign and item are correct but the beneficiary does not match the will. |
| `unmeasured`        | *(reserved by gate_core)* Measurement did not complete. |

Measurement is deterministic: the **first** failing check names the refusal and measurement stops. The precedence order is: `death_unverified` → `seal_broken` → `will_superseded` → `sign_unoccupied` / `share_mismatch` / `beneficiary_unknown`.

---

## The Two Elias Vane Wills

The demo fixtures represent the estate of Elias Vane, who died on 2026-10-28 in Hollow Hill.

- **2019 will** (`will_2019.json`, sealed 2019-10-31): 6 bequests covering Pisces, Aquarius, Capricorn, Leo, Taurus, and Aries.
- **2024 will** (`will_2024.json`, sealed 2024-10-31): 7 bequests — all 6 from the 2019 will plus Scorpio.

The 2024 will contains the supersession condition: *"If a later seal appears bearing my name, let the later govern."* Because the registry holds both wills and the 2024 will has the later `sealed_date`, any distribution claim submitted against the 2019 will is refused with `will_superseded`. The receipt's observations include the seal of the governing (2024) will so an auditor can identify which will applies.
