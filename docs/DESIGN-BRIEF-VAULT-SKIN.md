# Design Brief — The Vault (web skin for the bundle desk)

Status: prepared 2026-11-09 at David's direction as the third skin of the
house. It mirrors the approved Estate Desk brief (docs/DESIGN-BRIEF-WEB-SKIN.md)
and the Notices brief (docs/DESIGN-BRIEF-NOTICES-SKIN.md), and rests on the
ratified Vault desk (.kiro/specs/vault/, including its 2026-11-08 ratification).
Binding for the vault-ui spec.

## 1. One house, third desk

The web house gains the Vault's rooms beside the estate and notices rooms.
Both existing desks' pages and routes are unchanged. Navigation in the shared
header links all three desks, as three visibly separate groups. Vault title:
**The Vault**. Desk line: ***"Nothing leaves this house unmeasured — not even
the records."*** Both appear on every Vault room. The house tagline of the
other desks stays as is.

## 2. Three rooms

- **The Bundle** — this desk's register: the sealed estate file as the house
  holds it. The four papers (will, death record, family record, inventory),
  each with its own SHA-256 seal in canonical (path) order; the single
  **bundle certificate** (the hash of that table); the bundle id and the seal
  of the lock record itself. Nothing here is editable; no forms.
- **The Release Desk** — the workbench: six presets B1–B6 (§3). No free
  builder in this skin.
- **The Vault Archive** — the vault chain: every receipt in full, replay
  verification, and the tamper demonstration on a copy (the vault chain is
  never mutated), mirroring the other archives.

## 3. Presets — the six release scenarios

Buttons B1–B6 in narrative order, each presenting a bundle for release and
re-measuring it against the lock record:

| # | The bundle presented | Stamp |
|---|---|---|
| B1 | untouched | `PASS` — the bundle may leave |
| B2 | an inventory figure altered | `REFUSED · file_changed`, naming the paper |
| B3 | a stray paper added | `REFUSED · file_added`, naming the paper |
| B4 | the death record removed | `REFUSED · file_missing`, naming the paper |
| B5 | restored | `PASS`, under the original certificate |
| B6 | the lock record itself altered | `REFUSED · seal_broken` (hard tamper) |

Each result prints the stamp, the certificate the verdict was measured
against, the named paper (for a refusal), and the full receipt. Every stamp
shown is rendered from the desk's real output (the receipt the gate issued);
the preset's printed "Expected" line is a caption only and is never the
source of a stamp. Ghost → solid on verdict, as before; oxblood stamp for
refusals; no alarm.

## 4. Chain and state language

The Vault keeps its **own chain**, separate from the estate and notices
chains: one append-only house chain for the vault domain. Preset receipts
append to it (PASS and REFUSED alike). The chain is never edited and never
shrinks. Same paper-ledger palette — paper `#faf7f0`, ink `#1a1714`,
oxblood `#7a2e2a`, ghost grey, hairlines — and Georgia serif; no JavaScript;
no animation beyond the single existing claim-block ghost→solid colour/opacity
transition. All text escaped. **Interfaces display verdicts, never decide
them**: every verdict comes from `gate_core.adjudicate()` with the
`VaultMeasurer`; the skin holds no comparison, hashing-for-judgement or
precedence logic of its own.

## 5. Hard stop — the altered lock record

If the lock record does not recompute, adjudication halts with the gate's hard
tamper error and **nothing is appended**. The page presents it as
`REFUSED · seal_broken`, inside a seal-broken notice, HTTP 200, stating that
the event was not recorded in the vault chain — mirroring estate scenario G
and the Notices behaviour. (`seal_broken` is a display label for the hard
error, not a vault refusal name; the vault vocabulary stays
`file_changed`, `file_missing`, `file_added`.)

## 6. Disclosure

The bundle-certificate method is the author's own prior work (Appendix G),
disclosed in the Vault spec; the skin repeats nothing of it beyond what the
desk displays. Python standard library only.
