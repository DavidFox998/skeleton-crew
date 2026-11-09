# Technical Design — The Vault Web Skin

## Constraints
Python 3.11+ stdlib only. `webui` → `vault`, `gate_core`. No JS. Decisions only via `gate_core.adjudicate()` + `VaultMeasurer`. Follows the Notices skin structure: `state.py` (register) / `render.py` (pure HTML) / `server.py` (dispatch).

## Files
```
webui/state.py    + VAULT_SCENARIO_DEFINITIONS, VaultRegister
webui/render.py   + vault_page_shell, render_bundle, render_vault_desk,
                    render_vault_desk_with_result, render_vault_archive,
                    render_release_stamp; shared _house_nav() (3 groups); CSS additions
webui/server.py   + vault routes, HouseHandler.vault_register (lazy default)
run_webui.py      + constructs VaultRegister
tests/test_vault_ui.py
```

## VaultRegister (state.py)
- `__init__(fixtures_dir=vault.scenarios.DEFAULT_FIXTURES)`: builds the bundle in a temp dir (`vault.build_bundle`), seals it once with `vault.lock_bundle(BUNDLE_ID, root)` → `_lock_record` (a `SealedMandate`); holds `VaultMeasurer`, `_chain`, `_mutex` (threading.Lock).
- `lock_record` property; `papers()` → `[(path, sha256)]` read from the lock content.
- `adjudicate_preset(label) -> (verdict | None, receipt | None, tamper_error)`: under the mutex builds the presented bundle for the label in a fresh temp copy (mutation = the situation, nothing more), `present_bundle(...)`, and calls `adjudicate(claim, lock, measurer, chain)`. B6 passes a forged lock (original seal, altered table) exactly as `vault.scenarios` does. `MandateTamperError` → `(None, None, True)`; nothing appended. Unknown label → `KeyError`.
- `chain_snapshot()`, `verify_vault_chain()`, `tamper_demo()` (deep copy; alters `payload.bundle_id`/first file hash in the last receipt, keeps stale `own_hash`; never touches `_chain`).

## Routes (server.py)
GET `/vault`, `/vault/desk`, `/vault/archive`; POST `/vault/preset`, `/vault/archive/verify`, `/vault/archive/tamper`. `HouseHandler.vault_register` defaults to a lazily built register so existing test harnesses that set only `register` and `notices_register` keep working.

## Rendering
- Stamp: `<div class="release-stamp"><p class="verdict-pass|verdict-refused">…</p>` + certificate (`span.hash.certificate`) + named paper (`span.hash.paper-path`) + one-line caption; derived solely from `receipt.verdict` and `receipt.measurements`.
- Bundle page: `table.fact-table` of `path | span.hash.paper-seal`; certificate `span.hash.certificate`; lock seal `span.hash.lock-seal`.
- Tamper: `seal-broken-notice` with `REFUSED · seal_broken`; "not recorded in the vault chain".
- CSS: only `.release-stamp` (same hairline/padding language as `.publish-stamp`); no new transitions or animation.

## Decisions
- Presets rebuild a real bundle on disk and take the real census, so the measurer sees what the scenarios see; the skin does not hand-craft manifests.
- `seal_broken` is a display label for the hard error (as in the other desks), not a vault refusal.
- No free builder (not in the brief).
