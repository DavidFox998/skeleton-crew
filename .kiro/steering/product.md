# Product Steering — Skeleton Crew

## Purpose

Skeleton Crew is a reusable gate skeleton validated by two real applications, each operating as a desk inside one small mortuary. It exists to prove that the same structural pattern can govern decisions in different domains without modification to the core.

## The Skeleton Pattern

Every desk in Skeleton Crew follows a single repeating structure:

1. **Typed claim** — a structured assertion submitted by a claimant.
2. **Independent measurement** — the claim is measured by code that has no interest in the outcome and no knowledge of who submitted the claim.
3. **Gate verdict** — the result is either `PASS` or `REFUSED`. A refusal always carries exactly one machine-readable refusal name drawn from a per-domain vocabulary.
4. **Hash-chained receipt** — every verdict produces a receipt that records the claim, the measurements, the verdict, and the hash of the previous receipt in the chain, making the entire history replayable and tamper-evident.

## The Two Desks

### Desk 1 — Executor

The mandate is a sealed will. A proposed estate distribution is submitted as a claim. The distribution is measured against the will before any asset may be released. The will is sealed at the moment it is admitted; nothing downstream may alter the mandate.

### Desk 2 — Citation Gate

An obituary draft contains factual claims. Each claim is submitted to the gate and measured against source records (vital statistics, contemporaneous records, verified citations). A claim may not appear in the published obituary until its verdict is `PASS`.

## Design Tone

All user interfaces across both desks share one tone: **quiet and dignified**.

- Visual effects are used only where they communicate state. Unverified claims appear as ghost text. Verified claims resolve to solid type. Refused claims are marked clearly but without alarm.
- No theatrical animation. No decorative motion. Every visual transition must earn its place by conveying information the user needs.
- Typography, spacing, and color are chosen for readability and restraint, not for brand expression.

## Hard Rules

1. **User interfaces display verdicts; they never decide them.** A UI may show a verdict, explain it, and present options for what to do next. It may not override, suppress, or alter a verdict.
2. **All decisional logic lives in the gate core library.** The gate core has no UI, no network access, and no I/O beyond explicit load/save helpers. It is a pure computation library.
3. **The gate core has no external dependencies.** Python standard library only.
4. **Seals are SHA-256 hashes over canonical JSON.** Canonical form is `json.dumps` with `sort_keys=True` and fixed separators `(', ', ': ')` stripped to `(',', ':')`.
