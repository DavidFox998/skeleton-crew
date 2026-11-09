# META SUMMARY v4 — Skeleton Crew (rewritten 2026-11-03)

For the Devpost summary and the write-up. Points at key moments in the
film; the film is the demonstration, this is its index.

## What this is

Skeleton Crew is one gate skeleton — typed claim → independent measurement
against a sealed record → PASS with a hash-chained receipt, or REFUSED
with a machine-readable refusal name — proven by two applications built
from it: an estate desk (Executor) and a mortuary notices desk (Citation
Gate). The demo film puts a man inside that system for one night and lets
the desks measure him.

## The Anchored Collision API — and what it enables

Every measurement in the skeleton is an ANCHORED COLLISION: a claim is
routed to collide with a sealed anchor — the mandate, the record, the
will — and the verdict is the result of that collision, anchored in a
replayable receipt chain. Nothing is asserted; things collide, and the
collision is the evidence.

What it enables:

1. **Verdicts that are evidence, not opinions.** Anyone can re-run the
   collision and get the same verdict, bit for bit (film: the Archive
   replay — and what a broken anchor looks like: CHAIN FAILED AT
   RECEIPT INDEX 1).
2. **Refusals an agent can act on.** A refusal NAMES itself
   (will_superseded, source_contradicts, death_unverified), so calling
   systems can route, retry, or escalate instead of parsing prose
   (film: every stamp that falls).
3. **Honesty about the unmeasurable.** A claim that cannot collide with
   any anchor is not waved through or argued with — it is recorded as
   unmeasured, and it does not proceed (film: the millpond claim; the
   closing receipt's blank disposition).
4. **Tenant replaceability.** Any measurer implementing the same
   collision produces the same verdicts; the anchor, not the operator,
   is the authority (film: three desks, one rule, no desk decides
   differently).

## The Honesty Act and the virtue map

The Honesty Act, as framed in the virtue map (2026-10-25): AI culture
ranks by honesty; an assertion without measurement is a claim minted,
not proven. The mapped virtues and their enabling behaviors are the
skeleton's parts list:

- **Honesty → Proven.** No claim stands on its own say-so; it collides
  or it is unmeasured. (The Register's intake.)
- **Integrity → Apathy.** The desks' flatness is the behavior that
  enables integrity: no pleading, grief, or status moves a verdict.
  (Every conversation Silas loses by being human at a procedure.)
- **Transparency → Receipts.** Every verdict issues a receipt; the chain
  is the memory. (The Archive.)
- **Accountability → Anchor.** Authority lives in the sealed record, not
  in whoever is on duty. (Two wills; the later seal governs — the same
  answer a Michigan jury reached in 2023.)
- **Candor → Named refusal.** The system says no in words a machine can
  file. (The stamps.)

## Where this answers current AI mandates

- **EU AI Act, Art. 12 (record-keeping):** high-risk systems must log
  events for traceability. The receipt chain is exactly this, by
  construction — and the film's Archive scene shows the log being
  *replayed*, not merely kept.
- **EU AI Act, Art. 13 (transparency):** instructions and outputs a
  deployer can interpret. Named refusals and receipts are
  machine-interpretable outputs, not prose.
- **EU AI Act, Art. 14 (human oversight):** the system is built so a
  human can intervene — because it fails CLOSED. Unmeasured and tampered
  claims halt and append nothing; oversight is never asked to catch a
  silent pass.
- **NIST AI RMF (Measure / Manage):** risk is measured at the point of
  the claim and managed by named refusal — measured, not minted.
- **ISO/IEC 42001 (AI management):** an auditable control loop — claim,
  measure, verdict, receipt, replay — is the management system in
  miniature.

The mandates ask, in different words, for one thing: systems that can
show their work and refuse when they cannot. This is that, running, in
two desks of a mortuary — with a man at the counter learning what every
deployer is about to learn: the house keeps what it cannot measure.
