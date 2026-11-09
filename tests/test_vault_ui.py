"""
tests.test_vault_ui
~~~~~~~~~~~~~~~~~~~
Unit tests for The Vault web skin (webui/).

Tests cover:
1. Render functions: Bundle, Release Desk, Vault Archive, shell and nav.
2. Preset verdicts B1-B6, in parity with vault/scenarios.py.
3. Tamper display: hard tamper surfaces as REFUSED · seal_broken, HTTP 200,
   nothing recorded.
4. Chain behaviour: append-only, own chain, verify, tamper demo on a copy.
5. Escaping, routes, the other desks unaffected, CSS audit, no JavaScript.

Stamps and certificates are read from the rendered stamps/spans of the page
(not from the static "Expected:" captions on the preset blocks), and the
certificate is compared with the real lock record and with
vault.scenarios.run_scenarios().

All tests use the real gate_core and vault libraries. No mocking of gate logic.
"""

from __future__ import annotations

import pathlib
import re
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"

PAPERS = ["death_record.json", "family_record.json", "inventory.json", "will_2024.json"]


def _make_vault_register():
    from webui.state import VaultRegister
    return VaultRegister(str(FIXTURES))


def _make_house_register():
    from webui.state import HouseRegister
    return HouseRegister(
        will_paths=[str(FIXTURES / "will_2019.json"), str(FIXTURES / "will_2024.json")],
        death_record_paths=[str(FIXTURES / "death_record.json")],
    )


def _make_notices_register():
    from webui.state import NoticesRegister
    return NoticesRegister(
        death_record_path=str(FIXTURES / "death_record.json"),
        will_path=str(FIXTURES / "will_2024.json"),
        family_record_path=str(FIXTURES / "family_record.json"),
    )


def _tamper_lock(register) -> None:
    """Alter the lock record content after sealing, breaking its seal."""
    register._lock_record.content["files"]["inventory.json"] = "0" * 64


def _body(html: str) -> str:
    """The page body only (the stylesheet also names these classes)."""
    i = html.find("<body>")
    return html if i < 0 else html[i:]


def _stamps(html: str) -> list[str]:
    """Text of every rendered release stamp, e.g. 'PASS' / 'REFUSED · file_changed'."""
    return re.findall(r'<div class="release-stamp"><p class="verdict-[a-z]+">([^<]*)</p>', _body(html))


def _certificates(html: str) -> list[str]:
    return re.findall(r'<span class="hash certificate">([0-9a-f]+)</span>', _body(html))


def _paper_paths(html: str) -> list[str]:
    return re.findall(r'<span class="hash paper-path">([^<]*)</span>', _body(html))


def _paper_seals(html: str) -> list[str]:
    return re.findall(r'<span class="hash paper-seal">([0-9a-f]+)</span>', _body(html))


def _scenario_results() -> dict:
    import vault
    return {r.label: r for r in vault.run_scenarios()}


# ---------------------------------------------------------------------------
# Helper: start a test server on an ephemeral port
# ---------------------------------------------------------------------------

class _TestServer:
    """Context manager that starts the HouseHandler on a random port."""

    def __init__(self):
        self.register = _make_house_register()
        self.notices_register = _make_notices_register()
        self.vault_register = _make_vault_register()
        self.port = None
        self._server = None
        self._thread = None

    def __enter__(self):
        from webui.server import HouseHandler
        HouseHandler.register = self.register
        HouseHandler.notices_register = self.notices_register
        HouseHandler.vault_register = self.vault_register
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), HouseHandler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def get(self, path: str) -> tuple[int, str]:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as resp:
            return resp.status, resp.read().decode("utf-8")

    def post(self, path: str, data: dict) -> tuple[int, str]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=urllib.parse.urlencode(data).encode("utf-8"),
            method="POST",
        )
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")


def _status_of(fn, *args):
    try:
        return fn(*args)[0]
    except urllib.error.HTTPError as exc:
        return exc.code


# ---------------------------------------------------------------------------
# 1. Render functions
# ---------------------------------------------------------------------------

class TestRenderVault(unittest.TestCase):
    def setUp(self):
        from webui import render
        from webui.state import VAULT_SCENARIO_DEFINITIONS
        self.render = render
        self.defs = VAULT_SCENARIO_DEFINITIONS
        self.reg = _make_vault_register()

    def test_bundle_shows_real_certificate_lock_seal_and_four_papers(self):
        html = self.render.render_bundle(self.reg.lock_record, self.reg.papers())
        lock = self.reg.lock_record
        self.assertEqual(_certificates(html), [lock.content["certificate"]])
        self.assertIn(lock.seal, html)
        self.assertEqual(_paper_seals(html), [lock.content["files"][p] for p in PAPERS])
        for p in PAPERS:
            self.assertIn(f"<td>{p}</td>", html)

    def test_bundle_papers_in_canonical_order(self):
        html = self.render.render_bundle(self.reg.lock_record, self.reg.papers())
        paths = re.findall(r"<td>([a-z_0-9]+\.json)</td>", html)
        self.assertEqual(paths, sorted(paths))

    def test_bundle_has_no_forms_or_buttons(self):
        html = self.render.render_bundle(self.reg.lock_record, self.reg.papers())
        self.assertNotIn("<form", html)
        self.assertNotIn("<button", html)

    def test_desk_contains_all_six_labels_in_order(self):
        html = self.render.render_vault_desk(self.defs)
        labels = re.findall(r'<span class="preset-label">(B\d)</span>', html)
        self.assertEqual(labels, ["B1", "B2", "B3", "B4", "B5", "B6"])

    def test_desk_without_result_has_no_stamps(self):
        html = self.render.render_vault_desk(self.defs)
        self.assertEqual(_stamps(html), [])

    def test_desk_forms_post_to_vault_preset(self):
        html = self.render.render_vault_desk(self.defs)
        self.assertEqual(html.count('action="/vault/preset"'), 6)
        for n in range(1, 7):
            self.assertIn(f'name="preset" value="B{n}"', html)

    def test_archive_empty(self):
        html = self.render.render_vault_archive([])
        self.assertIn("Vault Chain", html)
        self.assertIn("0 receipts", html)
        self.assertIn("No receipts in the vault chain yet.", html)

    def test_archive_shows_own_and_previous_hashes(self):
        self.reg.adjudicate_preset("B1")
        self.reg.adjudicate_preset("B2")
        chain = self.reg.chain_snapshot()
        html = self.render.render_vault_archive(chain)
        for r in chain:
            self.assertIn(r.own_hash, html)
            self.assertIn(r.previous_hash, html)

    def test_vault_shell_title_line_and_nav(self):
        html = self.render.vault_page_shell("t", "<p>x</p>")
        self.assertIn("<h1>The Vault</h1>", html)
        self.assertIn("Nothing leaves this house unmeasured \u2014 not even the records.", html)
        for href in ("/", "/desk", "/archive", "/notices/sources", "/notices",
                     "/notices/archive", "/vault", "/vault/desk", "/vault/archive"):
            self.assertIn(f'href="{href}"', html)

    def test_other_shells_link_the_vault(self):
        for html in (self.render.page_shell("t", ""), self.render.notices_page_shell("t", "")):
            for href in ("/vault", "/vault/desk", "/vault/archive"):
                self.assertIn(f'href="{href}"', html)

    def test_nav_groups_three_desks(self):
        html = self.render.vault_page_shell("t", "")
        self.assertEqual(html.count('class="nav-group"'), 3)
        self.assertEqual(html.count('class="nav-separator"'), 2)

    def test_release_stamp_is_rendered_from_the_receipt(self):
        self.reg.adjudicate_preset("B3")
        receipt = self.reg.chain_snapshot()[0]
        html = self.render.render_release_stamp(receipt)
        self.assertIn("REFUSED \u00b7 file_added", html)
        self.assertIn("stray_note.txt", html)
        self.assertIn(receipt.measurements["certificate"], html)


# ---------------------------------------------------------------------------
# 2. Preset verdicts, in parity with vault/scenarios.py
# ---------------------------------------------------------------------------

class TestVaultPresetVerdicts(unittest.TestCase):
    def setUp(self):
        self.reg = _make_vault_register()

    def test_B1_pass(self):
        verdict, receipt, tamper = self.reg.adjudicate_preset("B1")
        self.assertFalse(tamper)
        self.assertEqual(receipt.verdict, {"type": "pass"})
        self.assertEqual(receipt.measurements["file_count"], 4)
        self.assertEqual(receipt.measurements["files_verified"], PAPERS)

    def test_B2_file_changed_names_inventory(self):
        _v, receipt, _t = self.reg.adjudicate_preset("B2")
        self.assertEqual(receipt.verdict, {"type": "refused", "name": "file_changed"})
        self.assertEqual(receipt.measurements["path"], "inventory.json")

    def test_B3_file_added_names_stray_paper(self):
        _v, receipt, _t = self.reg.adjudicate_preset("B3")
        self.assertEqual(receipt.verdict, {"type": "refused", "name": "file_added"})
        self.assertEqual(receipt.measurements["path"], "stray_note.txt")

    def test_B4_file_missing_names_death_record(self):
        _v, receipt, _t = self.reg.adjudicate_preset("B4")
        self.assertEqual(receipt.verdict, {"type": "refused", "name": "file_missing"})
        self.assertEqual(receipt.measurements["path"], "death_record.json")

    def test_B5_pass_under_original_certificate(self):
        original = self.reg.lock_record.content["certificate"]
        _v, receipt, _t = self.reg.adjudicate_preset("B5")
        self.assertEqual(receipt.verdict, {"type": "pass"})
        self.assertEqual(receipt.measurements["certificate"], original)

    def test_B6_hard_tamper_records_nothing(self):
        verdict, receipt, tamper = self.reg.adjudicate_preset("B6")
        self.assertTrue(tamper)
        self.assertIsNone(verdict)
        self.assertIsNone(receipt)
        self.assertEqual(self.reg.chain_snapshot(), [])

    def test_unknown_label_raises(self):
        with self.assertRaises(KeyError):
            self.reg.adjudicate_preset("B7")

    def test_parity_with_vault_scenarios(self):
        scen = _scenario_results()
        for label in ("B1", "B2", "B3", "B4", "B5", "B6"):
            reg = _make_vault_register()
            verdict, receipt, tamper = reg.adjudicate_preset(label)
            ref = scen[label]
            self.assertEqual(tamper, ref.tamper_error is not None, label)
            if tamper:
                self.assertIsNone(receipt, label)
                continue
            self.assertEqual(verdict, ref.verdict, label)
            self.assertEqual(receipt.verdict, ref.receipt.verdict, label)
            for key in ("certificate", "path", "changed", "missing", "added",
                        "expected_sha256", "found_sha256", "files_verified"):
                self.assertEqual(receipt.measurements.get(key),
                                 ref.receipt.measurements.get(key), (label, key))

    def test_certificate_equals_scenarios_certificate(self):
        scen = _scenario_results()
        self.assertEqual(self.reg.lock_record.content["certificate"], scen["B1"].certificate)

    def test_expected_captions_match_issued_verdicts(self):
        from webui.state import VAULT_SCENARIO_DEFINITIONS
        for defn in VAULT_SCENARIO_DEFINITIONS:
            reg = _make_vault_register()
            _v, receipt, tamper = reg.adjudicate_preset(defn["label"])
            if tamper:
                shown = "REFUSED \u00b7 seal_broken"
            elif receipt.verdict["type"] == "pass":
                shown = "PASS"
            else:
                shown = "REFUSED \u00b7 " + receipt.verdict["name"]
            self.assertEqual(shown, defn["expected_verdict"], defn["label"])


# ---------------------------------------------------------------------------
# 3. Tamper display
# ---------------------------------------------------------------------------

class TestVaultTamperDisplay(unittest.TestCase):
    def test_register_with_altered_lock_reports_tamper_for_every_preset(self):
        for label in ("B1", "B2", "B3", "B4", "B5", "B6"):
            reg = _make_vault_register()
            _tamper_lock(reg)
            verdict, receipt, tamper = reg.adjudicate_preset(label)
            self.assertTrue(tamper, label)
            self.assertIsNone(receipt, label)
            self.assertEqual(reg.chain_snapshot(), [], label)

    def test_render_tamper_shows_refusal_and_no_stamp(self):
        from webui import render
        from webui.state import VAULT_SCENARIO_DEFINITIONS
        html = render.render_vault_desk_with_result(
            VAULT_SCENARIO_DEFINITIONS, "B6", None, None, True)
        self.assertIn("seal-broken-notice", _body(html))
        self.assertIn("REFUSED \u00b7 seal_broken", _body(html))
        self.assertIn("This event was not recorded in the vault chain.", html)
        self.assertEqual(_stamps(html), [])
        self.assertNotIn("own_hash", _body(html))

    def test_http_B6_returns_200_seal_broken_and_records_nothing(self):
        with _TestServer() as srv:
            status, body = srv.post("/vault/preset", {"preset": "B6"})
            self.assertEqual(status, 200)
            self.assertIn("REFUSED \u00b7 seal_broken", _body(body))
            self.assertEqual(_stamps(body), [])
            self.assertEqual(_certificates(body), [])
            self.assertEqual(srv.vault_register.chain_snapshot(), [])
            _s, archive = srv.get("/vault/archive")
            self.assertIn("Vault Chain \u2014 0 receipts", archive)

    def test_http_altered_register_lock_returns_200_seal_broken(self):
        with _TestServer() as srv:
            _tamper_lock(srv.vault_register)
            status, body = srv.post("/vault/preset", {"preset": "B1"})
            self.assertEqual(status, 200)
            self.assertIn("REFUSED \u00b7 seal_broken", _body(body))
            self.assertEqual(_stamps(body), [])
            self.assertEqual(srv.vault_register.chain_snapshot(), [])

    def test_tamper_does_not_disturb_earlier_chain(self):
        with _TestServer() as srv:
            srv.post("/vault/preset", {"preset": "B1"})
            srv.post("/vault/preset", {"preset": "B6"})
            chain = srv.vault_register.chain_snapshot()
            self.assertEqual(len(chain), 1)
            self.assertTrue(srv.vault_register.verify_vault_chain().ok)


# ---------------------------------------------------------------------------
# 4. Chain behaviour
# ---------------------------------------------------------------------------

class TestVaultChain(unittest.TestCase):
    def setUp(self):
        self.reg = _make_vault_register()

    def test_chain_grows_one_receipt_per_preset_but_not_on_tamper(self):
        for i, label in enumerate(("B1", "B2", "B3", "B4", "B5"), start=1):
            self.reg.adjudicate_preset(label)
            self.assertEqual(len(self.reg.chain_snapshot()), i)
        self.reg.adjudicate_preset("B6")
        self.assertEqual(len(self.reg.chain_snapshot()), 5)

    def test_receipts_are_hash_linked(self):
        for label in ("B1", "B2", "B5"):
            self.reg.adjudicate_preset(label)
        chain = self.reg.chain_snapshot()
        self.assertEqual(chain[0].previous_hash, "0" * 64)
        for prev, cur in zip(chain, chain[1:]):
            self.assertEqual(cur.previous_hash, prev.own_hash)
        self.assertTrue(self.reg.verify_vault_chain().ok)

    def test_refusals_do_not_alter_the_lock_record(self):
        before = (self.reg.lock_record.seal, self.reg.lock_record.content["certificate"])
        for label in ("B2", "B3", "B4", "B6"):
            self.reg.adjudicate_preset(label)
        after = (self.reg.lock_record.seal, self.reg.lock_record.content["certificate"])
        self.assertEqual(before, after)

    def test_chain_snapshot_is_a_copy(self):
        self.reg.adjudicate_preset("B1")
        snap = self.reg.chain_snapshot()
        snap.clear()
        self.assertEqual(len(self.reg.chain_snapshot()), 1)

    def test_tamper_demo_empty_chain_ok(self):
        self.assertTrue(self.reg.tamper_demo().ok)

    def test_tamper_demo_reports_hash_mismatch_and_leaves_chain(self):
        self.reg.adjudicate_preset("B1")
        self.reg.adjudicate_preset("B2")
        before = self.reg.chain_snapshot()
        result = self.reg.tamper_demo()
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_reason, "hash_mismatch")
        self.assertEqual(result.failure_index, 1)
        self.assertEqual(self.reg.chain_snapshot(), before)
        self.assertTrue(self.reg.verify_vault_chain().ok)

    def test_b5_after_b4_on_one_chain_both_verify(self):
        self.reg.adjudicate_preset("B4")
        self.reg.adjudicate_preset("B5")
        chain = self.reg.chain_snapshot()
        self.assertEqual([r.verdict.get("name", "pass") for r in chain], ["file_missing", "pass"])
        self.assertTrue(self.reg.verify_vault_chain().ok)


# ---------------------------------------------------------------------------
# 5. Escaping
# ---------------------------------------------------------------------------

class TestVaultEscaping(unittest.TestCase):
    def test_render_escapes_paper_names_and_ids(self):
        from webui import render
        from gate_core import seal_mandate
        evil = "<script>alert(1)</script>"
        lock = seal_mandate("vault", {
            "kind": "bundle_lock", "bundle_id": evil,
            "files": {evil: "ab" * 32}, "certificate": "cd" * 32})
        html = render.render_bundle(lock, [(evil, "ab" * 32)])
        self.assertNotIn(evil, html)
        self.assertIn("&lt;script&gt;", html)

    def test_stamp_escapes_named_paper(self):
        from webui import render
        from gate_core import Receipt
        evil = "<b>x</b>"
        receipt = Receipt(
            claim={}, measurements={"path": evil, "certificate": "ab" * 32},
            measurement_error=None, verdict={"type": "refused", "name": "file_added"},
            timestamp_utc="t", previous_hash="0" * 64, own_hash="1" * 64)
        html = render.render_release_stamp(receipt)
        self.assertNotIn(evil, html)
        self.assertIn("&lt;b&gt;", html)

    def test_http_post_unknown_preset_escaped_in_400(self):
        with _TestServer() as srv:
            try:
                srv.post("/vault/preset", {"preset": "<i>B9</i>"})
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8")
                self.assertEqual(exc.code, 400)
                self.assertNotIn("<i>B9</i>", body)


# ---------------------------------------------------------------------------
# 6. Routes over a real HTTP server
# ---------------------------------------------------------------------------

class TestVaultRoutes(unittest.TestCase):
    def test_get_bundle_200_with_live_certificate(self):
        with _TestServer() as srv:
            status, body = srv.get("/vault")
            self.assertEqual(status, 200)
            self.assertIn("The Vault", body)
            self.assertEqual(_certificates(body),
                             [srv.vault_register.lock_record.content["certificate"]])
            self.assertEqual(len(_paper_seals(body)), 4)

    def test_get_desk_200(self):
        with _TestServer() as srv:
            status, body = srv.get("/vault/desk")
            self.assertEqual(status, 200)
            self.assertEqual(_stamps(body), [])

    def test_get_archive_200_empty(self):
        with _TestServer() as srv:
            status, body = srv.get("/vault/archive")
            self.assertEqual(status, 200)
            self.assertIn("Vault Chain \u2014 0 receipts", body)

    def test_every_vault_room_has_title_and_line(self):
        with _TestServer() as srv:
            pages = [srv.get(p)[1] for p in ("/vault", "/vault/desk", "/vault/archive")]
            pages.append(srv.post("/vault/preset", {"preset": "B1"})[1])
            for body in pages:
                self.assertIn("<h1>The Vault</h1>", body)
                self.assertIn("Nothing leaves this house unmeasured \u2014 not even the records.", body)

    def test_post_B1_pass_stamp_and_live_certificate(self):
        with _TestServer() as srv:
            status, body = srv.post("/vault/preset", {"preset": "B1"})
            self.assertEqual(status, 200)
            self.assertEqual(_stamps(body), ["PASS"])
            self.assertEqual(_certificates(body)[0],
                             srv.vault_register.lock_record.content["certificate"])
            self.assertIn("The bundle may leave the house.", body)

    def test_post_refusals_stamped_and_naming_the_paper(self):
        expected = {
            "B2": ("REFUSED \u00b7 file_changed", "inventory.json"),
            "B3": ("REFUSED \u00b7 file_added", "stray_note.txt"),
            "B4": ("REFUSED \u00b7 file_missing", "death_record.json"),
        }
        with _TestServer() as srv:
            for label, (stamp, path) in expected.items():
                _s, body = srv.post("/vault/preset", {"preset": label})
                self.assertEqual(_stamps(body), [stamp], label)
                self.assertEqual(_paper_paths(body), [path], label)
                self.assertIn("The bundle is held.", body)

    def test_post_B5_pass_under_original_certificate(self):
        with _TestServer() as srv:
            original = srv.vault_register.lock_record.content["certificate"]
            srv.post("/vault/preset", {"preset": "B4"})
            _s, body = srv.post("/vault/preset", {"preset": "B5"})
            self.assertEqual(_stamps(body), ["PASS"])
            self.assertEqual(_certificates(body)[0], original)

    def test_stamp_follows_the_gate_not_the_caption(self):
        # With the caption saying B1 expects PASS, an altered paper on the
        # register's side must still produce what the gate issued.
        with _TestServer() as srv:
            real = srv.vault_register.adjudicate_preset
            _v, r, _t = real("B2")
            _s, body = srv.post("/vault/preset", {"preset": "B2"})
            self.assertEqual(_stamps(body), ["REFUSED \u00b7 " + r.verdict["name"]])
            self.assertNotIn("PASS", _stamps(body))

    def test_preset_result_resolves_only_the_matched_block(self):
        with _TestServer() as srv:
            _s, body = srv.post("/vault/preset", {"preset": "B3"})
            self.assertEqual(_body(body).count("claim-block resolved"), 1)
            self.assertEqual(_body(body).count("claim-block ghost"), 5)

    def test_result_includes_full_receipt(self):
        with _TestServer() as srv:
            _s, body = srv.post("/vault/preset", {"preset": "B1"})
            receipt = srv.vault_register.chain_snapshot()[0]
            self.assertIn(receipt.own_hash, body)
            self.assertIn(receipt.previous_hash, body)

    def test_post_preset_unknown_and_missing_are_400(self):
        with _TestServer() as srv:
            self.assertEqual(_status_of(srv.post, "/vault/preset", {"preset": "B9"}), 400)
            self.assertEqual(_status_of(srv.post, "/vault/preset", {}), 400)

    def test_archive_shows_receipts_after_presets(self):
        with _TestServer() as srv:
            srv.post("/vault/preset", {"preset": "B1"})
            srv.post("/vault/preset", {"preset": "B2"})
            _s, body = srv.get("/vault/archive")
            self.assertIn("Vault Chain \u2014 2 receipts", body)
            for r in srv.vault_register.chain_snapshot():
                self.assertIn(r.own_hash, body)

    def test_archive_verify_chain_intact(self):
        with _TestServer() as srv:
            srv.post("/vault/preset", {"preset": "B1"})
            _s, body = srv.post("/vault/archive/verify", {})
            self.assertIn("Chain intact \u2014 1 receipt verified.", body)

    def test_archive_tamper_failure_shown_and_chain_unmodified(self):
        with _TestServer() as srv:
            srv.post("/vault/preset", {"preset": "B1"})
            before = srv.vault_register.chain_snapshot()
            _s, body = srv.post("/vault/archive/tamper", {})
            self.assertIn("chain verification FAILED at receipt index 0", body)
            self.assertIn("hash_mismatch", body)
            self.assertIn("The vault chain was not modified.", body)
            self.assertEqual(srv.vault_register.chain_snapshot(), before)

    def test_unknown_vault_path_404(self):
        with _TestServer() as srv:
            self.assertEqual(_status_of(srv.get, "/vault/nowhere"), 404)

    def test_vault_chain_is_separate_from_other_chains(self):
        with _TestServer() as srv:
            srv.post("/adjudicate", {"preset": "A"})
            srv.post("/notices/preset", {"preset": "N1"})
            srv.post("/vault/preset", {"preset": "B1"})
            self.assertEqual(len(srv.register.chain_snapshot()), 1)
            self.assertEqual(len(srv.notices_register.chain_snapshot()), 3)
            self.assertEqual(len(srv.vault_register.chain_snapshot()), 1)

    def test_existing_desks_unaffected(self):
        with _TestServer() as srv:
            for path in ("/", "/desk", "/archive", "/notices/sources", "/notices", "/notices/archive"):
                status, body = srv.get(path)
                self.assertEqual(status, 200, path)
                self.assertNotIn("<h1>The Vault</h1>", body)
            _s, body = srv.post("/adjudicate", {"preset": "A"})
            self.assertIn("PASS", body)

    def test_navigation_on_every_house_page(self):
        with _TestServer() as srv:
            for path in ("/", "/desk", "/notices", "/vault", "/vault/desk", "/vault/archive"):
                _s, body = srv.get(path)
                for href in ("/", "/desk", "/archive", "/notices/sources", "/notices",
                             "/notices/archive", "/vault", "/vault/desk", "/vault/archive"):
                    self.assertIn(f'href="{href}"', body, (path, href))

    def test_lazy_default_register_when_none_set(self):
        # A harness that sets only the estate and notices registers still
        # gets a working Vault (built on first use from the fixtures).
        from webui.server import HouseHandler
        saved = HouseHandler.vault_register
        HouseHandler.vault_register = None
        HouseHandler.register = _make_house_register()
        HouseHandler.notices_register = _make_notices_register()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), HouseHandler)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            url = f"http://127.0.0.1:{httpd.server_address[1]}/vault"
            with urllib.request.urlopen(url) as resp:
                body = resp.read().decode("utf-8")
            self.assertEqual(len(_paper_seals(body)), 4)
            self.assertIsNotNone(HouseHandler.vault_register)
        finally:
            httpd.shutdown()
            httpd.server_close()
            t.join(timeout=5)
            HouseHandler.vault_register = saved


# ---------------------------------------------------------------------------
# 7. CSS and no-JavaScript audit
# ---------------------------------------------------------------------------

class TestVaultCSS(unittest.TestCase):
    def _style(self, html: str) -> str:
        m = re.search(r"<style>(.*?)</style>", html, re.S)
        self.assertIsNotNone(m)
        return m.group(1)

    def _pages(self, srv):
        pages = [srv.get(p)[1] for p in ("/vault", "/vault/desk", "/vault/archive")]
        pages.append(srv.post("/vault/preset", {"preset": "B1"})[1])
        pages.append(srv.post("/vault/preset", {"preset": "B6"})[1])
        return pages

    def test_palette_and_typeface(self):
        with _TestServer() as srv:
            css = self._style(srv.get("/vault")[1])
        self.assertRegex(css, r"--paper:\s*#faf7f0")
        self.assertRegex(css, r"--ink:\s*#1a1714")
        self.assertRegex(css, r"--oxblood:\s*#7a2e2a")
        self.assertIn("Georgia", css)

    def test_no_animation_and_single_transition(self):
        with _TestServer() as srv:
            for html in self._pages(srv):
                css = self._style(html)
                self.assertNotIn("@keyframes", css)
                self.assertNotIn("animation:", css)
                self.assertEqual(css.count("transition:"), 1)
                m = re.search(r"([^{}]*)\{[^{}]*transition:([^;}]*)", css)
                self.assertIn(".claim-block", m.group(1))

    def test_no_javascript(self):
        with _TestServer() as srv:
            for html in self._pages(srv):
                low = html.lower()
                self.assertNotIn("<script", low)
                self.assertNotIn("onclick", low)
                self.assertNotIn("javascript:", low)


if __name__ == "__main__":
    unittest.main()
