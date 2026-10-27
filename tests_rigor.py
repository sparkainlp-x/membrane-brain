"""Tests for the rigor experiments (rigor.py, render_results.py) and the
packaging metadata. Standard library only. Run: python tests_rigor.py
"""

import json
import math
import os
import random
import re
import unittest

import brain
import render_results
import rigor
from brain import BrainGeometry, MembraneBrain, noisy, rand_field

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


class TestStatistics(unittest.TestCase):
    def test_wilson_known_values(self):
        lo, hi = rigor.wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.2775, places=3)
        lo, hi = rigor.wilson(5, 10)
        self.assertAlmostEqual(lo + hi, 1.0, places=9)
        self.assertAlmostEqual(rigor.wilson(10, 10)[1], 1.0, places=12)
        self.assertTrue(math.isnan(rigor.wilson(0, 0)[0]))
        lo, hi = rigor.wilson(50, 100)       # textbook: 0.404 to 0.596
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)

    def test_auc_known_values(self):
        self.assertEqual(rigor.auc([3, 4], [1, 2]), 1.0)
        self.assertEqual(rigor.auc([1, 2], [3, 4]), 0.0)
        self.assertEqual(rigor.auc([1, 1], [1, 1]), 0.5)
        self.assertAlmostEqual(rigor.auc([1, 3], [2]), 0.5)

    def test_ranks_and_spearman(self):
        self.assertEqual(rigor.ranks([1, 1, 2]), [1.5, 1.5, 3.0])
        a = [1, 2, 3, 4, 5]
        self.assertAlmostEqual(rigor.spearman(a, [x * x for x in a]), 1.0)
        self.assertAlmostEqual(rigor.spearman(a, a[::-1]), -1.0)
        self.assertTrue(math.isnan(rigor.spearman(a, [1] * 5)))

    def test_bootstrap_is_deterministic_and_brackets_the_mean(self):
        vals = [0.2, 0.4, 0.5, 0.9, 0.3, 0.6]
        a = rigor.boot_ci(vals, 500, "t")
        self.assertEqual(a, rigor.boot_ci(vals, 500, "t"))
        self.assertLessEqual(a[0], rigor.mean(vals))
        self.assertGreaterEqual(a[1], rigor.mean(vals))
        self.assertEqual(rigor.boot_ci([0.5] * 5, 100, "t"), (0.5, 0.5))

    def test_streams_are_reproducible_and_separate(self):
        self.assertEqual(rigor.stream("a", 1).random(),
                         rigor.stream("a", 1).random())
        self.assertNotEqual(rigor.stream("a", 1).random(),
                            rigor.stream("b", 1).random())
        self.assertNotEqual(rigor.stream("a", 1).random(),
                            rigor.stream("a", 2).random())

    def test_clean_replaces_non_finite(self):
        self.assertEqual(rigor.clean({"a": [math.inf, 1.0, float("nan")]}),
                         {"a": [None, 1.0, None]})


class TestVariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rigor.clear_cache()
        cls.b = rigor.get_brain(42)

    def test_get_brain_is_cached_and_matches_brain_py(self):
        self.assertIs(rigor.get_brain(42), self.b)
        self.assertEqual(self.b.patterns, MembraneBrain(n=128, seed=42).patterns)

    def test_cut_geometry_removes_exactly_the_cross_edges(self):
        g = self.b.geometry
        c = rigor.cut_geometry(g)
        self.assertEqual(c.cross_edges, [])
        self.assertEqual(sorted(c.edges + g.cross_edges), sorted(g.edges))
        self.assertTrue(set(c.edges) <= set(g.edges))
        # the original is untouched
        self.assertEqual(len(g.cross_edges), 12)
        delays = c.delays_from(self.b.seed_ids[0])
        right = [d for n, d in zip(c.neurons, delays)
                 if n.hemisphere == "right"]
        self.assertTrue(all(math.isinf(d) for d in right))

    def test_module_split_is_a_rewiring_not_a_cut(self):
        g = self.b.geometry
        cut = rigor.cut_geometry(g)
        rew = BrainGeometry(n=128, seed=42, coupling=False)
        self.assertNotEqual(set(cut.edges), set(rew.edges))

    def test_random_geometry(self):
        g = self.b.geometry
        r1 = rigor.random_geometry(g, 5)
        r2 = rigor.random_geometry(g, 5)
        r3 = rigor.random_geometry(g, 6)
        self.assertEqual(r1.edges, r2.edges)
        self.assertNotEqual(r1.edges, r3.edges)
        deg = {n.id: 0 for n in g.neurons}
        for a, b in r1.edges:
            deg[a] += 1
            deg[b] += 1
        self.assertGreaterEqual(min(deg.values()), g.k)
        self.assertEqual(len(r1.neurons), 128)
        self.assertEqual(len(g.edges), 314)  # original untouched

    def test_pure_phase_brain_has_flat_amplitude(self):
        pb = rigor.pure_phase_brain(self.b)
        for p, sid in zip(pb.patterns, self.b.seed_ids):
            self.assertAlmostEqual(
                math.sqrt(sum(abs(c) ** 2 for c in p)), 1.0, places=9)
            delays = self.b.geometry.delays_from(sid)
            mags = {round(abs(c), 9) for c, d in zip(p, delays)
                    if math.isfinite(d)}
            self.assertEqual(len(mags), 1)       # one amplitude everywhere
        self.assertIsNone(pb.tau)

    def test_global_phase_is_invisible_to_overlap(self):
        p = self.b.patterns[0]
        q = [c * complex(math.cos(1.234), math.sin(1.234)) for c in p]
        self.assertAlmostEqual(abs(brain.overlap(q, p)), 1.0, places=12)

    def test_random_pattern_brain(self):
        a = rigor.random_pattern_brain(self.b, 3)
        b = rigor.random_pattern_brain(self.b, 3)
        self.assertEqual(a.patterns, b.patterns)
        self.assertEqual(len(a.patterns), 4)
        self.assertNotEqual(a.patterns[0], self.b.patterns[0])

    def test_variants_do_not_mutate_the_source_brain(self):
        before = list(self.b.patterns[0])
        rigor.pure_phase_brain(self.b)
        rigor.with_geometry(self.b, rigor.cut_geometry(self.b.geometry))
        self.assertEqual(self.b.patterns[0], before)
        self.assertEqual(len(self.b.geometry.cross_edges), 12)


class TestScoring(unittest.TestCase):
    def test_score_matches_decide(self):
        rigor.clear_cache()
        b = rigor.calibrated(7)
        self.assertIsNotNone(b.tau)
        rng = random.Random(3)
        plist = rigor.probes(b, rng, 0.2, 10)
        s = rigor.score(b, plist)
        acc = sum(1 for f, _ in plist if b.decide(f)[0] == "accept")
        ok = sum(1 for f, lab in plist
                 if b.decide(f)[1] == b.EXPERIENCE_NAMES[lab])
        self.assertEqual(s["n"], 40)
        self.assertEqual(s["accept"], acc)
        self.assertEqual(s["accept_ok"], ok)
        self.assertEqual(s["accept"], s["accept_ok"] + s["accept_wrong"])

    def test_calibrated_does_not_modify_the_cached_brain(self):
        rigor.clear_cache()
        b = rigor.calibrated(3)
        self.assertIsNone(rigor.get_brain(3).tau)
        self.assertIsNotNone(b.tau)
        self.assertEqual(rigor.calibrated(3).tau, b.tau)

    def test_refusals_counts_below_tau(self):
        rigor.clear_cache()
        b = rigor.calibrated(1)
        rng = random.Random(0)
        fields = [rand_field(128, rng) for _ in range(50)]
        r = rigor.refusals(b, fields)
        self.assertEqual(r, sum(1 for f in fields
                                if b.decide(f)[0] == "reject"))

    def test_noiseless_probes_are_always_recognised(self):
        rigor.clear_cache()
        b = rigor.calibrated(2)
        s = rigor.score(b, rigor.probes(b, random.Random(1), 0.0, 5))
        self.assertEqual(s["argmax_ok"], 20)
        self.assertEqual(s["accept_ok"], 20)

    def test_tau_sweep_endpoints(self):
        rows = rigor.sweep_tau([0.5, 0.6], [0.1, 0.2], [0.0, 0.3, 1.0])
        self.assertEqual(rows[0], (0.0, 1.0, 0.0, 1.0 - 1.0))
        self.assertEqual(rows[1], (0.3, 1.0, 1.0, 1.0))
        self.assertEqual(rows[2], (1.0, 0.0, 1.0, 0.0))


class TestSplitHelpers(unittest.TestCase):
    def test_fast_delays_equal_the_module_dijkstra(self):
        geo = BrainGeometry(n=128, seed=42)
        for src in (0, 55, 120):
            self.assertEqual(rigor.fast_delays(geo, src),
                             geo.delays_from(src))

    def test_seed_42_known_structure(self):
        geo = BrainGeometry(n=128, seed=42)
        self.assertEqual(rigor.components(geo), 2)
        cut = rigor.cut_geometry(geo)
        self.assertEqual(rigor.components(cut), 3)
        b = MembraneBrain(n=128, seed=42)
        unreach, med = rigor.cross_stats(geo, b.seed_ids[0])
        self.assertAlmostEqual(unreach, 22 / 64)       # the isolated fragment
        self.assertEqual(med, b.spread_time(b.seed_ids[0]))
        self.assertEqual(rigor.cross_stats(cut, b.seed_ids[0])[0], 1.0)
        self.assertTrue(math.isinf(rigor.cross_stats(cut, b.seed_ids[0])[1]))

    def test_left_seeds_are_left_hemisphere(self):
        geo = BrainGeometry(n=128, seed=9)
        for s in rigor.left_seeds(geo):
            self.assertEqual(geo.neurons[s].hemisphere, "left")


class TestExperiments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = rigor.clean(rigor.run_all(rigor.QUICK))

    def test_reproduction_matches_the_readme(self):
        r = self.res["reproduction"]
        self.assertEqual((r["neurons"], r["edges"], r["cross_edges"]),
                         (128, 314, 12))
        self.assertEqual(round(r["median_delay"], 2), 36.41)
        self.assertEqual(r["split_cross_edges"], 0)
        self.assertEqual(round(r["tau"], 3), 0.238)
        self.assertEqual(round(r["youden_j"], 3), 1.0)
        self.assertEqual((r["recognition_ok"], r["recognition_n"]), (40, 40))
        self.assertEqual((r["refused"], r["refused_n"]), (50, 50))
        self.assertEqual(r["clean_left_front"], "left-front")

    def test_run_is_deterministic(self):
        again = rigor.clean(rigor.run_all(rigor.QUICK))
        self.assertEqual(self.res, again)
        json.dumps(self.res, sort_keys=True)     # JSON-serialisable

    def test_multiseed_basics(self):
        m = self.res["multiseed"]
        self.assertEqual(m["seeds"], rigor.QUICK["multiseed_seeds"])
        self.assertGreater(m["gated_correct"]["rate"], 0.9)
        self.assertGreater(m["random_refused"]["rate"], 0.9)
        lo, hi = m["gated_correct"]["wilson"]
        self.assertLessEqual(lo, m["gated_correct"]["rate"])
        self.assertGreaterEqual(hi, m["gated_correct"]["rate"])
        self.assertLessEqual(m["gated_correct"]["rate"],
                             m["argmax_correct"]["rate"] + 1e-12)

    def test_noise_zero_is_perfect_and_high_noise_degrades(self):
        rows = {r["sigma"]: r for r in self.res["noise"]["rows"]}
        self.assertEqual(rows[0.0]["argmax_ok"]["rate"], 1.0)
        self.assertLess(rows[0.6]["argmax_ok"]["rate"],
                        rows[0.0]["argmax_ok"]["rate"])
        self.assertLess(rows[0.6]["accept"]["rate"], 0.5)

    def test_null_controls(self):
        n = self.res["nulls"]
        self.assertTrue(0.1 < n["shuffled_labels"]["rate"] < 0.4)
        self.assertLess(n["shuffled_calibration_j_in_sample"]["mean"], 0.5)
        self.assertGreater(n["global_phase_overlap"]["min"], 1 - 1e-9)
        self.assertGreater(n["real"]["gated_correct"]["rate"], 0.9)
        for key in ("pure_phase", "random_graph", "random_patterns"):
            self.assertIn("argmax_correct", n[key])

    def test_tau_curve(self):
        c = self.res["tau"]["curve"]
        self.assertEqual(c[0]["tau"], 0.0)
        self.assertEqual(c[0]["accept_true"], 1.0)
        self.assertEqual(c[0]["refuse_random"], 0.0)
        self.assertEqual(c[-1]["accept_true"], 0.0)
        self.assertGreater(self.res["tau"]["auc_random_ood"]["mean"], 0.99)

    def test_split_is_unreachable_by_construction(self):
        s = self.res["split"]
        self.assertEqual(s["cut_left_wave_unreachable_fraction_min"], 1.0)
        self.assertEqual(s["rewired_left_wave_unreachable_fraction_min"], 1.0)
        self.assertGreater(s["rewire_differs_from_cut"], 0)

    def test_cut_recognition_rows(self):
        rows = self.res["cut_recognition"]["rows"]
        self.assertEqual([r["width"] for r in rows],
                         rigor.QUICK["cut_widths"])
        self.assertGreater(rows[0]["overlap_intact_vs_cut_pattern"]["mean"],
                           rows[-1]["overlap_intact_vs_cut_pattern"]["mean"])
        self.assertLess(rows[0]["energy_in_opposite_hemisphere"]["mean"],
                        rows[-1]["energy_in_opposite_hemisphere"]["mean"])


class TestCommittedResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "results", "results.json"),
                  encoding="utf-8") as fh:
            cls.res = json.load(fh)

    def test_results_md_is_the_rendering_of_results_json(self):
        self.assertEqual(read("RESULTS.md"), render_results.render(self.res))

    def test_json_is_the_full_configuration(self):
        self.assertEqual(self.res["config"], rigor.clean(rigor.FULL))
        self.assertEqual(self.res["multiseed"]["seeds"], 200)

    def test_reproduction_in_json_matches_a_fresh_computation(self):
        fresh = rigor.clean(rigor.e_reproduction())
        self.assertEqual(self.res["reproduction"], fresh)

    def test_results_md_keeps_the_honest_framing(self):
        t = read("RESULTS.md")
        self.assertIn("This is a toy, not a brain", t)
        self.assertIn("## 9. Honest limits", t)
        self.assertIn("does **not** reproduce", t)
        self.assertNotIn("doi.org", t.lower())


class TestMetadata(unittest.TestCase):
    def test_versions_and_authors_agree(self):
        v = brain.__version__
        self.assertEqual(v, "0.1.0")
        self.assertIn('version = "%s"' % v, read("pyproject.toml"))
        self.assertIn("version: %s" % v, read("CITATION.cff"))
        z = json.loads(read(".zenodo.json"))
        self.assertEqual(z["version"], v)
        self.assertEqual(z["license"], "AGPL-3.0-only")
        self.assertEqual(z["creators"][0]["orcid"], "0009-0000-9778-5374")
        self.assertEqual(z["creators"][0]["name"], "Brisson, Jean-François")
        self.assertIn("0009-0000-9778-5374", read("CITATION.cff"))
        self.assertIn("Jean-François", read("CITATION.cff"))

    def test_no_invented_doi(self):
        self.assertIsNone(re.search(r"^doi:", read("CITATION.cff"), re.M))
        self.assertNotIn("10.5281", read("CITATION.cff"))
        self.assertNotIn("10.5281", read(".zenodo.json"))
        self.assertNotIn("10.5281", read("README.md"))

    def test_ci_matrix_is_310_to_313(self):
        w = read(os.path.join(".github", "workflows", "tests.yml"))
        for v in ("3.10", "3.11", "3.12", "3.13"):
            self.assertIn('"%s"' % v, w)


if __name__ == "__main__":
    unittest.main(verbosity=2)
