# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Jean-Francois Brisson (Spark AI NLP)
"""Tests for the light injection (light.py). Run: python tests_light.py

PRE-REGISTERED CLAIMS — thresholds frozen here BEFORE the measurement
run below. Never move a threshold to force a pass; a FAIL is a result.

  (i)   BIPHASIC: recall at the optimum dose exceeds recall at dose 0
        AND at 3x optimum by >= 0.05 each.
  (ii)  STRESS: recall falls monotonically (non-increasing at every
        step, total drop >= 0.10) across the stress grid.
  (iii) DOSE BEATS WAVELENGTH: same wavelength, dose 0 vs optimum
        gives a recall gap; same dose, wavelengths 630/808/980 nm give
        a smaller gap; require dose-gap > 2x wavelength-gap.
  (iv)  EARLY BEATS LATE: same total light, before stress onset vs
        after onset: early recall exceeds late recall by >= 0.05.

One frozen protocol for all four: sigma 0.40, 200 trials, seed
20261117 (light.MEASUREMENT_*). The committed results file
(results/results_light.json) must equal a fresh light.measure_all().
"""

import json
import math
import os
import unittest

from brain import MembraneBrain
import light

HERE = os.path.dirname(os.path.abspath(__file__))

# Frozen thresholds (must match light.CLAIM_*; asserted in test_thresholds_are_frozen).
BIPHASIC_MIN_GAP = 0.05
STRESS_MIN_DROP = 0.10
DOSE_WL_MIN_RATIO = 2.0
EARLY_MIN_GAP = 0.05


class TestThresholdsFrozen(unittest.TestCase):
    def test_thresholds_are_frozen(self):
        self.assertEqual(light.CLAIM_BIPHASIC_MIN_GAP, BIPHASIC_MIN_GAP)
        self.assertEqual(light.CLAIM_STRESS_MIN_DROP, STRESS_MIN_DROP)
        self.assertEqual(light.CLAIM_DOSE_WL_MIN_RATIO, DOSE_WL_MIN_RATIO)
        self.assertEqual(light.CLAIM_EARLY_MIN_GAP, EARLY_MIN_GAP)


class TestLightUnits(unittest.TestCase):
    def test_atp_curve_is_biphasic_with_interior_optimum(self):
        self.assertEqual(light.atp_factor(0.0), 1.0)
        self.assertGreater(light.atp_factor(light.DOSE_OPT),
                           light.atp_factor(0.0))
        self.assertGreater(light.atp_factor(light.DOSE_OPT),
                           light.atp_factor(3 * light.DOSE_OPT))
        # Rises to the optimum, then declines: 25 < 50 > 100 > 150.
        atps = [light.atp_factor(d) for d in (25.0, 50.0, 100.0, 150.0)]
        self.assertLess(atps[0], atps[1])
        self.assertLess(atps[2], atps[1])
        self.assertLess(atps[3], atps[2])
        self.assertGreater(light.atp_factor(1000.0), 1.0)
        self.assertLess(light.atp_factor(1000.0),
                        light.atp_factor(3 * light.DOSE_OPT))

    def test_atp_rejects_negative_dose(self):
        with self.assertRaises(ValueError):
            light.atp_factor(-1.0)

    def test_wavelength_efficiency_is_wide_and_peaked_at_808(self):
        self.assertEqual(light.wavelength_efficiency(808.0), 1.0)
        for wl in (630.0, 980.0):
            eff = light.wavelength_efficiency(wl)
            self.assertLess(eff, 1.0)
            self.assertGreater(eff, 0.5)  # WIDE: wavelength is a weak modulation
        with self.assertRaises(ValueError):
            light.wavelength_efficiency(0.0)

    def test_protection_is_a_fraction_rising_with_dose(self):
        self.assertEqual(light.protection(0.0), 0.0)
        p = light.protection(light.DOSE_OPT)
        self.assertGreater(p, 0.0)
        self.assertLess(p, 1.0)
        self.assertLess(light.protection(25.0), p)

    def test_sigma_effective_light_lowers_it_stress_raises_it(self):
        base = light.sigma_effective(0.40, 0.0, 0.0)
        self.assertEqual(base, 0.40)
        lit = light.sigma_effective(0.40, light.DOSE_OPT, 0.0)
        self.assertLess(lit, base)
        stressed = light.sigma_effective(0.40, 0.0, 1.0)
        self.assertGreater(stressed, base)
        self.assertAlmostEqual(stressed, 0.40 * (1.0 + light.STRESS_GAIN))
        with self.assertRaises(ValueError):
            light.sigma_effective(0.40, 0.0, 1.5)
        with self.assertRaises(ValueError):
            light.sigma_effective(0.0, 0.0, 0.0)

    def test_stress_after_rules(self):
        # No light: full rate after onset, capped at 1.
        self.assertAlmostEqual(light.stress_after(12, 2, 0.10, None, 0.0), 1.0)
        self.assertAlmostEqual(light.stress_after(5, 2, 0.10, None, 0.0), 0.30)
        # Nothing accumulates before onset.
        self.assertEqual(light.stress_after(2, 2, 0.10, None, 0.0), 0.0)
        # Early light ends with less stress than late light, same dose.
        p = light.protection(light.DOSE_OPT)
        early = light.stress_after(12, 2, 0.10, 0, p)
        late = light.stress_after(12, 2, 0.10, 10, p)
        self.assertLess(early, late)
        # Light cannot remove stress already accumulated: late light
        # still ends above the no-stress baseline, and above early.
        self.assertGreater(late, 0.0)
        # Stronger protection -> less final stress.
        self.assertLess(light.stress_after(12, 2, 0.10, 0, 0.9),
                        light.stress_after(12, 2, 0.10, 0, 0.1))
        with self.assertRaises(ValueError):
            light.stress_after(12, 2, 0.10, 0, 1.0)

    def test_determinism(self):
        brain = MembraneBrain(n=128, seed=42)
        a = light.recall_at(brain, 0.30)
        b = light.recall_at(brain, 0.30)
        self.assertEqual(a, b)
        self.assertEqual(light.simulate(brain, 50.0, light_time=0),
                         light.simulate(brain, 50.0, light_time=0))
        self.assertEqual(light.measure_all(), light.measure_all())


class TestPreRegisteredClaims(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = light.measure_all()

    def test_i_biphasic(self):
        c = self.m["claims"]["i_biphasic"]
        self.assertGreaterEqual(c["gap_optimum_minus_zero"], BIPHASIC_MIN_GAP)
        self.assertGreaterEqual(c["gap_optimum_minus_3x"], BIPHASIC_MIN_GAP)
        self.assertTrue(c["pass"], c)

    def test_ii_stress(self):
        c = self.m["claims"]["ii_stress"]
        self.assertTrue(c["non_increasing"], c["recalls"])
        self.assertGreaterEqual(c["total_drop"], STRESS_MIN_DROP)
        self.assertTrue(c["pass"], c)

    def test_iii_dose_beats_wavelength(self):
        c = self.m["claims"]["iii_dose_beats_wavelength"]
        self.assertGreater(c["dose_gap"],
                           DOSE_WL_MIN_RATIO * c["wavelength_gap"])
        self.assertTrue(c["pass"], c)

    def test_iv_early_beats_late(self):
        c = self.m["claims"]["iv_early_beats_late"]
        self.assertGreaterEqual(c["gap"], EARLY_MIN_GAP)
        self.assertTrue(c["pass"], c)


class TestCommittedLightResults(unittest.TestCase):
    def test_results_light_json_matches_a_fresh_computation(self):
        path = os.path.join(HERE, "results", "results_light.json")
        with open(path, encoding="utf-8") as fh:
            committed = json.load(fh)
        self.assertEqual(committed, light.measure_all())
        self.assertEqual(committed["version"], "0.2.0")
        self.assertTrue(all(c["pass"]
                            for c in committed["claims"].values()),
                        committed["claims"])

    def test_results_light_json_has_no_clinical_claim(self):
        path = os.path.join(HERE, "results", "results_light.json")
        with open(path, encoding="utf-8") as fh:
            text = fh.read().lower()
        for banned in ("treat", "prevent", "cure", "therapy", "patient"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
