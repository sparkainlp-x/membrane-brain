"""Rigor experiments for membrane-brain v0.1.0 (stdlib only, seeded).

SYNTHETIC toy. Nothing here is neuroscience, a clinical statement or a
property of any real brain. Every number in RESULTS.md is produced by
``run_all`` below and stored in ``results/results.json``.

Run:  python rigor.py --write        # full run (a few minutes), writes
                                     #   results/results.json and RESULTS.md
      python rigor.py --render-only  # re-render RESULTS.md from the JSON
      python rigor.py --quick        # small run, prints a summary only

brain.py is imported unchanged. Variants (cut graph, random graph, pure
phase waves, random patterns) are built here by copying a MembraneBrain
and replacing its geometry or patterns.
"""

import argparse
import copy
import json
import math
import os
import random
import sys
import zlib

from brain import (BrainGeometry, MembraneBrain, noisy, normalize,
                   overlap, rand_field)

HERE = os.path.dirname(os.path.abspath(__file__))
SIGMA_DEFAULT = 0.15
N_NEURONS = 128

FULL = {
    "multiseed_seeds": 200, "noise_seeds": 100,
    "noise_sigmas": [round(0.05 * i, 2) for i in range(13)],
    "noise_per_pattern": 20, "tau_seeds": 200, "tau_grid_step": 0.02,
    "split_seeds": 200, "k_values": [2, 3, 4, 5, 6, 8], "k_seeds": 60,
    "cut_seeds": 100, "cut_widths": [12.0, 24.0, 48.0],
    "null_seeds": 100, "boot": 10000,
}
QUICK = {
    "multiseed_seeds": 6, "noise_seeds": 4,
    "noise_sigmas": [0.0, 0.15, 0.6], "noise_per_pattern": 4,
    "tau_seeds": 6, "tau_grid_step": 0.1,
    "split_seeds": 8, "k_values": [3, 4], "k_seeds": 4,
    "cut_seeds": 4, "cut_widths": [12.0, 48.0],
    "null_seeds": 4, "boot": 200,
}


# ---------------------------------------------------------------- statistics
def stream(tag, seed):
    """Deterministic RNG stream for (experiment tag, seed)."""
    return random.Random(zlib.crc32(tag.encode()) * 1_000_003 + int(seed))


def wilson(k, n, z=1.959964):
    """Wilson 95% interval for k successes in n trials."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mean(xs):
    return sum(xs) / len(xs)


def boot_ci(values, boot, tag="boot", stat=mean):
    """Percentile bootstrap 95% CI of stat over the values (resampling seeds)."""
    vals = list(values)
    n = len(vals)
    if n == 0:
        return (float("nan"), float("nan"))
    rng = stream(tag, n)
    outs = []
    for _ in range(boot):
        outs.append(stat([vals[rng.randrange(n)] for _ in range(n)]))
    outs.sort()
    return (outs[int(0.025 * boot)], outs[min(boot - 1, int(0.975 * boot))])


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for t in range(i, j + 1):
            r[order[t]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return r


def pearson(a, b):
    ma, mb = mean(a), mean(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if sa == 0 or sb == 0:
        return float("nan")
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def spearman(a, b):
    return pearson(ranks(a), ranks(b))


def spearman_ci(a, b, boot, tag):
    pairs = list(zip(a, b))
    n = len(pairs)
    rng = stream(tag, n)
    outs = []
    for _ in range(boot):
        s = [pairs[rng.randrange(n)] for _ in range(n)]
        r = spearman([p[0] for p in s], [p[1] for p in s])
        if not math.isnan(r):
            outs.append(r)
    outs.sort()
    if not outs:
        return (float("nan"), float("nan"))
    return (outs[int(0.025 * len(outs))],
            outs[min(len(outs) - 1, int(0.975 * len(outs)))])


def auc(pos, neg):
    """P(pos > neg) + 0.5 P(tie): the area under the ROC curve."""
    gt = 0.0
    for p in pos:
        for q in neg:
            gt += 1.0 if p > q else (0.5 if p == q else 0.0)
    return gt / (len(pos) * len(neg))


def clean(x):
    """JSON-safe copy: inf/nan -> None; floats rounded to 10 decimals so the
    stored results do not depend on float summation details (sum() became
    compensated in Python 3.12)."""
    if isinstance(x, float):
        return round(x, 10) if math.isfinite(x) else None
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


# ---------------------------------------------------------------- builders
_BRAINS = {}


def get_brain(seed, width=12.0):
    key = (seed, width)
    if key not in _BRAINS:
        _BRAINS[key] = MembraneBrain(n=N_NEURONS, seed=seed, width=width)
    return _BRAINS[key]


_CAL = {}


def clear_cache():
    _BRAINS.clear()
    _CAL.clear()


def calibrated(seed):
    """A copy of the seed's brain with the standard gate (tau frozen once)."""
    if seed not in _CAL:
        b = copy.copy(get_brain(seed))
        tau, j = calibrate_default(b, stream("ms-cal", seed))
        _CAL[seed] = (tau, j)
    b = copy.copy(get_brain(seed))
    b.tau = _CAL[seed][0]
    return b


def cut_geometry(geo):
    """The SAME graph with every cross-hemisphere edge deleted (a pure cut)."""
    g = copy.copy(geo)
    cross = set(geo.cross_edges)
    g.edges = [e for e in geo.edges if e not in cross]
    g.cross_edges = []
    return g


def random_geometry(geo, seed):
    """Same neurons, each wired to k uniformly random others (no layout)."""
    g = copy.copy(geo)
    rng = stream("randgraph", seed)
    edges = set()
    ids = [n.id for n in geo.neurons]
    for a in ids:
        others = [b for b in ids if b != a]
        for b in rng.sample(others, geo.k):
            edges.add((min(a, b), max(a, b)))
    g.edges = sorted(edges)
    g.cross_edges = [(a, b) for a, b in g.edges
                     if g.neurons[a].hemisphere != g.neurons[b].hemisphere]
    return g


def with_geometry(brain, geo):
    b = copy.copy(brain)
    b.geometry = geo
    b.patterns = [b.wave(s) for s in b.seed_ids]
    b.tau = None
    return b


def pure_phase_brain(brain):
    """Same graph and delays, but amplitude 1 everywhere (no envelope)."""
    b = copy.copy(brain)
    pats = []
    for sid in b.seed_ids:
        out = []
        for d in b.geometry.delays_from(sid):
            if math.isinf(d):
                out.append(0j)
            else:
                ph = 2.0 * math.pi * d / b.period
                out.append(complex(math.cos(ph), math.sin(ph)))
        pats.append(normalize(out))
    b.patterns = pats
    b.tau = None
    return b


def random_pattern_brain(brain, seed):
    """Four random unit fields as the stored patterns (no layout at all)."""
    b = copy.copy(brain)
    rng = stream("randpat", seed)
    b.patterns = [rand_field(brain.n, rng) for _ in range(4)]
    b.tau = None
    return b


# ---------------------------------------------------------------- evaluation
def probes(brain, rng, sigma, per_pattern):
    """(field, label) pairs: noisy copies of each stored pattern."""
    out = []
    for k in range(4):
        for _ in range(per_pattern):
            out.append((noisy(brain.patterns[k], sigma, rng), k))
    return out


def calibrate_default(brain, rng, sigma=SIGMA_DEFAULT, n=100):
    """Same recipe as demo.py: n noisy in-probes (cycling patterns), n random."""
    ins = [noisy(brain.patterns[k % 4], sigma, rng) for k in range(n)]
    ood = [rand_field(brain.n, rng) for _ in range(n)]
    return brain.calibrate(ins, ood)


def winner(brain, field):
    w, _ = brain.project(field)
    return w


def score(brain, plist):
    """Counts for labelled probes: argmax-correct (ungated) and gated outcomes."""
    n = len(plist)
    argmax_ok = accept = accept_ok = accept_wrong = 0
    for f, lab in plist:
        w = winner(brain, f)
        ok = (w == lab)
        argmax_ok += ok
        acc = brain.tau is None or brain.max_overlap(f) >= brain.tau
        if acc:
            accept += 1
            accept_ok += ok
            accept_wrong += (not ok)
    return {"n": n, "argmax_ok": argmax_ok, "accept": accept,
            "accept_ok": accept_ok, "accept_wrong": accept_wrong}


def refusals(brain, fields):
    return sum(1 for f in fields
               if brain.tau is not None and brain.max_overlap(f) < brain.tau)


def rate_block(counts, key, boot, tag, per_seed_key=None):
    """Pooled Wilson interval and seed-cluster bootstrap interval for a rate."""
    k = sum(c[key] for c in counts)
    n = sum(c["n"] for c in counts)
    per_seed = [c[key] / c["n"] for c in counts]
    return {"k": k, "n": n, "rate": k / n,
            "wilson": list(wilson(k, n)),
            "seed_boot": list(boot_ci(per_seed, boot, tag)),
            "seed_min": min(per_seed)}


# ---------------------------------------------------------------- experiments
def e_reproduction():
    """The README's seed-42 numbers, recomputed."""
    brain = MembraneBrain(n=128, seed=42)
    geo = brain.geometry
    split = BrainGeometry(n=128, seed=42, coupling=False)
    rng = random.Random(11)
    ins = [noisy(brain.patterns[k % 4], 0.15, rng) for k in range(100)]
    ood = [rand_field(128, rng) for _ in range(100)]
    tau, j = brain.calibrate(ins, ood)
    rng2 = random.Random(99)
    ok = sum(1 for k in range(40)
             if brain.decide(noisy(brain.patterns[k % 4], 0.15,
                                   rng2))[1] == brain.EXPERIENCE_NAMES[k % 4])
    rej = sum(1 for _ in range(50)
              if brain.decide(rand_field(128, rng2))[0] == "reject")
    return {"neurons": len(geo.neurons), "edges": len(geo.edges),
            "cross_edges": len(geo.cross_edges),
            "median_delay": brain.spread_time(brain.seed_ids[0]),
            "split_cross_edges": len(split.cross_edges),
            "tau": tau, "youden_j": j, "recognition_ok": ok,
            "recognition_n": 40, "refused": rej, "refused_n": 50,
            "clean_left_front": brain.decide(brain.patterns[0])[1]}


def e_multiseed(cfg):
    """Fresh-probe recognition/refusal over many layouts (calibrate, freeze, test)."""
    rows = []
    for seed in range(cfg["multiseed_seeds"]):
        b = calibrated(seed)
        tau, j_in = _CAL[seed]
        rt = stream("ms-test", seed)
        test = probes(b, rt, SIGMA_DEFAULT, 50)
        s = score(b, test)
        ood = [rand_field(b.n, rt) for _ in range(200)]
        s["ood_n"] = len(ood)
        s["refused"] = refusals(b, ood)
        s["tau"] = tau
        s["j_in_sample"] = j_in
        s["j_held_out"] = (s["accept"] / s["n"]) - (1 - s["refused"] / len(ood))
        s["distinct_seed_neurons"] = len(set(b.seed_ids))
        rows.append(s)
    B = cfg["boot"]
    for r in rows:
        r["ood_rate_n"] = r["ood_n"]
    ref_counts = [{"n": r["ood_n"], "refused": r["refused"]} for r in rows]
    taus = [r["tau"] for r in rows]
    return {
        "seeds": len(rows),
        "argmax_correct": rate_block(rows, "argmax_ok", B, "ms-argmax"),
        "gated_correct": rate_block(rows, "accept_ok", B, "ms-gated"),
        "gate_accepts_true": rate_block(rows, "accept", B, "ms-acc"),
        "accepted_but_wrong": rate_block(rows, "accept_wrong", B, "ms-wrong"),
        "random_refused": rate_block(ref_counts, "refused", B, "ms-ref"),
        "tau": {"mean": mean(taus), "min": min(taus), "max": max(taus),
                "boot": list(boot_ci(taus, B, "ms-tau"))},
        "j_in_sample_mean": mean([r["j_in_sample"] for r in rows]),
        "j_in_sample_eq_1": sum(1 for r in rows
                                if r["j_in_sample"] > 1 - 1e-9),
        "j_held_out": {"mean": mean([r["j_held_out"] for r in rows]),
                       "boot": list(boot_ci([r["j_held_out"] for r in rows],
                                            B, "ms-jho")),
                       "min": min(r["j_held_out"] for r in rows)},
        "seeds_with_fewer_than_4_distinct_seed_neurons":
            sum(1 for r in rows if r["distinct_seed_neurons"] < 4),
        "seeds_with_any_random_accepted":
            sum(1 for r in rows if r["refused"] < r["ood_n"]),
    }


def e_noise(cfg):
    """Recognition and gate behaviour against probe noise; tau frozen at 0.15."""
    out = []
    seeds = range(cfg["noise_seeds"])
    for sigma in cfg["noise_sigmas"]:
        cnts = []
        for seed in seeds:
            b = calibrated(seed)
            rt = stream("noise-%s" % sigma, seed)
            cnts.append(score(b, probes(b, rt, sigma,
                                        cfg["noise_per_pattern"])))
        B = cfg["boot"]
        row = {"sigma": sigma}
        for key in ("argmax_ok", "accept_ok", "accept_wrong", "accept"):
            row[key] = rate_block(cnts, key, B, "nz-%s-%s" % (key, sigma))
        row["refused_true_pattern"] = 1.0 - row["accept"]["rate"]
        out.append(row)
    # random fields are independent of sigma: one line
    cnts = []
    for seed in seeds:
        b = calibrated(seed)
        rt = stream("noise-ood", seed)
        fs = [rand_field(b.n, rt) for _ in range(100)]
        cnts.append({"n": len(fs), "refused": refusals(b, fs)})
    return {"seeds": cfg["noise_seeds"], "rows": out,
            "random_refused": rate_block(cnts, "refused", cfg["boot"],
                                         "nz-ood"),
            "chance": 0.25}


def _eval_variant(make, seeds, boot, tag, gated=True, sigma=SIGMA_DEFAULT,
                  per_pattern=25):
    """Recognition of a brain variant at sigma; gate calibrated on the variant."""
    cnts = []
    for seed in seeds:
        b = copy.copy(make(seed))
        if gated:
            calibrate_default(b, stream(tag + "-cal", seed), sigma)
        rt = stream(tag + "-test", seed)
        cnts.append(score(b, probes(b, rt, sigma, per_pattern)))
    return {"argmax_correct": rate_block(cnts, "argmax_ok", boot, tag + "a"),
            "gated_correct": rate_block(cnts, "accept_ok", boot, tag + "g"),
            "gate_accepts": rate_block(cnts, "accept", boot, tag + "c")}


def e_nulls(cfg):
    seeds = list(range(cfg["null_seeds"]))
    B = cfg["boot"]
    res = {"seeds": len(seeds), "sigma": SIGMA_DEFAULT}
    # (a) shuffled labels: same probes and predictions, labels permuted
    cnts = []
    for seed in seeds:
        b = get_brain(seed)
        rt = stream("null-shuf", seed)
        test = probes(b, rt, SIGMA_DEFAULT, 25)
        labels = [lab for _, lab in test]
        rt.shuffle(labels)
        ok = sum(1 for (f, _), lab in zip(test, labels)
                 if winner(b, f) == lab)
        cnts.append({"n": len(test), "ok": ok})
    res["shuffled_labels"] = rate_block(cnts, "ok", B, "null-shuf")
    # (b) permutation null for the calibration statistic itself: the best
    # in-sample Youden J when the in/out labels of the 200 calibration probes
    # are shuffled. A J of 1.000 must be judged against this, not against 0.
    jperm = []
    for seed in seeds:
        b = copy.copy(get_brain(seed))
        rt = stream("null-shufcal", seed)
        pool = ([noisy(b.patterns[k % 4], SIGMA_DEFAULT, rt)
                 for k in range(100)]
                + [rand_field(b.n, rt) for _ in range(100)])
        rt.shuffle(pool)
        _, j = b.calibrate(pool[:100], pool[100:])
        jperm.append(j)
    res["shuffled_calibration_j_in_sample"] = {
        "mean": mean(jperm), "max": max(jperm),
        "boot": list(boot_ci(jperm, B, "null-shufj"))}
    # (c) pure phase (no envelope), (d) random graph, (e) random patterns,
    # (f) the real thing for reference
    res["real"] = _eval_variant(lambda s: get_brain(s), seeds, B, "v-real")
    res["pure_phase"] = _eval_variant(
        lambda s: pure_phase_brain(get_brain(s)), seeds, B, "v-phase")
    res["random_graph"] = _eval_variant(
        lambda s: with_geometry(get_brain(s),
                                random_geometry(get_brain(s).geometry, s)),
        seeds, B, "v-rgraph")
    res["random_patterns"] = _eval_variant(
        lambda s: random_pattern_brain(get_brain(s), s), seeds, B, "v-rpat")
    # pairwise overlaps of stored patterns (how separable are they?)
    pm = []
    pm_pure = []
    for seed in seeds:
        b = get_brain(seed)
        pb = pure_phase_brain(b)
        for src, dst in ((b, pm), (pb, pm_pure)):
            for i in range(4):
                for j in range(i + 1, 4):
                    dst.append(abs(overlap(src.patterns[i], src.patterns[j])))
    res["pattern_overlap"] = {
        "enveloped_mean": mean(pm), "enveloped_max": max(pm),
        "pure_phase_mean": mean(pm_pure), "pure_phase_max": max(pm_pure)}
    # (g) the one thing the membrane-heart falsification was about: waves that
    # differ only by a global phase. |overlap| cannot tell them apart.
    gp = []
    for seed in seeds:
        b = get_brain(seed)
        rt = stream("null-gp", seed)
        p = b.patterns[0]
        for _ in range(10):
            th = rt.uniform(0, 2 * math.pi)
            q = [c * complex(math.cos(th), math.sin(th)) for c in p]
            gp.append(abs(overlap(q, p)))
    res["global_phase_overlap"] = {"min": min(gp), "max": max(gp), "n": len(gp)}
    return res


def sweep_tau(in_max, ood_max, grid):
    """accept rate, refusal rate, J for each tau in grid."""
    rows = []
    for t in grid:
        tpr = sum(1 for v in in_max if v >= t) / len(in_max)
        fpr = sum(1 for v in ood_max if v >= t) / len(ood_max)
        rows.append((t, tpr, 1 - fpr, tpr - fpr))
    return rows


def e_tau(cfg):
    seeds = range(cfg["tau_seeds"])
    B = cfg["boot"]
    step = cfg["tau_grid_step"]
    grid = [round(step * i, 6) for i in range(int(round(0.6 / step)) + 1)]
    per_tau = {t: {"tpr": [], "tnr": [], "j": []} for t in grid}
    aucs, gaps, frozen_j = [], [], []
    ood1_ref, ood1_n = 0, 0   # structured OOD: wave from a random neuron
    ood2_ref, ood2_n = 0, 0   # structured OOD: another layout's patterns
    ood1_auc, ood2_auc, rand_auc = [], [], []
    ood1_label = [0, 0, 0, 0]
    for seed in seeds:
        b = calibrated(seed)
        rt = stream("tau-test", seed)
        ins = [noisy(b.patterns[k % 4], SIGMA_DEFAULT, rt)
               for k in range(200)]
        rnd = [rand_field(b.n, rt) for _ in range(200)]
        in_max = [b.max_overlap(f) for f in ins]
        rnd_max = [b.max_overlap(f) for f in rnd]
        aucs.append(auc(in_max, rnd_max))
        gaps.append(min(in_max) - max(rnd_max))
        for t, tpr, tnr, j in sweep_tau(in_max, rnd_max, grid):
            per_tau[t]["tpr"].append(tpr)
            per_tau[t]["tnr"].append(tnr)
            per_tau[t]["j"].append(j)
        frozen_j.append(sum(1 for v in in_max if v >= b.tau) / 200
                        - sum(1 for v in rnd_max if v >= b.tau) / 200)
        # structured OOD 1: a noisy wave started from a random neuron
        s1 = [noisy(b.wave(rt.randrange(b.n)), SIGMA_DEFAULT, rt)
              for _ in range(40)]
        m1 = [b.max_overlap(f) for f in s1]
        ood1_ref += sum(1 for v in m1 if v < b.tau)
        ood1_n += len(m1)
        ood1_auc.append(auc(in_max, m1))
        for f in s1:
            if b.max_overlap(f) >= b.tau:
                ood1_label[winner(b, f)] += 1
        # structured OOD 2: noisy stored patterns of ANOTHER layout
        other = get_brain(seed + 1000)
        s2 = [noisy(other.patterns[k % 4], SIGMA_DEFAULT, rt)
              for k in range(40)]
        m2 = [b.max_overlap(f) for f in s2]
        ood2_ref += sum(1 for v in m2 if v < b.tau)
        ood2_n += len(m2)
        ood2_auc.append(auc(in_max, m2))
        rand_auc.append(aucs[-1])
    curve = []
    for t in grid:
        d = per_tau[t]
        curve.append({"tau": t, "accept_true": mean(d["tpr"]),
                      "refuse_random": mean(d["tnr"]),
                      "j": mean(d["j"]),
                      "j_boot": list(boot_ci(d["j"], B, "tau-j-%s" % t))})
    best = max(curve, key=lambda r: r["j"])
    taus_cal = [calibrated(s).tau for s in seeds]
    perfect = [t["tau"] for t in curve if t["j"] > 1 - 1e-9]
    return {
        "seeds": cfg["tau_seeds"], "sigma": SIGMA_DEFAULT, "curve": curve,
        "best_mean_j": {"tau": best["tau"], "j": best["j"]},
        "frozen_tau_held_out_j": {
            "mean": mean(frozen_j),
            "boot": list(boot_ci(frozen_j, B, "tau-fj")),
            "fraction_equal_1": sum(1 for v in frozen_j if v > 1 - 1e-9)
            / len(frozen_j)},
        "auc_random_ood": {"mean": mean(aucs),
                           "boot": list(boot_ci(aucs, B, "tau-auc")),
                           "fraction_equal_1": sum(1 for a in aucs
                                                   if a == 1.0) / len(aucs),
                           "min": min(aucs)},
        "gap_in_min_minus_random_max": {
            "mean": mean(gaps), "boot": list(boot_ci(gaps, B, "tau-gap")),
            "fraction_positive": sum(1 for g in gaps if g > 0) / len(gaps)},
        "mean_tau_calibrated": mean(taus_cal),
        "fractions_tau_grid_with_mean_j_1": perfect,
        "structured_ood": {
            "other_neuron_wave": {
                "refused": ood1_ref, "n": ood1_n,
                "wilson": list(wilson(ood1_ref, ood1_n)),
                "auc_vs_true": {"mean": mean(ood1_auc),
                                "boot": list(boot_ci(ood1_auc, B, "tau-a1"))},
                "accepted_as": ood1_label},
            "other_layout_patterns": {
                "refused": ood2_ref, "n": ood2_n,
                "wilson": list(wilson(ood2_ref, ood2_n)),
                "auc_vs_true": {"mean": mean(ood2_auc),
                                "boot": list(boot_ci(ood2_auc, B, "tau-a2"))}},
        },
    }


# ---------------------------------------------------------------- split toy
def components(geo):
    seen = {}
    c = 0
    adj = {n.id: [] for n in geo.neurons}
    for a, b in geo.edges:
        adj[a].append(b)
        adj[b].append(a)
    for n in geo.neurons:
        if n.id in seen:
            continue
        st = [n.id]
        while st:
            u = st.pop()
            if u in seen:
                continue
            seen[u] = c
            st.extend(adj[u])
        c += 1
    return c


def fast_delays(geo, source):
    """Same Dijkstra as BrainGeometry.delays_from, with a prebuilt adjacency."""
    import heapq
    adj = {n.id: [] for n in geo.neurons}
    for a, b in geo.edges:
        adj[a].append(b)
        adj[b].append(a)
    by_id = {n.id: n for n in geo.neurons}
    times = {n.id: math.inf for n in geo.neurons}
    times[source] = 0.0
    heap = [(0.0, source)]
    while heap:
        t, u = heapq.heappop(heap)
        if t > times[u]:
            continue
        a = by_id[u]
        for v in adj[u]:
            w = math.hypot(a.x - by_id[v].x, a.y - by_id[v].y)
            if t + w < times[v]:
                times[v] = t + w
                heapq.heappush(heap, (times[v], v))
    return [times[n.id] for n in geo.neurons]


def cross_stats(geo, source):
    """(unreachable fraction of opposite hemisphere, median finite delay)."""
    d = fast_delays(geo, source)
    hemi = geo.neurons[source].hemisphere
    other = [x for n, x in zip(geo.neurons, d) if n.hemisphere != hemi]
    fin = sorted(x for x in other if math.isfinite(x))
    unreachable = 1.0 - len(fin) / len(other)
    med = fin[len(fin) // 2] if fin else math.inf   # same as spread_time
    return unreachable, med


def left_seeds(geo):
    return [geo.nearest_neuron(-17.0, 5.0), geo.nearest_neuron(-17.0, -5.0)]


def e_split(cfg):
    B = cfg["boot"]
    seeds = range(cfg["split_seeds"])
    rows = []
    for seed in seeds:
        geo = BrainGeometry(n=N_NEURONS, seed=seed)
        cut = cut_geometry(geo)
        rew = BrainGeometry(n=N_NEURONS, seed=seed, coupling=False)
        seeds_l = left_seeds(geo)
        u_i, m_i, u_c, u_r = [], [], [], []
        for s in seeds_l:
            u, m = cross_stats(geo, s)
            u_i.append(u)
            m_i.append(m)
            u_c.append(cross_stats(cut, s)[0])
            u_r.append(cross_stats(rew, s)[0])
        rows.append({
            "seed": seed, "cross": len(geo.cross_edges),
            "comp_intact": components(geo), "comp_cut": components(cut),
            "comp_rewired": components(rew),
            "edges_rewired_not_in_cut": len(set(rew.edges) - set(cut.edges)),
            "unreach_intact": mean(u_i), "unreach_cut": mean(u_c),
            "unreach_rewired": mean(u_r),
            "median_delay": m_i[0], "n_left_seeds": 2,
        })
    n = len(rows)
    ui = [r["unreach_intact"] for r in rows]
    cross = [r["cross"] for r in rows]
    fin = [r for r in rows if math.isfinite(r["median_delay"])]
    rho = spearman([r["cross"] for r in fin], [r["median_delay"] for r in fin])
    rho_ci = spearman_ci([r["cross"] for r in fin],
                         [r["median_delay"] for r in fin], B, "split-rho")
    bins = []
    for lo, hi in ((0, 3), (4, 7), (8, 11), (12, 15), (16, 99)):
        sel = [r["median_delay"] for r in fin if lo <= r["cross"] <= hi]
        if sel:
            bins.append({"cross_edges": "%d-%d" % (lo, min(hi, 99)) if hi < 99
                         else "%d+" % lo, "n": len(sel),
                         "median_of_median_delay": sorted(sel)[len(sel) // 2],
                         "mean": mean(sel),
                         "boot": list(boot_ci(sel, B, "split-bin-%d" % lo))})
    ksweep = []
    for k in cfg["k_values"]:
        crs, med, conn, reach, unr = [], [], 0, 0, []
        ks = list(range(cfg["k_seeds"]))
        for seed in ks:
            g = BrainGeometry(n=N_NEURONS, seed=seed, k=k)
            crs.append(len(g.cross_edges))
            conn += (components(g) == 1)
            u, m = cross_stats(g, left_seeds(g)[0])
            unr.append(u)
            if math.isfinite(m):
                med.append(m)
                reach += 1
        ksweep.append({
            "k": k, "seeds": len(ks), "cross_mean": mean(crs),
            "cross_boot": list(boot_ci(crs, B, "k-cr-%d" % k)),
            "fraction_single_component": conn / len(ks),
            "fraction_left_seed_reaches_right": reach / len(ks),
            "unreachable_mean": mean(unr),
            "median_delay_mean": mean(med) if med else None,
            "median_delay_boot": list(boot_ci(med, B, "k-md-%d" % k))
            if med else None})
    return {
        "seeds": n,
        "cross_edges": {"mean": mean(cross), "min": min(cross),
                        "max": max(cross),
                        "boot": list(boot_ci(cross, B, "split-cross")),
                        "seeds_with_zero": sum(1 for c in cross if c == 0)},
        "intact_left_wave_unreachable_fraction": {
            "mean": mean(ui), "boot": list(boot_ci(ui, B, "split-ui")),
            "seeds_with_any_unreachable": sum(1 for v in ui if v > 0),
            "seeds_fully_reaching_right": sum(1 for v in ui if v == 0)},
        "cut_left_wave_unreachable_fraction_min": min(
            r["unreach_cut"] for r in rows),
        "rewired_left_wave_unreachable_fraction_min": min(
            r["unreach_rewired"] for r in rows),
        "components": {
            "intact_gt1": sum(1 for r in rows if r["comp_intact"] > 1),
            "cut_gt2": sum(1 for r in rows if r["comp_cut"] > 2),
            "rewired_gt2": sum(1 for r in rows if r["comp_rewired"] > 2)},
        "rewire_differs_from_cut": sum(
            1 for r in rows if r["edges_rewired_not_in_cut"] > 0),
        "median_delay": {"n": len(fin),
                         "mean": mean([r["median_delay"] for r in fin]),
                         "boot": list(boot_ci([r["median_delay"]
                                               for r in fin], B,
                                              "split-md")),
                         "inf_seeds": n - len(fin)},
        "delay_vs_cross_spearman": {"rho": rho, "ci": list(rho_ci),
                                    "n": len(fin)},
        "delay_by_cross_bin": bins,
        "k_sweep": ksweep,
    }


def e_cut_recognition(cfg):
    """Recognition with the cross edges deleted. Measured only."""
    B = cfg["boot"]
    out = []
    seeds = range(cfg["cut_seeds"])
    for width in cfg["cut_widths"]:
        intact, mixed, allcut = [], [], []
        ov, opp = [], []
        for seed in seeds:
            b = copy.copy(get_brain(seed, width))
            calibrate_default(b, stream("cut-cal", seed))
            cb = with_geometry(b, cut_geometry(b.geometry))
            rt = stream("cut-test-%s" % width, seed)
            # (1) intact memory, intact probes
            intact.append(score(b, probes(b, rt, SIGMA_DEFAULT, 25)))
            # (2) intact memory (frozen gate), probes from the cut brain
            mixed.append(score(b, [(noisy(cb.patterns[k], SIGMA_DEFAULT, rt),
                                    k) for k in range(4)
                                   for _ in range(25)]))
            # (3) memory stored after the cut, own gate
            calibrate_default(cb, stream("cut-cal2", seed))
            allcut.append(score(cb, probes(cb, rt, SIGMA_DEFAULT, 25)))
            for k in range(4):
                ov.append(abs(overlap(cb.patterns[k], b.patterns[k])))
                h = b.geometry.neurons[b.seed_ids[k]].hemisphere
                opp.append(sum(abs(c) ** 2 for c, n in
                               zip(b.patterns[k], b.geometry.neurons)
                               if n.hemisphere != h))
        row = {"width": width}
        for name, cn in (("intact", intact), ("cut_probes_intact_memory",
                                              mixed),
                         ("cut_everything", allcut)):
            row[name] = {
                "gated_correct": rate_block(cn, "accept_ok", B,
                                            "cut-%s-%s-g" % (name, width)),
                "argmax_correct": rate_block(cn, "argmax_ok", B,
                                             "cut-%s-%s-a" % (name, width)),
            }
        row["overlap_intact_vs_cut_pattern"] = {
            "mean": mean(ov), "min": min(ov),
            "boot": list(boot_ci(ov, B, "cut-ov-%s" % width))}
        row["energy_in_opposite_hemisphere"] = {
            "mean": mean(opp), "max": max(opp),
            "boot": list(boot_ci(opp, B, "cut-opp-%s" % width))}
        out.append(row)
    return {"seeds": cfg["cut_seeds"], "sigma": SIGMA_DEFAULT, "rows": out}


def run_all(cfg):
    clear_cache()
    return {
        "config": cfg,
        "reproduction": e_reproduction(),
        "multiseed": e_multiseed(cfg),
        "noise": e_noise(cfg),
        "nulls": e_nulls(cfg),
        "tau": e_tau(cfg),
        "split": e_split(cfg),
        "cut_recognition": e_cut_recognition(cfg),
    }


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--out-dir", default=HERE)
    a = ap.parse_args(argv)
    jpath = os.path.join(a.out_dir, "results", "results.json")
    if a.render_only:
        with open(jpath, encoding="utf-8") as f:
            res = json.load(f)
    else:
        res = clean(run_all(QUICK if a.quick else FULL))
    if a.write and not a.quick:
        os.makedirs(os.path.dirname(jpath), exist_ok=True)
        with open(jpath, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, sort_keys=True)
            f.write("\n")
    if (a.write or a.render_only) and not a.quick:
        import render_results
        with open(os.path.join(a.out_dir, "RESULTS.md"), "w",
                  encoding="utf-8") as f:
            f.write(render_results.render(res))
    print(json.dumps(res["multiseed"]["gated_correct"], sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
