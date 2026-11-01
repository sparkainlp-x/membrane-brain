"""Numerical stability and edge-case tests for membrane-brain.

Run:
    python tests_numerical.py
"""

import math
import unittest

from brain import MembraneBrain, normalize, overlap


class TestNumericalStability(unittest.TestCase):
    def test_normalize_rejects_zero_and_tiny_vectors(self):
        for bad_vector in ([0j], [1e-300 + 0j]):
            with self.assertRaises(ValueError):
                normalize(bad_vector)

    def test_normalize_preserves_direction_and_unit_norm(self):
        vector = [3 + 4j, 1 - 2j]
        unit = normalize(vector)

        self.assertAlmostEqual(
            math.sqrt(sum(abs(component) ** 2 for component in unit)),
            1.0,
            places=12,
        )

        first_ratio = (unit[0] / vector[0]).real
        second_ratio = (unit[1] / vector[1]).real
        self.assertAlmostEqual(first_ratio, second_ratio, places=12)

    def test_overlap_matches_conjugate_linear_definition(self):
        field = [1 + 1j, 2 - 1j]
        pattern = [1j, 1]

        expected = (
            pattern[0].conjugate() * field[0]
            + pattern[1].conjugate() * field[1]
        )
        result = overlap(field, pattern)

        self.assertAlmostEqual(result.real, expected.real, places=12)
        self.assertAlmostEqual(result.imag, expected.imag, places=12)

    def test_zero_field_projection_refuses(self):
        brain = MembraneBrain(n=64, seed=42)
        winner, probabilities = brain.project([0j] * 64)

        self.assertIsNone(winner)
        self.assertEqual(probabilities, [0.0] * len(brain.patterns))

    def test_calibrate_rejects_empty_probe_sets(self):
        brain = MembraneBrain(n=64, seed=42)

        with self.assertRaises(ValueError):
            brain.calibrate([], [])

    def test_wave_patterns_are_finite_and_unit_norm(self):
        brain = MembraneBrain(n=128, seed=42)

        for pattern in brain.patterns:
            self.assertTrue(
                all(
                    math.isfinite(component.real)
                    and math.isfinite(component.imag)
                    for component in pattern
                )
            )
            self.assertAlmostEqual(
                math.sqrt(sum(abs(component) ** 2 for component in pattern)),
                1.0,
                places=12,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
