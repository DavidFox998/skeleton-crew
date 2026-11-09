"""
webui.server
~~~~~~~~~~~~
ThreadingHTTPServer and HouseHandler for The Estate Desk and The Notices Desk.

Route dispatch lives here. No HTML generation, no gate logic.

Entry point:
    python -m webui.server           (port from env PORT or 8000)
    python run_webui.py [--port N]   (preferred entry with fixture paths)
"""

from __future__ import annotations

import os
import pathlib
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

from webui import render
from webui.state import NOTICES_SCENARIO_DEFINITIONS, SCENARIO_DEFINITIONS, HouseRegister, NoticesRegister

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class HouseHandler(BaseHTTPRequestHandler):
    """HTTP request handler for both desks (Estate and Notices).

    The class-level ``register`` and ``notices_register`` attributes must be
    set on the class before ``serve_forever()`` is called.  This is the standard http.server pattern
    for sharing state across per-request handler instances.
    """

    register: HouseRegister  # set on class before serve_forever()
    notices_register: NoticesRegister  # set on class before serve_forever()

    # ── Routing ───────────────────────────────────────────────────────────

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        try:
            match path:
                case "/":
                    self._get_register()
                case "/desk":
                    self._get_desk()
                case "/archive":
                    self._get_archive()
                case "/notices/sources":
                    self._get_notices_sources()
                case "/notices":
                    self._get_notices()
                case "/notices/archive":
                    self._get_notices_archive()
                case _:
                    self._send_404()
        except Exception:
            self._send_500()

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        try:
            match path:
                case "/adjudicate":
                    self._post_adjudicate()
                case "/desk/builder-rows":
                    self._post_builder_rows()
                case "/archive/verify":
                    self._post_archive_verify()
                case "/archive/tamper-demo":
                    self._post_tamper_demo()
                case "/notices/preset":
                    self._post_notices_preset()
                case "/notices/assertion":
                    self._post_notices_assertion()
                case "/notices/new-draft":
                    self._post_notices_new_draft()
                case "/notices/archive/verify":
                    self._post_notices_archive_verify()
                case "/notices/archive/tamper":
                    self._post_notices_archive_tamper()
                case _:
                    self._send_404()
        except Exception:
            self._send_500()

    # ── GET handlers ─────────────────────────────────────────────────────

    def _get_register(self) -> None:
        body = render.render_register(self.register.registry)
        self._send_html(render.page_shell("The Estate Desk", body))

    def _get_desk(self) -> None:
        body = render.render_desk(SCENARIO_DEFINITIONS, self.register.registry)
        self._send_html(render.page_shell("The Estate Desk — Desk", body))

    def _get_archive(self) -> None:
        chain = self.register.chain_snapshot()
        body = render.render_archive(chain)
        self._send_html(render.page_shell("The Estate Desk — Archive", body))

    # ── POST handlers ─────────────────────────────────────────────────────

    def _post_adjudicate(self) -> None:
        form = self._read_form()

        if form.get("builder") == ["1"]:
            # Free builder submission
            will_seal_list = form.get("will_seal", [])
            if not will_seal_list:
                self._send_400("Missing field: will_seal")
                return
            will_seal = will_seal_list[0]

            row_count_raw = form.get("row_count", ["1"])[0]
            try:
                row_count = int(row_count_raw)
            except ValueError:
                row_count = 1

            distributions: list[dict] = []
            for i in range(row_count):
                sign = (form.get(f"sign_{i}") or [""])[0]
                item = (form.get(f"item_{i}") or [""])[0]
                beneficiary = (form.get(f"beneficiary_{i}") or [""])[0]
                if sign or item or beneficiary:
                    distributions.append({
                        "sign": sign,
                        "item": item,
                        "beneficiary": beneficiary,
                    })

            try:
                verdict, receipt, tamper_error = self.register.adjudicate_custom(
                    will_seal, distributions
                )
            except ValueError as exc:
                self._send_400(str(exc))
                return

            body = render.render_desk_with_result(
                SCENARIO_DEFINITIONS,
                self.register.registry,
                "builder",
                verdict,
                receipt,
                tamper_error,
            )
            self._send_html(render.page_shell("The Estate Desk — Desk", body))

        else:
            # Preset submission
            preset_list = form.get("preset", [])
            if not preset_list:
                self._send_400("Missing field: preset")
                return
            label = preset_list[0]

            try:
                verdict, receipt, tamper_error = self.register.adjudicate_preset(label)
            except KeyError as exc:
                self._send_400(str(exc))
                return

            body = render.render_desk_with_result(
                SCENARIO_DEFINITIONS,
                self.register.registry,
                label,
                verdict,
                receipt,
                tamper_error,
            )
            self._send_html(render.page_shell("The Estate Desk — Desk", body))

    def _post_builder_rows(self) -> None:
        """Reload the builder form with a new row count."""
        form = self._read_form()
        will_seal_list = form.get("will_seal", [])
        selected_seal = will_seal_list[0] if will_seal_list else None

        row_count_raw = (form.get("row_count") or ["1"])[0]
        try:
            row_count = max(1, min(12, int(row_count_raw)))
        except ValueError:
            row_count = 1

        body = render.render_desk(SCENARIO_DEFINITIONS, self.register.registry)
        # Rebuild with the proper builder form (row count + will selection)
        blocks = ""
        for defn in SCENARIO_DEFINITIONS:
            blocks += render._render_preset_block(defn)

        builder = render.render_builder_form(
            self.register.registry,
            selected_will_seal=selected_seal,
            row_count=row_count,
        )
        body = (
            "<h2>The Desk — Adjudication Workbench</h2>"
            "<p>Seven preset claims in casework order, followed by the free builder.</p>"
            "<hr>"
            f"{blocks}"
            "<hr>"
            "<h2>Free Builder</h2>"
            f"{builder}"
        )
        self._send_html(render.page_shell("The Estate Desk — Desk", body))

    def _post_archive_verify(self) -> None:
        replay = self.register.verify_house_chain()
        chain = self.register.chain_snapshot()
        body = render.render_archive(chain, replay_result=replay)
        self._send_html(render.page_shell("The Estate Desk — Archive", body))

    def _post_tamper_demo(self) -> None:
        tamper = self.register.tamper_demo()
        chain = self.register.chain_snapshot()
        body = render.render_archive(chain, tamper_result=tamper, tamper_demo_ran=True)
        self._send_html(render.page_shell("The Estate Desk — Archive", body))

    # ── Notices Desk handlers ────────────────────────────────────────────

    def _get_notices_sources(self) -> None:
        body = render.render_sources(self.notices_register.source_registry)
        self._send_html(render.notices_page_shell("The Notices Desk — Sources", body))

    def _get_notices(self) -> None:
        nr = self.notices_register
        body = render.render_notices_desk(
            NOTICES_SCENARIO_DEFINITIONS,
            nr.source_registry,
            nr.working_draft,
            nr.working_draft_publish_state(),
        )
        self._send_html(render.notices_page_shell("The Notices Desk", body))

    def _get_notices_archive(self) -> None:
        chain = self.notices_register.chain_snapshot()
        body = render.render_notices_archive(chain)
        self._send_html(render.notices_page_shell("The Notices Desk — Notice Archive", body))

    def _post_notices_preset(self) -> None:
        form = self._read_form()
        preset_list = form.get("preset", [])
        if not preset_list:
            self._send_400("Missing field: preset")
            return
        label = preset_list[0]
        nr = self.notices_register
        try:
            entries, decisions, tamper_error = nr.adjudicate_preset(label)
        except KeyError as exc:
            self._send_400(str(exc))
            return
        body = render.render_notices_desk_with_preset_result(
            NOTICES_SCENARIO_DEFINITIONS,
            nr.source_registry,
            nr.working_draft,
            nr.working_draft_publish_state(),
            label,
            entries,
            decisions,
            tamper_error,
        )
        self._send_html(render.notices_page_shell("The Notices Desk", body))

    def _post_notices_assertion(self) -> None:
        form = self._read_form()
        sentence = (form.get("sentence") or [""])[0]
        fact_key = (form.get("fact_key") or [""])[0]
        value = (form.get("value") or [""])[0]
        citation_raw = (form.get("citation") or [""])[0]
        if not sentence or not fact_key:
            self._send_400("Missing field: sentence and fact_key are required")
            return
        citation = citation_raw if citation_raw else None
        nr = self.notices_register
        entry, _decision, tamper_error = nr.adjudicate_assertion(
            sentence, fact_key, value, citation
        )
        body = render.render_notices_desk_with_assertion_result(
            NOTICES_SCENARIO_DEFINITIONS,
            nr.source_registry,
            nr.working_draft,
            nr.working_draft_publish_state(),
            entry,
            tamper_error,
        )
        self._send_html(render.notices_page_shell("The Notices Desk", body))

    def _post_notices_new_draft(self) -> None:
        self.notices_register.new_draft()
        self._get_notices()

    def _post_notices_archive_verify(self) -> None:
        nr = self.notices_register
        replay = nr.verify_notices_chain()
        chain = nr.chain_snapshot()
        body = render.render_notices_archive(chain, replay_result=replay)
        self._send_html(render.notices_page_shell("The Notices Desk — Notice Archive", body))

    def _post_notices_archive_tamper(self) -> None:
        nr = self.notices_register
        tamper = nr.tamper_demo()
        chain = nr.chain_snapshot()
        body = render.render_notices_archive(chain, tamper_result=tamper, tamper_demo_ran=True)
        self._send_html(render.notices_page_shell("The Notices Desk — Notice Archive", body))

    # ── Utilities ─────────────────────────────────────────────────────────

    def _read_form(self) -> dict[str, list[str]]:
        """Read and parse a URL-encoded form body."""
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        return urllib.parse.parse_qs(raw, keep_blank_values=True)

    def _send_html(self, html: str, status: int = 200) -> None:
        """Encode HTML as UTF-8 and send with the given status."""
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_404(self) -> None:
        page = render.page_shell(
            "The Estate Desk — Not Found",
            "<h2>404 — Not Found</h2><p>The requested path does not exist.</p>",
        )
        self._send_html(page, status=404)

    def _send_400(self, detail: str = "") -> None:
        detail_html = render._e(detail)
        page = render.page_shell(
            "The Estate Desk — Bad Request",
            f"<h2>400 — Bad Request</h2><p>{detail_html}</p>",
        )
        self._send_html(page, status=400)

    def _send_500(self) -> None:
        traceback.print_exc(file=sys.stderr)
        page = render.page_shell(
            "The Estate Desk — Server Error",
            "<h2>500 — Internal Server Error</h2>"
            "<p>An unexpected error occurred. Details have been written to the server log.</p>",
        )
        self._send_html(page, status=500)

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: ANN001
        """Write access log to stderr (default behaviour, not suppressed)."""
        sys.stderr.write(f"{self.address_string()} - - [{self.log_date_time_string()}] {fmt % args}\n")


# Backward-compatible name: the estate routes are served by HouseHandler.
EstateHandler = HouseHandler


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------


def run(
    host: str = "127.0.0.1",
    port: int = 8000,
    register: HouseRegister | None = None,
    notices_register: NoticesRegister | None = None,
) -> None:
    """Start the ThreadingHTTPServer. Blocks until KeyboardInterrupt."""
    if register is not None:
        HouseHandler.register = register
    if notices_register is not None:
        HouseHandler.notices_register = notices_register
    elif not hasattr(HouseHandler, "notices_register"):
        HouseHandler.notices_register = _default_notices_register()

    with ThreadingHTTPServer((host, port), HouseHandler) as httpd:
        sys.stderr.write(f"The Estate Desk is open at http://{host}:{port}/\n")
        sys.stderr.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            sys.stderr.write("\nServer stopped.\n")


# ---------------------------------------------------------------------------
# __main__ entry point  (python -m webui.server)
# ---------------------------------------------------------------------------


def _default_register() -> HouseRegister:
    """Construct a HouseRegister from the standard fixture paths."""
    root = pathlib.Path(__file__).parent.parent
    fixtures = root / "fixtures"
    return HouseRegister(
        will_paths=[
            str(fixtures / "will_2019.json"),
            str(fixtures / "will_2024.json"),
        ],
        death_record_paths=[
            str(fixtures / "death_record.json"),
        ],
    )


def _default_notices_register() -> NoticesRegister:
    """Construct a NoticesRegister from the standard fixture paths."""
    root = pathlib.Path(__file__).parent.parent
    fixtures = root / "fixtures"
    return NoticesRegister(
        death_record_path=str(fixtures / "death_record.json"),
        will_path=str(fixtures / "will_2024.json"),
        family_record_path=str(fixtures / "family_record.json"),
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    register = _default_register()
    notices_register = _default_notices_register()
    HouseHandler.register = register
    HouseHandler.notices_register = notices_register
    run(host="127.0.0.1", port=port, register=register, notices_register=notices_register)
