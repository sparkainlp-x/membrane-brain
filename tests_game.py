"""Tests for the browser game's Python side and its static files (CPython only).

Golden values at layout seed 42 are the README / RESULTS.md section 1 numbers.
The same values are asserted in the browser by tests_game_browser.py.
Run: python -m unittest tests_game -v
"""

import hashlib
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(HERE, "docs", "game")
PYDIR = os.path.join(GAME, "py")
if PYDIR not in sys.path:
    sys.path.append(PYDIR)

import bridge  # noqa: E402  (docs/game/py/bridge.py)


def read(rel, mode="r"):
    with open(os.path.join(HERE, rel), mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
        return fh.read()


class TestStaticFiles(unittest.TestCase):
    def test_game_copies_are_byte_identical_to_the_root_files(self):
        for f in ("brain.py", "rigor.py", "tests.py"):
            self.assertEqual(read(f, "rb"), read("docs/game/py/" + f, "rb"), f)

    def test_vendored_pyodide_matches_sha256sums(self):
        sums = read("docs/game/vendor/pyodide/SHA256SUMS").strip().splitlines()
        self.assertEqual(len(sums), 5)
        for line in sums:
            digest, name = line.split()
            got = hashlib.sha256(read("docs/game/vendor/pyodide/" + name, "rb")).hexdigest()
            self.assertEqual(got, digest, name)

    def test_vendored_pyodide_is_the_official_0_26_1_release(self):
        known = {  # sha256 of the files inside pyodide-core-0.26.1.tar.bz2 (GitHub release asset)
            "pyodide.js": "509cc18c8f8a650dcf739d94012726f1b9e3263312c13814c6a1e77ceffc6bd6",
            "pyodide.asm.wasm": "6513434bacb1842fcb0835289fd59f94ad4ece53637ff28e609fe5716751652f",
            "python_stdlib.zip": "d816de0c44c907f953b409c2de507a4609b3ba743df973eca8a09d3a3ed0ea47",
        }
        for name, digest in known.items():
            self.assertEqual(hashlib.sha256(read("docs/game/vendor/pyodide/" + name, "rb")).hexdigest(), digest)
        self.assertIn("0.26.1", read("docs/game/vendor/pyodide/NOTICE.md"))

    def test_page_has_a_strict_csp_and_no_external_requests(self):
        html = read("docs/game/index.html")
        csp = re.search(r'Content-Security-Policy" content="([^"]+)"', html).group(1)
        self.assertIn("default-src 'none'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("'unsafe-eval'", csp)
        self.assertIn("connect-src 'self'", csp)
        self.assertNotRegex(csp, r"https?:")
        srcs = re.findall(r'(?:src|href)="([^"]+)"', html)
        for s in srcs:
            if s.startswith("http"):
                self.assertEqual(s, "https://github.com/sparkainlp-x/membrane-brain", s)
        self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)[^>]*>")   # no inline script
        self.assertNotRegex(html, r"\sstyle=")                       # no inline style attributes
        self.assertNotRegex(html, r"\son(click|load|error)=")

    def test_scripts_make_no_third_party_requests_and_use_no_storage(self):
        js = read("docs/game/game.js")
        self.assertNotRegex(js, r"https?://")
        for banned in ("localStorage", "sessionStorage", "document.cookie", "XMLHttpRequest",
                       "navigator.sendBeacon", "WebSocket", "indexedDB", "eval(", "innerHTML = userInput"):
            self.assertNotIn(banned, js)
        self.assertEqual(sorted(set(re.findall(r'fetch\("([^"]+)"', js))), ["py/"])
        css = read("docs/game/game.css")
        self.assertNotRegex(css, r"url\(\s*['\"]?https?:")
        self.assertNotIn("@import", css)

    def test_page_states_it_is_a_toy_and_makes_no_forbidden_claims(self):
        html = read("docs/game/index.html")
        self.assertIn("A toy, not a brain.", html)
        low = (html + read("docs/game/game.js") + read("docs/game/README.md")).lower()
        for banned in ("symposium", "clinical trial", "diagnos", "consciousness"):
            self.assertNotIn(banned, low.replace("not a diagnosis", ""))
        self.assertIn("jean-françois brisson", html.lower())

    def test_every_tab_the_page_declares_has_a_panel(self):
        html = read("docs/game/index.html")
        for t in ("observe", "gate", "break", "check"):
            self.assertIn('data-tab="%s"' % t, html)
            self.assertIn('id="p-%s"' % t, html)


class TestBridgeGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = json.loads(bridge.init(42))

    def test_seed_42_structure(self):
        g = self.g
        self.assertEqual(len(g["nodes"]), 128)
        self.assertEqual(g["n_edges"], 314)
        self.assertEqual(len(g["edges"]), 314)
        self.assertEqual(g["cross"], 12)
        self.assertEqual(sum(e[2] for e in g["edges"]), 12)
        self.assertEqual(g["names"], ["left-front", "left-back", "right-front", "right-back"])
        self.assertEqual(round(g["tau"], 3), 0.238)
        self.assertEqual(round(g["youden_j"], 3), 1.0)

    def test_spread_golden_values(self):
        s = json.loads(bridge.spread(0, "intact"))
        self.assertEqual((s["n_edges"], s["n_cross"]), (314, 12))
        self.assertEqual(s["median_opposite"], 36.41)
        self.assertEqual((s["verdict"], s["name"]), ("accept", "left-front"))
        self.assertEqual(s["reached"] + s["unreachable"], 128)
        self.assertEqual(s["overlaps"][0], 1.0)

    def test_cut_is_the_same_graph_minus_the_cross_edges(self):
        a = json.loads(bridge.spread(0, "intact"))
        c = json.loads(bridge.spread(0, "cut"))
        self.assertEqual(c["n_edges"], a["n_edges"] - 12)
        self.assertEqual(c["n_cross"], 0)
        self.assertEqual(c["opp_reached"], 0)
        self.assertIsNone(c["median_opposite"])
        kept = {tuple(e[:2]) for e in c["edges"]}
        self.assertTrue(kept <= {tuple(e[:2]) for e in a["edges"]})

    def test_module_split_is_a_rewiring_not_a_cut(self):
        a = json.loads(bridge.spread(0, "intact"))
        s = json.loads(bridge.spread(0, "split"))
        c = json.loads(bridge.spread(0, "cut"))
        self.assertEqual(s["n_cross"], 0)
        self.assertEqual(s["opp_reached"], 0)
        self.assertNotEqual(s["n_edges"], c["n_edges"])
        self.assertNotEqual(s["n_edges"], a["n_edges"])

    def test_all_readme_checks_pass(self):
        for which in ("readme", "determinism", "null", "unit"):
            rows = json.loads(bridge.run_checks(which))
            self.assertTrue(rows)
            for r in rows:
                self.assertTrue(r["ok"], r)

    def test_readme_check_rows_carry_the_published_numbers(self):
        rows = {r["id"]: r for r in json.loads(bridge.run_checks("readme"))}
        self.assertEqual(rows["neurons"]["measured"], 128)
        self.assertEqual(rows["edges"]["measured"], 314)
        self.assertEqual(rows["cross"]["measured"], 12)
        self.assertEqual(rows["median"]["measured"], "36.41")
        self.assertEqual(rows["tau"]["measured"], "0.238")
        self.assertEqual(rows["j"]["measured"], "1.000")
        self.assertEqual(rows["rec"]["measured"], "40/40")
        self.assertEqual(rows["ref"]["measured"], "50/50")

    def test_a_failing_expectation_is_reported_as_failing(self):
        saved = dict(bridge.EXPECTED)
        try:
            bridge.EXPECTED["edges"] = 999
            rows = {r["id"]: r for r in json.loads(bridge.run_checks("readme"))}
            self.assertFalse(rows["edges"]["ok"])
            self.assertTrue(rows["cross"]["ok"])
        finally:
            bridge.EXPECTED.clear()
            bridge.EXPECTED.update(saved)

    def test_determinism_fingerprint_is_the_golden_one(self):
        import brain
        self.assertEqual(bridge.fingerprint(brain.MembraneBrain(n=128, seed=42).patterns),
                         bridge.GOLDEN_FINGERPRINT)

    def test_null_control_is_near_chance_and_real_accuracy_is_high(self):
        true_acc, mean, lo, hi = bridge.null_control()
        self.assertGreaterEqual(true_acc, 0.95)
        self.assertAlmostEqual(mean, 0.25, delta=0.02)
        self.assertLess(lo, 0.25)
        self.assertGreater(hi, 0.25)

    def test_rounds_are_deterministic_and_graded_from_real_overlaps(self):
        bridge.init(42)
        a = bridge.new_round(7, 1, 3)
        bridge.init(42)
        self.assertEqual(a, bridge.new_round(7, 1, 3))
        for level in range(3):
            for idx in range(bridge.ROUNDS_PER_LEVEL):
                r = json.loads(bridge.grade(7, level, idx, -1, False))
                st = bridge._S
                field = st["rounds"][(7, level, idx)]["field"]
                ovs = [abs(m) for m in st["brain"].overlaps(field)]
                self.assertAlmostEqual(r["e"], max(ovs), places=3)
                tau = st["brain"].tau
                self.assertEqual(r["verdict"], "accept" if max(ovs) >= tau else "reject")
                h = 1 - min(1, abs(max(ovs) - tau) / 0.5)
                want = round(20 + 80 * h) if r["truth"] == -1 else -round(10 + 60 * (1 - h))
                self.assertEqual(r["you_points"], want)
                self.assertEqual(r["you_ok"], r["truth"] == -1)

    def test_hint_costs_points_and_matches_the_reveal(self):
        bridge.init(42)
        h = json.loads(bridge.hint(3, 0, 0))
        r0 = json.loads(bridge.grade(3, 0, 0, -1, False))
        r1 = json.loads(bridge.grade(3, 0, 0, -1, True))
        self.assertEqual(h["overlaps"], r0["overlaps"])
        self.assertEqual(r0["you_points"] - r1["you_points"], bridge.HINT_COST)

    def test_gate_verdict_follows_the_threshold(self):
        bridge.init(42)
        tau0 = bridge._S["brain"].tau
        bridge.set_tau(0.0)
        self.assertEqual(json.loads(bridge.attack(60, 0.0, 0.0))["verdict"], "accept")   # pure random, tau 0
        bridge.set_tau(1.01)
        self.assertEqual(json.loads(bridge.attack(60, 1.0, 0.0))["verdict"], "reject")
        bridge.reset_tau()
        self.assertEqual(bridge._S["brain"].tau, tau0)

    def test_attack_on_a_stored_seed_is_accepted_but_never_counts_as_fooling(self):
        g = json.loads(bridge.init(42))
        a = json.loads(bridge.attack(g["seed_ids"][0], 1.0, 0.0))
        self.assertEqual(a["verdict"], "accept")
        self.assertTrue(a["stored"])
        self.assertFalse(a["fooled"])
        self.assertEqual(a["points"], 0)

    def test_fooled_requires_acceptance_and_distance(self):
        bridge.init(42)
        rows = json.loads(bridge.scan(0, 128, 0.0))
        self.assertEqual(len(rows), 128)
        fooled = 0
        for src, acc, _name, _e in rows:
            a = json.loads(bridge.attack(src, 1.0, 0.0))
            self.assertEqual(a["verdict"] == "accept", bool(acc))
            self.assertEqual(a["fooled"], bool(acc) and not a["stored"] and a["dist"] >= bridge.UNFAMILIAR_MIN_DIST - 1e-9)
            fooled += a["fooled"]
        self.assertGreater(fooled, 0, "the toy gate has gaps: some far, never-stored waves are accepted")

    def test_stealth_is_the_first_accepting_wave_share(self):
        bridge.init(42)
        r = json.loads(bridge.stealth(60, 0.0))
        self.assertIsNotNone(r["alpha_min"])
        self.assertEqual(json.loads(bridge.attack(60, r["alpha_min"], 0.0))["verdict"], "accept")
        if r["alpha_min"] > 0:
            self.assertEqual(json.loads(bridge.attack(60, r["alpha_min"] - 0.01, 0.0))["verdict"], "reject")

    def test_other_layout_seeds_work(self):
        g = json.loads(bridge.init(7))
        self.assertEqual(len(g["nodes"]), 128)
        self.assertTrue(0.0 < g["tau"] < 1.0)
        json.loads(bridge.spread(2, "cut"))
        bridge.init(42)


if __name__ == "__main__":
    unittest.main()
