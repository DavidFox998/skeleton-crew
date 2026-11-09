# Skeleton Crew

One skeleton, two bodies.

**Skeleton Crew** is a reusable gate skeleton — a lean template for systems
where nothing moves on an assertion alone — proven by two distinct
applications built from it: the two desks of a small mortuary that handles
the estates ordinary probate cannot settle.

> The dead leave instructions. The living leave claims. Both get measured.

## The skeleton

Every action in both applications passes through one gate:

```
typed claim → independent measurement → gate verdict → hash-chained receipt
```

- A **claim** is typed and specific: who asks, for what, under which mandate.
- A **measurer** checks the claim against a **sealed mandate** (SHA-256 seal
  over canonical JSON). It does not trust the claim; it measures it.
- The **gate** returns `PASS`, or `REFUSED` with a machine-readable refusal
  name (`death_unverified`, `will_superseded`, `source_contradicts`, …).
  A measurer that cannot measure fails closed: `unmeasured`. A broken seal
  is not a refusal — it is a hard tamper error, and nothing proceeds.
- Every verdict is written to a **hash-chained receipt log** that can be
  replayed and verified end to end. Interfaces display verdicts; they never
  decide them.

Python 3.11+, standard library only. No network calls.

## The two desks

**The Estate Desk** (`executor/`, skin: "The Estate Desk")
A sealed will is the mandate. Proposed distributions are measured before
anything is released: the death itself is a claim (a missing or unsealed
registrar death record is refused `death_unverified`), then seal integrity,
supersession, share arithmetic, and beneficiary occupancy. Fixture case:
the Vane estate — the distribution under the 2019 will is refused
`will_superseded`; under the governing 2024 will it passes, item by item —
except one bequest addressed to *"the one who knows what happened at the
millpond in '87."* Knowledge cannot be measured. The letter is kept.

**The Notices Desk** (`citation_gate/`, skin: "The Notices Desk")
An obituary draft is a bundle of factual claims. Each claim must cite a
sealed source (death record, will, family record) and match it exactly
before the notice may be printed. Publish only when *every* assertion has
a PASS receipt.

Historical controls in `fixtures/controls/` (Monroe, Poe, Franklin,
Hughes) were run through both desks; every verdict matches the public
record, including the cases the desks must refuse or keep unmeasured.

## Run it

```sh
python3 -m unittest discover -s tests   # 220 tests
python3 run_webui.py                    # both desk skins on localhost:8000
```

## Layout

- `gate_core/` — the skeleton: claims, mandates, seals, measurers, gate, receipts
- `executor/` — Estate Desk application
- `citation_gate/` — Notices Desk application
- `webui/` — the two paper-ledger web skins (no JavaScript; verdicts rendered from real desk output)
- `fixtures/` — the Vane estate files and the historical controls
- `.kiro/` — steering and the spec files this project was built from
- `docs/` — story, design briefs, house staff, and build notes

## How it was built

Built with **Kiro** (spec-driven development, driven through the Kiro CLI
and Kiro Web) for Kiroween 2026, Skeleton Crew category. The gate pattern —
typed claims, sealed mandates, named refusals, chained receipts — is the
author's own prior work; all code in this repository was written fresh for
this project. One disclosed patch: when a build session hit the Kiro usage
cap, the Notices Desk server bootstrap glue (~100 lines in
`webui/server.py`) was completed by hand and is marked as such in the
project notes.

License: MIT (see `LICENSE`).
