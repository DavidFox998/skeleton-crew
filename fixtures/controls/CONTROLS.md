# Historical control cases

Two real, publicly documented deaths, encoded as desk fixtures to test whether
the Skeleton Crew engines measure *data they were not built for*. Facts are
drawn from public sources (probate reporting of the Monroe will; standard
biographical records for Poe). The fictional Vane fixtures remain the demo.

## Case 1 — Marilyn Monroe (1962) — positive control, both desks

- Will executed January 1961 (commonly dated 14 January), filed for probate in
  New York; briefly contested, admitted as valid. Bequests encoded one per slot:
  75% of the residue + all personal effects to Lee Strasberg; 25% of the
  residue to Dr. Marianne Kris (for psychiatric work); $100,000 in trust for
  her mother Gladys Baker; $10,000 each to half-sister Bernice Miracle and
  secretary May Reis; $5,000 each to Norman and Hedda Rosten. The Brentwood
  house took no specific bequest and fell to the residue — the one empty slot.
- Death: found dead 5 August 1962 at 12305 Fifth Helena Drive, Brentwood,
  aged 36. Official finding: acute barbiturate poisoning, "probable suicide";
  the circumstances have been publicly disputed ever since.
- Expected: a faithful distribution PASSes at the Executor desk; the residue
  reassigned to Arthur Miller (who took nothing under the will) is refused
  `beneficiary_unknown`; a short distribution is `share_mismatch`. At the
  notices desk, a wire-style obituary mixing true facts with the Miller claim
  and an invented house bequest to Eunice Murray is refused
  (`source_contradicts`, then `unsupported_claim`) and publishes only once
  corrected.

## Case 2 — Edgar Allan Poe (1849) — negative control, notices desk

- Died 7 October 1849 in Baltimore, cause never established; born 19 January
  1809 in Boston. Died intestate — no will exists; Griswold's literary
  executorship came from Maria Clemm's appointment, not a testament.
- The draft measured here is modelled on Rufus Wilmot Griswold's "Ludwig"
  obituary (New-York Tribune, 9 October 1849) and Memoir — the most famous
  false obituary in American letters.
- Expected: the death facts PASS; a Baltimore birthplace claim is refused
  `source_contradicts`; the claim that Poe's will appointed Griswold is
  refused `unsupported_claim` (there is no will to cite).
- KNOWN SCHEMA LIMIT found by this control: Griswold's most famous factual
  falsehood — that Poe was *expelled* from the University of Virginia (he
  left; he was not expelled) — cannot be measured yet, because the family
  record's fact table has no education key. The desk refuses what it can
  measure and is silent on what it cannot; extending the fact extractors is
  the recorded fix.

## Executor control result — the desk's true boundary (found 2026-11-02)

The Citation desk measured both real cases with no adaptation. The Executor
desk could not take the Monroe case at all, and the control found exactly
why, in two layers inside `executor/measurer.py`:

1. The vector must be exactly 12 bits, or the claim is refused
   `seal_broken` with reason `vector_length_mismatch`.
2. Occupancy is computed by zipping the vector against a hard-coded
   `ZODIAC_MSB_TO_LSB` constant — bequest keys that are not zodiac signs
   read as `sign_unoccupied` regardless of the will's own contents.

So the Executor, as built, is an instrument for zodiac-keyed wills only —
the Vane case's shape lives inside the app, not just its fixtures. The
gate_core underneath is untouched by this (the Citation desk proves its
generality on the same data). The recorded fix, when taken: the measurer
derives its slot keys and vector length from the mandate itself (the
bequests' own keys plus `empty_signs`), which leaves the Vane case —
whose keys are the zodiac — behaving identically.

Encoding note: the Executor's slot keys are the harness's keying only. Every
amount, name, date, and place above is the historical record.

## Resolution — measurer generalization (2026-11-02, on David's order)

The Executor measurer no longer consults a zodiac constant. Each will
carries a sealed `slots` list — the ordered slot names its vector's bits
correspond to — and the measurer reads the layout from the mandate itself
(the zodiac list survives only as a legacy fallback for mandates without
`slots`). Because the slots live inside the sealed content, the layout is
itself under seal. Full suite after the change: **220 tests, all green**,
Vane scenarios A–G identical. The desk's bit order for the Vane wills is
the house's historical order (sealed in the fixtures), not the textbook
zodiac sequence — the generalization makes that order explicit data
instead of hidden code.

## Case 3 — Aretha Franklin (2018) — court control: supersession

Two handwritten wills: 2010 (notarized, locked cabinet; Bloomfield Hills
house to Ted White Jr. and Kecalf Franklin equally; business-class
condition) and March 2014 (spiral notebook under a couch cushion; the
house to Kecalf alone; executor crossed out and replaced). July 2023,
Oakland County probate jury: **the 2014 will governs**.

Desk results — the registry's governing will is the 2014 will, as the
jury found. A faithful 2014 distribution PASSes; a distribution under
the 2010 will is refused `will_superseded`; the 2010 house term asserted
under the 2014 will is refused `beneficiary_unknown`. Notices desk: her
Detroit death PASSes; the common claim she was *born* in Detroit (she
was born in Memphis and raised in Detroit) is refused
`source_contradicts`; the house-to-Kecalf report PASSes.

## Case 4 — Howard Hughes (1976) — court control: forgery and intestacy

Hughes died intestate; the handwritten "Mormon Will" that surfaced at
LDS headquarters (sixteenths to the church, the Boy Scouts, an orphans'
home, his ex-wives, and Melvin "DuMar" of Gabbs, Nevada) was ruled a
**forgery by a Nevada jury in June 1978**.

Desk results — with no will in the registry, the Executor desk has no
mandate and cannot open the case (the intestacy truth). The Mormon Will
presented as a mandate, its seal computed over a tidied text rather than
the document as written, halts adjudication with the hard tamper error
— the desk's `seal_broken`, matching the jury. Notices desk: his death
date PASSes; "died in Las Vegas" is refused `source_contradicts` (he
died en route to Houston); the Dummar sixteenth, cited to the probate
record, is refused `unsupported_claim`.

## Study result (2026-11-02)

Four real deaths, both desks, every verdict matching the historical and
court record: Monroe (1961 will executes clean; Miller and Murray
claims refused), Poe (Griswold's inventions refused; no will to cite),
Franklin (the desk and the jury pick the same will), Hughes (no mandate
to open; the forged mandate halts the desk). Remaining known limit: the
family fact table's fixed keys (no education fact — Griswold's UVA
"expulsion" lie is still unmeasurable), recorded above.
