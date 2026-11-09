# Design Brief — The Notices Desk (web skin for Citation Gate)

Status: prepared by Talitha 2026-11-02 under David's "I'm game" — mirrors the
approved Estate Desk brief (docs/DESIGN-BRIEF-WEB-SKIN.md) in the same house.
One canon fix rides along (item 7).

## 1. One house, second desk

The web house gains the Citation Gate's rooms beside the estate rooms. The
estate pages (Register / Desk / Archive) are unchanged. Navigation in the
shared header links both desks. Notices title: **The Notices Desk**. Desk
line: **"Nothing is printed here unmeasured."** The house tagline stays as is.

## 2. Three rooms

- **The Sources** — this desk's register: the three sealed source records the
  house holds (death record, governing will of 2024, family record), each
  shown with its seal and its full fact table — the facts print is measured
  against. Nothing here is editable.
- **The Notices Desk** — the workbench (presets + free builder, §3–4).
- **The Notice Archive** — the notices chain: every receipt in full, replay
  verification, and the tamper demonstration on a copy (house chain never
  mutated), mirroring the estate Archive.

## 3. Presets — the six scenario drafts

Buttons N1–N6 in narrative order, each running its whole draft: every
assertion printed with its sentence, verdict state (ghost = unmeasured,
solid ink = PASS, oxblood stamp `REFUSED · <name>`), and its receipt. The
draft's publish decision is stamped at the foot: `PUBLISHABLE` with the
receipt ids, or `REFUSED · <first refusal name>`. N5 runs both phases in one
action (draft refused, correction appended, draft publishable). Preset
receipts append to the notices chain; publish checks always evaluate the
draft's own assertions, never the whole chain.

## 4. Free builder — compose a draft assertion by assertion

Fields: the sentence as it will print (text); the fact key (a dropdown of
every fact key the three sources expose, labelled with its source); the
claimed value (typed free text — typing the wrong value is how
`source_contradicts` happens); the citation (death record / will / family
record / *no citation* — choosing none is how `missing_citation` happens).
"Measure this assertion" adjudicates it onto the notices chain and adds it
to the working draft; after each assertion the working draft's publish
state is shown. "Begin a new draft" closes the working draft (the chain is
append-only — nothing is ever removed; the archive keeps everything).

## 5. Chains and state language

The notices desk keeps its **own chain**, separate from the estate chain —
each desk's receipts are its own ledger. Same paper-ledger palette and
typography as the estate rooms; same stamp language; no animation except a
claim resolving ghost→solid on verdict, as before. All user input escaped;
interfaces display verdicts, never decide them.

## 6. Hard stops

If a cited source's seal fails, adjudication halts with the gate's hard
tamper error and nothing is appended (the Citation Gate behavior verified
2026-11-02); the page presents it as `REFUSED · seal_broken`, mirroring
estate scenario G's presentation.

## 7. Canon fix riding along (David's wording, 2026-11-02)

Elias Vane was a **self-professed Tree Wizard**. The family record's
occupation fact, the citation scenarios' assertion text/value (N1, N5), and
the matching test are updated together: value `self-professed Tree Wizard`,
sentence "He was a self-professed Tree Wizard." The full suite must stay
green with the new wording.
