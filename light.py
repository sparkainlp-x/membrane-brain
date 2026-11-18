# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Jean-Francois Brisson (Spark AI NLP)
"""membrane-brain v0.2.0 — light injection: 808 nm PBM-style light dose
coupled into the membrane brain (stdlib only, seeded, reproducible).

The coupling, in one sentence: light raises an ATP proxy, ATP lowers the
effective probe noise, mitochondrial stress raises it again, and light
applied before stress onset protects more than the same light applied
after it. One mechanism only — energy lowers effective noise:

    sigma_eff = sigma * (1 + STRESS_GAIN * stress) / atp_factor(dose, wl)

with a hormetic (biphasic) ATP curve

    atp = 1 + GAIN * dose * exp(-dose / DOSE_OPT) * efficiency(wl)

peaked at DOSE_OPT, and a WIDE wavelength efficiency peaked at 808 nm,
so dose is the strong predictor and wavelength a weak modulation.

Timing rules (explicit, and the whole point of the early-vs-late claim):
stress is 0 before `onset`, then grows by `rate` per step, capped at 1.
Light applied at step `light_time` multiplies later increments by
(1 - protection), where protection = 1 - 1/atp. Stress already
accumulated is NEVER removed: late light slows further damage but
cannot restore already-fragmented patterns. Early light therefore ends
with less stress than the same dose applied late.

Honest limits — read before any use
------------------------------------
Synthetic toy model, not a brain, not a medical device, not a treatment
and not a prevention claim. This module tests the CODE's light-energy
coupling — whether recall in this toy moves with dose, stress and
timing in the directions the four pre-registered claims state. It says
nothing about whether light treats or prevents disease in a person.
The clinical PBM evidence is mixed: a 2026 randomized double-blind
trial (80 people, mild cognitive impairment due to Alzheimer's, 808 nm,
6x/week, 12 weeks) showed better cognitive outcomes vs placebo, while
a 2026 systematic review (Photonics 2026, 13, 488; 30 studies, ~2244
participants) found Alzheimer's cognition benefit only at adequate
irradiance (GRADE moderate), Parkinson's motor benefit mixed (GRADE
low) and no benefit for acute ischaemic stroke (GRADE high). Dose
(irradiance) matters more than wavelength alone. No prevention claim
is proven. None of the numbers here are clinical evidence.
"""

import json
import math
import random

from brain import MembraneBrain, noisy

__version__ = "0.2.0"

# ---------------------------------------------------------------- constants
# Toy light-dose units (NOT J/cm^2, NOT a clinical dose). Chosen during
# design so the toy's effects sit on the steep part of the recall-vs-
# noise curve (see DESIGN.md); the claim thresholds were frozen after
# the design was fixed and before the official measurement run.
DOSE_OPT = 50.0        # interior optimum of the hormetic ATP curve
GAIN = 0.03            # ATP gain per unit dose at the optimum shape
BASE_ATP = 1.0         # ATP factor at dose 0 (no light)
WL_PEAK = 808.0        # PBM wavelength, nm
WL_WIDTH = 300.0       # WIDE Gaussian width: wavelength is a weak modulation
STRESS_GAIN = 1.5      # stress 1.0 multiplies effective noise by 2.5

# Frozen measurement protocol (one protocol for all four claims).
MEASUREMENT_SIGMA = 0.40
MEASUREMENT_TRIALS = 200
MEASUREMENT_SEED = 20261117
DOSE_GRID = (0.0, 25.0, 50.0, 100.0, 150.0)
STRESS_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
WAVELENGTHS = (630.0, 808.0, 980.0)
TIMING_STEPS = 12
TIMING_ONSET = 2
TIMING_RATE = 0.10
EARLY_TIME = 0    # light before stress onset
LATE_TIME = 10    # same light, well after stress onset

# Frozen claim thresholds (also asserted literally in tests_light.py;
# never moved to force a pass).
CLAIM_BIPHASIC_MIN_GAP = 0.05   # (i) optimum beats dose 0 AND 3x optimum
CLAIM_STRESS_MIN_DROP = 0.10    # (ii) total recall drop across stress grid
CLAIM_DOSE_WL_MIN_RATIO = 2.0   # (iii) dose gap > 2x wavelength gap
CLAIM_EARLY_MIN_GAP = 0.05      # (iv) early beats late


# ---------------------------------------------------------------- light
def wavelength_efficiency(wavelength_nm):
    """Wide Gaussian peaked at 808 nm; 1.0 at the peak, < 1 elsewhere."""
    if wavelength_nm <= 0:
        raise ValueError("wavelength must be positive")
    return math.exp(-((wavelength_nm - WL_PEAK) / WL_WIDTH) ** 2)


def atp_factor(dose, wavelength_nm=808.0):
    """Hormetic ATP proxy: 1 at dose 0, peak at DOSE_OPT, declines after.

    Biphasic by construction: dose * exp(-dose / DOSE_OPT) rises to the
    optimum and falls toward zero, so ATP returns toward baseline at
    high dose instead of saturating.
    """
    if dose < 0:
        raise ValueError("dose must be >= 0")
    return (BASE_ATP + GAIN * dose * math.exp(-dose / DOSE_OPT)
            * wavelength_efficiency(wavelength_nm))


def protection(dose, wavelength_nm=808.0):
    """Fraction of later stress increments blocked by the light.

    0 at dose 0, rising with ATP toward (but never reaching) 1.
    """
    return 1.0 - 1.0 / atp_factor(dose, wavelength_nm)


def sigma_effective(sigma, dose, stress, wavelength_nm=808.0):
    """Effective probe noise: ATP lowers it, stress raises it."""
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    if not 0.0 <= stress <= 1.0:
        raise ValueError("stress must be in [0, 1]")
    return sigma * (1.0 + STRESS_GAIN * stress) / atp_factor(dose, wavelength_nm)


def stress_after(steps, onset, rate, light_time, prot):
    """Final stress after `steps` time steps (pure helper, unit-tested).

    Stress is 0 before `onset`, then +rate per step, capped at 1.0.
    Light applied at step `light_time` (None = no light) multiplies
    later increments by (1 - prot); stress already accumulated stays.
    """
    if steps < 0 or onset < 0 or rate < 0:
        raise ValueError("steps, onset and rate must be >= 0")
    if not 0.0 <= prot < 1.0:
        raise ValueError("protection must be in [0, 1)")
    if light_time is not None and light_time < 0:
        raise ValueError("light_time must be >= 0 or None")
    stress = 0.0
    for t in range(steps):
        inc = rate if t >= onset else 0.0
        if light_time is not None and t >= light_time:
            inc *= (1.0 - prot)
        stress = min(1.0, stress + inc)
    return stress


# ---------------------------------------------------------------- recall
def recall_at(brain, sigma_eff, trials=MEASUREMENT_TRIALS,
              seed=MEASUREMENT_SEED):
    """Fraction of noisy probes correctly named, gate off (tau=None).

    Same protocol as tests.py test_noisy_recognition: probes cycle the
    four stored patterns, one seeded rng stream. A fixed seed reuses
    the same underlying noise directions across sigma values (each
    probe is pattern + sigma * z for the same z), which keeps the
    recall-vs-noise curve smooth instead of sampling-noisy.
    """
    rng = random.Random(seed)
    brain.tau = None
    ok = 0
    for k in range(trials):
        probe = noisy(brain.patterns[k % 4], sigma_eff, rng)
        _, name, _ = brain.decide(probe)
        ok += name == brain.EXPERIENCE_NAMES[k % 4]
    return ok / trials


def recall_with_light(brain, dose, sigma=MEASUREMENT_SIGMA, stress=0.0,
                      wavelength_nm=808.0, trials=MEASUREMENT_TRIALS,
                      seed=MEASUREMENT_SEED):
    """Recall at one dose / stress / wavelength point."""
    return recall_at(brain, sigma_effective(sigma, dose, stress,
                                            wavelength_nm),
                     trials=trials, seed=seed)


def simulate(brain, dose, wavelength_nm=808.0, light_time=None,
             onset=TIMING_ONSET, steps=TIMING_STEPS, rate=TIMING_RATE,
             sigma=MEASUREMENT_SIGMA, trials=MEASUREMENT_TRIALS,
             seed=MEASUREMENT_SEED):
    """One time-stepped light/stress run; returns its measured numbers."""
    prot = protection(dose, wavelength_nm)
    stress = stress_after(steps, onset, rate, light_time, prot)
    seff = sigma_effective(sigma, dose, stress, wavelength_nm)
    return {
        "dose": dose,
        "wavelength_nm": wavelength_nm,
        "light_time": light_time,
        "onset": onset,
        "steps": steps,
        "rate": rate,
        "protection": prot,
        "stress": stress,
        "sigma_eff": seff,
        "recall": recall_at(brain, seff, trials=trials, seed=seed),
    }


# ---------------------------------------------------------------- claims
def measure_all(brain=None, sigma=MEASUREMENT_SIGMA,
                trials=MEASUREMENT_TRIALS, seed=MEASUREMENT_SEED):
    """Run the four pre-registered claim measurements; JSON-serialisable.

    No thresholds are moved here: verdicts use the frozen CLAIM_*
    constants. Recompute with: python -c "import json, light;
    json.dump(light.measure_all(), open('results/results_light.json','w'), indent=2)".
    """
    brain = brain if brain is not None else MembraneBrain(n=128, seed=42)
    dose_rows = [
        {"dose": d, "wavelength_nm": 808.0,
         "atp": atp_factor(d),
         "sigma_eff": sigma_effective(sigma, d, 0.0),
         "recall": recall_with_light(brain, d, sigma=sigma,
                                     trials=trials, seed=seed)}
        for d in DOSE_GRID
    ]
    stress_rows = [
        {"stress": s,
         "sigma_eff": sigma_effective(sigma, 0.0, s),
         "recall": recall_with_light(brain, 0.0, sigma=sigma, stress=s,
                                     trials=trials, seed=seed)}
        for s in STRESS_GRID
    ]
    wl_rows = [
        {"wavelength_nm": w,
         "efficiency": wavelength_efficiency(w),
         "atp": atp_factor(DOSE_OPT, w),
         "sigma_eff": sigma_effective(sigma, DOSE_OPT, 0.0, w),
         "recall": recall_with_light(brain, DOSE_OPT, sigma=sigma,
                                     wavelength_nm=w, trials=trials,
                                     seed=seed)}
        for w in WAVELENGTHS
    ]
    early = simulate(brain, DOSE_OPT, light_time=EARLY_TIME, sigma=sigma,
                     trials=trials, seed=seed)
    late = simulate(brain, DOSE_OPT, light_time=LATE_TIME, sigma=sigma,
                    trials=trials, seed=seed)
    no_light = simulate(brain, DOSE_OPT, light_time=None, sigma=sigma,
                        trials=trials, seed=seed)

    by_dose = {r["dose"]: r["recall"] for r in dose_rows}
    biphasic_gaps = {
        "optimum_minus_zero": by_dose[DOSE_OPT] - by_dose[0.0],
        "optimum_minus_3x_optimum": by_dose[DOSE_OPT] - by_dose[3 * DOSE_OPT],
    }
    stress_recalls = [r["recall"] for r in stress_rows]
    dose_gap = wl_rows[1]["recall"] - by_dose[0.0]  # 808 nm, optimum dose
    wl_gap = max(r["recall"] for r in wl_rows) - min(r["recall"] for r in wl_rows)
    claims = {
        "i_biphasic": {
            "threshold_min_gap": CLAIM_BIPHASIC_MIN_GAP,
            "optimum_dose": DOSE_OPT,
            "recall_dose_0": by_dose[0.0],
            "recall_optimum": by_dose[DOSE_OPT],
            "recall_3x_optimum": by_dose[3 * DOSE_OPT],
            "gap_optimum_minus_zero": biphasic_gaps["optimum_minus_zero"],
            "gap_optimum_minus_3x": biphasic_gaps["optimum_minus_3x_optimum"],
            "pass": (biphasic_gaps["optimum_minus_zero"] >= CLAIM_BIPHASIC_MIN_GAP
                     and biphasic_gaps["optimum_minus_3x_optimum"] >= CLAIM_BIPHASIC_MIN_GAP),
        },
        "ii_stress": {
            "threshold_min_drop": CLAIM_STRESS_MIN_DROP,
            "recalls": stress_recalls,
            "non_increasing": all(b <= a for a, b in
                                  zip(stress_recalls, stress_recalls[1:])),
            "total_drop": stress_recalls[0] - stress_recalls[-1],
            "pass": (all(b <= a for a, b in
                         zip(stress_recalls, stress_recalls[1:]))
                     and stress_recalls[0] - stress_recalls[-1] >= CLAIM_STRESS_MIN_DROP),
        },
        "iii_dose_beats_wavelength": {
            "threshold_min_ratio": CLAIM_DOSE_WL_MIN_RATIO,
            "dose_gap": dose_gap,
            "wavelength_gap": wl_gap,
            "ratio": dose_gap / wl_gap if wl_gap > 0 else float("inf"),
            "pass": wl_gap > 0 and dose_gap > CLAIM_DOSE_WL_MIN_RATIO * wl_gap,
        },
        "iv_early_beats_late": {
            "threshold_min_gap": CLAIM_EARLY_MIN_GAP,
            "early_light_time": EARLY_TIME,
            "late_light_time": LATE_TIME,
            "early_recall": early["recall"],
            "late_recall": late["recall"],
            "gap": early["recall"] - late["recall"],
            "pass": early["recall"] - late["recall"] >= CLAIM_EARLY_MIN_GAP,
        },
    }
    return {
        "version": __version__,
        "protocol": {
            "sigma": sigma, "trials": trials, "seed": seed,
            "brain_seed": 42, "n_neurons": 128,
            "dose_grid": list(DOSE_GRID), "stress_grid": list(STRESS_GRID),
            "wavelengths_nm": list(WAVELENGTHS),
            "timing": {"steps": TIMING_STEPS, "onset": TIMING_ONSET,
                       "rate": TIMING_RATE, "early_time": EARLY_TIME,
                       "late_time": LATE_TIME},
            "constants": {"dose_opt": DOSE_OPT, "gain": GAIN,
                          "base_atp": BASE_ATP, "wl_peak_nm": WL_PEAK,
                          "wl_width_nm": WL_WIDTH,
                          "stress_gain": STRESS_GAIN},
        },
        "dose_rows": dose_rows,
        "stress_rows": stress_rows,
        "wavelength_rows": wl_rows,
        "timing": {"early": early, "late": late, "no_light": no_light},
        "claims": claims,
    }


if __name__ == "__main__":
    print(json.dumps(measure_all(), indent=2))
