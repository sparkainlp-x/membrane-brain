"""Tests for membrane-brain v0.1.0. Run: python tests.py"""

import math
import random
import unittest

from brain import (
    BrainGeometry,
    MembraneBrain,
    noisy,
    rand_field,
)


class TestMembraneBrain(unittest.TestCase):
    def test_geometry_two_hemispheres_and_coupling(self):
        geo = BrainGeometry(n=128, seed=42)
        self.assertEqual(len(geo.neurons), 128)
        left = [n for n in geo.neurons if n.hemisphere == "left"]
        right = [n for n in geo.neurons if n.hemisphere == "right"]
        self.assertEqual(len(left), 64)
        self.assertEqual(len(right), 64)
        self.assertGreater(len(geo.cross_edges), 0)

    def test_patterns_unit_and_distinct(self):
        brain = MembraneBrain(n=128, seed=42)
        self.assertEqual(len(brain.patterns), 4)
        for p in brain.patterns:
            self.assertAlmostEqual(
                math.sqrt(sum(abs(c) ** 2 for c in p)), 1.0, places=9)
        for i in range(4):
            for j in range(i + 1, 4):
                ov = abs(sum(a.conjugate() * b for a, b
                             in zip(brain.patterns[i],
                                    brain.patterns[j])))
                self.assertLess(ov, 0.95)

    def test_clean_experience_recognition(self):
        brain = MembraneBrain(n=128, seed=42)
        brain.tau = None
        for i, p in enumerate(brain.patterns):
            verdict, name, _ = brain.decide(p)
            self.assertEqual(verdict, "accept")
            self.assertEqual(name, brain.EXPERIENCE_NAMES[i])

    def test_noisy_recognition(self):
        brain = MembraneBrain(n=128, seed=42)
        brain.tau = None
        rng = random.Random(7)
        ok, trials = 0, 40
        for k in range(trials):
            probe = noisy(brain.patterns[k % 4], 0.15, rng)
            _, name, _ = brain.decide(probe)
            ok += name == brain.EXPERIENCE_NAMES[k % 4]
        self.assertGreaterEqual(ok / trials, 0.90)

    def test_gate_refuses_random(self):
        brain = MembraneBrain(n=128, seed=42)
        rng = random.Random(11)
        in_probes = [noisy(brain.patterns[k % 4], 0.15, rng)
                     for k in range(100)]
        ood_probes = [rand_field(128, rng) for _ in range(100)]
        tau, j = brain.calibrate(in_probes, ood_probes)
        self.assertGreater(j, 0.90)
        self.assertGreater(tau, 0.2)
        self.assertLess(tau, 0.95)
        rng2 = random.Random(99)
        accepted = sum(
            1 for k in range(50)
            if brain.decide(noisy(brain.patterns[k % 4], 0.15,
                                  rng2))[0] == "accept")
        rejected = sum(
            1 for _ in range(50)
            if brain.decide(rand_field(128, rng2))[0] == "reject")
        self.assertGreaterEqual(accepted / 50, 0.90)
        self.assertGreaterEqual(rejected / 50, 0.90)

    def test_split_blocks_cross_spread(self):
        full = BrainGeometry(n=128, seed=42, coupling=True)
        split = BrainGeometry(n=128, seed=42, coupling=False)
        self.assertEqual(len(split.cross_edges), 0)
        left_seed = full.nearest_neuron(-17.0, 5.0)
        delays = split.delays_from(left_seed)
        right_delays = [d for neu, d in zip(split.neurons, delays)
                        if neu.hemisphere == "right"]
        self.assertTrue(all(math.isinf(d) for d in right_delays))
        # With coupling, the same wave does reach the other side.
        brain = MembraneBrain(n=128, seed=42)
        self.assertTrue(math.isfinite(brain.spread_time(left_seed)))

    def test_determinism(self):
        a = MembraneBrain(n=64, seed=123)
        b = MembraneBrain(n=64, seed=123)
        self.assertEqual(a.patterns, b.patterns)
        self.assertEqual(a.geometry.edges, b.geometry.edges)


if __name__ == "__main__":
    unittest.main(verbosity=2)
