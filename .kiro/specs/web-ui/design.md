# Technical Design — Executor Web Skin

**Implements:** `.kiro/specs/web-ui/requirements.md`  
**Approved design brief:** `docs/DESIGN-BRIEF-WEB-SKIN.md`

---

## Constraints

- Python 3.11+, standard library only (`http.server`, `html`, `json`, `hashlib`, `datetime`, `copy`, `urllib.parse`, `threading`).
- No external dependencies beyond `gate_core` and `executor`.
- No JavaScript. All interactivity is plain HTML forms and server-rendered responses.
- No client-side templating. All HTML is produced by pure Python functions in `render.py`.
- `webui/` contains no verdict logic, no measurement logic, and no mandate-verification logic.

---

## Package layout

```
skeleton-crew/
    gate_core/          — unchanged
    executor/           — unchanged
    fixtures/           — unchanged
    webui/
        __init__.py     — package marker; no public API
        server.py       — ThreadingHTTPServer + request handler; all route dispatch
        render.py       — pure functions returning HTML strings; one embedded CSS block
        state.py        — HouseRegister: registry, chain, adjudication helpers
    run_webui.py        — entry point: `python run_webui.py [--port 8080]`
```

`webui` imports from `gate_core` and `executor`. Neither `gate_core` nor `executor` imports from `webui`.

---

## `state.py`

### Purpose

Owns all mutable server state and all calls into `gate_core` and `executor`. No HTML, no HTTP logic.

### `HouseRegister`

```python
import copy
import datetime
from gate_core.gate import adjudicate, MandateTamperError
from gate_core.receipt import verify_chain, Receipt
from gate_core.mandate import SealedMandate
from executor.registry import ExecutorRegistry
from executor.measurer import ExecutorMeasurer
from executor.claims import make_distribution_claim
from executor.scenarios import SCENARIO_DEFINITIONS  # see below

class HouseRegister:
    def __init__(
        self,
        will_paths: list[str],
        death_record_paths: list[str],
    ) -> None:
        self._registry = ExecutorRegistry(will_paths, death_record_paths)
        self._registry_no_death = ExecutorRegistry(will_paths, [])  # Scenario F view
        self._measurer = ExecutorMeasurer(self._registry)
        self._measurer_no_death = ExecutorMeasurer(self._registry_no_death)
        self._chain: list[Receipt] = []  # append-only house chain
```

#### `adjudicate_preset(label: str) -> tuple[Verdict | None, Receipt | None, bool]`

Returns `(verdict, receipt, tamper_error)`.

- Resolves the scenario definition for `label` from `SCENARIO_DEFINITIONS`.
- For all scenarios except G: calls `gate_core.adjudicate(claim, mandate, measurer, self._chain, timestamp_utc=...)`.
  - On success: appends the returned receipt to `self._chain`; returns `(verdict, receipt, False)`.
- For Scenario F: uses `self._registry_no_death` and `self._measurer_no_death` to build the claim and measurer. Appends the receipt normally.
- For Scenario G: constructs a tampered `SealedMandate` (original seal, mutated content). Calls `gate_core.adjudicate(...)`. Catches `MandateTamperError`; does NOT append; returns `(None, None, True)`.

Signature:

```python
def adjudicate_preset(
    self,
    label: str,
) -> tuple["Verdict | None", "Receipt | None", bool]:
    ...
```

#### `adjudicate_custom(will_seal: str, distributions: list[dict]) -> tuple[Verdict | None, Receipt | None, bool]`

- Looks up the will via `self._registry.will_by_seal(will_seal)`. Returns an error tuple if not found.
- Constructs a claim via `make_distribution_claim(will_seal, distributions)`.
- Calls `gate_core.adjudicate(claim, mandate, self._measurer, self._chain, timestamp_utc=...)`.
- Catches `MandateTamperError` (should not occur for valid registry wills, but handled defensively): returns `(None, None, True)`.
- On normal return: appends receipt to `self._chain`; returns `(verdict, receipt, False)`.

Signature:

```python
def adjudicate_custom(
    self,
    will_seal: str,
    distributions: list[dict],
) -> tuple["Verdict | None", "Receipt | None", bool]:
    ...
```

#### `chain_snapshot() -> list[Receipt]`

Returns a shallow copy of `self._chain` (a new list, same receipt objects — receipts are frozen dataclasses).

```python
def chain_snapshot(self) -> list[Receipt]:
    return list(self._chain)
```

#### `verify_house_chain() -> ReplayResult`

Calls `gate_core.verify_chain(self._chain)` and returns the result.

```python
def verify_house_chain(self) -> "ReplayResult":
    return verify_chain(self._chain)
```

#### `tamper_demo() -> ReplayResult`

1. Makes a deep copy of `self._chain` via `copy.deepcopy(self._chain)`.
2. If the copy is empty, returns a synthetic `ReplayResult(ok=True, failure_index=None, failure_reason=None)` with a note that no receipts exist to demonstrate against (handled in rendering).
3. Mutates one field in the last receipt of the copy: replaces a value in `receipt.claim["payload"]` with a sentinel string. Because `Receipt` is a frozen dataclass, the mutation is performed by building a new dict from the receipt's fields with the altered value, then constructing a new `Receipt` with `own_hash` unchanged (to simulate a real tamper).
4. Calls `gate_core.verify_chain(mutated_copy)` and returns the result.
5. Does NOT modify `self._chain`.

```python
def tamper_demo(self) -> "ReplayResult":
    ...
```

#### `registry` property

Exposes `self._registry` (read-only) for use by `render.py` when building the Register room and the builder form.

```python
@property
def registry(self) -> ExecutorRegistry:
    return self._registry
```

### `SCENARIO_DEFINITIONS`

A module-level list of dicts in `state.py` (or a separate `scenarios_data.py`) defining the seven scenarios. Each dict carries:

```python
{
    "label": "A",                   # str
    "description": str,             # human-readable summary for the Desk display
    "will_selector": "2024",        # "2024" | "2019" | "tampered_2024"
    "distributions": [...],         # list[dict] with sign/item/beneficiary
    "registry_variant": "full",     # "full" | "no_death_record"
}
```

This mirrors the structure in `executor/scenarios.py` but is owned by `webui/state.py` so the web layer controls its own demo data without coupling to the executor's internal scenario runner.

### Thread safety

`HouseRegister._chain` is mutated only in `adjudicate_preset` and `adjudicate_custom`. The `ThreadingHTTPServer` handles each request in a thread. A `threading.Lock` (stored as `self._lock`) must guard all reads and writes to `self._chain`.

```python
import threading

class HouseRegister:
    def __init__(self, ...):
        ...
        self._lock = threading.Lock()

    def adjudicate_preset(self, label):
        with self._lock:
            ...

    def adjudicate_custom(self, will_seal, distributions):
        with self._lock:
            ...

    def chain_snapshot(self):
        with self._lock:
            return list(self._chain)

    def verify_house_chain(self):
        with self._lock:
            return verify_chain(list(self._chain))

    def tamper_demo(self):
        with self._lock:
            chain_copy = copy.deepcopy(self._chain)
        # mutate copy and verify outside the lock
        ...
```

---

## `render.py`

### Purpose

Pure functions that accept data objects and return HTML strings. No HTTP, no state, no I/O. All functions are deterministic given the same input.

### Escaping rule

Every user-supplied string inserted into HTML is wrapped with `html.escape()`. Fixture data is also escaped (defense in depth). The pattern is:

```python
import html

def _e(s: object) -> str:
    return html.escape(str(s))
```

`_e()` is used at every point of interpolation.

### CSS block

A single CSS block is embedded in the `<style>` element of every page. It is produced by `render.css() -> str` and included via `render.page_shell(title, body_html)`. The CSS block implements the paper-ledger design:

#### Palette variables

```css
:root {
    --paper:    #faf7f0;
    --ink:      #1a1714;
    --ghost:    #9a938a;
    --oxblood:  #7a2e2a;
    --hairline: #d8d2c4;
}
```

#### Typography

```css
body {
    background-color: var(--paper);
    color: var(--ink);
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 1rem;
    line-height: 1.6;
    max-width: 52rem;
    margin: 0 auto;
    padding: 2rem 1.5rem;
}
```

#### Hairline rules

```css
hr, .rule {
    border: none;
    border-top: 1px solid var(--hairline);
    margin: 1.5rem 0;
}
```

#### Navigation

```css
nav {
    border-bottom: 1px solid var(--hairline);
    padding-bottom: 0.75rem;
    margin-bottom: 2rem;
}
nav a {
    color: var(--ink);
    text-decoration: none;
    margin-right: 1.5rem;
    letter-spacing: 0.04em;
}
nav a:hover {
    text-decoration: underline;
}
```

#### Ghost class (unmeasured)

```css
.ghost {
    color: var(--ghost);
    opacity: 0.75;
}
```

#### Verdict states

```css
/* PASS */
.verdict-pass {
    color: var(--ink);
    font-weight: bold;
}
.verdict-pass::before {
    content: "✦ ";
}

/* REFUSED stamp */
.verdict-refused {
    color: var(--oxblood);
    font-weight: bold;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

/* seal_broken notice (synthetic, not a real receipt) */
.seal-broken-notice {
    color: var(--oxblood);
    border: 1px solid var(--oxblood);
    padding: 0.75rem 1rem;
    margin-top: 1rem;
}
```

#### Ghost → solid transition (the only permitted animation)

```css
.claim-block {
    transition: color 0.4s ease, opacity 0.4s ease;
}
.claim-block.ghost {
    color: var(--ghost);
    opacity: 0.75;
}
.claim-block.resolved {
    color: var(--ink);
    opacity: 1;
}
```

No `@keyframes` declarations. No `animation:` properties. No other `transition:` declarations.

#### Monospaced hashes

```css
.hash {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.8rem;
    word-break: break-all;
}
```

#### Will columns (Register room)

```css
.will-columns {
    display: flex;
    gap: 2rem;
    flex-wrap: wrap;
}
.will-column {
    flex: 1 1 18rem;
    border: 1px solid var(--hairline);
    padding: 1rem;
}
.will-column.superseded {
    /* 2019 will inherits .ghost for text; border also dimmed */
    border-color: var(--ghost);
}
.vector-bit {
    font-family: 'Courier New', Courier, monospace;
}
.vector-bit.changed {
    text-decoration: underline;
    text-underline-offset: 3px;
}
```

#### Forms and buttons

```css
button, input[type="submit"] {
    background: var(--paper);
    color: var(--ink);
    border: 1px solid var(--ink);
    padding: 0.35rem 0.9rem;
    font-family: inherit;
    font-size: 0.9rem;
    cursor: pointer;
    letter-spacing: 0.05em;
}
button:hover, input[type="submit"]:hover {
    background: var(--ink);
    color: var(--paper);
}
input[type="text"], select {
    font-family: inherit;
    font-size: 0.9rem;
    border: 1px solid var(--hairline);
    background: var(--paper);
    color: var(--ink);
    padding: 0.25rem 0.5rem;
}
```

### Render functions

All functions return `str`. None mutate state.

#### `page_shell(title: str, body_html: str) -> str`

Returns a complete `<!DOCTYPE html>…</html>` document. Embeds the CSS block from `render.css()`. Includes the navigation bar (links to `/`, `/desk`, `/archive`). Inserts `body_html` into `<main>`.

```python
def page_shell(title: str, body_html: str) -> str: ...
```

#### `render_register(registry: ExecutorRegistry) -> str`

Produces the Register room body. Calls into `registry.all_wills(testator)` and `registry.death_record(testator)` to gather data.

- Renders the testator heading.
- Renders the death record status line.
- Renders the two will columns side by side (`.will-columns`): 2019 with `.ghost .superseded`, 2024 without.
- For each will, renders the vector as individual `.vector-bit` spans; bits that differ between the two will vectors carry an additional `.changed` class.
- For each will, renders the bequest table (occupied signs only: sign, item, beneficiary).

```python
def render_register(registry: "ExecutorRegistry") -> str: ...
```

#### `render_desk(scenario_defs: list[dict], registry: "ExecutorRegistry") -> str`

Produces the Desk room body.

- Iterates `scenario_defs` in order (A → G) and renders each as a preset block: description, claim summary (in `.ghost` styling), and a `<form method="post" action="/adjudicate">` with a hidden `preset` field and a submit button.
- Below the presets, renders the builder form (see §builder-form).

```python
def render_desk(scenario_defs: list[dict], registry: "ExecutorRegistry") -> str: ...
```

#### `render_desk_with_result(scenario_defs, registry, label_or_builder, verdict, receipt, tamper_error) -> str`

Like `render_desk` but injects the verdict result block immediately after the matching preset (or after the builder form, for custom submissions). The preset block that was submitted transitions from `.ghost` to `.resolved`.

For normal verdicts: renders the receipt via `render_receipt(receipt)`.  
For `tamper_error=True`: renders a `<div class="seal-broken-notice">` with the seal_broken text.

```python
def render_desk_with_result(
    scenario_defs: list[dict],
    registry: "ExecutorRegistry",
    label_or_builder: str,
    verdict: "Verdict | None",
    receipt: "Receipt | None",
    tamper_error: bool,
) -> str: ...
```

#### `render_receipt(receipt: Receipt) -> str`

Renders all receipt fields in a `<dl>` (definition list):

- `claim` — domain, claim_type, payload as formatted JSON.
- `measurements` — observations as formatted JSON, or "unmeasured" if None.
- `measurement_error` — if not None.
- `verdict` — rendered via `render_verdict_badge(verdict_dict)`.
- `timestamp_utc`.
- `previous_hash` — in a `<span class="hash">`.
- `own_hash` — in a `<span class="hash">`.

```python
def render_receipt(receipt: "Receipt") -> str: ...
```

#### `render_verdict_badge(verdict_dict: dict) -> str`

Given a receipt's `verdict` dict (`{"type": "pass"}` or `{"type": "refused", "name": "..."}`), returns the appropriate HTML:

- `{"type": "pass"}` → `<span class="verdict-pass">PASS</span>`
- `{"type": "refused", "name": n}` → `<span class="verdict-refused">REFUSED · {_e(n)}</span>`

```python
def render_verdict_badge(verdict_dict: dict) -> str: ...
```

#### `render_archive(chain: list[Receipt], replay_result=None, tamper_result=None, tamper_demo_ran=False) -> str`

Renders the Archive room:

- Header: "House Chain — N receipts."
- Each receipt rendered via `render_receipt()`, separated by `.rule` dividers, in append order.
- "Verify chain integrity" form: `<form method="post" action="/archive/verify">`.
- If `replay_result` is provided: renders the `ReplayResult`.
- "Tamper demonstration" form: `<form method="post" action="/archive/tamper-demo">`.
- If `tamper_demo_ran=True`: renders `tamper_result` (a `ReplayResult`) plus the text "The house chain was not modified."

```python
def render_archive(
    chain: list["Receipt"],
    replay_result: "ReplayResult | None" = None,
    tamper_result: "ReplayResult | None" = None,
    tamper_demo_ran: bool = False,
) -> str: ...
```

#### `render_builder_form(registry: ExecutorRegistry, selected_will_seal: str | None = None, row_count: int = 1) -> str`

Renders the free builder form:

- Will picker: `<select name="will_seal">` with one option per sealed will (value = seal, display = `"{sealed_date} — {seal[:12]}…"`).
- Row count: `<input type="number" name="row_count" min="1" max="12">` plus a "Set rows" submit button posting to `POST /desk/builder-rows` (a helper that reloads the builder with the requested number of rows and the selected will).
- Distribution rows: for `i` in `range(row_count)`, one row containing:
  - `<select name="sign_{i}">` — options are occupied sign names from the selected will's bequests.
  - `<select name="item_{i}">` — options are item values from the selected will's bequests. The `<select>` is rendered with options interleaved: each `sign` option corresponds to the same-indexed `item` option. (Because no JavaScript is allowed, sign and item dropdowns are independent; the implementor may choose to render only the item for the selected sign, driven by a separate form reload, or render all items and let the measurer catch mismatches. Either approach is valid; the spec does not mandate tight coupling.)
  - `<input type="text" name="beneficiary_{i}">` — no default value.
- Hidden `<input type="hidden" name="builder" value="1">`.
- Submit button: "Submit for adjudication" → `POST /adjudicate`.

```python
def render_builder_form(
    registry: "ExecutorRegistry",
    selected_will_seal: str | None = None,
    row_count: int = 1,
) -> str: ...
```

---

## `server.py`

### Purpose

Defines the `ThreadingHTTPServer` and the `EstateHandler(BaseHTTPRequestHandler)`. All route dispatch lives here. No HTML generation, no gate logic.

### Server startup

```python
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

def run(host: str = "127.0.0.1", port: int = 8080, register: "HouseRegister" = None) -> None:
    """Start the server. Blocks until KeyboardInterrupt."""
    ...
```

A single `HouseRegister` instance is created before the server starts and is passed into the handler class via a class-level attribute (standard `http.server` pattern):

```python
class EstateHandler(BaseHTTPRequestHandler):
    register: "HouseRegister"  # set on the class before server.serve_forever()
    ...
```

### Routes

| Method | Path | Handler method | Description |
|--------|------|----------------|-------------|
| `GET` | `/` | `_get_register` | Register room |
| `GET` | `/desk` | `_get_desk` | Desk room |
| `GET` | `/archive` | `_get_archive` | Archive room |
| `POST` | `/adjudicate` | `_post_adjudicate` | Preset or builder submission |
| `POST` | `/desk/builder-rows` | `_post_builder_rows` | Reload builder with new row count |
| `POST` | `/archive/verify` | `_post_archive_verify` | Run verify_chain on house chain |
| `POST` | `/archive/tamper-demo` | `_post_tamper_demo` | Run tamper demonstration |

Unknown paths return HTTP 404 with a minimal HTML error page.

### `do_GET` dispatch

```python
def do_GET(self):
    path = self.path.split("?")[0]
    match path:
        case "/":      self._get_register()
        case "/desk":  self._get_desk()
        case "/archive": self._get_archive()
        case _:        self._send_404()
```

### `do_POST` dispatch

```python
def do_POST(self):
    path = self.path.split("?")[0]
    match path:
        case "/adjudicate":          self._post_adjudicate()
        case "/desk/builder-rows":   self._post_builder_rows()
        case "/archive/verify":      self._post_archive_verify()
        case "/archive/tamper-demo": self._post_tamper_demo()
        case _:                      self._send_404()
```

### Body parsing

POST bodies are `application/x-www-form-urlencoded`. The handler reads `Content-Length` bytes from `self.rfile`, then decodes with `urllib.parse.parse_qs(body, keep_blank_values=True)`.

```python
def _read_form(self) -> dict[str, list[str]]:
    length = int(self.headers.get("Content-Length", 0))
    raw = self.rfile.read(length).decode("utf-8", errors="replace")
    return urllib.parse.parse_qs(raw, keep_blank_values=True)
```

### `_send_html(html: str, status: int = 200)`

```python
def _send_html(self, html: str, status: int = 200) -> None:
    encoded = html.encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(encoded)))
    self.end_headers()
    self.wfile.write(encoded)
```

### Route implementations (sketches)

#### `_get_register()`

```python
def _get_register(self):
    body = render.render_register(self.register.registry)
    self._send_html(render.page_shell("The Estate Desk — Register", body))
```

#### `_get_desk()`

```python
def _get_desk(self):
    body = render.render_desk(SCENARIO_DEFINITIONS, self.register.registry)
    self._send_html(render.page_shell("The Estate Desk — Desk", body))
```

#### `_get_archive()`

```python
def _get_archive(self):
    chain = self.register.chain_snapshot()
    body = render.render_archive(chain)
    self._send_html(render.page_shell("The Estate Desk — Archive", body))
```

#### `_post_adjudicate()`

Reads form fields. If `form["builder"] == ["1"]`:
- Extracts `will_seal`, `row_count`, and per-row `sign_N`/`item_N`/`beneficiary_N`.
- Calls `self.register.adjudicate_custom(will_seal, distributions)`.
- Renders the Desk with the builder result.

Otherwise:
- Extracts `preset` label.
- Calls `self.register.adjudicate_preset(label)`.
- Renders the Desk with the preset result.

#### `_post_builder_rows()`

Extracts `will_seal` and `row_count` from form. Renders the Desk with the builder form reloaded for the given will and row count. Does not adjudicate.

#### `_post_archive_verify()`

```python
def _post_archive_verify(self):
    replay = self.register.verify_house_chain()
    chain = self.register.chain_snapshot()
    body = render.render_archive(chain, replay_result=replay)
    self._send_html(render.page_shell("The Estate Desk — Archive", body))
```

#### `_post_tamper_demo()`

```python
def _post_tamper_demo(self):
    tamper = self.register.tamper_demo()
    chain = self.register.chain_snapshot()
    body = render.render_archive(chain, tamper_result=tamper, tamper_demo_ran=True)
    self._send_html(render.page_shell("The Estate Desk — Archive", body))
```

### Logging

`BaseHTTPRequestHandler.log_message` is not suppressed. Default access logging to stderr is acceptable.

---

## `run_webui.py`

Entry point at the repository root. Resolves fixture paths relative to its own location, constructs a `HouseRegister`, sets it on `EstateHandler`, and calls `server.run()`.

```python
#!/usr/bin/env python3
"""Start the Executor web skin. Usage: python run_webui.py [--port N]"""
import argparse
import pathlib
from webui.state import HouseRegister, SCENARIO_DEFINITIONS
from webui.server import EstateHandler, run

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    register = HouseRegister(
        will_paths=[
            str(FIXTURES / "will_2019.json"),
            str(FIXTURES / "will_2024.json"),
        ],
        death_record_paths=[
            str(FIXTURES / "death_record.json"),
        ],
    )
    EstateHandler.register = register
    run(port=args.port, register=register)

if __name__ == "__main__":
    main()
```

---

## Data flow summary

```
Browser                 server.py               state.py              gate_core / executor
   |                       |                       |                          |
   |  GET /desk            |                       |                          |
   |---------------------->|                       |                          |
   |                       | render_desk(...)      |                          |
   |<----------------------|                       |                          |
   |                       |                       |                          |
   |  POST /adjudicate     |                       |                          |
   |  preset=A             |                       |                          |
   |---------------------->|                       |                          |
   |                       | adjudicate_preset("A")|                          |
   |                       |---------------------->|                          |
   |                       |                       | make_distribution_claim  |
   |                       |                       |------------------------->|
   |                       |                       | adjudicate(claim, ...)   |
   |                       |                       |------------------------->|
   |                       |                       | (Verdict, Receipt)       |
   |                       |                       |<-------------------------|
   |                       |                       | _chain.append(receipt)   |
   |                       | (verdict, receipt, F) |                          |
   |                       |<----------------------|                          |
   |                       | render_desk_with_result(...)                     |
   |  200 HTML             |                       |                          |
   |<----------------------|                       |                          |
```

---

## Error handling in the web layer

| Situation | Web layer response |
|-----------|-------------------|
| Unknown preset label | HTTP 400 with "Unknown scenario label: {label}" |
| Unknown will seal in builder | HTTP 400 with "No will found for seal prefix {seal[:12]}…" |
| `MandateTamperError` | Caught; renders seal_broken notice; chain unchanged |
| Missing form field | HTTP 400 with field name |
| Any other unhandled exception in a route | HTTP 500 with minimal error page; exception logged to stderr |

HTTP 500 pages do not include raw exception tracebacks in the response body (security boundary). The full traceback is written to stderr.

---

## Design decisions

**Why does `state.py` own `SCENARIO_DEFINITIONS` rather than importing from `executor.scenarios`?**  
`executor.scenarios` defines a `run_scenarios()` runner that manages its own chain-per-scenario semantics (each scenario gets a fresh chain). The web skin needs the opposite: all adjudications append to a single house chain. The scenario definitions (will selectors, distributions, descriptions) are duplicated in `state.py` so the web layer can control timing, registry variant, and chain assignment independently.

**Why is the builder sign/item relationship not strictly coupled in the form?**  
No JavaScript means no dynamic form updates. Two patterns are acceptable: (a) a two-step form reload where selecting a will reloads the builder, and selecting a sign reloads the item; (b) rendering both dropdowns from all bequests and letting the measurer catch mismatches. The spec permits either. Implementation should choose whichever produces a more usable interface within the no-JS constraint.

**Why a class-level `register` attribute on `EstateHandler`?**  
`BaseHTTPRequestHandler` is instantiated per-request by `HTTPServer`. The standard pattern for sharing state across requests is to set it on the handler class before `serve_forever()`. A closure or a `functools.partial`-based handler factory are equally valid alternatives.

**Why `threading.Lock` rather than a single-threaded server?**  
`ThreadingHTTPServer` is specified to enable concurrent request handling (especially useful during development with browsers that open parallel connections for resources). The lock is a correctness requirement, not a performance optimisation.

**Why is the house chain not persisted to disk?**  
This version is a demonstration skin. The brief specifies no persistence requirement. Persistence (via `gate_core.receipt.save_chain`) is a natural future extension and the hook is already in gate_core.
