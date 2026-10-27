"""Headless-browser test of the game: runs the real Python in Pyodide (WebAssembly)
and compares what the page shows with what CPython computes from the same code.

Skipped when Playwright or a Chromium binary is unavailable (the standard CI matrix);
the dedicated 'game-browser' CI job installs both.
Run: python -m unittest tests_game_browser -v
"""

import functools
import http.server
import json
import os
import re
import socketserver
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(HERE, "docs", "game")
sys.path.append(os.path.join(GAME, "py"))

try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False

# canvas mapping used by game.js
XMIN, XMAX, YMIN, YMAX = -24.5, 24.5, -10.2, 10.2


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@unittest.skipUnless(HAVE_PW, "Playwright not installed")
class TestGameInBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import bridge
        cls.bridge = bridge
        cls.geo = json.loads(bridge.init(42))
        handler = functools.partial(Quiet, directory=GAME)
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        cls.browser = None
        errors = []
        for kw in ({}, {"executable_path": os.environ.get("MB_CHROME", "/usr/bin/google-chrome")}):
            try:
                cls.browser = cls.pw.chromium.launch(headless=True, args=["--no-sandbox"], **kw)
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc)[:120])
        if cls.browser is None:
            cls.pw.stop()
            cls.httpd.shutdown()
            raise unittest.SkipTest("no Chromium available: %s" % errors)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def open(self, width=1100, height=900):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.logs, self.requests = [], []
        page.on("console", lambda m: self.logs.append((m.type, m.text)) if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: self.logs.append(("pageerror", str(e))))
        page.on("request", lambda r: self.requests.append(r.url))
        page.goto("http://127.0.0.1:%d/index.html" % self.port)
        page.wait_for_selector("body[data-ready]", state="attached", timeout=120000)
        self.assertEqual(page.get_attribute("body", "data-ready"), "1", page.inner_text("#status"))
        return page

    def tearDown(self):
        pass

    def test_boot_shows_the_seed_42_numbers_and_loads_nothing_third_party(self):
        page = self.open()
        st = page.inner_text("#status")
        self.assertIn("128 neurons, 314 edges, 12 cross edges, tau 0.238", st)
        self.assertIn("Python 3.12", st)
        hosts = {u.split("/")[2] for u in self.requests if u.startswith("http")}
        self.assertEqual(hosts, {"127.0.0.1:%d" % self.port})
        self.assertEqual([l for l in self.logs if l[0] in ("error", "pageerror")], [], self.logs)
        self.assertIn("A toy, not a brain.", page.inner_text(".banner"))
        page.close()

    def test_observe_cut_makes_the_other_hemisphere_unreachable(self):
        page = self.open()
        self.assertIn("42/64", page.inner_text("#obs-stats"))      # intact: 42 of 64 right-hemisphere neurons reached
        self.assertIn("36.41", page.inner_text("#obs-stats"))
        page.check('input[name=mode][value=cut]')
        txt = page.inner_text("#obs-stats")
        self.assertIn("0/64", txt)
        self.assertIn("unreachable", txt)
        self.assertIn("302 (0 cross)", txt)
        page.check('input[name=mode][value=split]')
        self.assertIn("0/64", page.inner_text("#obs-stats"))
        page.close()

    def test_test_the_code_panel_all_pass_and_match_cpython(self):
        page = self.open()
        page.click("#tab-check")
        page.click("#c-run")
        page.wait_for_selector("#c-sum[data-total]", timeout=120000)
        total, passed = int(page.get_attribute("#c-sum", "data-total")), int(page.get_attribute("#c-sum", "data-pass"))
        self.assertEqual((passed, total), (16, 16), page.inner_text("#c-groups"))
        self.assertEqual(page.locator('.badge[data-ok="false"]').count(), 0)
        cell = lambda cid: page.inner_text('tr[data-check="%s"] td:nth-child(3)' % cid).strip()  # noqa: E731
        want = {r["id"]: r["measured"] for r in json.loads(self.bridge.run_checks("readme"))}
        for cid in ("neurons", "edges", "cross", "median", "split", "tau", "j", "rec", "ref", "clean"):
            self.assertEqual(cell(cid), str(want[cid]), cid)
        self.assertEqual(cell("median"), "36.41")
        self.assertEqual(cell("tau"), "0.238")
        self.assertEqual(cell("rec"), "40/40")
        self.assertEqual(cell("ref"), "50/50")
        self.assertEqual(cell("det_fp"), self.bridge.GOLDEN_FINGERPRINT)     # WebAssembly == CPython
        self.assertEqual(cell("unit"), "7 tests, 0 failed")
        t, mean, lo, hi = self.bridge.null_control()
        self.assertIn("%.1f%%" % (100 * mean), cell("null_shuf"))            # same shuffled-label chance level
        page.close()

    def test_be_the_gate_run_matches_cpython_scores(self):
        page = self.open()
        page.click("#tab-gate")
        page.fill("#g-run", "1")
        page.click("#g-start")
        you = gate = 0
        for level in range(3):
            for idx in range(8):
                page.click('#g-answers button[data-ans="-1"]')
                r = json.loads(self.bridge.grade(1, level, idx, -1, False))
                you += r["you_points"]
                gate += r["gate_points"]
                self.assertIn("It was", page.inner_text("#g-result"))
                page.click("#g-next")
        res = page.inner_text("#g-result")
        self.assertIn("Run 1, tau 0.238", res)
        self.assertIn("you %d points" % you, res)
        self.assertIn("real gate %d points" % gate, res)
        self.assertEqual(page.inner_text("#g-you"), str(you))
        self.assertEqual(page.inner_text("#g-gate"), str(gate))
        page.close()

    def test_measure_costs_points(self):
        page = self.open()
        page.click("#tab-gate")
        page.click("#g-start")
        page.click("#g-hint")
        self.assertIn("red line = tau 0.238", page.inner_text("#g-bars"))
        page.click('#g-answers button[data-ans="-1"]')
        r = json.loads(self.bridge.grade(1, 0, 0, -1, True))
        self.assertEqual(page.inner_text("#g-you"), str(r["you_points"]))
        page.close()

    def test_break_the_gate_click_matches_cpython_and_scan_counts(self):
        page = self.open()
        page.click("#tab-break")
        box = page.locator("#brain").bounding_box()
        src = 60
        x, y, _ = self.geo["nodes"][src]
        page.mouse.click(box["x"] + (x - XMIN) / (XMAX - XMIN) * box["width"],
                         box["y"] + (YMAX - y) / (YMAX - YMIN) * box["height"])
        a = json.loads(self.bridge.attack(src, 1.0, 0.0))
        stats = page.inner_text("#b-stats")
        self.assertIn("#%d" % src, stats)
        self.assertIn("%.3f / %.3f" % (a["e"], a["tau"]), stats)
        self.assertIn(("accept: " + a["name"]) if a["verdict"] == "accept" else "refuse", stats)
        page.click("#b-scan")
        page.wait_for_selector("#b-result:has-text('green rings')", timeout=120000)
        rows = json.loads(self.bridge.scan(0, 128, 0.0))
        n_acc = sum(r[1] for r in rows)
        self.assertRegex(page.inner_text("#b-result"), r"accepts waves from %d/128 neurons" % n_acc)
        page.close()

    def test_break_slider_changes_the_verdict_like_cpython(self):
        page = self.open()
        page.click("#tab-break")
        box = page.locator("#brain").bounding_box()
        x, y, _ = self.geo["nodes"][60]
        page.mouse.click(box["x"] + (x - XMIN) / (XMAX - XMIN) * box["width"],
                         box["y"] + (YMAX - y) / (YMAX - YMIN) * box["height"])
        page.fill("#b-alpha", "0")
        self.assertIn("refuse", page.inner_text("#b-stats"))
        page.close()

    def test_mobile_viewport_has_no_horizontal_overflow(self):
        page = self.open(width=390, height=844)
        for tab in ("observe", "gate", "break", "check"):
            page.click("#tab-" + tab)
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 391, tab)
        page.close()


if __name__ == "__main__":
    unittest.main()
