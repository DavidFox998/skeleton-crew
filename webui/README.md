# The Estate Desk — Executor Web Skin

A server-rendered web interface for the Skeleton Crew executor gate.
Displays verdicts; never decides them.

## Starting the server

```bash
# From the repository root:
python run_webui.py                  # port 8000
python run_webui.py --port 8080      # custom port

# Or via the module entry point (reads PORT env var):
python -m webui.server               # port from $PORT or 8000
PORT=9090 python -m webui.server     # port 9090
```

No external packages required. Python 3.11+ standard library only.

## The three rooms

| Room    | URL        | Purpose |
|---------|------------|---------|
| Register | `GET /`    | Case file: testator identity, sealed death record, 2019 and 2024 wills side by side. The superseded 2019 will is displayed in ghost gray; the one bit that differs between the two will vectors is underlined. |
| Desk    | `GET /desk` | Workbench: seven preset claims as a casework sequence, plus a free builder for composing arbitrary distributions. |
| Archive | `GET /archive` | The house receipt chain, chain-integrity verification, and tamper demonstration. |

## The house chain

One append-only chain is held in server memory for the session (not persisted to disk).
Every adjudication that produces a receipt appends it to the chain — regardless of which
will was involved or whether the verdict was PASS or REFUSED.

The single exception is **Scenario G** (altered page): when the executor's `adjudicate()`
raises `MandateTamperError`, the web layer catches it, renders a `seal_broken` notice,
and appends **nothing** to the chain. The chain is as if the tampered claim never arrived.

## Scenario G — what it demonstrates

Scenario G submits the 2024 will with its original seal intact but its content
silently altered (a beneficiary replaced). The gate core detects that the
SHA-256 of the content no longer matches the stored seal and raises
`MandateTamperError` before any measurement occurs.

The Desk presents this as `REFUSED · seal_broken` with the note:
"Mandate seal verification failed. This event was not recorded in the house chain."

No receipt is written. The archive chain length is unchanged.

## Tamper demonstration (Archive room)

The Archive's "Run tamper demonstration" button operates on a **deep copy** of
the chain. It mutates one receipt in the copy (alters a beneficiary in the claim
payload while leaving the original `own_hash` unchanged), then calls
`verify_chain()` on the mutated copy. The result will show `hash_mismatch`.

The house chain itself is **never mutated** by this demonstration, as confirmed
by the "The house chain was not modified." message in the result page and by the
subsequent "Verify chain integrity" returning "Chain intact".

## Running the tests

```bash
# Full test suite (gate_core + executor + webui):
python -m unittest discover -s tests

# webui tests only:
python -m unittest tests.test_webui
```

All tests use the real `gate_core` and `executor` libraries with the fixture files
in `fixtures/`. No mocking of gate logic.

## Implementation notes

- Python 3.11+ standard library only: `http.server`, `html`, `json`, `hashlib`,
  `datetime`, `copy`, `urllib.parse`, `threading`.
- No JavaScript. All interactivity is plain HTML forms with server-rendered responses.
- All user-supplied strings are escaped with `html.escape()` before insertion into HTML.
- The `webui/` package contains no verdict logic, no measurement logic, and no
  mandate-verification logic. It calls `gate_core.adjudicate()` and renders what returns.

## The Vault (third desk)

| Room | URL | Purpose |
|------|-----|---------|
| The Bundle | `GET /vault` | The sealed estate file: four papers, their seals, the bundle certificate and lock-record seal. |
| Release Desk | `GET /vault/desk` | Presets B1–B6; each presents a bundle for release and shows the gate's stamp and receipt. |
| Vault Archive | `GET /vault/archive` | The vault's own chain, verification, and tamper demonstration on a copy. |

Verdicts come from `gate_core.adjudicate()` with `vault.VaultMeasurer`; the skin only displays them. A lock record that does not recompute (B6) is shown as `REFUSED · seal_broken`, HTTP 200, and nothing is appended to the vault chain. Spec: `.kiro/specs/vault-ui/`; brief: `docs/DESIGN-BRIEF-VAULT-SKIN.md`.
