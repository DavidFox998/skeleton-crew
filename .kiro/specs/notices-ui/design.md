# Technical Design — Notices Desk Web Skin

**Implements:** `.kiro/specs/notices-ui/requirements.md`  
**Approved design brief:** `docs/DESIGN-BRIEF-NOTICES-SKIN.md`

---

## Constraints

- Python 3.11+, standard library only (`http.server`, `html`, `json`, `hashlib`, `datetime`, `copy`, `urllib.parse`, `threading`).
- Extends `webui/` — no new top-level packages, no new entry-point files beyond a `run_notices.py` or extending `run_webui.py`.
- No external dependencies beyond `gate_core`, `executor`, and `citation_gate`.
- No JavaScript. All interactivity is plain HTML forms and server-rendered responses.
- No client-side templating. All HTML is produced by pure Python functions in `render.py`.
- `webui/` contains no verdict logic, no measurement logic, and no mandate-verification logic.
- `citation_gate/` and `executor/` are not modified by this feature (except the canon fix to `fixtures/family_record.json` and the two matching changes in `citation_gate/scenarios.py` and `tests/test_citation_gate.py` — those are data fixes, not logic changes).

---

## Package layout

No new top-level packages are introduced. All new code is added to the existing `webui/` package:

```
skeleton-crew/
    gate_core/                    — unchanged
    executor/                     — unchanged
    citation_gate/
        scenarios.py              — canon fix: N1 and N5 assertion text/value only
        (all other files unchanged)
    fixtures/
        family_record.json        — canon fix: occupation → "self-professed Tree Wizard"
    webui/
        __init__.py               — unchanged
        state.py                  — HouseRegister unchanged; NoticesRegister added
        render.py                 — existing functions unchanged; notices render functions added;
                                    page_shell gains the two extra nav links
        server.py                 — EstateHandler unchanged; NoticesHandler added;
                                    run() updated to construct and attach both registers
    run_webui.py                  — updated to also construct NoticesRegister and set
                                    NoticesHandler.notices_register
    tests/
        test_webui.py             — unchanged
        test_notices_ui.py        — new
```

`webui` imports from `gate_core` and `citation_gate`. The dependency direction is unchanged: neither `gate_core` nor `citation_gate` imports from `webui`.

---

## Canon fix — `fixtures/family_record.json` and `citation_gate/scenarios.py`

Before any web code changes, the following data fixes are applied:

1. **`fixtures/family_record.json`**: Change `"occupation"` from `"keeper of the Hollow Hill light (retired)"` to `"self-professed Tree Wizard"`.

2. **`citation_gate/scenarios.py`** — `_SCENARIO_N1`, assertion at index 2:
   - `text`: `"He was a self-professed Tree Wizard."`
   - `value`: `"self-professed Tree Wizard"`

3. **`citation_gate/scenarios.py`** — `_SCENARIO_N5A`, assertion at index 2:
   - `text`: `"He was a self-professed Tree Wizard."`
   - `value`: `"self-professed Tree Wizard"`

4. **`tests/test_citation_gate.py`**: Update any assertion-text or assertion-value strings that reference the old occupation wording to use `"self-professed Tree Wizard"`. The full test suite must remain green after the fix.

These four files are the only files touched by the canon fix. The `SourceRegistry`, `CitationMeasurer`, and `publish.check_publish` implementations are unchanged.

---

## `state.py` — NoticesRegister

### Purpose

Owns all mutable state for the Notices Desk. Mirrors the structure of `HouseRegister` but governs the citation gate domain. No HTML, no HTTP logic.

### `NoticesRegister`

```python
import copy
import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from gate_core.gate import adjudicate, MandateTamperError
from gate_core.mandate import seal_mandate, SealedMandate
from gate_core.receipt import Receipt, ReplayResult, verify_chain
from gate_core.verdict import Verdict

from citation_gate.claims import make_assertion_claim
from citation_gate.measurer import CitationMeasurer
from citation_gate.publish import PublishDecision, check_publish
from citation_gate.sources import SourceRegistry


@dataclass
class AssertionEntry:
    """One assertion in the working draft, after adjudication."""
    text: str
    fact_key: str
    value: str
    citation: str | None
    claim_hash: str           # canonical-JSON SHA-256 of the Claim dict
    verdict: dict | None      # receipt.verdict or None on tamper
    receipt: Receipt | None   # None on tamper


class NoticesRegister:
    def __init__(
        self,
        death_record_path: str,
        will_path: str,
        family_record_path: str,
    ) -> None:
        self._source_registry = SourceRegistry(
            death_record_path=death_record_path,
            will_path=will_path,
            family_record_path=family_record_path,
        )
        self._measurer = CitationMeasurer(self._source_registry)
        self._desk_mandate: SealedMandate = seal_mandate(
            "citation",
            {"desk": "notices", "mandate": "Adjudicate factual assertions for obituary publication."},
        )
        self._chain: list[Receipt] = []
        self._working_draft: list[AssertionEntry] = []
        self._lock = threading.Lock()
```

#### Properties

```python
@property
def source_registry(self) -> SourceRegistry:
    """Expose the SourceRegistry (read-only) for render helpers."""
    return self._source_registry

@property
def working_draft(self) -> list[AssertionEntry]:
    """Return a shallow copy of the current working draft under lock."""
    with self._lock:
        return list(self._working_draft)
```

#### `adjudicate_preset(label: str) -> tuple[list[AssertionEntry], list[PublishDecision], bool]`

Adjudicates a full preset draft by label (`N1`–`N6`). For N5, runs both phases.

Returns `(assertion_entries, publish_decisions, tamper_error)` where:
- `assertion_entries`: all `AssertionEntry` objects produced across all phases.
- `publish_decisions`: a `PublishDecision` per phase (one for N1–N4, N6; two for N5).
- `tamper_error`: `True` if `MandateTamperError` was raised during any assertion.

Implementation sketch:

```python
def adjudicate_preset(
    self,
    label: str,
) -> tuple[list["AssertionEntry"], list["PublishDecision"], bool]:
    from webui.state import NOTICES_SCENARIO_DEFINITIONS  # see below
    spec = next((d for d in NOTICES_SCENARIO_DEFINITIONS if d["label"] == label), None)
    if spec is None:
        raise KeyError(f"Unknown notices scenario label: {label!r}")

    with self._lock:
        entries: list[AssertionEntry] = []
        decisions: list[PublishDecision] = []

        for phase in spec["phases"]:
            phase_hashes: list[str] = []
            for a in phase["assertions"]:
                claim = make_assertion_claim(
                    text=a["text"],
                    fact_key=a["fact_key"],
                    value=a["value"],
                    citation=a["citation"],
                )
                ch = _claim_hash(claim)
                phase_hashes.append(ch)
                try:
                    verdict, receipt = adjudicate(
                        claim,
                        self._desk_mandate,
                        self._measurer,
                        self._chain,
                        timestamp_utc=_utc_now(),
                    )
                    entries.append(AssertionEntry(
                        text=a["text"],
                        fact_key=a["fact_key"],
                        value=a["value"],
                        citation=a["citation"],
                        claim_hash=ch,
                        verdict=receipt.verdict,
                        receipt=receipt,
                    ))
                except MandateTamperError:
                    entries.append(AssertionEntry(
                        text=a["text"],
                        fact_key=a["fact_key"],
                        value=a["value"],
                        citation=a["citation"],
                        claim_hash=ch,
                        verdict=None,
                        receipt=None,
                    ))
                    return entries, decisions, True

            decision = check_publish(phase["label"], phase_hashes, self._chain)
            decisions.append(decision)

        return entries, decisions, False
```

Note: preset adjudications append to the notices chain but do **not** modify the working draft. The working draft is for the free builder only.

#### `adjudicate_assertion(text, fact_key, value, citation) -> tuple[AssertionEntry, PublishDecision, bool]`

Adjudicates a single free-builder assertion.

- Builds a `Claim` via `make_assertion_claim(text, fact_key, value, citation)`.
- Calls `gate_core.adjudicate(claim, self._desk_mandate, self._measurer, self._chain, ...)`.
- On success: appends receipt to `self._chain`; appends an `AssertionEntry` to `self._working_draft`.
- On `MandateTamperError`: returns `(entry_with_none_receipt, dummy_refused_decision, True)` — nothing appended.
- After a successful adjudication, calls `check_publish` on the current working draft's claim hashes to produce the `PublishDecision`.
- Returns `(assertion_entry, publish_decision, tamper_error)`.

```python
def adjudicate_assertion(
    self,
    text: str,
    fact_key: str,
    value: str,
    citation: str | None,
) -> tuple["AssertionEntry", "PublishDecision", bool]:
    with self._lock:
        claim = make_assertion_claim(
            text=text,
            fact_key=fact_key,
            value=value,
            citation=citation,
        )
        ch = _claim_hash(claim)
        try:
            verdict, receipt = adjudicate(
                claim,
                self._desk_mandate,
                self._measurer,
                self._chain,
                timestamp_utc=_utc_now(),
            )
            entry = AssertionEntry(
                text=text, fact_key=fact_key, value=value, citation=citation,
                claim_hash=ch, verdict=receipt.verdict, receipt=receipt,
            )
            self._working_draft.append(entry)
            draft_hashes = [e.claim_hash for e in self._working_draft]
            decision = check_publish("working_draft", draft_hashes, self._chain)
            return entry, decision, False
        except MandateTamperError:
            entry = AssertionEntry(
                text=text, fact_key=fact_key, value=value, citation=citation,
                claim_hash=ch, verdict=None, receipt=None,
            )
            # Do NOT append to working_draft or chain
            refused = PublishDecision(publishable=False, receipt_ids=None, refusal_name="seal_broken")
            return entry, refused, True
```

#### `new_draft() -> None`

Clears `self._working_draft`. Does not touch `self._chain`.

```python
def new_draft(self) -> None:
    with self._lock:
        self._working_draft = []
```

#### `chain_snapshot() -> list[Receipt]`

Returns a shallow copy of `self._chain` under lock.

#### `verify_notices_chain() -> ReplayResult`

Calls `gate_core.verify_chain(snapshot)` on a locked snapshot.

#### `tamper_demo() -> ReplayResult`

1. Makes a `copy.deepcopy(self._chain)` under lock.
2. If the copy is empty, returns `ReplayResult(ok=True, failure_index=None, failure_reason=None)`.
3. Mutates the last receipt's `claim` dict — navigates to `payload` and alters an assertion value — then constructs a new `Receipt` with the mutated claim and the original `own_hash` (so the content no longer matches the hash).
4. Calls `gate_core.verify_chain(mutated_copy)` and returns the `ReplayResult`.
5. Does NOT modify `self._chain`.

### `NOTICES_SCENARIO_DEFINITIONS`

A module-level list of dicts in `webui/state.py` defining the six notices preset scenarios. Each dict has the following shape:

```python
{
    "label": "N1",               # str — the label shown on the button
    "description": str,          # human-readable summary
    "phases": [                  # list of one or two phase dicts
        {
            "label": "N1",       # phase label used for check_publish draft_id
            "assertions": [      # list of assertion dicts
                {
                    "text":     str,
                    "fact_key": str,
                    "value":    str,
                    "citation": str | None,
                },
                ...
            ],
        },
    ],
    "expected_publish": str,     # human-readable expected outcome for display
}
```

N5 is the only scenario with two phases:

```python
{
    "label": "N5",
    "description": "Two-phase draft: wrong birthplace corrected",
    "phases": [
        {
            "label": "N5a",
            "assertions": [
                # ... three assertions including wrong birthplace "Galway"
            ],
        },
        {
            "label": "N5b",
            "assertions": [
                # ... corrected birthplace "Hollow Hill" only
            ],
        },
    ],
    "expected_publish": "N5a: REFUSED · source_contradicts; N5b: PUBLISHABLE",
}
```

The assertion data in `NOTICES_SCENARIO_DEFINITIONS` mirrors `citation_gate/scenarios.py` but is owned by `webui/state.py` so the web layer controls its own demo data without coupling to the citation gate's internal runner. After the canon fix, N1 and N5a/N5b occupation assertions use `"self-professed Tree Wizard"`.

### Thread safety

`NoticesRegister._chain` and `_working_draft` are mutated only in `adjudicate_preset`, `adjudicate_assertion`, and `new_draft`. A `threading.Lock` (stored as `self._lock`) guards all reads and writes. The same pattern as `HouseRegister`.

### Module-level helpers

```python
def _canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))

def _claim_hash(claim) -> str:
    return hashlib.sha256(_canonical_json(claim.to_dict()).encode("utf-8")).hexdigest()

def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

These may be shared with `HouseRegister` helpers already in `state.py` or defined as private module-level functions alongside `NoticesRegister`.

---

## `render.py` — navigation update

### `page_shell` update

`page_shell(title, body_html)` is updated to include the two additional nav links. The nav now renders as two groups:

```html
<nav>
  <span class="nav-group">
    <a href="/">Register</a>
    <a href="/desk">Desk</a>
    <a href="/archive">Archive</a>
  </span>
  <span class="nav-separator">·</span>
  <span class="nav-group">
    <a href="/notices/sources">Sources</a>
    <a href="/notices">Notices</a>
    <a href="/notices/archive">Notice Archive</a>
  </span>
</nav>
```

Two small CSS rules are added to support the separator styling (no change to existing classes):

```css
.nav-separator {
    color: var(--ghost);
    margin-right: 1.5rem;
}
.nav-group {
    display: inline;
}
```

The title in `page_shell` is passed by each handler; the desk subtitle is injected by the handler calling a notices-specific page shell or by a shared helper that takes a subtitle argument.

**Alternative:** A `notices_page_shell(title, body_html)` thin wrapper that calls the updated `page_shell` with the Notices desk title and subtitle baked in. Either approach is acceptable; the implementation should choose whichever produces the least duplication.

---

## `render.py` — notices render functions

All new functions are added to `webui/render.py` alongside the existing estate functions. All existing functions remain unchanged.

### `render_sources(source_registry: SourceRegistry) -> str`

Produces the Sources room body.

- Iterates over the three source IDs in a fixed order: `death_record`, `will_2024`, `family_record`.
- For each source:
  - Renders the source ID as an `<h3>` heading.
  - Renders the source seal prefix: `<span class="hash">{seal[:12]}…</span>`.
  - Renders the fact table as a `<dl>` or two-column `<table>`: one row per key/value pair in the source's fact table.
  - Applies `_e()` to all fact keys and values.
- No forms, no submit buttons.

```python
def render_sources(source_registry: "SourceRegistry") -> str: ...
```

### `render_notices_desk(scenario_defs: list[dict], source_registry: "SourceRegistry", working_draft: list["AssertionEntry"], publish_state: "PublishDecision | None") -> str`

Produces the Notices Desk workbench body.

- Iterates `scenario_defs` in order (N1 → N6) and renders each as a preset block: description, assertion list (in `.ghost` styling), and a `<form method="post" action="/notices/preset">` with a hidden `preset` field and a submit button.
- Below the presets, renders the working draft summary:
  - Lists each `AssertionEntry` with its text and verdict badge (or ghost if no verdict).
  - Shows the current `publish_state` if not None.
- Below the working draft, renders the free assertion builder form via `render_assertion_builder(source_registry)`.
- Renders the "Begin a new draft" form: `<form method="post" action="/notices/new-draft">` with a single submit button.

```python
def render_notices_desk(
    scenario_defs: list[dict],
    source_registry: "SourceRegistry",
    working_draft: list["AssertionEntry"],
    publish_state: "PublishDecision | None",
) -> str: ...
```

### `render_notices_desk_with_preset_result(scenario_defs, source_registry, working_draft, publish_state, label, entries, decisions, tamper_error) -> str`

Like `render_notices_desk` but injects the full preset result block immediately after the matching preset form. The matched preset's assertion list transitions from `.ghost` to `.resolved`. Each `AssertionEntry` in `entries` is rendered with its verdict badge. Each `PublishDecision` in `decisions` is rendered as a publish stamp.

```python
def render_notices_desk_with_preset_result(
    scenario_defs: list[dict],
    source_registry: "SourceRegistry",
    working_draft: list["AssertionEntry"],
    publish_state: "PublishDecision | None",
    label: str,
    entries: list["AssertionEntry"],
    decisions: list["PublishDecision"],
    tamper_error: bool,
) -> str: ...
```

### `render_notices_desk_with_assertion_result(scenario_defs, source_registry, working_draft, publish_state, entry, tamper_error) -> str`

Like `render_notices_desk` but renders the latest assertion result beneath the builder form and updates the working draft display.

```python
def render_notices_desk_with_assertion_result(
    scenario_defs: list[dict],
    source_registry: "SourceRegistry",
    working_draft: list["AssertionEntry"],
    publish_state: "PublishDecision | None",
    entry: "AssertionEntry",
    tamper_error: bool,
) -> str: ...
```

### `render_assertion_builder(source_registry: SourceRegistry) -> str`

Renders the free-assertion builder form.

Fields:
- `<input type="text" name="sentence">` — sentence text, no pre-filled value.
- `<select name="fact_key">` — one `<optgroup>` per source (label = source ID), options are that source's fact keys.
- `<input type="text" name="value">` — claimed value, no pre-filled value.
- `<select name="citation">` — options: `death_record` (display "Death record"), `will_2024` (display "Will of 2024"), `family_record` (display "Family record"), `""` (display "No citation").
- Submit: `<input type="submit" value="Measure this assertion">` posting to `POST /notices/assertion`.

```python
def render_assertion_builder(source_registry: "SourceRegistry") -> str: ...
```

### `render_publish_decision(decision: PublishDecision) -> str`

Renders a `PublishDecision` as a publish stamp.

- If `publishable=True`: `<p class="verdict-pass">PUBLISHABLE</p>` followed by a list of receipt IDs (each `own_hash`).
- If `publishable=False`: `<p class="verdict-refused">REFUSED · {_e(decision.refusal_name)}</p>`.

```python
def render_publish_decision(decision: "PublishDecision") -> str: ...
```

### `render_notices_archive(chain, replay_result=None, tamper_result=None, tamper_demo_ran=False) -> str`

Mirrors `render_archive` but uses "notices chain" in all copy strings and posts to `/notices/archive/verify` and `/notices/archive/tamper`.

```python
def render_notices_archive(
    chain: "list[Receipt]",
    replay_result: "ReplayResult | None" = None,
    tamper_result: "ReplayResult | None" = None,
    tamper_demo_ran: bool = False,
) -> str: ...
```

---

## `server.py` — NoticesHandler

### Class definition

```python
class NoticesHandler(BaseHTTPRequestHandler):
    """HTTP request handler for The Notices Desk.

    The class-level ``notices_register`` attribute must be set on the class
    before ``serve_forever()`` is called.
    """

    notices_register: "NoticesRegister"  # set on class before serve_forever()
```

### Routes

| Method | Path | Handler method | Description |
|--------|------|----------------|-------------|
| `GET` | `/notices/sources` | `_get_sources` | Sources room |
| `GET` | `/notices` | `_get_notices` | Notices Desk workbench |
| `GET` | `/notices/archive` | `_get_notices_archive` | Notice Archive |
| `POST` | `/notices/preset` | `_post_preset` | Run a preset draft |
| `POST` | `/notices/assertion` | `_post_assertion` | Measure a free-builder assertion |
| `POST` | `/notices/new-draft` | `_post_new_draft` | Begin a new working draft |
| `POST` | `/notices/archive/verify` | `_post_notices_verify` | Verify notices chain integrity |
| `POST` | `/notices/archive/tamper` | `_post_notices_tamper` | Run notices tamper demonstration |

### Integration with `EstateHandler`

`EstateHandler` and `NoticesHandler` are separate request handler classes. The existing `ThreadingHTTPServer` is extended by a single dispatcher handler class `HouseHandler` that inherits from `BaseHTTPRequestHandler` and delegates to the appropriate sub-handler based on path prefix. Alternatively, both classes' routing logic can be merged into a single `HouseHandler` that dispatches on path.

**Preferred approach:** A single `HouseHandler(BaseHTTPRequestHandler)` that holds both `register` (estate) and `notices_register` (notices) as class-level attributes and routes all paths:

```python
class HouseHandler(BaseHTTPRequestHandler):
    register: "HouseRegister"
    notices_register: "NoticesRegister"

    def do_GET(self):
        path = self.path.split("?")[0]
        match path:
            case "/" | "/desk" | "/archive":
                # delegate to estate GET handlers
                ...
            case "/notices/sources" | "/notices" | "/notices/archive":
                # delegate to notices GET handlers
                ...
            case _:
                self._send_404()

    def do_POST(self):
        path = self.path.split("?")[0]
        match path:
            case "/adjudicate" | "/desk/builder-rows" | "/archive/verify" | "/archive/tamper-demo":
                # delegate to estate POST handlers
                ...
            case "/notices/preset" | "/notices/assertion" | "/notices/new-draft" \
               | "/notices/archive/verify" | "/notices/archive/tamper":
                # delegate to notices POST handlers
                ...
            case _:
                self._send_404()
```

`HouseHandler` replaces `EstateHandler` as the handler class passed to `ThreadingHTTPServer`. `EstateHandler` becomes a mixin or base class, or its methods are merged into `HouseHandler`. The implementation must choose the cleanest approach; the spec requires that the existing estate routes continue to work unchanged.

### GET handler implementations

#### `_get_sources()`

```python
def _get_sources(self):
    body = render.render_sources(self.notices_register.source_registry)
    title = "The Notices Desk — Sources"
    self._send_html(render.notices_page_shell(title, body))
```

#### `_get_notices()`

```python
def _get_notices(self):
    draft = self.notices_register.working_draft
    # Compute current publish state from working draft
    publish_state = None  # no state until first assertion
    if draft:
        from webui.state import NOTICES_SCENARIO_DEFINITIONS
        # ... (publish state derived from draft entries' claim_hashes and the chain)
    body = render.render_notices_desk(
        NOTICES_SCENARIO_DEFINITIONS,
        self.notices_register.source_registry,
        draft,
        publish_state,
    )
    self._send_html(render.notices_page_shell("The Notices Desk", body))
```

The working draft's current publish state is recomputed on each `GET /notices` by inspecting the working draft entries stored in `NoticesRegister`. Because `NoticesRegister` stores claim hashes in each `AssertionEntry`, `check_publish` can be called from the handler using the snapshot chain without re-adjudicating.

**Preferred alternative:** `NoticesRegister` exposes a `working_draft_publish_state() -> PublishDecision | None` method that encapsulates this computation under lock.

#### `_get_notices_archive()`

```python
def _get_notices_archive(self):
    chain = self.notices_register.chain_snapshot()
    body = render.render_notices_archive(chain)
    self._send_html(render.notices_page_shell("The Notice Archive", body))
```

### POST handler implementations

#### `_post_preset()`

```python
def _post_preset(self):
    form = self._read_form()
    label_list = form.get("preset", [])
    if not label_list:
        self._send_400("Missing field: preset")
        return
    label = label_list[0]

    try:
        entries, decisions, tamper_error = self.notices_register.adjudicate_preset(label)
    except KeyError as exc:
        self._send_400(str(exc))
        return

    from webui.state import NOTICES_SCENARIO_DEFINITIONS
    draft = self.notices_register.working_draft
    publish_state = self.notices_register.working_draft_publish_state()
    body = render.render_notices_desk_with_preset_result(
        NOTICES_SCENARIO_DEFINITIONS,
        self.notices_register.source_registry,
        draft,
        publish_state,
        label,
        entries,
        decisions,
        tamper_error,
    )
    self._send_html(render.notices_page_shell("The Notices Desk", body))
```

#### `_post_assertion()`

```python
def _post_assertion(self):
    form = self._read_form()
    sentence = (form.get("sentence") or [""])[0]
    fact_key = (form.get("fact_key") or [""])[0]
    value = (form.get("value") or [""])[0]
    citation_raw = (form.get("citation") or [""])[0]
    citation = citation_raw if citation_raw else None

    if not sentence:
        self._send_400("Missing field: sentence")
        return
    if not fact_key:
        self._send_400("Missing field: fact_key")
        return

    entry, publish_decision, tamper_error = self.notices_register.adjudicate_assertion(
        text=sentence,
        fact_key=fact_key,
        value=value,
        citation=citation,
    )

    from webui.state import NOTICES_SCENARIO_DEFINITIONS
    draft = self.notices_register.working_draft
    body = render.render_notices_desk_with_assertion_result(
        NOTICES_SCENARIO_DEFINITIONS,
        self.notices_register.source_registry,
        draft,
        publish_decision,
        entry,
        tamper_error,
    )
    self._send_html(render.notices_page_shell("The Notices Desk", body))
```

#### `_post_new_draft()`

```python
def _post_new_draft(self):
    self.notices_register.new_draft()
    from webui.state import NOTICES_SCENARIO_DEFINITIONS
    body = render.render_notices_desk(
        NOTICES_SCENARIO_DEFINITIONS,
        self.notices_register.source_registry,
        [],
        None,
    )
    self._send_html(render.notices_page_shell("The Notices Desk", body))
```

#### `_post_notices_verify()`

```python
def _post_notices_verify(self):
    replay = self.notices_register.verify_notices_chain()
    chain = self.notices_register.chain_snapshot()
    body = render.render_notices_archive(chain, replay_result=replay)
    self._send_html(render.notices_page_shell("The Notice Archive", body))
```

#### `_post_notices_tamper()`

```python
def _post_notices_tamper(self):
    tamper = self.notices_register.tamper_demo()
    chain = self.notices_register.chain_snapshot()
    body = render.render_notices_archive(chain, tamper_result=tamper, tamper_demo_ran=True)
    self._send_html(render.notices_page_shell("The Notice Archive", body))
```

### Error handling

Identical to `EstateHandler`:

| Situation | Response |
|-----------|----------|
| Unknown preset label | HTTP 400 with "Unknown notices scenario label: {label}" |
| Missing `sentence` field | HTTP 400 with "Missing field: sentence" |
| Missing `fact_key` field | HTTP 400 with "Missing field: fact_key" |
| `MandateTamperError` | Caught; renders seal_broken notice; chain unchanged |
| Any unhandled exception | HTTP 500; traceback to stderr only |

---

## `run_webui.py` update

The entry point is updated to construct a `NoticesRegister` from the three citation fixture paths and attach it to the handler class:

```python
from webui.state import HouseRegister, NoticesRegister, SCENARIO_DEFINITIONS
from webui.server import HouseHandler, run

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    register = HouseRegister(
        will_paths=[str(FIXTURES / "will_2019.json"), str(FIXTURES / "will_2024.json")],
        death_record_paths=[str(FIXTURES / "death_record.json")],
    )
    notices_register = NoticesRegister(
        death_record_path=str(FIXTURES / "death_record.json"),
        will_path=str(FIXTURES / "will_2024.json"),
        family_record_path=str(FIXTURES / "family_record.json"),
    )
    HouseHandler.register = register
    HouseHandler.notices_register = notices_register
    run(port=args.port, register=register, notices_register=notices_register)
```

---

## Data flow summary

```
Browser                  server.py                state.py              citation_gate / gate_core
   |                        |                        |                          |
   |  GET /notices          |                        |                          |
   |----------------------->|                        |                          |
   |                        | render_notices_desk()  |                          |
   |<-----------------------|                        |                          |
   |                        |                        |                          |
   |  POST /notices/preset  |                        |                          |
   |  preset=N1             |                        |                          |
   |----------------------->|                        |                          |
   |                        | adjudicate_preset("N1")|                          |
   |                        |----------------------->|                          |
   |                        |                        | make_assertion_claim()   |
   |                        |                        |------------------------->|
   |                        |                        | adjudicate(claim, ...)   |
   |                        |                        |------------------------->|
   |                        |                        | (Verdict, Receipt)       |
   |                        |                        |<-------------------------|
   |                        |                        | check_publish(...)       |
   |                        |                        |------------------------->|
   |                        |                        | PublishDecision          |
   |                        |                        |<-------------------------|
   |                        |                        | _chain.append(receipt)   |
   |                        | (entries, decisions, F)|                          |
   |                        |<-----------------------|                          |
   |                        | render_notices_desk_with_preset_result(...)       |
   |  200 HTML              |                        |                          |
   |<-----------------------|                        |                          |
```

---

## Design decisions

**Why `NOTICES_SCENARIO_DEFINITIONS` in `webui/state.py` rather than importing from `citation_gate.scenarios`?**  
`citation_gate/scenarios.py` owns a `run_scenarios()` runner with its own chain-per-scenario semantics. The web skin needs a single shared notices chain across all adjudications. Duplicating the scenario data in `webui/state.py` gives the web layer control over timing, chain assignment, and the N5 two-phase sequencing, exactly as `SCENARIO_DEFINITIONS` does for the estate desk.

**Why a single `HouseHandler` rather than separate `EstateHandler` and `NoticesHandler`?**  
`ThreadingHTTPServer` takes one handler class. A dispatcher handler avoids monkey-patching `EstateHandler` with new routes and keeps all routing in one place. The estate methods are unchanged; they simply move into (or are called from) `HouseHandler`.

**Why does `adjudicate_preset` not modify the working draft?**  
Preset adjudications run complete, self-contained demo drafts. Mixing them into the working draft would confuse the builder flow. The working draft is exclusively for free-builder assertions composed assertion by assertion.

**Why store `claim_hash` in `AssertionEntry`?**  
`check_publish` requires the canonical-JSON SHA-256 hash of each assertion's `Claim` dict, not the receipt's `own_hash`. Storing `claim_hash` in the `AssertionEntry` at adjudication time avoids recomputing it when the working draft's publish state is re-evaluated on subsequent `GET /notices` requests.

**Why is the desk mandate a freshly-sealed dict rather than one of the three source records?**  
The desk mandate governs the adjudication session — it is the desk's own authority seal, distinct from the per-source mandates the measurer checks internally. This mirrors the estate pattern: `HouseRegister` uses the 2024 will as the mandate for estate adjudications; `NoticesRegister` uses its own freshly-constructed mandate for citation adjudications. The desk mandate is stable for the lifetime of the server process.
