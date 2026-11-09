"""
webui.render
~~~~~~~~~~~~
Pure functions that return HTML strings for all rooms of The Estate Desk and
The Notices Desk. No HTTP, no state, no I/O. All functions are deterministic
given the same input.

Escaping rule: every user-supplied string is wrapped with _e() = html.escape(str(s)).
Fixture data is also escaped as a defense-in-depth measure.
"""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gate_core.receipt import Receipt, ReplayResult
    from executor.registry import ExecutorRegistry
    from citation_gate.sources import SourceRegistry
    from citation_gate.publish import PublishDecision
    from webui.state import AssertionEntry
    from gate_core.mandate import SealedMandate

# ---------------------------------------------------------------------------
# Escaping helper
# ---------------------------------------------------------------------------


def _e(s: object) -> str:
    """Escape a value for safe HTML insertion."""
    return html.escape(str(s))


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------


def css() -> str:
    """Return the full embedded CSS block."""
    return """
:root {
    --paper:    #faf7f0;
    --ink:      #1a1714;
    --ghost:    #9a938a;
    --oxblood:  #7a2e2a;
    --hairline: #d8d2c4;
}

*, *::before, *::after {
    box-sizing: border-box;
}

html {
    background-color: var(--paper);
}

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

h1 {
    font-size: 1.6rem;
    letter-spacing: 0.03em;
    margin-bottom: 0.25rem;
}

h2 {
    font-size: 1.15rem;
    letter-spacing: 0.04em;
    border-bottom: 1px solid var(--hairline);
    padding-bottom: 0.4rem;
    margin-top: 2rem;
}

h3 {
    font-size: 1rem;
    letter-spacing: 0.04em;
    margin-bottom: 0.5rem;
}

p.subtitle {
    color: var(--ghost);
    font-size: 0.95rem;
    letter-spacing: 0.06em;
    margin-top: 0;
    margin-bottom: 2rem;
}

hr, .rule {
    border: none;
    border-top: 1px solid var(--hairline);
    margin: 1.5rem 0;
}

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

/* Ghost (unmeasured) */
.ghost {
    color: var(--ghost);
    opacity: 0.75;
}

/* Claim-block state transition — the ONLY permitted animation */
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

/* PASS verdict */
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

/* seal_broken synthetic notice */
.seal-broken-notice {
    color: var(--oxblood);
    border: 1px solid var(--oxblood);
    padding: 0.75rem 1rem;
    margin-top: 1rem;
}

/* Monospaced hashes */
.hash {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.8rem;
    word-break: break-all;
}

/* Will columns — Register room */
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
    border-color: var(--ghost);
}

/* Bit vector */
.vector-bit {
    font-family: 'Courier New', Courier, monospace;
}

.vector-bit.changed {
    text-decoration: underline;
    text-underline-offset: 3px;
}

/* Receipt definition list */
dl.receipt {
    margin: 0;
}

dl.receipt dt {
    font-weight: bold;
    letter-spacing: 0.04em;
    margin-top: 0.75rem;
    font-size: 0.85rem;
    text-transform: uppercase;
    color: var(--ghost);
}

dl.receipt dd {
    margin-left: 0;
    margin-top: 0.15rem;
    font-size: 0.9rem;
}

pre.json-block {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.78rem;
    background: none;
    border: 1px solid var(--hairline);
    padding: 0.5rem;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
}

/* Bequest table */
table.bequests {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
    margin-top: 0.5rem;
}

table.bequests th {
    text-align: left;
    border-bottom: 1px solid var(--hairline);
    padding: 0.25rem 0.5rem 0.25rem 0;
    font-weight: bold;
    letter-spacing: 0.04em;
    font-size: 0.8rem;
    text-transform: uppercase;
    color: var(--ghost);
}

table.bequests td {
    padding: 0.2rem 0.5rem 0.2rem 0;
    vertical-align: top;
    border-bottom: 1px solid var(--hairline);
}

/* Preset scenario blocks */
.preset-block {
    border: 1px solid var(--hairline);
    padding: 1rem;
    margin-bottom: 1rem;
}

.preset-label {
    font-family: 'Courier New', Courier, monospace;
    font-weight: bold;
    font-size: 1.1rem;
    margin-right: 0.75rem;
}

/* Forms and buttons */
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

input[type="text"], input[type="number"], select {
    font-family: inherit;
    font-size: 0.9rem;
    border: 1px solid var(--hairline);
    background: var(--paper);
    color: var(--ink);
    padding: 0.25rem 0.5rem;
}

.builder-row {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    align-items: center;
    margin-bottom: 0.5rem;
    padding: 0.5rem;
    border: 1px solid var(--hairline);
}

.builder-row label {
    font-size: 0.85rem;
    color: var(--ghost);
}

/* Archive receipt cards */
.receipt-card {
    border: 1px solid var(--hairline);
    padding: 1rem;
    margin-bottom: 1.5rem;
}

.receipt-index {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.8rem;
    color: var(--ghost);
    margin-bottom: 0.5rem;
}

/* Verification result */
.chain-ok {
    color: var(--ink);
    border: 1px solid var(--hairline);
    padding: 0.75rem 1rem;
    margin-top: 1rem;
}

.chain-fail {
    color: var(--oxblood);
    border: 1px solid var(--oxblood);
    padding: 0.75rem 1rem;
    margin-top: 1rem;
}

.tamper-demo-result {
    margin-top: 1rem;
}

.not-modified-notice {
    color: var(--ink);
    font-style: italic;
    margin-top: 0.75rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--hairline);
}

/* Nav separator and groups for two-desk navigation */
.nav-separator {
    color: var(--ghost);
    margin-right: 1.5rem;
}

.nav-group {
    display: inline;
}

/* Fact table for source records */
table.fact-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
    margin-top: 0.5rem;
}

table.fact-table th {
    text-align: left;
    border-bottom: 1px solid var(--hairline);
    padding: 0.25rem 0.5rem 0.25rem 0;
    font-weight: bold;
    letter-spacing: 0.04em;
    font-size: 0.8rem;
    text-transform: uppercase;
    color: var(--ghost);
}

table.fact-table td {
    padding: 0.2rem 0.5rem 0.2rem 0;
    vertical-align: top;
    border-bottom: 1px solid var(--hairline);
}

/* Source record card */
.source-card {
    border: 1px solid var(--hairline);
    padding: 1rem;
    margin-bottom: 1.5rem;
}

/* Assertion entry in draft or preset results */
.assertion-entry {
    padding: 0.4rem 0;
    border-bottom: 1px solid var(--hairline);
}

.assertion-entry:last-child {
    border-bottom: none;
}

/* Working draft section */
.working-draft {
    border: 1px solid var(--hairline);
    padding: 1rem;
    margin-bottom: 1rem;
}

/* Publish stamp */
.publish-stamp {
    margin-top: 0.75rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--hairline);
}

/* Release stamp (The Vault) */
.release-stamp {
    margin-top: 0.75rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--hairline);
}
"""


# ---------------------------------------------------------------------------
# Page shell
# ---------------------------------------------------------------------------


def _house_nav() -> str:
    """Return the shared three-desk navigation (Estate · Notices · Vault)."""
    return (
        '<nav>'
        '<span class="nav-group">'
        '<a href="/">Register</a>'
        '<a href="/desk">Desk</a>'
        '<a href="/archive">Archive</a>'
        '</span>'
        '<span class="nav-separator">·</span>'
        '<span class="nav-group">'
        '<a href="/notices/sources">Sources</a>'
        '<a href="/notices">Notices</a>'
        '<a href="/notices/archive">Notice Archive</a>'
        '</span>'
        '<span class="nav-separator">·</span>'
        '<span class="nav-group">'
        '<a href="/vault">Bundle</a>'
        '<a href="/vault/desk">Release</a>'
        '<a href="/vault/archive">Vault Archive</a>'
        '</span>'
        '</nav>'
    )


def page_shell(title: str, body_html: str) -> str:
    """Return a complete <!DOCTYPE html> document with embedded CSS and nav."""
    nav = _house_nav()
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"  <title>{_e(title)}</title>\n"
        "  <style>\n"
        f"{css()}"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "<header>\n"
        "  <h1>The Estate Desk</h1>\n"
        "  <p class=\"subtitle\">Nothing leaves this house unmeasured.</p>\n"
        f"  {nav}\n"
        "</header>\n"
        f"<main>{body_html}</main>\n"
        "</body>\n"
        "</html>\n"
    )


def notices_page_shell(title: str, body_html: str) -> str:
    """Return a complete <!DOCTYPE html> document for The Notices Desk."""
    nav = _house_nav()
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"  <title>{_e(title)}</title>\n"
        "  <style>\n"
        f"{css()}"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "<header>\n"
        "  <h1>The Notices Desk</h1>\n"
        "  <p class=\"subtitle\">Nothing is printed here unmeasured.</p>\n"
        f"  {nav}\n"
        "</header>\n"
        f"<main>{body_html}</main>\n"
        "</body>\n"
        "</html>\n"
    )


def vault_page_shell(title: str, body_html: str) -> str:
    """Return a complete <!DOCTYPE html> document for The Vault."""
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"  <title>{_e(title)}</title>\n"
        "  <style>\n"
        f"{css()}"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "<header>\n"
        "  <h1>The Vault</h1>\n"
        "  <p class=\"subtitle\">Nothing leaves this house unmeasured \u2014 not even the records.</p>\n"
        f"  {_house_nav()}\n"
        "</header>\n"
        f"<main>{body_html}</main>\n"
        "</body>\n"
        "</html>\n"
    )


# ---------------------------------------------------------------------------
# Verdict badge
# ---------------------------------------------------------------------------


def render_verdict_badge(verdict_dict: dict) -> str:
    """Return a small HTML span representing the verdict.

    Args:
        verdict_dict: {"type": "pass"} or {"type": "refused", "name": "..."}
    """
    if verdict_dict.get("type") == "pass":
        return '<span class="verdict-pass">PASS</span>'
    elif verdict_dict.get("type") == "refused":
        name = _e(verdict_dict.get("name", "unknown"))
        return f'<span class="verdict-refused">REFUSED · {name}</span>'
    else:
        return f'<span class="verdict-refused">REFUSED · {_e(verdict_dict.get("name", "unknown"))}</span>'


# ---------------------------------------------------------------------------
# Receipt rendering
# ---------------------------------------------------------------------------


def render_receipt(receipt: "Receipt") -> str:
    """Render all fields of a Receipt as a <dl> definition list.

    Hashes are rendered in <span class="hash">. No fields are truncated.
    """
    claim_json = _e(json.dumps(receipt.claim, indent=2, ensure_ascii=False))
    measurements_html: str
    if receipt.measurements is None:
        measurements_html = "<em>unmeasured</em>"
    else:
        measurements_html = (
            f'<pre class="json-block">'
            f'{_e(json.dumps(receipt.measurements, indent=2, ensure_ascii=False))}'
            f'</pre>'
        )

    measurement_error_html = ""
    if receipt.measurement_error is not None:
        measurement_error_html = (
            f"<dt>Measurement Error</dt>"
            f"<dd>{_e(receipt.measurement_error)}</dd>"
        )

    verdict_badge = render_verdict_badge(receipt.verdict)

    return (
        '<dl class="receipt">'
        "<dt>Claim</dt>"
        f'<dd><pre class="json-block">{claim_json}</pre></dd>'
        "<dt>Measurements</dt>"
        f"<dd>{measurements_html}</dd>"
        f"{measurement_error_html}"
        "<dt>Verdict</dt>"
        f"<dd>{verdict_badge}</dd>"
        "<dt>Timestamp (UTC)</dt>"
        f"<dd>{_e(receipt.timestamp_utc)}</dd>"
        "<dt>Previous Hash</dt>"
        f'<dd><span class="hash">{_e(receipt.previous_hash)}</span></dd>'
        "<dt>Own Hash</dt>"
        f'<dd><span class="hash">{_e(receipt.own_hash)}</span></dd>'
        "</dl>"
    )


# ---------------------------------------------------------------------------
# Register room
# ---------------------------------------------------------------------------

# ZODIAC order (MSB→LSB) — must match executor.measurer.ZODIAC_MSB_TO_LSB
_ZODIAC_MSB_TO_LSB = [
    "Pisces", "Aquarius", "Capricorn", "Sagittarius",
    "Scorpio", "Cancer", "Gemini", "Leo",
    "Virgo", "Libra", "Taurus", "Aries",
]


def _render_bequest_table(bequests: list[dict], ghost: bool = False) -> str:
    """Render a bequest table for occupied signs."""
    ghost_class = ' class="ghost"' if ghost else ""
    rows = ""
    for b in bequests:
        rows += (
            f"<tr>"
            f"<td>{_e(b.get('sign', ''))}</td>"
            f"<td>{_e(b.get('item', ''))}</td>"
            f"<td>{_e(b.get('beneficiary', ''))}</td>"
            f"</tr>"
        )
    return (
        f'<table class="bequests"{ghost_class}>'
        "<thead><tr>"
        "<th>Sign</th><th>Item</th><th>Beneficiary</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    )


def _render_vector_spans(vector_2024: str, vector_other: str, is_2024: bool) -> str:
    """Render a bit vector as individual .vector-bit spans.

    Bits that differ between the two vectors carry an additional .changed class.
    """
    spans = ""
    reference_vec = vector_2024 if not is_2024 else vector_other
    this_vec = vector_2024 if is_2024 else vector_other

    for i, bit in enumerate(this_vec):
        # A bit is "changed" if it differs from its counterpart in the other vector
        changed = (i < len(reference_vec)) and (bit != reference_vec[i])
        cls = "vector-bit changed" if changed else "vector-bit"
        spans += f'<span class="{cls}">{_e(bit)}</span>'
    return spans


def render_register(registry: "ExecutorRegistry") -> str:
    """Render the Register room (GET /)."""
    testator = "Elias Vane"
    all_wills = registry.all_wills(testator)
    death_record = registry.death_record(testator)

    # Sort: oldest first (index 0 = 2019, index -1 = 2024)
    will_2019 = all_wills[0] if len(all_wills) >= 2 else None
    will_2024 = all_wills[-1] if all_wills else None

    # Death record status
    if death_record is not None:
        dr_seal_prefix = _e(death_record.seal[:12])
        dr_status = (
            f"<p>Death record present. Seal: "
            f'<span class="hash">{dr_seal_prefix}…</span>'
            f"</p>"
        )
    else:
        dr_status = "<p class=\"ghost\">Death record: absent.</p>"

    # Vectors for diff computation
    vec_2024 = will_2024.content.get("vector", "") if will_2024 else ""
    vec_2019 = will_2019.content.get("vector", "") if will_2019 else ""

    # 2024 will column
    if will_2024:
        vec_spans_2024 = _render_vector_spans(vec_2024, vec_2019, is_2024=True)
        bequests_2024 = will_2024.content.get("bequests", [])
        date_2024 = _e(will_2024.content.get("sealed_date", ""))
        seal_2024 = _e(will_2024.seal[:12])
        col_2024 = (
            '<div class="will-column">'
            f"<h3>Will — {date_2024}</h3>"
            f'<p>Seal: <span class="hash">{seal_2024}…</span></p>'
            f"<p>Vector: {vec_spans_2024}</p>"
            f"{_render_bequest_table(bequests_2024)}"
            "</div>"
        )
    else:
        col_2024 = '<div class="will-column"><p class="ghost">No 2024 will found.</p></div>'

    # 2019 will column (ghost / superseded)
    if will_2019:
        vec_spans_2019 = _render_vector_spans(vec_2024, vec_2019, is_2024=False)
        bequests_2019 = will_2019.content.get("bequests", [])
        date_2019 = _e(will_2019.content.get("sealed_date", ""))
        seal_2019 = _e(will_2019.seal[:12])
        col_2019 = (
            '<div class="will-column superseded ghost">'
            f"<h3>Will — {date_2019} (superseded)</h3>"
            f'<p>Seal: <span class="hash">{seal_2019}…</span></p>'
            f"<p>Vector: {vec_spans_2019}</p>"
            f"{_render_bequest_table(bequests_2019, ghost=True)}"
            "</div>"
        )
    else:
        col_2019 = '<div class="will-column superseded ghost"><p>No 2019 will found.</p></div>'

    body = (
        f"<h2>Testator: {_e(testator)}</h2>"
        f"{dr_status}"
        "<hr>"
        "<h2>Will Register</h2>"
        '<div class="will-columns">'
        f"{col_2019}"
        f"{col_2024}"
        "</div>"
    )
    return body


# ---------------------------------------------------------------------------
# Desk room — preset blocks
# ---------------------------------------------------------------------------


def _render_preset_block(
    defn: dict,
    resolved: bool = False,
    verdict_html: str = "",
) -> str:
    """Render a single preset scenario block."""
    label = _e(defn["label"])
    description = _e(defn["description"])
    expected = _e(defn.get("expected_verdict", ""))
    ghost_class = "resolved" if resolved else "ghost"

    # Claim summary table
    dists = defn.get("distributions", [])
    rows = ""
    for d in dists[:10]:  # cap display at 10 rows for sanity
        rows += (
            f"<tr>"
            f"<td>{_e(d.get('sign', ''))}</td>"
            f"<td>{_e(d.get('item', ''))}</td>"
            f"<td>{_e(d.get('beneficiary', ''))}</td>"
            f"</tr>"
        )
    if len(dists) > 10:
        rows += f"<tr><td colspan=\"3\">… and {len(dists) - 10} more</td></tr>"

    claim_table = (
        '<table class="bequests">'
        "<thead><tr><th>Sign</th><th>Item</th><th>Beneficiary</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    ) if dists else ""

    verdict_section = f'<div class="verdict-result">{verdict_html}</div>' if verdict_html else ""

    will_label = _e(defn.get("will_selector", ""))
    registry_variant = _e(defn.get("registry_variant", "full"))

    return (
        f'<div class="preset-block">'
        f'<div class="claim-block {ghost_class}">'
        f'<p><span class="preset-label">{label}</span>{description}</p>'
        f"<p><small>Will: {will_label} · Registry: {registry_variant} · Expected: {expected}</small></p>"
        f"{claim_table}"
        f'<form method="post" action="/adjudicate" style="margin-top:0.75rem;">'
        f'<input type="hidden" name="preset" value="{label}">'
        f'<input type="submit" value="Adjudicate Preset {label}">'
        f"</form>"
        f"</div>"
        f"{verdict_section}"
        f"</div>"
    )


def render_desk(scenario_defs: list[dict], registry: "ExecutorRegistry") -> str:
    """Render the Desk room body (GET /desk)."""
    blocks = ""
    for defn in scenario_defs:
        blocks += _render_preset_block(defn)

    builder = render_builder_form(registry)

    return (
        "<h2>The Desk — Adjudication Workbench</h2>"
        "<p>Seven preset claims in casework order, followed by the free builder.</p>"
        "<hr>"
        f"{blocks}"
        "<hr>"
        "<h2>Free Builder</h2>"
        f"{builder}"
    )


def render_desk_with_result(
    scenario_defs: list[dict],
    registry: "ExecutorRegistry",
    label_or_builder: str,
    verdict: object,
    receipt: "Receipt | None",
    tamper_error: bool,
) -> str:
    """Like render_desk but injects the verdict result after the matching preset."""
    # Build the verdict HTML
    if tamper_error:
        verdict_html = (
            '<div class="seal-broken-notice">'
            '<p><span class="verdict-refused">REFUSED · seal_broken</span></p>'
            "<p>Mandate seal verification failed. This event was not recorded in the house chain.</p>"
            "</div>"
        )
    elif receipt is not None:
        verdict_html = render_receipt(receipt)
    else:
        verdict_html = '<p class="ghost">No result.</p>'

    blocks = ""
    for defn in scenario_defs:
        if defn["label"] == label_or_builder:
            blocks += _render_preset_block(defn, resolved=True, verdict_html=verdict_html)
        else:
            blocks += _render_preset_block(defn)

    # If it was a builder submission, render builder with result appended
    if label_or_builder == "builder":
        builder_result = (
            "<h3>Adjudication Result</h3>"
            f"{verdict_html}"
        )
        builder = render_builder_form(registry) + builder_result
    else:
        builder = render_builder_form(registry)

    return (
        "<h2>The Desk — Adjudication Workbench</h2>"
        "<p>Seven preset claims in casework order, followed by the free builder.</p>"
        "<hr>"
        f"{blocks}"
        "<hr>"
        "<h2>Free Builder</h2>"
        f"{builder}"
    )


# ---------------------------------------------------------------------------
# Builder form
# ---------------------------------------------------------------------------


def render_builder_form(
    registry: "ExecutorRegistry",
    selected_will_seal: str | None = None,
    row_count: int = 1,
) -> str:
    """Render the free-builder form.

    The form does not pre-fill beneficiary fields with fixture data.
    """
    testator = "Elias Vane"
    all_wills = registry.all_wills(testator)

    if not all_wills:
        return "<p class=\"ghost\">No wills available.</p>"

    # Will picker
    will_options = ""
    for w in all_wills:
        seal = w.seal
        date = w.content.get("sealed_date", "unknown")
        seal_prefix = seal[:12]
        display = f"{date} — {seal_prefix}…"
        selected_attr = ' selected' if seal == selected_will_seal else ''
        will_options += f'<option value="{_e(seal)}"{selected_attr}>{_e(display)}</option>'

    # Resolve the selected will for sign/item dropdowns
    if selected_will_seal:
        selected_will = registry.will_by_seal(selected_will_seal)
    else:
        selected_will = all_wills[-1]  # default to latest

    # Get occupied bequests from the selected will
    if selected_will:
        occupied_bequests = selected_will.content.get("bequests", [])
    else:
        occupied_bequests = []

    # Build sign options (occupied signs only, in vector order)
    # The bequests in the fixture are already for occupied signs;
    # sort them by ZODIAC order to match vector order.
    zodiac_order = {s: i for i, s in enumerate(_ZODIAC_MSB_TO_LSB)}
    occupied_sorted = sorted(
        occupied_bequests,
        key=lambda b: zodiac_order.get(b.get("sign", ""), 999),
    )

    sign_options = "".join(
        f'<option value="{_e(b["sign"])}">{_e(b["sign"])}</option>'
        for b in occupied_sorted
    )
    item_options = "".join(
        f'<option value="{_e(b["item"])}">{_e(b["item"])}</option>'
        for b in occupied_sorted
    )

    # Distribution rows
    current_seal = selected_will.seal if selected_will else (all_wills[-1].seal if all_wills else "")
    rows_html = ""
    for i in range(max(1, row_count)):
        rows_html += (
            f'<div class="builder-row">'
            f'<label>Row {i + 1}</label>'
            f'<select name="sign_{i}">{sign_options}</select>'
            f'<select name="item_{i}">{item_options}</select>'
            f'<input type="text" name="beneficiary_{i}" placeholder="Beneficiary (type name)">'
            f"</div>"
        )

    # Row-count setter form
    row_setter = (
        '<form method="post" action="/desk/builder-rows" style="margin-bottom:1rem;">'
        f'<input type="hidden" name="will_seal" value="{_e(current_seal)}">'
        '<label>Distribution rows: '
        f'<input type="number" name="row_count" min="1" max="12" value="{_e(row_count)}">'
        '</label> '
        '<input type="submit" value="Set rows">'
        '</form>'
    )

    # Main builder form
    builder_form = (
        '<form method="post" action="/adjudicate">'
        f'<p><label>Will: <select name="will_seal">{will_options}</select></label></p>'
        f'<input type="hidden" name="builder" value="1">'
        f'<input type="hidden" name="row_count" value="{_e(row_count)}">'
        f"{rows_html}"
        '<p><input type="submit" value="Submit for adjudication"></p>'
        '</form>'
    )

    return (
        f"{row_setter}"
        f"{builder_form}"
    )


# ---------------------------------------------------------------------------
# Archive room
# ---------------------------------------------------------------------------


def _render_replay_result(result: "ReplayResult") -> str:
    """Render a chain verification ReplayResult."""
    if result.ok:
        n = "unknown"  # caller provides context
        return (
            '<div class="chain-ok">'
            "Chain intact — all receipts verified."
            "</div>"
        )
    else:
        return (
            '<div class="chain-fail">'
            f"<p>Chain verification FAILED at receipt index {_e(result.failure_index)}.</p>"
            f"<p>Reason: {_e(result.failure_reason)}</p>"
            "</div>"
        )


def render_archive(
    chain: "list[Receipt]",
    replay_result: "ReplayResult | None" = None,
    tamper_result: "ReplayResult | None" = None,
    tamper_demo_ran: bool = False,
) -> str:
    """Render the Archive room (GET /archive)."""
    n = len(chain)
    receipts_html = ""
    for i, receipt in enumerate(chain):
        receipts_html += (
            f'<div class="receipt-card">'
            f'<p class="receipt-index">Receipt #{i + 1}</p>'
            f"{render_receipt(receipt)}"
            f"</div>"
        )
    if not receipts_html:
        receipts_html = "<p class=\"ghost\">No receipts in the chain yet.</p>"

    # Verify chain integrity form
    replay_section = ""
    if replay_result is not None:
        if replay_result.ok:
            ok_text = f"Chain intact — {n} receipt{'s' if n != 1 else ''} verified."
            replay_section = (
                f'<div class="chain-ok">{_e(ok_text)}</div>'
            )
        else:
            replay_section = (
                '<div class="chain-fail">'
                f"<p>Chain verification FAILED at receipt index {_e(replay_result.failure_index)}.</p>"
                f"<p>Reason: {_e(replay_result.failure_reason)}</p>"
                "</div>"
            )

    verify_form = (
        '<form method="post" action="/archive/verify" style="margin-top:1rem;">'
        '<input type="submit" value="Verify chain integrity">'
        "</form>"
        f"{replay_section}"
    )

    # Tamper demonstration form
    tamper_section = ""
    if tamper_demo_ran and tamper_result is not None:
        if tamper_result.ok:
            tamper_section = (
                '<div class="tamper-demo-result">'
                '<div class="chain-ok">Chain intact (no receipts to tamper — chain is empty).</div>'
                '<p class="not-modified-notice">The house chain was not modified.</p>'
                "</div>"
            )
        else:
            tamper_section = (
                '<div class="tamper-demo-result chain-fail">'
                f"<p>Tamper demonstration: chain verification FAILED at receipt index {_e(tamper_result.failure_index)}.</p>"
                f"<p>Reason: {_e(tamper_result.failure_reason)}</p>"
                '<p class="not-modified-notice">The house chain was not modified.</p>'
                "</div>"
            )

    tamper_form = (
        "<hr>"
        "<h3>Tamper Demonstration</h3>"
        "<p>Runs verify_chain on a deep copy of the chain with one receipt mutated. "
        "The house chain itself is never modified by this demonstration.</p>"
        '<form method="post" action="/archive/tamper-demo" style="margin-top:0.5rem;">'
        '<input type="submit" value="Run tamper demonstration">'
        "</form>"
        f"{tamper_section}"
    )

    return (
        f"<h2>House Chain — {_e(n)} receipt{'s' if n != 1 else ''}.</h2>"
        f"{receipts_html}"
        "<hr>"
        "<h3>Verify Chain Integrity</h3>"
        f"{verify_form}"
        f"{tamper_form}"
    )


# ===========================================================================
# Notices Desk render functions
# ===========================================================================

# Fixed source display order
_NOTICE_SOURCE_IDS = ("death_record", "will_2024", "family_record")

_NOTICE_SOURCE_LABELS = {
    "death_record":  "Death Record",
    "will_2024":     "Will of 2024",
    "family_record": "Family Record",
}

_CITATION_OPTIONS = [
    ("death_record",  "Death record"),
    ("will_2024",     "Will of 2024"),
    ("family_record", "Family record"),
    ("",              "No citation"),
]


# ---------------------------------------------------------------------------
# render_publish_decision
# ---------------------------------------------------------------------------

def render_publish_decision(decision: "PublishDecision") -> str:
    """Render a PublishDecision as a publish stamp."""
    if decision.publishable:
        ids_html = ""
        if decision.receipt_ids:
            id_items = "".join(
                f'<li><span class="hash">{_e(rid)}</span></li>'
                for rid in decision.receipt_ids
            )
            ids_html = f"<ul>{id_items}</ul>"
        return (
            f'<div class="publish-stamp">'
            f'<p class="verdict-pass">PUBLISHABLE</p>'
            f"{ids_html}"
            f"</div>"
        )
    else:
        name = _e(decision.refusal_name or "unknown")
        return (
            f'<div class="publish-stamp">'
            f'<p class="verdict-refused">REFUSED · {name}</p>'
            f"</div>"
        )


# ---------------------------------------------------------------------------
# render_sources
# ---------------------------------------------------------------------------

def render_sources(source_registry: "SourceRegistry") -> str:
    """Render the Sources room body (GET /notices/sources)."""
    cards = ""
    for source_id in _NOTICE_SOURCE_IDS:
        label = _NOTICE_SOURCE_LABELS.get(source_id, source_id)
        source = source_registry.source(source_id)
        fact_table = source_registry.fact_table(source_id)

        if source is None:
            cards += (
                f'<div class="source-card">'
                f"<h3>{_e(source_id)}</h3>"
                f'<p class="ghost">{_e(label)} — source not loaded.</p>'
                f"</div>"
            )
            continue

        seal_prefix = _e(source.seal[:12])
        seal_html = f'<p>Seal: <span class="hash">{seal_prefix}…</span></p>'

        # Fact table
        if fact_table:
            rows = "".join(
                f"<tr><td>{_e(k)}</td><td>{_e(v)}</td></tr>"
                for k, v in fact_table.items()
            )
            table_html = (
                '<table class="fact-table">'
                "<thead><tr><th>Key</th><th>Value</th></tr></thead>"
                f"<tbody>{rows}</tbody>"
                "</table>"
            )
        else:
            table_html = '<p class="ghost">No facts available.</p>'

        cards += (
            f'<div class="source-card">'
            f"<h3>{_e(source_id)}</h3>"
            f'<p class="ghost">{_e(label)}</p>'
            f"{seal_html}"
            f"{table_html}"
            f"</div>"
        )

    return (
        "<h2>The Sources</h2>"
        "<p>The three sealed source records held by this desk. "
        "Each seal is a SHA-256 hash of the record's canonical JSON.</p>"
        "<hr>"
        f"{cards}"
    )


# ---------------------------------------------------------------------------
# render_assertion_builder
# ---------------------------------------------------------------------------

def render_assertion_builder(source_registry: "SourceRegistry") -> str:
    """Render the free-assertion builder form."""
    # Build fact_key optgroups: one per source
    optgroups = ""
    for source_id in _NOTICE_SOURCE_IDS:
        label = _NOTICE_SOURCE_LABELS.get(source_id, source_id)
        fact_table = source_registry.fact_table(source_id)
        if not fact_table:
            continue
        options = "".join(
            f'<option value="{_e(k)}">{_e(source_id)} — {_e(k)}</option>'
            for k in fact_table.keys()
        )
        optgroups += f'<optgroup label="{_e(source_id)}">{options}</optgroup>'

    # Citation options
    citation_opts = "".join(
        f'<option value="{_e(val)}">{_e(display)}</option>'
        for val, display in _CITATION_OPTIONS
    )

    return (
        '<form method="post" action="/notices/assertion">'
        "<p>"
        '<label>Sentence: '
        '<input type="text" name="sentence" size="60" placeholder="As it will print in the notice">'
        "</label>"
        "</p>"
        "<p>"
        '<label>Fact key: '
        f'<select name="fact_key">{optgroups}</select>'
        "</label>"
        "</p>"
        "<p>"
        '<label>Claimed value: '
        '<input type="text" name="value" size="40" placeholder="The value you are asserting">'
        "</label>"
        "</p>"
        "<p>"
        '<label>Citation: '
        f'<select name="citation">{citation_opts}</select>'
        "</label>"
        "</p>"
        '<p><input type="submit" value="Measure this assertion"></p>'
        "</form>"
    )


# ---------------------------------------------------------------------------
# _render_assertion_entry_html  (shared helper)
# ---------------------------------------------------------------------------

def _render_assertion_entry_html(entry: "AssertionEntry", resolved: bool = True) -> str:
    """Render one AssertionEntry as a .assertion-entry div."""
    state_class = "resolved" if resolved else "ghost"

    if entry.verdict is None:
        # Tamper — seal_broken synthetic
        badge = '<span class="verdict-refused">REFUSED · seal_broken</span>'
    else:
        badge = render_verdict_badge(entry.verdict)

    citation_display = _e(entry.citation) if entry.citation else "<em>no citation</em>"

    receipt_html = ""
    if entry.receipt is not None:
        receipt_html = (
            "<details><summary>Receipt</summary>"
            f"{render_receipt(entry.receipt)}"
            "</details>"
        )

    return (
        f'<div class="assertion-entry claim-block {state_class}">'
        f"<p>{_e(entry.text)}</p>"
        f"<p><small>key: {_e(entry.fact_key)} · value: {_e(entry.value)} · "
        f"citation: {citation_display}</small></p>"
        f"<p>{badge}</p>"
        f"{receipt_html}"
        f"</div>"
    )


# ---------------------------------------------------------------------------
# _render_notices_preset_block  (shared helper)
# ---------------------------------------------------------------------------

def _render_notices_preset_block(
    defn: dict,
    resolved: bool = False,
    result_html: str = "",
) -> str:
    """Render one notices preset block."""
    label = _e(defn["label"])
    description = _e(defn["description"])
    expected = _e(defn.get("expected_publish", ""))
    ghost_class = "resolved" if resolved else "ghost"

    # Assertion preview (ghost sentences)
    assertion_previews = ""
    for phase in defn.get("phases", []):
        for a in phase.get("assertions", []):
            citation = _e(a["citation"]) if a.get("citation") else "no citation"
            assertion_previews += (
                f'<p class="ghost assertion-sentence">{_e(a["text"])} '
                f'<small>key: {_e(a["fact_key"])} · citation: {citation}</small></p>'
            )

    result_section = f'<div class="verdict-result">{result_html}</div>' if result_html else ""

    return (
        f'<div class="preset-block">'
        f'<div class="claim-block {ghost_class}">'
        f'<p><span class="preset-label">{label}</span>{description}</p>'
        f"<p><small>Expected: {expected}</small></p>"
        f"{assertion_previews}"
        f'<form method="post" action="/notices/preset" style="margin-top:0.75rem;">'
        f'<input type="hidden" name="preset" value="{_e(defn["label"])}">'
        f'<input type="submit" value="Run {_e(defn["label"])}">'
        f"</form>"
        f"</div>"
        f"{result_section}"
        f"</div>"
    )


# ---------------------------------------------------------------------------
# _render_working_draft_section
# ---------------------------------------------------------------------------

def _render_working_draft_section(
    working_draft: "list[AssertionEntry]",
    publish_state: "PublishDecision | None",
) -> str:
    """Render the current working draft and its publish state."""
    if not working_draft:
        draft_entries_html = '<p class="ghost">No assertions in the working draft yet.</p>'
    else:
        draft_entries_html = "".join(
            _render_assertion_entry_html(e, resolved=True)
            for e in working_draft
        )

    publish_html = ""
    if publish_state is not None:
        publish_html = render_publish_decision(publish_state)

    return (
        '<div class="working-draft">'
        "<h3>Working Draft</h3>"
        f"{draft_entries_html}"
        f"{publish_html}"
        "</div>"
    )


# ---------------------------------------------------------------------------
# render_notices_desk
# ---------------------------------------------------------------------------

def render_notices_desk(
    scenario_defs: list[dict],
    source_registry: "SourceRegistry",
    working_draft: "list[AssertionEntry]",
    publish_state: "PublishDecision | None",
) -> str:
    """Render the Notices Desk workbench body (GET /notices)."""
    blocks = "".join(_render_notices_preset_block(defn) for defn in scenario_defs)

    working_draft_section = _render_working_draft_section(working_draft, publish_state)

    builder = render_assertion_builder(source_registry)

    new_draft_form = (
        '<form method="post" action="/notices/new-draft" style="margin-top:1rem;">'
        '<input type="submit" value="Begin a new draft">'
        "</form>"
    )

    return (
        "<h2>The Notices Desk — Adjudication Workbench</h2>"
        "<p>Six preset scenario drafts, followed by the free assertion builder.</p>"
        "<hr>"
        f"{blocks}"
        "<hr>"
        "<h2>Working Draft</h2>"
        f"{working_draft_section}"
        f"{new_draft_form}"
        "<hr>"
        "<h2>Free Builder</h2>"
        "<p>Compose an assertion and measure it against the source records.</p>"
        f"{builder}"
    )


# ---------------------------------------------------------------------------
# render_notices_desk_with_preset_result
# ---------------------------------------------------------------------------

def render_notices_desk_with_preset_result(
    scenario_defs: list[dict],
    source_registry: "SourceRegistry",
    working_draft: "list[AssertionEntry]",
    publish_state: "PublishDecision | None",
    label: str,
    entries: "list[AssertionEntry]",
    decisions: "list[PublishDecision]",
    tamper_error: bool,
) -> str:
    """Like render_notices_desk but injects the full preset result after the matching block."""
    # Build result HTML for the matched preset
    if tamper_error:
        result_html = (
            '<div class="seal-broken-notice">'
            '<p><span class="verdict-refused">REFUSED · seal_broken</span></p>'
            "<p>Source seal verification failed. This event was not recorded in the notices chain.</p>"
            "</div>"
        )
    else:
        assertion_html = "".join(
            _render_assertion_entry_html(e, resolved=True) for e in entries
        )
        decisions_html = "".join(render_publish_decision(d) for d in decisions)
        result_html = assertion_html + decisions_html

    blocks = ""
    for defn in scenario_defs:
        if defn["label"] == label:
            blocks += _render_notices_preset_block(defn, resolved=True, result_html=result_html)
        else:
            blocks += _render_notices_preset_block(defn)

    working_draft_section = _render_working_draft_section(working_draft, publish_state)

    builder = render_assertion_builder(source_registry)

    new_draft_form = (
        '<form method="post" action="/notices/new-draft" style="margin-top:1rem;">'
        '<input type="submit" value="Begin a new draft">'
        "</form>"
    )

    return (
        "<h2>The Notices Desk — Adjudication Workbench</h2>"
        "<p>Six preset scenario drafts, followed by the free assertion builder.</p>"
        "<hr>"
        f"{blocks}"
        "<hr>"
        "<h2>Working Draft</h2>"
        f"{working_draft_section}"
        f"{new_draft_form}"
        "<hr>"
        "<h2>Free Builder</h2>"
        "<p>Compose an assertion and measure it against the source records.</p>"
        f"{builder}"
    )


# ---------------------------------------------------------------------------
# render_notices_desk_with_assertion_result
# ---------------------------------------------------------------------------

def render_notices_desk_with_assertion_result(
    scenario_defs: list[dict],
    source_registry: "SourceRegistry",
    working_draft: "list[AssertionEntry]",
    publish_state: "PublishDecision | None",
    entry: "AssertionEntry",
    tamper_error: bool,
) -> str:
    """Like render_notices_desk but renders the latest assertion result beneath the builder."""
    blocks = "".join(_render_notices_preset_block(defn) for defn in scenario_defs)

    working_draft_section = _render_working_draft_section(working_draft, publish_state)

    new_draft_form = (
        '<form method="post" action="/notices/new-draft" style="margin-top:1rem;">'
        '<input type="submit" value="Begin a new draft">'
        "</form>"
    )

    builder = render_assertion_builder(source_registry)

    if tamper_error:
        assertion_result_html = (
            '<div class="seal-broken-notice">'
            '<p><span class="verdict-refused">REFUSED · seal_broken</span></p>'
            "<p>Source seal verification failed. This assertion was not recorded in the notices chain.</p>"
            "</div>"
        )
    else:
        assertion_result_html = (
            "<h3>Adjudication Result</h3>"
            + _render_assertion_entry_html(entry, resolved=True)
        )

    return (
        "<h2>The Notices Desk — Adjudication Workbench</h2>"
        "<p>Six preset scenario drafts, followed by the free assertion builder.</p>"
        "<hr>"
        f"{blocks}"
        "<hr>"
        "<h2>Working Draft</h2>"
        f"{working_draft_section}"
        f"{new_draft_form}"
        "<hr>"
        "<h2>Free Builder</h2>"
        "<p>Compose an assertion and measure it against the source records.</p>"
        f"{builder}"
        f"{assertion_result_html}"
    )


# ---------------------------------------------------------------------------
# render_notices_archive
# ---------------------------------------------------------------------------

def render_notices_archive(
    chain: "list[Receipt]",
    replay_result: "ReplayResult | None" = None,
    tamper_result: "ReplayResult | None" = None,
    tamper_demo_ran: bool = False,
) -> str:
    """Render the Notice Archive body (GET /notices/archive)."""
    n = len(chain)
    receipts_html = ""
    for i, receipt in enumerate(chain):
        receipts_html += (
            f'<div class="receipt-card">'
            f'<p class="receipt-index">Receipt #{i + 1}</p>'
            f"{render_receipt(receipt)}"
            f"</div>"
        )
    if not receipts_html:
        receipts_html = '<p class="ghost">No receipts in the notices chain yet.</p>'

    # Verify chain integrity section
    replay_section = ""
    if replay_result is not None:
        if replay_result.ok:
            ok_text = f"Chain intact — {n} receipt{'s' if n != 1 else ''} verified."
            replay_section = f'<div class="chain-ok">{_e(ok_text)}</div>'
        else:
            replay_section = (
                '<div class="chain-fail">'
                f"<p>Chain verification FAILED at receipt index {_e(replay_result.failure_index)}.</p>"
                f"<p>Reason: {_e(replay_result.failure_reason)}</p>"
                "</div>"
            )

    verify_form = (
        '<form method="post" action="/notices/archive/verify" style="margin-top:1rem;">'
        '<input type="submit" value="Verify chain integrity">'
        "</form>"
        f"{replay_section}"
    )

    # Tamper demonstration section
    tamper_section = ""
    if tamper_demo_ran and tamper_result is not None:
        if tamper_result.ok:
            tamper_section = (
                '<div class="tamper-demo-result">'
                '<div class="chain-ok">Chain intact (no receipts to tamper — chain is empty).</div>'
                '<p class="not-modified-notice">The notices chain was not modified.</p>'
                "</div>"
            )
        else:
            tamper_section = (
                '<div class="tamper-demo-result chain-fail">'
                f"<p>Tamper demonstration: chain verification FAILED at receipt index {_e(tamper_result.failure_index)}.</p>"
                f"<p>Reason: {_e(tamper_result.failure_reason)}</p>"
                '<p class="not-modified-notice">The notices chain was not modified.</p>'
                "</div>"
            )

    tamper_form = (
        "<hr>"
        "<h3>Tamper Demonstration</h3>"
        "<p>Runs verify_chain on a deep copy of the notices chain with one receipt mutated. "
        "The notices chain itself is never modified by this demonstration.</p>"
        '<form method="post" action="/notices/archive/tamper" style="margin-top:0.5rem;">'
        '<input type="submit" value="Run tamper demonstration">'
        "</form>"
        f"{tamper_section}"
    )

    return (
        f"<h2>Notice Chain — {_e(n)} receipt{'s' if n != 1 else ''}.</h2>"
        f"{receipts_html}"
        "<hr>"
        "<h3>Verify Chain Integrity</h3>"
        f"{verify_form}"
        f"{tamper_form}"
    )


# ===========================================================================
# The Vault render functions
# ===========================================================================


def render_bundle(lock_record: "SealedMandate", papers: "list[tuple[str, str]]") -> str:
    """Render The Bundle room body (GET /vault): the sealed estate file."""
    content = lock_record.content
    rows = "".join(
        f'<tr><td>{_e(path)}</td><td><span class="hash paper-seal">{_e(seal)}</span></td></tr>'
        for path, seal in papers
    )
    table = (
        '<table class="fact-table">'
        "<thead><tr><th>Paper</th><th>Seal (SHA-256)</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    )
    return (
        "<h2>The Bundle</h2>"
        "<p>The whole estate file, sealed at intake as one bundle under a single "
        "chain certificate. Each paper's seal is the SHA-256 of its bytes; the "
        "certificate is the SHA-256 of this table.</p>"
        "<hr>"
        '<div class="source-card">'
        f"<h3>{_e(content['bundle_id'])}</h3>"
        f'<p class="ghost">Lock record \u00b7 {_e(len(papers))} papers</p>'
        f'<p>Bundle certificate: <span class="hash certificate">{_e(content["certificate"])}</span></p>'
        f'<p>Lock record seal: <span class="hash lock-seal">{_e(lock_record.seal)}</span></p>'
        f"{table}"
        "</div>"
    )


def render_release_stamp(receipt: "Receipt") -> str:
    """Render the release stamp for an issued receipt.

    Everything shown is read from the receipt the gate issued: its verdict and
    its measurements.  Nothing is decided here.
    """
    verdict = receipt.verdict
    obs = receipt.measurements or {}
    certificate = obs.get("certificate")
    cert_html = (
        f'<p>Measured against certificate: <span class="hash certificate">{_e(certificate)}</span></p>'
        if certificate else ""
    )
    if verdict.get("type") == "pass":
        return (
            '<div class="release-stamp">'
            '<p class="verdict-pass">PASS</p>'
            "<p>The bundle may leave the house.</p>"
            f"{cert_html}"
            f"<p><small>Papers verified: {_e(obs.get('file_count', ''))}</small></p>"
            "</div>"
        )
    name = _e(verdict.get("name", "unknown"))
    path_html = (
        f'<p>Paper: <span class="hash paper-path">{_e(obs["path"])}</span></p>'
        if "path" in obs else ""
    )
    return (
        '<div class="release-stamp">'
        f'<p class="verdict-refused">REFUSED \u00b7 {name}</p>'
        f"{path_html}"
        f"{cert_html}"
        "<p>The bundle is held.</p>"
        "</div>"
    )


def _render_vault_preset_block(
    defn: dict,
    resolved: bool = False,
    result_html: str = "",
) -> str:
    label = _e(defn["label"])
    result_section = f'<div class="verdict-result">{result_html}</div>' if result_html else ""
    ghost_class = "resolved" if resolved else "ghost"
    return (
        '<div class="preset-block">'
        f'<div class="claim-block {ghost_class}">'
        f'<p><span class="preset-label">{label}</span>{_e(defn["description"])}</p>'
        f"<p><small>Presented: {_e(defn['situation'])} \u00b7 Expected: {_e(defn['expected_verdict'])}</small></p>"
        '<form method="post" action="/vault/preset" style="margin-top:0.75rem;">'
        f'<input type="hidden" name="preset" value="{label}">'
        f'<input type="submit" value="Run {label}">'
        "</form>"
        "</div>"
        f"{result_section}"
        "</div>"
    )


def render_vault_desk(scenario_defs: list[dict]) -> str:
    """Render the Release Desk body (GET /vault/desk)."""
    return render_vault_desk_with_result(scenario_defs, None, None, None, False)


def render_vault_desk_with_result(
    scenario_defs: list[dict],
    label: "str | None",
    verdict: object,
    receipt: "Receipt | None",
    tamper_error: bool,
) -> str:
    """Release Desk body, with the result injected after the matching preset."""
    result_html = ""
    if label is not None:
        if tamper_error:
            result_html = (
                '<div class="seal-broken-notice">'
                '<p><span class="verdict-refused">REFUSED \u00b7 seal_broken</span></p>'
                "<p>Lock record verification failed. This event was not recorded in the vault chain.</p>"
                "</div>"
            )
        elif receipt is not None:
            result_html = render_release_stamp(receipt) + render_receipt(receipt)
        else:
            result_html = '<p class="ghost">No result.</p>'

    blocks = "".join(
        _render_vault_preset_block(d, resolved=True, result_html=result_html)
        if d["label"] == label else _render_vault_preset_block(d)
        for d in scenario_defs
    )
    return (
        "<h2>The Release Desk</h2>"
        "<p>Six bundles presented for release, each re-measured against the lock record.</p>"
        "<hr>"
        f"{blocks}"
    )


def render_vault_archive(
    chain: "list[Receipt]",
    replay_result: "ReplayResult | None" = None,
    tamper_result: "ReplayResult | None" = None,
    tamper_demo_ran: bool = False,
) -> str:
    """Render the Vault Archive body (GET /vault/archive)."""
    n = len(chain)
    receipts_html = "".join(
        f'<div class="receipt-card"><p class="receipt-index">Receipt #{i + 1}</p>'
        f"{render_receipt(r)}</div>"
        for i, r in enumerate(chain)
    ) or '<p class="ghost">No receipts in the vault chain yet.</p>'

    replay_section = ""
    if replay_result is not None:
        if replay_result.ok:
            ok_text = f"Chain intact \u2014 {n} receipt{'s' if n != 1 else ''} verified."
            replay_section = f'<div class="chain-ok">{_e(ok_text)}</div>'
        else:
            replay_section = (
                '<div class="chain-fail">'
                f"<p>Chain verification FAILED at receipt index {_e(replay_result.failure_index)}.</p>"
                f"<p>Reason: {_e(replay_result.failure_reason)}</p>"
                "</div>"
            )
    verify_form = (
        '<form method="post" action="/vault/archive/verify" style="margin-top:1rem;">'
        '<input type="submit" value="Verify chain integrity">'
        "</form>"
        f"{replay_section}"
    )

    tamper_section = ""
    if tamper_demo_ran and tamper_result is not None:
        if tamper_result.ok:
            tamper_section = (
                '<div class="tamper-demo-result">'
                '<div class="chain-ok">Chain intact (no receipts to tamper \u2014 chain is empty).</div>'
                '<p class="not-modified-notice">The vault chain was not modified.</p>'
                "</div>"
            )
        else:
            tamper_section = (
                '<div class="tamper-demo-result chain-fail">'
                f"<p>Tamper demonstration: chain verification FAILED at receipt index {_e(tamper_result.failure_index)}.</p>"
                f"<p>Reason: {_e(tamper_result.failure_reason)}</p>"
                '<p class="not-modified-notice">The vault chain was not modified.</p>'
                "</div>"
            )
    tamper_form = (
        "<hr>"
        "<h3>Tamper Demonstration</h3>"
        "<p>Runs verify_chain on a deep copy of the vault chain with one receipt mutated. "
        "The vault chain itself is never modified by this demonstration.</p>"
        '<form method="post" action="/vault/archive/tamper" style="margin-top:0.5rem;">'
        '<input type="submit" value="Run tamper demonstration">'
        "</form>"
        f"{tamper_section}"
    )
    return (
        f"<h2>Vault Chain \u2014 {_e(n)} receipt{'s' if n != 1 else ''}.</h2>"
        f"{receipts_html}"
        "<hr>"
        "<h3>Verify Chain Integrity</h3>"
        f"{verify_form}"
        f"{tamper_form}"
    )
