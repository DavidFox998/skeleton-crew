# Requirements — Gate Core Library

## Overview

The gate core library is the shared decision engine for all Skeleton Crew desks. It accepts typed claims, measures them against a sealed mandate, and issues tamper-evident verdicts. It contains no UI and no network access.

---

## User Stories and Acceptance Criteria

### US-1 — Submit a Typed Claim Against a Sealed Mandate

**As a** desk application,  
**I want to** submit a typed claim against a sealed mandate,  
**so that** the gate can evaluate whether the claim satisfies the mandate's terms.

**Acceptance Criteria**

- AC-1.1: A claim carries a domain identifier, a claim type, and a structured payload. The domain identifier links the claim to the correct mandate and refusal vocabulary.
- AC-1.2: A mandate is sealed before any claims are submitted against it. Once sealed, the mandate's content cannot be altered.
- AC-1.3: The gate rejects any claim submitted against a mandate whose seal cannot be verified. The rejection is distinct from a gate refusal and is raised as an error.
- AC-1.4: Claims are immutable value objects after construction.

---

### US-2 — Measure the Claim with Independent Code

**As a** gate core library,  
**I want to** invoke a measurement function that is independent of the claimant,  
**so that** the outcome cannot be influenced by the party who submitted the claim.

**Acceptance Criteria**

- AC-2.1: Measurement is performed by a component that conforms to a defined measurement protocol. The protocol accepts a claim and a mandate and returns a structured measurement result.
- AC-2.2: The measurement component has no access to verdict-forming logic. It observes and reports; it does not decide.
- AC-2.3: The measurement result records every observed value that influenced or could influence the verdict, keyed by a stable name.
- AC-2.4: If measurement raises an unhandled exception, the gate treats the claim as unmeasured (see US-4) and records the exception message in the receipt.

---

### US-3 — Issue a PASS or REFUSED Verdict

**As a** desk application,  
**I want to** receive a verdict of either PASS or REFUSED with a named reason,  
**so that** downstream logic can act on a definitive, machine-readable outcome.

**Acceptance Criteria**

- AC-3.1: The verdict is exactly one of two forms: `PASS` or `REFUSED(name)` where `name` is a string drawn from the per-domain refusal vocabulary registered for the claim's domain.
- AC-3.2: A `PASS` verdict carries no refusal name.
- AC-3.3: A `REFUSED` verdict carries exactly one refusal name. It never carries more than one.
- AC-3.4: The gate raises an error if a verdict attempts to use a refusal name that is not registered in the domain's vocabulary.
- AC-3.5: Verdicts are immutable value objects.

---

### US-4 — Refuse an Unmeasured Claim

**As a** desk application,  
**I want** any claim that was never measured to be refused with the refusal name `unmeasured`,  
**so that** gaps in measurement coverage are always surfaced as explicit, auditable refusals rather than silent failures.

**Acceptance Criteria**

- AC-4.1: If no measurement result is produced for a claim—whether because no measurer was registered, measurement raised an exception, or measurement was explicitly skipped—the verdict is `REFUSED('unmeasured')`.
- AC-4.2: The refusal name `unmeasured` is a reserved name present in every domain's refusal vocabulary without requiring explicit registration.
- AC-4.3: A claim cannot receive a `PASS` verdict without a corresponding measurement result.

---

### US-5 — Produce a Hash-Chained Receipt for Every Verdict

**As a** compliance officer,  
**I want** every verdict to produce a receipt that chains to the previous receipt,  
**so that** the full decision history is tamper-evident and independently auditable.

**Acceptance Criteria**

- AC-5.1: A receipt contains: the claim (verbatim), the measurement result (or a null measurement record with an explanation), the verdict, a UTC timestamp, and the SHA-256 hash of the immediately preceding receipt in the chain.
- AC-5.2: The first receipt in a chain uses a sentinel previous-hash value of 64 zero hex characters (`"0" * 64`).
- AC-5.3: The receipt's own hash is computed as SHA-256 over its canonical JSON serialization, excluding the `own_hash` field itself.
- AC-5.4: Receipts are immutable after creation.
- AC-5.5: A receipt can be serialized to and deserialized from canonical JSON without loss.

---

### US-6 — Replay and Verify the Receipt Chain

**As a** compliance officer,  
**I want to** replay the entire receipt chain and be told of the first broken link,  
**so that** I can detect any tampering or reconstruction error in the audit trail.

**Acceptance Criteria**

- AC-6.1: A replay function accepts an ordered list of receipts and returns a `ReplayResult`.
- AC-6.2: If all receipts are intact and correctly chained, the `ReplayResult` reports success.
- AC-6.3: If any receipt's stored hash does not match its recomputed hash, the `ReplayResult` reports failure and identifies the index of the first failing receipt.
- AC-6.4: If any receipt's stored previous-hash does not match the own-hash of the preceding receipt, the `ReplayResult` reports failure and identifies the index of the first broken link.
- AC-6.5: Replay stops at the first failure and does not report subsequent issues.

---

### US-7 — Seal and Verify a Mandate

**As a** desk application,  
**I want to** seal a mandate as a SHA-256 hash over its canonical JSON,  
**so that** any subsequent alteration of the mandate is detectable.

**Acceptance Criteria**

- AC-7.1: Sealing a mandate produces a hex-encoded SHA-256 digest computed over the canonical JSON of the mandate's content.
- AC-7.2: Canonical JSON is produced by `json.dumps` with `sort_keys=True` and separators `(',', ':')`.
- AC-7.3: Verifying a mandate recomputes the seal and compares it to the stored seal. Verification returns `True` if they match, `False` otherwise.
- AC-7.4: The seal is stored alongside the mandate content and is accessible for inclusion in receipts.
