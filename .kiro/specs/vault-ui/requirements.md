# Requirements — The Vault Web Skin

**Binding design brief:** `docs/DESIGN-BRIEF-VAULT-SKIN.md`. Desk spec: `.kiro/specs/vault/` (incl. its ratification). Pattern: `.kiro/specs/notices-ui/`.

## 1. Scope and identity

**REQ-1.1** Adds a third desk, The Vault, to the web house. The estate (`/`, `/desk`, `/archive`) and notices (`/notices/*`) routes are unchanged.

**REQ-1.2** Title **"The Vault"**; line *"Nothing leaves this house unmeasured — not even the records."* Both appear on every Vault room.

**REQ-1.3** Python 3.11+ standard library only; no JavaScript. `webui` may import `vault` and `gate_core`; `gate_core`, `vault`, `executor`, `citation_gate` are not modified.

**REQ-1.4** Same paper-ledger language: paper `#faf7f0`, ink `#1a1714`, oxblood `#7a2e2a`, Georgia serif.

AC-1.1 Estate and notices routes return 200 with their previous content. AC-1.2 Every Vault room contains the title and line. AC-1.3 No `<script>` on any page. AC-1.4 CSS contains the palette; only one `transition:` (claim-block colour/opacity) and no animation.

## 2. Navigation

**REQ-2.1** Every house page links all nine rooms: `/`, `/desk`, `/archive`, `/notices/sources`, `/notices`, `/notices/archive`, `/vault`, `/vault/desk`, `/vault/archive`.
**REQ-2.2** The three desks render as separate nav groups.

## 3. Rooms

| Room | Path | Purpose |
|---|---|---|
| The Bundle | `GET /vault` | Lock record: four papers, per-paper seals, bundle certificate, bundle id, lock seal. No forms. |
| Release Desk | `GET /vault/desk` | Presets B1–B6. |
| Vault Archive | `GET /vault/archive` | Vault chain, verification, tamper demonstration. |

**REQ-3.1** The Bundle lists the papers in canonical path order with their full SHA-256 seals and the full bundle certificate, rendered from the register's real lock record.
**REQ-3.2** The Release Desk lists B1–B6 in order, each with a "Run Bn" form posting `preset` to `POST /vault/preset`.
**REQ-3.3** The Archive shows every receipt in full (own and previous hashes), the receipt count, a verify form, and a tamper-demonstration form.

## 4. Adjudication

**REQ-4.1** `POST /vault/preset` with `preset=B1..B6` presents the corresponding bundle (as built by `vault.scenarios`' own situation: untouched; inventory figure altered; stray paper added; death record removed; restored; lock record altered) and calls `gate_core.adjudicate()` with `VaultMeasurer` against the register's lock record. The skin contains no comparison or precedence logic.
**REQ-4.2** Verdicts: B1 PASS; B2 `file_changed`; B3 `file_added`; B4 `file_missing`; B5 PASS under the original certificate; B6 hard tamper. Verdicts agree with `vault.scenarios.run_scenarios()`.
**REQ-4.3** A result shows the stamp, the certificate measured against, the named paper for a refusal, and the full receipt. The stamp is rendered from the issued receipt, not from the preset's "Expected" caption.
**REQ-4.4** Unknown or missing `preset` → HTTP 400.

## 5. Chain

**REQ-5.1** One append-only vault chain per register, separate from the estate and notices chains. Every receipt-producing preset appends exactly one receipt.
**REQ-5.2** The chain is guarded by a lock and never mutated by the tamper demonstration (runs on a deep copy; reports `hash_mismatch`).
**REQ-5.3** `POST /vault/archive/verify` replays the chain with `verify_chain`.

## 6. Hard stop

**REQ-6.1** If the lock record does not recompute (preset B6, or the register's lock altered after sealing), `MandateTamperError` is caught and the page shows `REFUSED · seal_broken` in a `seal-broken-notice`, HTTP 200, with no stamp/receipt and **nothing appended** to the chain.

## 7. Safety

**REQ-7.1** All dynamic text is HTML-escaped.
**REQ-7.2** The skin displays verdicts and never decides them.
