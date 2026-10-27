"""Demo for membrane-brain v0.1.0. Run: python demo.py"""

import random

from brain import BrainGeometry, MembraneBrain, noisy, rand_field


def main():
    brain = MembraneBrain(n=128, seed=42)
    geo = brain.geometry
    print(f"membrane-brain v0.1.0 — {len(geo.neurons)} neurons, "
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


if __name__ == "__main__":
    main()
