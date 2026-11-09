"""
tests.test_notices_ui
~~~~~~~~~~~~~~~~~~~~~
Unit tests for the Notices Desk web skin (webui/).

Tests cover:
1. Render functions: Sources, Notices Desk, Notice Archive.
2. Preset verdict parity: N1-N6 match citation_gate/scenarios.py.
3. Publish rule: a draft prints only when every assertion has a PASS receipt.
4. Free-builder assertions: PASS, source_contradicts, missing_citation.
5. Chain / draft semantics: chain only grows; new_draft clears the draft only.
6. Tamper demo: never mutates the notices chain.
7. Tampered mandate: surfaces as a refusal display, not a crash.
8. Input escaping.
9. Route tests over a real HTTP server.
10. CSS audit of the notices rooms.

All tests use the real gate_core and citation_gate libraries with fixture
files. No mocking of gate logic.
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

DEATH_RECORD_PATH = str(FIXTURES / "death_record.json")
WILL_PATH = str(FIXTURES / "will_2024.json")
FAMILY_RECORD_PATH = str(FIXTURES / "family_record.json")

N1_SENTENCE = "Elias Vane died on 28 October 2026."


def _make_notices_register():
    """Create a fresh NoticesRegister for each test."""
    from webui.state import NoticesRegister
    return NoticesRegister(
        death_record_path=DEATH_RECORD_PATH,
        will_path=WILL_PATH,
        family_record_path=FAMILY_RECORD_PATH,
    )


def _make_house_register():
    from webui.state import HouseRegister
    return HouseRegister(
        will_paths=[str(FIXTURES / "will_2019.json"), str(FIXTURES / "will_2024.json")],
        death_record_paths=[DEATH_RECORD_PATH],
    )


def _tamper_mandate(register) -> None:
    """Alter the desk mandate content after sealing, breaking its seal."""
    register._desk_mandate.content["mandate"] = "altered after sealing"


def _stamps(html: str) -> list[str]:
    """Return the text of every publish stamp in a page.

    Preset blocks always carry a static "Expected: ..." line, so assertions
    about a publish decision must look at the rendered stamps only.
    """
    return re.findall(r'<div class="publish-stamp"><p class="[^"]*">([^<]*)</p>', html)


def _draft_section(html: str) -> str:
    """Return the Working Draft section of a Notices Desk page."""
    start = html.index("<h2>Working Draft</h2>")
    return html[start:html.index("<hr>", start)]


def _before_draft(html: str) -> str:
    """Return the preset-block region (everything before the Working Draft)."""
    return html[:html.index("<h2>Working Draft</h2>")]


# ---------------------------------------------------------------------------
# Helper: start a test server on an ephemeral port
# ---------------------------------------------------------------------------

class _TestServer:
    """Context manager that starts the HouseHandler on a random port."""

    def __init__(self):
        self.register = _make_house_register()
        self.notices_register = _make_notices_register()
        self.port = None
        self._server = None
        self._thread = None

    def __enter__(self):
        from webui.server import HouseHandler
        HouseHandler.register = self.register
        HouseHandler.notices_register = self.notices_register
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
# 1. Render functions
# ---------------------------------------------------------------------------

class TestRenderNotices(unittest.TestCase):
    def setUp(self):
        from webui import render
        from webui.state import NOTICES_SCENARIO_DEFINITIONS
        self.render = render
        self.defs = NOTICES_SCENARIO_DEFINITIONS
        self.reg = _make_notices_register()

    def test_sources_contains_ids_seals_and_canon_occupation(self):
        html = self.render.render_sources(self.reg.source_registry)
        for sid in ("death_record", "will_2024", "family_record"):
            self.assertIn(sid, html)
            self.assertIn(self.reg.source_registry.source(sid).seal[:12], html)
        self.assertIn("self-professed Tree Wizard", html)

    def test_sources_has_no_forms_or_buttons(self):
        html = self.render.render_sources(self.reg.source_registry)
        self.assertNotIn("<form", html)
        self.assertNotIn("<button", html)

    def test_notices_desk_contains_all_six_labels_in_order(self):
        html = self.render.render_notices_desk(self.defs, self.reg.source_registry, [], None)
        positions = [html.find(f'value="N{i}"') for i in range(1, 7)]
        for i, pos in enumerate(positions, start=1):
            self.assertGreater(pos, -1, f"N{i} preset form missing")
        self.assertEqual(positions, sorted(positions))

    def test_notices_desk_presets_list_text_key_and_citation(self):
        html = self.render.render_notices_desk(self.defs, self.reg.source_registry, [], None)
        for defn in self.defs:
            for phase in defn["phases"]:
                for a in phase["assertions"]:
                    self.assertIn(a["text"], html)
                    self.assertIn(f"key: {a['fact_key']}", html)
        self.assertIn("citation: no citation", html)
        self.assertIn("citation: parish_register", html)

    def test_notices_desk_has_builder_and_new_draft_forms(self):
        html = self.render.render_notices_desk(self.defs, self.reg.source_registry, [], None)
        self.assertIn('action="/notices/preset"', html)
        self.assertIn('action="/notices/assertion"', html)
        self.assertIn('action="/notices/new-draft"', html)
        self.assertIn("Measure this assertion", html)

    def test_builder_select_options_labelled_by_source_and_key(self):
        html = self.render.render_assertion_builder(self.reg.source_registry)
        for sid in ("death_record", "will_2024", "family_record"):
            self.assertIn(f'<optgroup label="{sid}">', html)
            for key in self.reg.source_registry.fact_table(sid):
                self.assertIn(f'<option value="{key}">{sid} — {key}</option>', html)
        self.assertIn('<option value="">No citation</option>', html)

    def test_notices_desk_builder_not_prefilled(self):
        html = self.render.render_notices_desk(self.defs, self.reg.source_registry, [], None)
        for tag in re.findall(r'<input type="text"[^>]*>', html):
            self.assertNotRegex(tag, r'value="[^"]+"')

    def test_notices_archive_empty(self):
        html = self.render.render_notices_archive([])
        self.assertIn("Notice Chain — 0 receipts", html)

    def test_notices_archive_shows_own_hashes(self):
        self.reg.adjudicate_preset("N1")
        chain = self.reg.chain_snapshot()
        html = self.render.render_notices_archive(chain)
        for r in chain:
            self.assertIn(r.own_hash, html)

    def test_notices_page_shell_header_and_nav(self):
        html = self.render.notices_page_shell("t", "<p>x</p>")
        self.assertIn("The Notices Desk", html)
        self.assertIn("Nothing is printed here unmeasured.", html)
        for href in ("/", "/desk", "/archive", "/notices/sources",
                     "/notices", "/notices/archive"):
            self.assertIn(f'href="{href}"', html)

    def test_publish_decision_rendering(self):
        from citation_gate.publish import PublishDecision
        ok = self.render.render_publish_decision(PublishDecision(True, ["abc"], None))
        self.assertIn("PUBLISHABLE", ok)
        self.assertIn("abc", ok)
        bad = self.render.render_publish_decision(
            PublishDecision(False, None, "source_contradicts"))
        self.assertIn("REFUSED · source_contradicts", bad)
        self.assertIn("verdict-refused", bad)


# ---------------------------------------------------------------------------
# 2. Preset verdict parity
# ---------------------------------------------------------------------------

class TestNoticesPresetVerdicts(unittest.TestCase):
    def setUp(self):
        self.reg = _make_notices_register()

    def _refusal(self, entry):
        self.assertEqual(entry.verdict["type"], "refused")
        return entry.verdict["name"]

    def test_N1_all_pass_publishable(self):
        entries, decisions, tamper = self.reg.adjudicate_preset("N1")
        self.assertFalse(tamper)
        self.assertEqual(len(entries), 3)
        for e in entries:
            self.assertEqual(e.verdict["type"], "pass")
        self.assertEqual(len(decisions), 1)
        self.assertTrue(decisions[0].publishable)
        self.assertEqual(len(decisions[0].receipt_ids), 3)

    def test_N2_source_contradicts(self):
        entries, decisions, tamper = self.reg.adjudicate_preset("N2")
        self.assertFalse(tamper)
        self.assertEqual(len(entries), 1)
        self.assertEqual(self._refusal(entries[0]), "source_contradicts")
        self.assertFalse(decisions[0].publishable)
        self.assertEqual(decisions[0].refusal_name, "source_contradicts")

    def test_N3_unsupported_claim(self):
        entries, decisions, tamper = self.reg.adjudicate_preset("N3")
        self.assertFalse(tamper)
        self.assertEqual(self._refusal(entries[0]), "unsupported_claim")
        self.assertFalse(decisions[0].publishable)
        self.assertEqual(decisions[0].refusal_name, "unsupported_claim")

    def test_N4_missing_citation(self):
        entries, decisions, tamper = self.reg.adjudicate_preset("N4")
        self.assertFalse(tamper)
        self.assertEqual(self._refusal(entries[0]), "missing_citation")
        self.assertFalse(decisions[0].publishable)
        self.assertEqual(decisions[0].refusal_name, "missing_citation")

    def test_N5_two_phases(self):
        entries, decisions, tamper = self.reg.adjudicate_preset("N5")
        self.assertFalse(tamper)
        self.assertEqual(len(entries), 4)
        self.assertEqual(len(decisions), 2)
        self.assertFalse(decisions[0].publishable)
        self.assertEqual(decisions[0].refusal_name, "source_contradicts")
        self.assertTrue(decisions[1].publishable)
        # N5a: pass, refused(source_contradicts), pass; N5b: pass
        self.assertEqual([e.verdict["type"] for e in entries],
                         ["pass", "refused", "pass", "pass"])
        self.assertEqual(entries[1].verdict["name"], "source_contradicts")

    def test_N6_unknown_source_unsupported_claim(self):
        entries, decisions, tamper = self.reg.adjudicate_preset("N6")
        self.assertFalse(tamper)
        self.assertEqual(self._refusal(entries[0]), "unsupported_claim")
        self.assertFalse(decisions[0].publishable)
        self.assertEqual(decisions[0].refusal_name, "unsupported_claim")

    def test_unknown_label_raises(self):
        with self.assertRaises(KeyError):
            self.reg.adjudicate_preset("N99")

    def test_parity_with_citation_gate_scenarios(self):
        """Web presets reproduce the verdicts and publish decisions that
        citation_gate.scenarios.run_scenarios() defines."""
        from citation_gate.scenarios import run_scenarios
        from gate_core import seal_mandate
        from citation_gate.sources import SourceRegistry

        sr = SourceRegistry(
            death_record_path=DEATH_RECORD_PATH,
            will_path=WILL_PATH,
            family_record_path=FAMILY_RECORD_PATH,
        )
        mandate = seal_mandate("citation", {"desk": "notices", "mandate": "parity"})
        reference = {r.label: r for r in run_scenarios(sr, mandate)}

        def verdict_dicts(draft_result):
            return [ar.receipt.verdict for ar in draft_result.assertion_results]

        for label, phases in (("N1", ["N1"]), ("N2", ["N2"]), ("N3", ["N3"]),
                              ("N4", ["N4"]), ("N5", ["N5a", "N5b"]), ("N6", ["N6"])):
            reg = _make_notices_register()
            entries, decisions, tamper = reg.adjudicate_preset(label)
            self.assertFalse(tamper)
            expected_verdicts = []
            for ph in phases:
                expected_verdicts += verdict_dicts(reference[ph])
            self.assertEqual([e.verdict for e in entries], expected_verdicts, label)
            self.assertEqual(len(decisions), len(phases), label)
            for d, ph in zip(decisions, phases):
                ref = reference[ph].publish_decision
                self.assertEqual(d.publishable, ref.publishable, ph)
                self.assertEqual(d.refusal_name, ref.refusal_name, ph)

    def test_expected_publish_strings_match_decisions(self):
        from webui.state import NOTICES_SCENARIO_DEFINITIONS
        for defn in NOTICES_SCENARIO_DEFINITIONS:
            reg = _make_notices_register()
            _entries, decisions, _t = reg.adjudicate_preset(defn["label"])
            parts = []
            for phase, d in zip(defn["phases"], decisions):
                text = ("PUBLISHABLE" if d.publishable
                        else f"REFUSED · {d.refusal_name}")
                parts.append(text if len(decisions) == 1 else f'{phase["label"]}: {text}')
            self.assertEqual("; ".join(parts), defn["expected_publish"], defn["label"])

    def test_preset_does_not_touch_working_draft(self):
        self.reg.adjudicate_preset("N1")
        self.assertEqual(self.reg.working_draft, [])
        self.assertIsNone(self.reg.working_draft_publish_state())


# ---------------------------------------------------------------------------
# 3. Publish rule
# ---------------------------------------------------------------------------

class TestPublishRule(unittest.TestCase):
    """A draft prints only when every assertion carries a PASS receipt."""

    def setUp(self):
        self.reg = _make_notices_register()

    def test_all_pass_draft_is_publishable(self):
        self.reg.adjudicate_assertion(N1_SENTENCE, "date_of_death", "2026-10-28", "death_record")
        entry, decision, _t = self.reg.adjudicate_assertion(
            "He was a self-professed Tree Wizard.", "occupation",
            "self-professed Tree Wizard", "family_record")
        self.assertTrue(decision.publishable)
        self.assertEqual(len(decision.receipt_ids), 2)
        self.assertTrue(self.reg.working_draft_publish_state().publishable)

    def test_one_refused_assertion_blocks_whole_draft(self):
        self.reg.adjudicate_assertion(N1_SENTENCE, "date_of_death", "2026-10-28", "death_record")
        _e, decision, _t = self.reg.adjudicate_assertion(
            "He was born in Galway.", "birthplace", "Galway", "family_record")
        self.assertFalse(decision.publishable)
        self.assertIsNone(decision.receipt_ids)
        self.assertEqual(decision.refusal_name, "source_contradicts")
        state = self.reg.working_draft_publish_state()
        self.assertFalse(state.publishable)

    def test_pass_after_refusal_does_not_unblock_draft(self):
        self.reg.adjudicate_assertion("He was born in Galway.", "birthplace", "Galway", "family_record")
        _e, decision, _t = self.reg.adjudicate_assertion(
            N1_SENTENCE, "date_of_death", "2026-10-28", "death_record")
        self.assertFalse(decision.publishable)

    def test_empty_draft_has_no_publish_state(self):
        self.assertIsNone(self.reg.working_draft_publish_state())

    def test_unmeasured_assertion_is_not_publishable(self):
        from citation_gate.publish import check_publish
        decision = check_publish("d", ["0" * 64], self.reg.chain_snapshot())
        self.assertFalse(decision.publishable)
        self.assertEqual(decision.refusal_name, "unmeasured")

    def test_publishable_receipt_ids_are_pass_receipts_in_chain(self):
        _entries, decisions, _t = self.reg.adjudicate_preset("N1")
        by_hash = {r.own_hash: r for r in self.reg.chain_snapshot()}
        for rid in decisions[0].receipt_ids:
            self.assertEqual(by_hash[rid].verdict["type"], "pass")


# ---------------------------------------------------------------------------
# 4. Free-builder assertions
# ---------------------------------------------------------------------------

class TestAssertionBuilder(unittest.TestCase):
    def setUp(self):
        self.reg = _make_notices_register()

    def test_custom_pass(self):
        before = len(self.reg.chain_snapshot())
        entry, decision, tamper = self.reg.adjudicate_assertion(
            N1_SENTENCE, "date_of_death", "2026-10-28", "death_record")
        self.assertFalse(tamper)
        self.assertEqual(entry.verdict["type"], "pass")
        self.assertIsNotNone(decision)
        self.assertEqual(len(self.reg.chain_snapshot()), before + 1)
        self.assertEqual(len(self.reg.working_draft), 1)

    def test_custom_source_contradicts(self):
        entry, decision, tamper = self.reg.adjudicate_assertion(
            "He bequeathed The Sealed Letter to Marta, the neighbor.",
            "bequest.Scorpio.beneficiary", "Marta, the neighbor", "will_2024")
        self.assertFalse(tamper)
        self.assertEqual(entry.verdict["type"], "refused")
        self.assertEqual(entry.verdict["name"], "source_contradicts")
        self.assertEqual(decision.refusal_name, "source_contradicts")

    def test_custom_missing_citation(self):
        entry, _d, tamper = self.reg.adjudicate_assertion(
            "He was born in Hollow Hill.", "birthplace", "Hollow Hill", None)
        self.assertFalse(tamper)
        self.assertEqual(entry.verdict["type"], "refused")
        self.assertEqual(entry.verdict["name"], "missing_citation")


# ---------------------------------------------------------------------------
# 5. Chain and draft semantics
# ---------------------------------------------------------------------------

class TestChainAndDraft(unittest.TestCase):
    def setUp(self):
        self.reg = _make_notices_register()

    def test_chain_grows_across_presets(self):
        self.reg.adjudicate_preset("N1")
        self.reg.adjudicate_preset("N2")
        self.assertEqual(len(self.reg.chain_snapshot()), 4)

    def test_n5_appends_four_receipts(self):
        self.reg.adjudicate_preset("N5")
        self.assertEqual(len(self.reg.chain_snapshot()), 4)

    def test_chain_snapshot_is_a_copy(self):
        self.reg.adjudicate_preset("N1")
        snap = self.reg.chain_snapshot()
        snap.clear()
        self.assertEqual(len(self.reg.chain_snapshot()), 3)

    def test_new_draft_clears_draft_not_chain(self):
        self.reg.adjudicate_assertion(N1_SENTENCE, "date_of_death", "2026-10-28", "death_record")
        before = len(self.reg.chain_snapshot())
        self.reg.new_draft()
        self.assertEqual(self.reg.working_draft, [])
        self.assertEqual(len(self.reg.chain_snapshot()), before)
        self.assertIsNone(self.reg.working_draft_publish_state())

    def test_verify_chain_ok_after_adjudications(self):
        self.assertTrue(self.reg.verify_notices_chain().ok)
        for label in ("N1", "N2", "N3", "N4", "N5", "N6"):
            self.reg.adjudicate_preset(label)
        self.reg.adjudicate_assertion(N1_SENTENCE, "date_of_death", "2026-10-28", "death_record")
        self.assertTrue(self.reg.verify_notices_chain().ok)


# ---------------------------------------------------------------------------
# 6. Tamper demo does not mutate notices chain
# ---------------------------------------------------------------------------

class TestNoticesTamperDemo(unittest.TestCase):
    def setUp(self):
        self.reg = _make_notices_register()

    def test_empty_chain_ok(self):
        self.assertTrue(self.reg.tamper_demo().ok)
        self.assertEqual(len(self.reg.chain_snapshot()), 0)

    def test_reports_hash_mismatch(self):
        self.reg.adjudicate_preset("N1")
        result = self.reg.tamper_demo()
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_reason, "hash_mismatch")

    def test_does_not_mutate_chain(self):
        self.reg.adjudicate_preset("N1")
        self.reg.adjudicate_preset("N2")
        before = self.reg.chain_snapshot()
        hashes_before = [r.own_hash for r in before]
        claims_before = [dict(r.claim) for r in before]
        self.reg.tamper_demo()
        after = self.reg.chain_snapshot()
        self.assertEqual(len(after), len(before))
        self.assertEqual([r.own_hash for r in after], hashes_before)
        self.assertEqual([dict(r.claim) for r in after], claims_before)
        self.assertTrue(self.reg.verify_notices_chain().ok)


# ---------------------------------------------------------------------------
# 7. Tampered mandate surfaces as a refusal display, not a crash
# ---------------------------------------------------------------------------

class TestTamperedMandate(unittest.TestCase):
    def setUp(self):
        self.reg = _make_notices_register()
        _tamper_mandate(self.reg)

    def test_preset_reports_tamper_and_records_nothing(self):
        entries, decisions, tamper = self.reg.adjudicate_preset("N1")
        self.assertTrue(tamper)
        self.assertEqual(decisions, [])
        self.assertIsNone(entries[0].verdict)
        self.assertIsNone(entries[0].receipt)
        self.assertEqual(len(self.reg.chain_snapshot()), 0)

    def test_assertion_reports_seal_broken_and_records_nothing(self):
        entry, decision, tamper = self.reg.adjudicate_assertion(
            N1_SENTENCE, "date_of_death", "2026-10-28", "death_record")
        self.assertTrue(tamper)
        self.assertIsNone(entry.receipt)
        self.assertFalse(decision.publishable)
        self.assertEqual(decision.refusal_name, "seal_broken")
        self.assertEqual(len(self.reg.chain_snapshot()), 0)
        self.assertEqual(self.reg.working_draft, [])

    def test_render_preset_tamper_shows_refusal(self):
        from webui import render
        from webui.state import NOTICES_SCENARIO_DEFINITIONS
        entries, decisions, tamper = self.reg.adjudicate_preset("N1")
        html = render.render_notices_desk_with_preset_result(
            NOTICES_SCENARIO_DEFINITIONS, self.reg.source_registry,
            self.reg.working_draft, None, "N1", entries, decisions, tamper)
        self.assertIn("seal-broken-notice", html)
        self.assertIn("REFUSED · seal_broken", html)
        self.assertEqual(_stamps(html), [])

    def test_render_assertion_tamper_shows_refusal(self):
        from webui import render
        from webui.state import NOTICES_SCENARIO_DEFINITIONS
        entry, _d, tamper = self.reg.adjudicate_assertion(
            N1_SENTENCE, "date_of_death", "2026-10-28", "death_record")
        html = render.render_notices_desk_with_assertion_result(
            NOTICES_SCENARIO_DEFINITIONS, self.reg.source_registry,
            self.reg.working_draft, None, entry, tamper)
        self.assertIn("seal-broken-notice", html)
        self.assertIn("REFUSED · seal_broken", html)
        self.assertIn("This assertion was not recorded in the notices chain.", html)
        self.assertNotIn("own_hash", html.split("seal-broken-notice", 1)[1].split("</div>", 1)[0])

    def test_http_preset_and_assertion_return_200_with_refusal(self):
        with _TestServer() as srv:
            _tamper_mandate(srv.notices_register)
            status, body = srv.post("/notices/preset", {"preset": "N1"})
            self.assertEqual(status, 200)
            self.assertIn("REFUSED · seal_broken", body)
            self.assertEqual(_stamps(body), [])
            status, body = srv.post("/notices/assertion", {
                "sentence": N1_SENTENCE, "fact_key": "date_of_death",
                "value": "2026-10-28", "citation": "death_record"})
            self.assertEqual(status, 200)
            self.assertIn("REFUSED · seal_broken", body)
            status, body = srv.get("/notices/archive")
            self.assertEqual(status, 200)
            self.assertIn("Notice Chain — 0 receipts", body)


# ---------------------------------------------------------------------------
# 8. Input escaping
# ---------------------------------------------------------------------------

class TestNoticesEscaping(unittest.TestCase):
    PAYLOAD = "<script>alert(1)</script>"

    def test_render_escapes_draft_text(self):
        from webui import render
        from webui.state import NOTICES_SCENARIO_DEFINITIONS
        reg = _make_notices_register()
        entry, _d, tamper = reg.adjudicate_assertion(
            self.PAYLOAD, "date_of_death", "2026-10-28", "death_record")
        html = render.render_notices_desk_with_assertion_result(
            NOTICES_SCENARIO_DEFINITIONS, reg.source_registry,
            reg.working_draft, reg.working_draft_publish_state(), entry, tamper)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert", html)

    def test_http_post_escapes_sentence(self):
        with _TestServer() as srv:
            status, body = srv.post("/notices/assertion", {
                "sentence": self.PAYLOAD, "fact_key": "date_of_death",
                "value": "2026-10-28", "citation": "death_record"})
            self.assertEqual(status, 200)
            self.assertIn("&lt;script&gt;", body)
            self.assertNotIn("<script>alert", body)


# ---------------------------------------------------------------------------
# 9. Routes
# ---------------------------------------------------------------------------

class TestNoticesRoutes(unittest.TestCase):
    def test_get_sources_200(self):
        with _TestServer() as srv:
            status, body = srv.get("/notices/sources")
            self.assertEqual(status, 200)
            for sid in ("death_record", "will_2024", "family_record"):
                self.assertIn(sid, body)
            self.assertIn("self-professed Tree Wizard", body)

    def test_get_notices_200(self):
        with _TestServer() as srv:
            status, body = srv.get("/notices")
            self.assertEqual(status, 200)
            for i in range(1, 7):
                self.assertIn(f"N{i}", body)

    def test_get_notices_archive_200_empty(self):
        with _TestServer() as srv:
            status, body = srv.get("/notices/archive")
            self.assertEqual(status, 200)
            self.assertIn("Notice Chain — 0 receipts", body)

    def test_post_preset_n1_publishable(self):
        with _TestServer() as srv:
            status, body = srv.post("/notices/preset", {"preset": "N1"})
            self.assertEqual(status, 200)
            self.assertEqual(_stamps(body), ["PUBLISHABLE"])
            self.assertIn("He was a self-professed Tree Wizard.", body)
            self.assertIn("✦", body)

    def test_post_preset_n2_refused(self):
        with _TestServer() as srv:
            status, body = srv.post("/notices/preset", {"preset": "N2"})
            self.assertEqual(status, 200)
            self.assertIn("REFUSED · source_contradicts", body)
            self.assertIn("verdict-refused", body)

    def test_post_preset_n3_n4_n6_refusals(self):
        expected = {"N3": "unsupported_claim", "N4": "missing_citation",
                    "N6": "unsupported_claim"}
        for label, name in expected.items():
            with _TestServer() as srv:
                status, body = srv.post("/notices/preset", {"preset": label})
                self.assertEqual(status, 200)
                self.assertEqual(_stamps(body), [f"REFUSED · {name}"])

    def test_post_preset_n5_both_phases(self):
        with _TestServer() as srv:
            status, body = srv.post("/notices/preset", {"preset": "N5"})
            self.assertEqual(status, 200)
            self.assertEqual(_stamps(body),
                             ["REFUSED · source_contradicts", "PUBLISHABLE"])

    def test_post_preset_unknown_and_missing_are_400(self):
        with _TestServer() as srv:
            for data in ({"preset": "N99"}, {}):
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    srv.post("/notices/preset", data)
                self.assertEqual(ctx.exception.code, 400)

    def test_post_assertion_pass(self):
        with _TestServer() as srv:
            status, body = srv.post("/notices/assertion", {
                "sentence": N1_SENTENCE, "fact_key": "date_of_death",
                "value": "2026-10-28", "citation": "death_record"})
            self.assertEqual(status, 200)
            self.assertIn("PASS", body)

    def test_post_assertion_missing_citation(self):
        with _TestServer() as srv:
            status, body = srv.post("/notices/assertion", {
                "sentence": "He was born in Hollow Hill.", "fact_key": "birthplace",
                "value": "Hollow Hill", "citation": ""})
            self.assertEqual(status, 200)
            self.assertIn("missing_citation", body)

    def test_post_assertion_source_contradicts(self):
        with _TestServer() as srv:
            status, body = srv.post("/notices/assertion", {
                "sentence": "test", "fact_key": "date_of_death",
                "value": "wrong", "citation": "death_record"})
            self.assertEqual(status, 200)
            self.assertIn("source_contradicts", body)

    def test_post_assertion_missing_fields_400(self):
        with _TestServer() as srv:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                srv.post("/notices/assertion", {"sentence": "", "fact_key": ""})
            self.assertEqual(ctx.exception.code, 400)

    def test_new_draft_clears_draft_keeps_chain(self):
        with _TestServer() as srv:
            srv.post("/notices/assertion", {
                "sentence": N1_SENTENCE, "fact_key": "date_of_death",
                "value": "2026-10-28", "citation": "death_record"})
            self.assertEqual(len(srv.notices_register.working_draft), 1)
            status, _body = srv.post("/notices/new-draft", {})
            self.assertEqual(status, 200)
            self.assertEqual(srv.notices_register.working_draft, [])
            status, body = srv.get("/notices")
            self.assertEqual(status, 200)
            self.assertNotIn(N1_SENTENCE, _draft_section(body))
            status, body = srv.get("/notices/archive")
            self.assertIn("Notice Chain — 1 receipt.", body)

    def test_archive_shows_three_receipts_after_n1(self):
        with _TestServer() as srv:
            srv.post("/notices/preset", {"preset": "N1"})
            _s, body = srv.get("/notices/archive")
            self.assertIn("Notice Chain — 3 receipts.", body)
            for r in srv.notices_register.chain_snapshot():
                self.assertIn(r.own_hash, body)

    def test_archive_verify_chain_intact(self):
        with _TestServer() as srv:
            srv.post("/notices/preset", {"preset": "N1"})
            status, body = srv.post("/notices/archive/verify", {})
            self.assertEqual(status, 200)
            self.assertIn("Chain intact — 3 receipts verified.", body)

    def test_preset_result_resolves_only_the_matched_block(self):
        with _TestServer() as srv:
            _s, before = srv.get("/notices")
            self.assertNotIn("claim-block resolved", _before_draft(before))
            _s, after = srv.post("/notices/preset", {"preset": "N2"})
            head = _before_draft(after)
            self.assertEqual(head.count('<div class="preset-block"><div class="claim-block resolved">'), 1)
            self.assertEqual(head.count('<div class="preset-block"><div class="claim-block ghost">'), 5)

    def test_archive_tamper_failure_shown_and_chain_unmodified(self):
        with _TestServer() as srv:
            srv.post("/notices/preset", {"preset": "N1"})
            hashes = [r.own_hash for r in srv.notices_register.chain_snapshot()]
            status, body = srv.post("/notices/archive/tamper", {})
            self.assertEqual(status, 200)
            self.assertIn("hash_mismatch", body)
            self.assertIn("The notices chain was not modified.", body)
            self.assertEqual(
                [r.own_hash for r in srv.notices_register.chain_snapshot()], hashes)
            status, body = srv.post("/notices/archive/verify", {})
            self.assertIn("chain intact", body.lower())

    def test_unknown_notices_path_404(self):
        with _TestServer() as srv:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                srv.get("/notices/nope")
            self.assertEqual(ctx.exception.code, 404)
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                srv.post("/notices/nope", {})
            self.assertEqual(ctx.exception.code, 404)

    def test_estate_routes_unaffected(self):
        with _TestServer() as srv:
            for path in ("/", "/desk", "/archive"):
                status, body = srv.get(path)
                self.assertEqual(status, 200)
            status, body = srv.post("/adjudicate", {"preset": "A"})
            self.assertEqual(status, 200)
            self.assertIn("PASS", body)

    def test_navigation_present_on_both_desks(self):
        with _TestServer() as srv:
            for path in ("/", "/notices", "/notices/sources", "/notices/archive"):
                _s, body = srv.get(path)
                self.assertIn('href="/notices/sources"', body)
                self.assertIn('href="/"', body)

    def test_estate_and_notices_chains_are_separate(self):
        with _TestServer() as srv:
            srv.post("/adjudicate", {"preset": "A"})
            srv.post("/notices/preset", {"preset": "N1"})
            self.assertEqual(len(srv.register.chain_snapshot()), 1)
            self.assertEqual(len(srv.notices_register.chain_snapshot()), 3)


# ---------------------------------------------------------------------------
# 10. CSS audit
# ---------------------------------------------------------------------------

class TestNoticesCSS(unittest.TestCase):
    def _style(self, html: str) -> str:
        m = re.search(r"<style>(.*?)</style>", html, re.S)
        self.assertIsNotNone(m)
        return m.group(1)

    def test_palette_present_on_sources(self):
        with _TestServer() as srv:
            _s, body = srv.get("/notices/sources")
            self.assertRegex(body, r"--ghost:\s*#9a938a")
            self.assertRegex(body, r"--oxblood:\s*#7a2e2a")

    def test_no_animation_in_any_notices_room(self):
        with _TestServer() as srv:
            pages = [srv.get(p)[1] for p in
                     ("/notices/sources", "/notices", "/notices/archive")]
            pages.append(srv.post("/notices/preset", {"preset": "N1"})[1])
            for html in pages:
                css = self._style(html)
                self.assertNotIn("@keyframes", css)
                self.assertNotIn("animation:", css)

    def test_only_transition_is_claim_block_color_and_opacity(self):
        with _TestServer() as srv:
            css = self._style(srv.get("/notices")[1])
        self.assertEqual(css.count("transition:"), 1)
        m = re.search(r"([^{}]*)\{[^{}]*transition:([^;}]*)", css)
        self.assertIsNotNone(m)
        self.assertIn(".claim-block", m.group(1))
        self.assertIn("color", m.group(2))
        self.assertIn("opacity", m.group(2))


if __name__ == "__main__":
    unittest.main()
