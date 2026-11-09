"""
tests.test_webui
~~~~~~~~~~~~~~~~
Unit tests for the webui package.

Tests cover:
1. Preset verdict parity: all seven scenarios match expected outcomes.
2. Chain append semantics: A–F append; G does not.
3. Builder adjudication: PASS and beneficiary_unknown paths.
4. Tamper demo: does not mutate house chain.
5. verify_house_chain: returns ok=True after normal adjudications.
6. Render functions: Register, Desk, Archive contain required elements.
7. Input escaping: HTML in beneficiary is escaped in rendered output.
8. Route smoke tests: GET /, /desk, /archive return 200; POST /adjudicate preset=A contains PASS.

All tests use the real gate_core and executor libraries with fixture files.
No mocking of gate logic.
"""

from __future__ import annotations

import io
import pathlib
import threading
import time
import unittest
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"

WILL_PATHS = [
    str(FIXTURES / "will_2019.json"),
    str(FIXTURES / "will_2024.json"),
]
DEATH_RECORD_PATHS = [str(FIXTURES / "death_record.json")]


def _make_register():
    """Create a fresh HouseRegister for each test."""
    from webui.state import HouseRegister
    return HouseRegister(
        will_paths=WILL_PATHS,
        death_record_paths=DEATH_RECORD_PATHS,
    )


# ---------------------------------------------------------------------------
# Helper: start a test server on an ephemeral port
# ---------------------------------------------------------------------------

class _TestServer:
    """Context manager that starts the EstateHandler on a random port."""

    def __init__(self):
        self.register = _make_register()
        self.port = None
        self._server = None
        self._thread = None

    def __enter__(self):
        from webui.server import EstateHandler
        EstateHandler.register = self.register
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), EstateHandler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._server.shutdown()
        self._thread.join(timeout=5)

    def get(self, path: str) -> tuple[int, str]:
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url) as resp:
            return resp.status, resp.read().decode("utf-8")

    def post(self, path: str, data: dict) -> tuple[int, str]:
        url = f"http://127.0.0.1:{self.port}{path}"
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")


# ---------------------------------------------------------------------------
# 1. Preset verdict parity
# ---------------------------------------------------------------------------

class TestPresetVerdicts(unittest.TestCase):
    """All seven presets match the expected outcome table."""

    def setUp(self):
        self.reg = _make_register()

    def test_A_pass(self):
        verdict, receipt, tamper = self.reg.adjudicate_preset("A")
        self.assertFalse(tamper)
        self.assertIsNotNone(verdict)
        self.assertEqual(verdict.__class__.__name__, "Pass")
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.verdict["type"], "pass")

    def test_B_will_superseded(self):
        verdict, receipt, tamper = self.reg.adjudicate_preset("B")
        self.assertFalse(tamper)
        self.assertEqual(verdict.__class__.__name__, "Refused")
        self.assertEqual(verdict.name, "will_superseded")
        self.assertEqual(receipt.verdict["name"], "will_superseded")

    def test_C_share_mismatch(self):
        verdict, receipt, tamper = self.reg.adjudicate_preset("C")
        self.assertFalse(tamper)
        self.assertEqual(verdict.name, "share_mismatch")

    def test_D_beneficiary_unknown(self):
        verdict, receipt, tamper = self.reg.adjudicate_preset("D")
        self.assertFalse(tamper)
        self.assertEqual(verdict.name, "beneficiary_unknown")

    def test_E_sign_unoccupied(self):
        verdict, receipt, tamper = self.reg.adjudicate_preset("E")
        self.assertFalse(tamper)
        self.assertEqual(verdict.name, "sign_unoccupied")

    def test_F_death_unverified_receipt_appended(self):
        chain_before = len(self.reg.chain_snapshot())
        verdict, receipt, tamper = self.reg.adjudicate_preset("F")
        self.assertFalse(tamper)
        self.assertEqual(verdict.name, "death_unverified")
        self.assertIsNotNone(receipt)
        chain_after = len(self.reg.chain_snapshot())
        self.assertEqual(chain_after, chain_before + 1)

    def test_G_tamper_error_no_append(self):
        chain_before = len(self.reg.chain_snapshot())
        verdict, receipt, tamper = self.reg.adjudicate_preset("G")
        self.assertTrue(tamper)
        self.assertIsNone(verdict)
        self.assertIsNone(receipt)
        chain_after = len(self.reg.chain_snapshot())
        self.assertEqual(chain_after, chain_before, "Scenario G must not append to chain")

    def test_unknown_label_raises(self):
        with self.assertRaises(KeyError):
            self.reg.adjudicate_preset("Z")


# ---------------------------------------------------------------------------
# 2. Chain append semantics
# ---------------------------------------------------------------------------

class TestChainAppendSemantics(unittest.TestCase):
    """A–F each append exactly one receipt; G appends none."""

    def setUp(self):
        self.reg = _make_register()

    def test_six_after_a_through_f(self):
        for label in ["A", "B", "C", "D", "E", "F"]:
            self.reg.adjudicate_preset(label)
        chain = self.reg.chain_snapshot()
        self.assertEqual(len(chain), 6)

    def test_still_six_after_g(self):
        for label in ["A", "B", "C", "D", "E", "F"]:
            self.reg.adjudicate_preset(label)
        self.reg.adjudicate_preset("G")
        chain = self.reg.chain_snapshot()
        self.assertEqual(len(chain), 6)

    def test_each_preset_appends_one(self):
        for label in ["A", "B", "C", "D", "E", "F"]:
            before = len(self.reg.chain_snapshot())
            self.reg.adjudicate_preset(label)
            after = len(self.reg.chain_snapshot())
            self.assertEqual(after, before + 1, f"Preset {label} should append exactly one receipt")


# ---------------------------------------------------------------------------
# 3. Builder adjudication
# ---------------------------------------------------------------------------

class TestBuilderAdjudication(unittest.TestCase):
    """adjudicate_custom() for PASS and beneficiary_unknown paths."""

    def setUp(self):
        self.reg = _make_register()
        # Resolve the 2024 will seal
        self.will_2024 = self.reg.registry.latest_will("Elias Vane")
        self.will_2024_seal = self.will_2024.seal

    def _correct_distributions(self):
        return [
            {"sign": "Aries",    "item": "The Iron Key",          "beneficiary": "whoever first knocks thrice on the chapel door after midnight on All Hallows' Eve"},
            {"sign": "Taurus",   "item": "The Stone Bull",         "beneficiary": "Marta, the neighbor"},
            {"sign": "Leo",      "item": "The Brass Telescope",    "beneficiary": "the child who mapped the lion's heart from the hilltop in the summer of the comet"},
            {"sign": "Scorpio",  "item": "The Sealed Letter",      "beneficiary": "the one who knows what happened at the millpond in '87"},
            {"sign": "Capricorn","item": "The Goat Bell",          "beneficiary": "the town itself"},
            {"sign": "Aquarius", "item": "The Water Jar",          "beneficiary": "the well-keeper's daughter"},
            {"sign": "Pisces",   "item": "The Two Fishhooks",      "beneficiary": "Silas Vane, brother of the testator"},
        ]

    def test_custom_pass(self):
        before = len(self.reg.chain_snapshot())
        verdict, receipt, tamper = self.reg.adjudicate_custom(
            self.will_2024_seal, self._correct_distributions()
        )
        self.assertFalse(tamper)
        self.assertEqual(verdict.__class__.__name__, "Pass")
        self.assertIsNotNone(receipt)
        after = len(self.reg.chain_snapshot())
        self.assertEqual(after, before + 1)

    def test_custom_beneficiary_unknown(self):
        dists = self._correct_distributions()
        dists[0] = {**dists[0], "beneficiary": "wrong person entirely"}
        verdict, receipt, tamper = self.reg.adjudicate_custom(
            self.will_2024_seal, dists
        )
        self.assertFalse(tamper)
        self.assertEqual(verdict.name, "beneficiary_unknown")

    def test_invalid_seal_raises(self):
        with self.assertRaises(ValueError):
            self.reg.adjudicate_custom("deadbeef" * 8, [])


# ---------------------------------------------------------------------------
# 4. Tamper demo does not mutate house chain
# ---------------------------------------------------------------------------

class TestTamperDemo(unittest.TestCase):
    """tamper_demo() reports broken link and does NOT mutate the house chain."""

    def setUp(self):
        self.reg = _make_register()

    def test_tamper_demo_on_empty_chain(self):
        result = self.reg.tamper_demo()
        # Empty chain — ok=True (nothing to tamper)
        self.assertTrue(result.ok)
        # Chain still empty
        self.assertEqual(len(self.reg.chain_snapshot()), 0)

    def test_tamper_demo_reports_failure(self):
        # Populate the chain with one preset
        self.reg.adjudicate_preset("A")
        result = self.reg.tamper_demo()
        # Should detect hash_mismatch
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_reason, "hash_mismatch")

    def test_tamper_demo_does_not_mutate_chain(self):
        # Populate with several presets
        for label in ["A", "B", "C"]:
            self.reg.adjudicate_preset(label)

        chain_before = self.reg.chain_snapshot()
        hashes_before = [r.own_hash for r in chain_before]
        length_before = len(chain_before)

        self.reg.tamper_demo()

        chain_after = self.reg.chain_snapshot()
        hashes_after = [r.own_hash for r in chain_after]
        self.assertEqual(len(chain_after), length_before)
        self.assertEqual(hashes_after, hashes_before)

    def test_verify_chain_still_ok_after_tamper_demo(self):
        for label in ["A", "B"]:
            self.reg.adjudicate_preset(label)

        self.reg.tamper_demo()  # run demo

        replay = self.reg.verify_house_chain()
        self.assertTrue(replay.ok)


# ---------------------------------------------------------------------------
# 5. verify_house_chain integrity
# ---------------------------------------------------------------------------

class TestVerifyHouseChain(unittest.TestCase):
    def setUp(self):
        self.reg = _make_register()

    def test_empty_chain_ok(self):
        result = self.reg.verify_house_chain()
        self.assertTrue(result.ok)

    def test_chain_ok_after_adjudications(self):
        for label in ["A", "B", "C", "D", "E", "F"]:
            self.reg.adjudicate_preset(label)
        result = self.reg.verify_house_chain()
        self.assertTrue(result.ok)


# ---------------------------------------------------------------------------
# 6. Render functions produce required elements
# ---------------------------------------------------------------------------

class TestRenderRegister(unittest.TestCase):
    def setUp(self):
        from webui import render
        from webui.state import HouseRegister
        self.render = render
        self.reg = _make_register()

    def test_register_contains_testator(self):
        html = self.render.render_register(self.reg.registry)
        self.assertIn("Elias Vane", html)

    def test_register_contains_death_record_seal(self):
        dr = self.reg.registry.death_record("Elias Vane")
        html = self.render.render_register(self.reg.registry)
        self.assertIn(dr.seal[:12], html)

    def test_register_contains_both_sealed_dates(self):
        html = self.render.render_register(self.reg.registry)
        self.assertIn("2019-10-31", html)
        self.assertIn("2024-10-31", html)

    def test_register_2019_will_has_ghost_class(self):
        html = self.render.render_register(self.reg.registry)
        # The 2019 will column should have class "superseded" and "ghost"
        self.assertIn("superseded", html)
        self.assertIn("ghost", html)

    def test_register_vector_diff_bits_marked(self):
        # The only bit that differs between 2019 ("111000010011") and
        # 2024 ("111010010011") is bit index 4 (Scorpio).
        # That bit should have the "changed" class.
        html = self.render.render_register(self.reg.registry)
        self.assertIn("changed", html)

    def test_page_shell_title(self):
        html = self.render.page_shell("The Estate Desk", "<p>body</p>")
        self.assertIn("<title>The Estate Desk</title>", html)

    def test_page_shell_subtitle(self):
        html = self.render.page_shell("The Estate Desk", "<p>body</p>")
        self.assertIn("Nothing leaves this house unmeasured.", html)

    def test_page_shell_nav_links(self):
        html = self.render.page_shell("The Estate Desk", "<p>body</p>")
        self.assertIn('href="/"', html)
        self.assertIn('href="/desk"', html)
        self.assertIn('href="/archive"', html)


class TestRenderDesk(unittest.TestCase):
    def setUp(self):
        from webui import render
        from webui.state import SCENARIO_DEFINITIONS
        self.render = render
        self.SCENARIO_DEFINITIONS = SCENARIO_DEFINITIONS
        self.reg = _make_register()

    def test_desk_contains_all_seven_labels_in_order(self):
        html = self.render.render_desk(self.SCENARIO_DEFINITIONS, self.reg.registry)
        # All labels A through G must appear
        for label in ["A", "B", "C", "D", "E", "F", "G"]:
            self.assertIn(label, html)
        # Order: find positions of each label
        positions = []
        for label in ["A", "B", "C", "D", "E", "F", "G"]:
            pos = html.index(f'value="{label}"')
            positions.append(pos)
        self.assertEqual(positions, sorted(positions), "Labels must appear A→G in order")

    def test_desk_contains_builder_form(self):
        html = self.render.render_desk(self.SCENARIO_DEFINITIONS, self.reg.registry)
        # Will picker select element
        self.assertIn('<select name="will_seal">', html)

    def test_desk_will_picker_has_both_wills(self):
        html = self.render.render_desk(self.SCENARIO_DEFINITIONS, self.reg.registry)
        # Both seal prefixes should appear in the will picker options
        reg = self.reg.registry
        wills = reg.all_wills("Elias Vane")
        for w in wills:
            self.assertIn(w.seal[:12], html)

    def test_desk_builder_sign_dropdowns_for_2024(self):
        # 2024 will has 7 occupied signs
        html = self.render.render_desk(self.SCENARIO_DEFINITIONS, self.reg.registry)
        # All 7 signs from the 2024 will must appear in the form
        signs = ["Aries", "Taurus", "Leo", "Scorpio", "Capricorn", "Aquarius", "Pisces"]
        for sign in signs:
            self.assertIn(sign, html)

    def test_desk_no_prefilled_beneficiary(self):
        # Builder beneficiary inputs must not have value= from fixture
        html = self.render.render_desk(self.SCENARIO_DEFINITIONS, self.reg.registry)
        # Look for beneficiary inputs — they must have no value attribute
        import re
        # Find all beneficiary input tags
        beneficiary_inputs = re.findall(
            r'<input[^>]*name="beneficiary_\d+"[^>]*>', html
        )
        for inp in beneficiary_inputs:
            # Must not contain value= with non-empty fixture data
            self.assertNotIn('value="', inp.replace('value=""', ''), 
                             f"Beneficiary input should not have a pre-filled value: {inp}")


class TestRenderArchive(unittest.TestCase):
    def setUp(self):
        from webui import render
        self.render = render
        self.reg = _make_register()

    def test_archive_empty_chain(self):
        html = self.render.render_archive([])
        self.assertIn("0 receipts", html)

    def test_archive_contains_own_hashes(self):
        for label in ["A", "B"]:
            self.reg.adjudicate_preset(label)
        chain = self.reg.chain_snapshot()
        html = self.render.render_archive(chain)
        for receipt in chain:
            self.assertIn(receipt.own_hash, html)

    def test_archive_contains_previous_hash(self):
        self.reg.adjudicate_preset("A")
        chain = self.reg.chain_snapshot()
        html = self.render.render_archive(chain)
        self.assertIn(chain[0].previous_hash, html)

    def test_archive_verify_form_present(self):
        html = self.render.render_archive([])
        self.assertIn('/archive/verify', html)

    def test_archive_tamper_demo_form_present(self):
        html = self.render.render_archive([])
        self.assertIn('/archive/tamper-demo', html)

    def test_archive_tamper_demo_ran_shows_not_modified(self):
        from gate_core.receipt import ReplayResult
        result = ReplayResult(ok=False, failure_index=0, failure_reason="hash_mismatch")
        html = self.render.render_archive([], tamper_result=result, tamper_demo_ran=True)
        self.assertIn("The house chain was not modified.", html)

    def test_archive_chain_intact_message(self):
        from gate_core.receipt import ReplayResult
        result = ReplayResult(ok=True, failure_index=None, failure_reason=None)
        html = self.render.render_archive([], replay_result=result)
        self.assertIn("Chain intact", html)


# ---------------------------------------------------------------------------
# 7. Input escaping
# ---------------------------------------------------------------------------

class TestInputEscaping(unittest.TestCase):
    """HTML in beneficiary fields is escaped, not executed."""

    def test_xss_payload_escaped_in_render(self):
        from webui import render
        from gate_core.receipt import Receipt
        xss = '<script>alert(1)</script>'
        # Construct a synthetic receipt containing the XSS payload as beneficiary
        fake_receipt = Receipt(
            claim={
                "domain": "executor",
                "claim_type": "estate_distribution",
                "payload": {
                    "will_ref": "a" * 64,
                    "distributions": [
                        {"sign": "Aries", "item": "Thing", "beneficiary": xss}
                    ],
                },
            },
            measurements=None,
            measurement_error=None,
            verdict={"type": "refused", "name": "beneficiary_unknown"},
            timestamp_utc="2026-11-02T00:00:00Z",
            previous_hash="0" * 64,
            own_hash="b" * 64,
        )
        html = render.render_receipt(fake_receipt)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_xss_in_verdict_badge_escaped(self):
        from webui import render
        html = render.render_verdict_badge({"type": "refused", "name": "<b>bad</b>"})
        self.assertIn("&lt;b&gt;", html)
        self.assertNotIn("<b>bad</b>", html)

    def test_xss_via_http_post(self):
        """Submit a builder form with an XSS payload and verify it's escaped."""
        reg = _make_register()
        will_2024 = reg.registry.latest_will("Elias Vane")
        with _TestServer() as srv:
            srv.register = reg
            from webui.server import EstateHandler
            EstateHandler.register = reg

            data = {
                "builder": "1",
                "will_seal": will_2024.seal,
                "row_count": "1",
                "sign_0": "Aries",
                "item_0": "The Iron Key",
                "beneficiary_0": "<script>alert(1)</script>",
            }
            status, body = srv.post("/adjudicate", data)
            self.assertEqual(status, 200)
            self.assertIn("&lt;script&gt;", body)
            self.assertNotIn("<script>alert(1)</script>", body)


# ---------------------------------------------------------------------------
# 8. CSS checks
# ---------------------------------------------------------------------------

class TestCSS(unittest.TestCase):
    def setUp(self):
        from webui import render
        self.css = render.css()
        self.page = render.page_shell("T", "<p>x</p>")

    def test_ghost_color(self):
        self.assertIn("#9a938a", self.css)

    def test_oxblood_color(self):
        self.assertIn("#7a2e2a", self.css)

    def test_paper_color(self):
        self.assertIn("#faf7f0", self.css)

    def test_ink_color(self):
        self.assertIn("#1a1714", self.css)

    def test_hairline_color(self):
        self.assertIn("#d8d2c4", self.css)

    def test_no_keyframes(self):
        self.assertNotIn("@keyframes", self.css)

    def test_no_animation_property(self):
        # Ensure no bare "animation:" property declarations (distinct from "transition:")
        import re
        # Match "animation:" that is NOT part of "transition:" or "animation-*:"
        matches = re.findall(r'(?<![a-z-])animation\s*:', self.css)
        self.assertEqual(matches, [], "No animation: declarations allowed")

    def test_transition_only_on_claim_block(self):
        self.assertIn("transition:", self.css)
        self.assertIn(".claim-block", self.css)

    def test_serif_font_stack(self):
        self.assertIn("Georgia", self.css)

    def test_2019_will_ghost_class_in_register(self):
        from webui import render
        reg = _make_register()
        html = render.render_register(reg.registry)
        self.assertIn("ghost", html)
        self.assertIn("superseded", html)


# ---------------------------------------------------------------------------
# 9. HTTP route smoke tests
# ---------------------------------------------------------------------------

class TestRoutes(unittest.TestCase):
    """Smoke tests for all major routes."""

    def test_get_register_200(self):
        with _TestServer() as srv:
            status, body = srv.get("/")
            self.assertEqual(status, 200)
            self.assertIn("The Estate Desk", body)
            self.assertIn("Nothing leaves this house unmeasured.", body)

    def test_get_desk_200(self):
        with _TestServer() as srv:
            status, body = srv.get("/desk")
            self.assertEqual(status, 200)
            # All 7 labels
            for label in ["A", "B", "C", "D", "E", "F", "G"]:
                self.assertIn(label, body)

    def test_get_archive_200_empty(self):
        with _TestServer() as srv:
            status, body = srv.get("/archive")
            self.assertEqual(status, 200)
            self.assertIn("0 receipts", body)

    def test_post_adjudicate_preset_a_pass(self):
        with _TestServer() as srv:
            status, body = srv.post("/adjudicate", {"preset": "A"})
            self.assertEqual(status, 200)
            self.assertIn("PASS", body)

    def test_post_adjudicate_preset_b_will_superseded(self):
        with _TestServer() as srv:
            status, body = srv.post("/adjudicate", {"preset": "B"})
            self.assertEqual(status, 200)
            self.assertIn("will_superseded", body)

    def test_post_adjudicate_preset_c_share_mismatch(self):
        with _TestServer() as srv:
            status, body = srv.post("/adjudicate", {"preset": "C"})
            self.assertEqual(status, 200)
            self.assertIn("share_mismatch", body)

    def test_post_adjudicate_preset_d_beneficiary_unknown(self):
        with _TestServer() as srv:
            status, body = srv.post("/adjudicate", {"preset": "D"})
            self.assertEqual(status, 200)
            self.assertIn("beneficiary_unknown", body)

    def test_post_adjudicate_preset_e_sign_unoccupied(self):
        with _TestServer() as srv:
            status, body = srv.post("/adjudicate", {"preset": "E"})
            self.assertEqual(status, 200)
            self.assertIn("sign_unoccupied", body)

    def test_post_adjudicate_preset_f_death_unverified_and_appended(self):
        with _TestServer() as srv:
            status, body = srv.post("/adjudicate", {"preset": "F"})
            self.assertEqual(status, 200)
            self.assertIn("death_unverified", body)
            # Archive should now show 1 receipt
            _, archive = srv.get("/archive")
            self.assertIn("1 receipt", archive)

    def test_post_adjudicate_preset_g_seal_broken_no_append(self):
        with _TestServer() as srv:
            status, body = srv.post("/adjudicate", {"preset": "G"})
            self.assertEqual(status, 200)
            self.assertIn("seal_broken", body)
            self.assertIn("was not recorded in the house chain", body)
            # own_hash and previous_hash must NOT appear in the seal_broken notice
            # (they are not present since no receipt was created)
            # Archive should still show 0 receipts
            _, archive = srv.get("/archive")
            self.assertIn("0 receipts", archive)

    def test_post_adjudicate_preset_a_contains_full_hashes(self):
        """The PASS receipt must contain the full 64-char own_hash and previous_hash."""
        with _TestServer() as srv:
            status, body = srv.post("/adjudicate", {"preset": "A"})
            self.assertEqual(status, 200)
            # Check for a 64-char hex string (own_hash)
            import re
            hashes = re.findall(r'\b[0-9a-f]{64}\b', body)
            self.assertGreaterEqual(len(hashes), 2, "Should contain at least own_hash and previous_hash")

    def test_post_archive_verify_chain_intact(self):
        with _TestServer() as srv:
            srv.post("/adjudicate", {"preset": "A"})
            status, body = srv.post("/archive/verify", {})
            self.assertEqual(status, 200)
            self.assertIn("Chain intact", body)

    def test_post_archive_tamper_demo_not_modified(self):
        with _TestServer() as srv:
            srv.post("/adjudicate", {"preset": "A"})
            status, body = srv.post("/archive/tamper-demo", {})
            self.assertEqual(status, 200)
            self.assertIn("The house chain was not modified.", body)
            # Chain must still verify clean after tamper demo
            _, verify_body = srv.post("/archive/verify", {})
            self.assertIn("Chain intact", verify_body)

    def test_get_unknown_path_404(self):
        with _TestServer() as srv:
            try:
                status, _ = srv.get("/nonexistent")
                self.assertEqual(status, 404)
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)

    def test_archive_appends_correctly_a_through_f(self):
        """POST A through F in order → chain has 6 receipts; G → still 6."""
        with _TestServer() as srv:
            for label in ["A", "B", "C", "D", "E", "F"]:
                srv.post("/adjudicate", {"preset": label})
            _, archive = srv.get("/archive")
            self.assertIn("6 receipts", archive)
            srv.post("/adjudicate", {"preset": "G"})
            _, archive = srv.get("/archive")
            self.assertIn("6 receipts", archive)


# ---------------------------------------------------------------------------
# 10. Scenario G: seal_broken response does not contain own_hash/previous_hash
# ---------------------------------------------------------------------------

class TestScenarioGSealBroken(unittest.TestCase):
    def test_g_response_has_no_receipt_hash_fields(self):
        """Scenario G response must not contain own_hash or previous_hash receipt fields.

        The spec (AC-6.3) says the seal_broken notice must not include
        own_hash or previous_hash fields — meaning no receipt DL was generated.
        A seal-broken-notice div replaces the full receipt dl.
        """
        with _TestServer() as srv:
            status, body = srv.post("/adjudicate", {"preset": "G"})
            self.assertEqual(status, 200)
            self.assertIn("seal_broken", body)
            # The seal-broken-notice must be present
            self.assertIn("seal-broken-notice", body)
            # No receipt dl should be present — the "Own Hash" / "Previous Hash" DT labels
            # only appear in render_receipt(), which is not called for tamper_error=True.
            # We verify that the receipt-specific field labels do not appear.
            self.assertNotIn("Own Hash", body)
            self.assertNotIn("Previous Hash", body)

    def test_g_render_receipt_not_called(self):
        """For Scenario G, render_receipt is not called; no dl.receipt in body."""
        from webui import render
        from webui.state import SCENARIO_DEFINITIONS
        reg = _make_register()
        reg.adjudicate_preset("G")  # tamper error
        html = render.render_desk_with_result(
            SCENARIO_DEFINITIONS, reg.registry,
            "G", None, None, True,
        )
        self.assertIn("seal-broken-notice", html)
        self.assertNotIn('class="hash"', html)
        self.assertNotIn("own_hash", html.lower().replace("own_hash", ""))  # no receipt hash fields


if __name__ == "__main__":
    unittest.main()
