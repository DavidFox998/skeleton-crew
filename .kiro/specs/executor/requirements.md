# Requirements — Executor Desk

## Overview

The Executor desk processes estate distribution claims against sealed wills. It is an application built on top of the gate_core library; it reuses `adjudicate()` without modification and registers its domain-specific mandate types, measurement logic, and refusal vocabulary within the framework gate_core defines.

A sealed will is the mandate. A proposed distribution of estate assets is the claim. No asset may be released without a `PASS` verdict. Every verdict — pass or refused — produces a hash-chained receipt.

---

## Domain Model

### The Will

A will contains:

| Field | Type | Notes |
|---|---|---|
| `testator` | string | Name of the person whose estate is being distributed. |
| `sealed_date` | string | ISO-8601 date on which the will was sealed (e.g. `"2024-10-31"`). |
| `vector` | string | 12-bit binary string. MSB (leftmost) = Pisces; LSB (rightmost) = Aries. A `1` means that zodiac sign has a bequest; a `0` means it is unoccupied. |
| `stated_popcount` | integer | The number of bequests as declared in the will text. Must equal the count of `1` bits in `vector`. |
| `bequests` | list | Each entry: `{sign, item, beneficiary}`. Exactly one entry per sign whose bit is `1`. |
| `empty_signs` | list | Zodiac signs whose bit in `vector` is `0`. Must be consistent with `vector`. |
| `condition` | string | Supersession rule declared by the testator. For the Elias Vane estate this reads: *"If a later seal appears bearing my name, let the later govern."* |

The zodiac sign order (MSB → LSB) is: Pisces, Aquarius, Capricorn, Sagittarius, Scorpio, Leo, Cancer, Gemini, Taurus, Aries. (12 positions; Libra and Virgo are not listed because the Vane fixtures use a 10-active-sign subset encoded in 12 bits — see vector note.)

> **Vector reference (Elias Vane, 2024 will):** `vector = "111010010011"`. Reading left to right: Pisces=1, Aquarius=1, Capricorn=1, Sagittarius=0, Scorpio=1, Leo=0, Cancer=0, Gemini=1 ... wait — the fixtures use a different ordering. The canonical order used by the fixtures is documented in the fixture files themselves under `"vector_order": "MSB=Pisces ... LSB=Aries"`. Implementors must read `vector_order` from the fixture and derive the sign-to-bit mapping from it; the exact 12-sign sequence is authoritative in the fixture, not inferred.

### The Death Record

A death record contains:

| Field | Type | Notes |
|---|---|---|
| `deceased` | string | Must match `testator` in the will being adjudicated. |
| `date_of_death` | string | ISO-8601 date. |
| `place` | string | Place of death. |
| `registrar` | string | Issuing authority. |
| `record` | string | Attestation text. |

A death record is sealed and stored as a `SealedMandate` in the registry under domain `"executor"` with a separate mandate type identifier.

### The Claim

| Field | Type | Notes |
|---|---|---|
| `domain` | string | Always `"executor"`. |
| `claim_type` | string | Always `"estate_distribution"`. |
| `payload.will_ref` | string | The seal (hex SHA-256) of the sealed will this distribution is claimed against. Identifies which will governs. |
| `payload.distributions` | list | Each entry: `{sign, item, beneficiary}`. One entry per occupied sign in the will. |

---

## Refusal Vocabulary

The executor desk registers the following names for domain `"executor"`. The gate_core reserved name `"unmeasured"` is also present in the vocabulary without explicit registration.

| Refusal name | Meaning |
|---|---|
| `death_unverified` | No sealed death record exists for the testator, or the death record's seal fails verification. |
| `seal_broken` | The will's own seal fails verification — the will bytes were altered after sealing. |
| `will_superseded` | A later-sealed will for the same testator exists in the registry. |
| `sign_unoccupied` | A distribution entry names a sign whose bit in the will's vector is `0`. |
| `share_mismatch` | A distribution entry names the correct sign but the item is wrong; or the same sign appears more than once in the distribution list; or the number of distribution entries differs from the vector's popcount; or the will's `stated_popcount` differs from the actual count of `1` bits in the vector. |
| `beneficiary_unknown` | The sign and item are correct but the beneficiary does not match the will. |
| `unmeasured` | *(reserved by gate_core)* Measurement did not complete. |

---

## Measurement Precedence

Measurement is deterministic. The **first** failing check names the refusal and measurement stops. Subsequent checks are not reported.

1. **Death record check** — if no sealed death record exists for the testator named in the will, or if the death record's seal fails `verify_mandate`, return `passed=False, refusal_name='death_unverified'`.
2. **Will seal check** — if `verify_mandate` on the will returns `False`, return `passed=False, refusal_name='seal_broken'`.
3. **Supersession check** — if the registry contains a will for the same testator with a later `sealed_date`, return `passed=False, refusal_name='will_superseded'`. The receipt's observations must include the seal of the superseding will.
4. **Per-distribution checks** — for each entry in `payload.distributions`, in the order they appear:
   a. **Sign occupied?** — look up the sign's bit in the vector. If `0`, return `passed=False, refusal_name='sign_unoccupied'`.
   b. **Share correct?** — verify that `item` equals the will's bequest item for that sign; that the sign has not already appeared in an earlier distribution entry; that the total number of distribution entries equals the vector's actual popcount; and that `stated_popcount` equals the vector's actual popcount. Any violation returns `passed=False, refusal_name='share_mismatch'`.
   c. **Beneficiary correct?** — verify that `beneficiary` equals the will's bequest beneficiary for that sign. Mismatch returns `passed=False, refusal_name='beneficiary_unknown'`.
5. If all checks pass, return `passed=True`.

> **Note on total-count and stated_popcount checks:** these are logically part of the share check (step 4b) but may be evaluated eagerly before per-entry iteration if the implementation chooses. The refusal name is still `share_mismatch`.

---

## User Stories and Acceptance Criteria

### US-EX-1 — Seal and Register a Will

**As a** clerk admitting a will to the registry,
**I want to** seal the will's JSON content and store the sealed mandate,
**so that** any subsequent alteration of the will is detectable before adjudication.

**Acceptance Criteria**

- AC-EX-1.1: Sealing a will calls `gate_core.seal_mandate` with domain `"executor"` and the will's JSON content. The returned `SealedMandate` is stored in the registry.
- AC-EX-1.2: The registry maintains a list of sealed wills per testator name, ordered by `sealed_date` ascending.
- AC-EX-1.3: The registry exposes a `latest_will(testator: str) -> SealedMandate | None` operation that returns the will with the greatest `sealed_date` for that testator, or `None` if no will exists.
- AC-EX-1.4: Fixture files are loaded and sealed at registry initialisation time. Fixture paths are injected, not hard-coded.

---

### US-EX-2 — Seal and Register a Death Record

**As a** clerk admitting a certified death record,
**I want to** seal the death record and store it in the registry,
**so that** no estate claim may be processed without a verified record of death.

**Acceptance Criteria**

- AC-EX-2.1: Sealing a death record calls `gate_core.seal_mandate` with domain `"executor"` and the death record's JSON content. The returned `SealedMandate` is stored in the registry keyed by `deceased` name.
- AC-EX-2.2: The registry exposes a `death_record(name: str) -> SealedMandate | None` operation.
- AC-EX-2.3: A missing death record returns `None` from `death_record()`; it does not raise.

---

### US-EX-3 — Submit an Estate Distribution Claim

**As a** beneficiary or estate administrator,
**I want to** submit a proposed distribution of the estate,
**so that** the gate can adjudicate whether the distribution matches the sealed will.

**Acceptance Criteria**

- AC-EX-3.1: The claim has `domain="executor"`, `claim_type="estate_distribution"`, and a payload containing `will_ref` (the hex seal of the target will) and `distributions` (a list of `{sign, item, beneficiary}` entries).
- AC-EX-3.2: The `claims` helper constructs a valid `gate_core.Claim` from a plain Python dict without the caller needing to import gate_core directly.
- AC-EX-3.3: The claim is immutable after construction (inherits `frozen=True` from `gate_core.Claim`).

---

### US-EX-4 — Adjudicate a Distribution Claim

**As a** desk application,
**I want to** adjudicate an estate distribution claim against a sealed will,
**so that** assets are released only when the distribution exactly matches the will's terms.

**Acceptance Criteria**

- AC-EX-4.1: Adjudication calls `gate_core.adjudicate(claim, sealed_will, measurer, chain)` exactly once per claim. No executor code re-derives the mandate-verification or receipt-chaining logic.
- AC-EX-4.2: The `ExecutorMeasurer` performs the precedence checks in the order defined in the Measurement Precedence section above.
- AC-EX-4.3: On `PASS`, the verdict is `gate_core.Pass`. The receipt records all observed values (sign bits checked, items compared, beneficiaries confirmed).
- AC-EX-4.4: On `REFUSED`, the verdict is `gate_core.Refused` with exactly one name from the executor refusal vocabulary. The receipt records the refusal name and the observation that triggered it.
- AC-EX-4.5: A tampered will (bytes altered after sealing) causes `gate_core.MandateTamperError` to propagate from `adjudicate` before a receipt is appended. This is distinct from the `seal_broken` refusal: `seal_broken` is returned by the measurer when it independently re-verifies the will's seal inside `measure()`; `MandateTamperError` is raised by gate_core itself at the top of `adjudicate()`. Both paths are tested.

---

### US-EX-5 — Produce a Hash-Chained Receipt for Every Verdict

**As a** compliance officer,
**I want** every executor verdict to be recorded in a hash-chained receipt,
**so that** the full distribution history for an estate is tamper-evident.

**Acceptance Criteria**

- AC-EX-5.1: Each call to `adjudicate` appends exactly one receipt to the chain (unless `MandateTamperError` is raised).
- AC-EX-5.2: The receipt chain can be verified by `gate_core.verify_chain` and must return `ok=True` for a chain of legitimately issued receipts.
- AC-EX-5.3: A `will_superseded` receipt includes the seal of the superseding will in its observations, so an auditor can identify which will governs.

---

## Acceptance Scenarios (Demo)

These seven scenarios are the concrete acceptance tests for the executor desk. They use the Elias Vane fixtures. Elias Vane died on 2026-10-28; his 2024 will supersedes his 2019 will.

**Scenario A — Correct 7-bequest distribution under the 2024 will → PASS**

Submit a distribution with exactly the seven bequests from `will_2024.json` in any order, referencing the 2024 will's seal. Expected: verdict `PASS`; receipt chain length 1; all 7 signs confirmed in observations.

```
distributions:
  Aries    → The Iron Key       → whoever first knocks thrice on the chapel door after midnight on All Hallows' Eve
  Taurus   → The Stone Bull     → Marta, the neighbor
  Leo      → The Brass Telescope → the child who mapped the lion's heart from the hilltop in the summer of the comet
  Scorpio  → The Sealed Letter  → the one who knows what happened at the millpond in '87
  Capricorn → The Goat Bell     → the town itself
  Aquarius → The Water Jar      → the well-keeper's daughter
  Pisces   → The Two Fishhooks  → Silas Vane, brother of the testator
```

**Scenario B — Any distribution under the 2019 will → REFUSED `will_superseded`**

Submit a distribution referencing the 2019 will's seal. The registry holds both wills; the 2024 will is later. Expected: verdict `REFUSED('will_superseded')`; receipt observations include the seal of the 2024 will.

**Scenario C — 2024 distribution plus an eighth bequest → REFUSED `share_mismatch`**

Submit the correct seven distributions plus one additional entry (any sign, any values). The total entry count (8) exceeds the vector popcount (7). Expected: verdict `REFUSED('share_mismatch')`.

**Scenario D — Correct sign and item, wrong beneficiary for Scorpio → REFUSED `beneficiary_unknown`**

Submit the seven 2024 bequests but replace the Scorpio beneficiary with any other string (e.g. `"an unknown claimant"`). Expected: verdict `REFUSED('beneficiary_unknown')`.

**Scenario E — Bequest under Gemini → REFUSED `sign_unoccupied`**

Submit a distribution that includes an entry for Gemini (bit = 0 in the 2024 vector). Expected: verdict `REFUSED('sign_unoccupied')`.

**Scenario F — Death record removed from registry → REFUSED `death_unverified`**

Adjudicate the correct 2024 distribution against a registry that has no death record for Elias Vane. Expected: verdict `REFUSED('death_unverified')`.

**Scenario G — Will bytes altered after sealing → REFUSED `seal_broken`**

Construct a `SealedMandate` whose `content` has been modified after the seal was computed (simulating a tampered will file) but whose `seal` field still holds the original hash. The measurer detects this via `verify_mandate`. Expected: verdict `REFUSED('seal_broken')`.

> Note: if the tamper is applied to the `SealedMandate` passed to `adjudicate()` (not just held in the registry), `gate_core.MandateTamperError` will be raised before the measurer runs, per gate_core design. Scenario G tests the measurer path: the tamper is on the registry copy that the measurer retrieves, while the object passed to `adjudicate()` is intact — or alternatively, the test directly calls `measure()` with a tampered mandate. The unit test for `MandateTamperError` is a separate case.
