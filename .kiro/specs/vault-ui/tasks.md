# Tasks — The Vault Web Skin

Spec: `requirements.md`, `design.md`, `docs/DESIGN-BRIEF-VAULT-SKIN.md`. Decisions only via `gate_core.adjudicate()` + `VaultMeasurer`.

## 1. Spec
- [x] 1.1 `.kiro/specs/vault-ui/{requirements,design,tasks}.md`
- [x] 1.2 `docs/DESIGN-BRIEF-VAULT-SKIN.md`

## 2. state.py
- [x] 2.1 `VAULT_SCENARIO_DEFINITIONS` (B1–B6, with label, description, expected_verdict)
- [x] 2.2 `VaultRegister`: lock record sealed once, own chain, mutex, `lock_record`, `papers()`
- [x] 2.3 `adjudicate_preset(label)` via `adjudicate()` + `VaultMeasurer`; tamper → `(None, None, True)`, nothing appended; unknown label → `KeyError`
- [x] 2.4 `chain_snapshot()`, `verify_vault_chain()`, `tamper_demo()` on a copy

## 3. render.py
- [x] 3.1 Shared three-group nav on all shells
- [x] 3.2 `vault_page_shell` (title + line)
- [x] 3.3 `render_bundle` (papers, seals, certificate, lock seal; no forms)
- [x] 3.4 `render_release_stamp`, `render_vault_desk`, `render_vault_desk_with_result` (incl. seal-broken notice)
- [x] 3.5 `render_vault_archive`
- [x] 3.6 `.release-stamp` CSS only; no new transition/animation

## 4. server.py / run_webui.py
- [x] 4.1 GET `/vault`, `/vault/desk`, `/vault/archive`
- [x] 4.2 POST `/vault/preset` (400 on missing/unknown), `/vault/archive/verify`, `/vault/archive/tamper`
- [x] 4.3 `vault_register` class attribute with lazy default; `run()` and `run_webui.py` wiring

## 5. Tests (`tests/test_vault_ui.py`)
- [x] 5.1 Render: bundle page stamps, desk presets, archive, shell/nav
- [x] 5.2 B1–B6 verdicts, parity with `vault.scenarios.run_scenarios()`
- [x] 5.3 Tamper display (B6 and altered register lock): seal_broken, 200, nothing recorded
- [x] 5.4 Chain behaviour: append-only, separate chains, verify, tamper demo leaves chain intact
- [x] 5.5 Escaping, routes/400/404, existing desks unaffected, CSS audit, no JS

## 6. Verification
- [x] 6.1 Full suite green; existing tests untouched
