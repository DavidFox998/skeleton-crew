# Executor Web Skin — Design Brief (approved by David, 2026-11-02)

The skin is a wrapper. It displays verdicts; it never decides them. All decisions
come from gate_core.adjudicate() via the executor measurer.

## Decisions

1. **No house name.** Title: "The Estate Desk". One quiet line beneath:
   "Nothing leaves this house unmeasured."
2. **Three rooms.** The Register (case file: testator, sealed death record,
   both wills side by side — 2019 in grayscale, its one-bit vector difference
   visible). The Desk (workbench: compose and judge distributions).
   The Archive (the receipt chain, replay, tamper demonstration).
3. **Paper-ledger look.** Off-white paper, ink-black serif type, hairline rules.
   The only color is verdict state: unmeasured = ghost gray; PASS = solid ink
   with seal mark; REFUSED = muted oxblood, name set like a stamp
   (REFUSED · will_superseded). No animation except a claim resolving
   ghost -> solid when its verdict returns (state change, not decoration).
   No theatrical effects of any kind.
4. **The Desk tells the story in order.** Seven preset claims as a casework
   sequence (death verified; old will refused; true will passes; then the
   breaks: eighth bequest, wrong hands, empty sign, altered page). Below the
   presets, a free builder: pick a will, add bequests via dropdowns,
   beneficiaries TYPED as free text (typing the wrong name is how
   beneficiary_unknown happens in real casework).
5. **Receipts print in full.** Every verdict returns its complete ledger entry
   on the Desk: claim, measurements, verdict, previous hash, own hash.
   No truncation for prettiness.

## Web semantics

- One append-only house chain (the Register's chain) held by the server.
  Every adjudication that produces a receipt appends it there, whichever will
  it concerned — a real register of everything the desk has judged.
- Scenario F (no death record) adjudicates against a registry view without
  the death record; its refusal receipt still appends to the house chain.
- Scenario G (altered will) raises the core's hard tamper error; the Desk
  presents it under the name seal_broken and NOTHING is appended.
- The Archive's tamper demonstration operates on a COPY of the chain;
  the house chain itself is never mutated by a demonstration.

## Scope boundary

Executor only. Citation Gate gets a sibling notices-desk skin later,
sharing this paper and ink. Tech: Python 3.11+ standard library only
(http.server), no external dependencies, server-rendered HTML/CSS.
