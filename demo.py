# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Jean-Francois Brisson (Spark AI NLP)
"""Demo for membrane-brain v0.2.0. Run: python demo.py"""

import random

from brain import BrainGeometry, MembraneBrain, noisy, rand_field
import light


def main():
    brain = MembraneBrain(n=128, seed=42)
    geo = brain.geometry
    print(f"membrane-brain v0.2.0 — {len(geo.neurons)} neurons, "
          f"{len(geo.edges)} edges, {len(geo.cross_edges)} cross-hemisphere")
    left_seed = brain.seed_ids[0]
    print(f"spread: left-front wave reaches the right hemisphere "
          f"in median {brain.spread_time(left_seed):.2f} distance units")
    split = BrainGeometry(n=128, seed=42, coupling=False)
    print(f"split toy: cross edges {len(split.cross_edges)} — "
          f"right side unreachable from the left seed")

    rng = random.Random(11)
    in_probes = [noisy(brain.patterns[k % 4], 0.15, rng)
                 for k in range(100)]
    ood_probes = [rand_field(128, rng) for _ in range(100)]
    tau, j = brain.calibrate(in_probes, ood_probes)
    print(f"gate calibrated: tau = {tau:.3f}, Youden J = {j:.3f} (frozen)")

    rng2 = random.Random(99)
    ok = sum(
        1 for k in range(40)
        if brain.decide(noisy(brain.patterns[k % 4], 0.15,
                              rng2))[1] == brain.EXPERIENCE_NAMES[k % 4])
    print(f"fresh noisy recognition (sigma=0.15): {ok}/40")
    rej = sum(
        1 for _ in range(50)
        if brain.decide(rand_field(128, rng2))[0] == "reject")
    print(f"fresh random fields refused: {rej}/50")
    clean = brain.decide(brain.patterns[0])
    print(f"clean left-front probe -> {clean[0]}: {clean[1]}")

    # v0.2.0 light section: headline numbers from the frozen protocol
    # (sigma 0.40, 200 trials, seed 20261117; full table in
    # results/results_light.json). brain.py behaviour is untouched.
    m = light.measure_all(brain)
    c = m["claims"]
    print(f"light: dose 0 recall {c['i_biphasic']['recall_dose_0']:.3f}, "
          f"optimum (dose 50) {c['i_biphasic']['recall_optimum']:.3f}, "
          f"3x optimum {c['i_biphasic']['recall_3x_optimum']:.3f}")
    print(f"light: stress 0 -> 1 recall "
          f"{m['stress_rows'][0]['recall']:.3f} -> "
          f"{m['stress_rows'][-1]['recall']:.3f}")
    print(f"light: dose gap {c['iii_dose_beats_wavelength']['dose_gap']:.3f} "
          f"vs wavelength gap "
          f"{c['iii_dose_beats_wavelength']['wavelength_gap']:.3f}")
    print(f"light: early {c['iv_early_beats_late']['early_recall']:.3f} "
          f"vs late {c['iv_early_beats_late']['late_recall']:.3f}")


if __name__ == "__main__":
    main()
