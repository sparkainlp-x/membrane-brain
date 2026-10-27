"""Game bridge for membrane-brain (SYNTHETIC toy; not a brain).

Runs unchanged under CPython and under Pyodide (WebAssembly). It imports
``brain.py`` and ``rigor.py`` exactly as shipped in the repository root (the
copies next to this file are byte-identical; tests_game.py enforces that) and
only adds game plumbing: JSON in, JSON out, round generation, scoring.

Every number the game shows comes from brain.py: overlaps, tau, delays,
verdicts. Nothing is faked or hard-coded here except the README's expected
values in ``EXPECTED`` that the "Test the code" panel compares against.

Copyright (C) 2026 Jean-François Brisson. SPDX-License-Identifier: AGPL-3.0-only
"""

import hashlib
import json
import math
import random
import unittest
import zlib
from io import StringIO

import brain as B
import rigor as R

NAMES = list(B.MembraneBrain.EXPERIENCE_NAMES)
UNFAMILIAR_MIN_DIST = 6.0   # a source this far from every stored seed is "unfamiliar"
LEVELS = (
    {"name": "Quiet room", "sigma": 0.10, "weights": (("pattern", 0.55), ("random", 0.45))},
    {"name": "Static", "sigma": 0.20, "weights": (("pattern", 0.45), ("random", 0.30), ("foreign", 0.25))},
    {"name": "Storm", "sigma": 0.30, "weights": (("pattern", 0.40), ("random", 0.20), ("foreign", 0.40))},
)
ROUNDS_PER_LEVEL = 8
HINT_COST = 15

# README / RESULTS.md section 1, the numbers the checks must reproduce.
EXPECTED = {
    "neurons": 128, "edges": 314, "cross_edges": 12, "median_delay": 36.41,
    "split_cross_edges": 0, "tau": 0.238, "youden_j": 1.0,
    "recognition_ok": 40, "recognition_n": 40, "refused": 50, "refused_n": 50,
    "clean_left_front": "left-front",
}
# Fingerprint of the seed-42 stored patterns (rounded to 9 decimals), computed
# once under CPython 3.13 and re-checked live in the browser (WebAssembly).
GOLDEN_FINGERPRINT = "aec0e18e4d8bb0d3"

_S = {}


def _stream(tag):
    return random.Random(zlib.crc32(tag.encode()))


def _num(x, nd=4):
    if isinstance(x, float):
        return round(x, nd) if math.isfinite(x) else None
    return x


def _polar(field):
    amp = [abs(c) for c in field]
    top = max(amp) or 1.0
    return ([round(a / top, 4) for a in amp],
            [round(math.atan2(c.imag, c.real), 3) for c in field])


def _geo_json(geo):
    cross = set(geo.cross_edges)
    return {
        "nodes": [[round(n.x, 3), round(n.y, 3), 0 if n.hemisphere == "left" else 1]
                  for n in geo.neurons],
        "edges": [[a, b, 1 if (a, b) in cross else 0] for a, b in geo.edges],
    }


def fingerprint(patterns):
    flat = []
    for p in patterns:
        for c in p:
            flat.append("%.9f,%.9f" % (c.real + 0.0, c.imag + 0.0))
    return hashlib.sha256(";".join(flat).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- session
def init(seed=42):
    """Build the toy brain, calibrate the gate with the demo.py recipe."""
    seed = int(seed)
    brain = B.MembraneBrain(n=128, seed=seed)
    rng = random.Random(11)
    ins = [B.noisy(brain.patterns[k % 4], 0.15, rng) for k in range(100)]
    ood = [B.rand_field(128, rng) for _ in range(100)]
    tau, j = brain.calibrate(ins, ood)
    # Held-out sets, only for the live accept/false-accept read-out.
    r2 = random.Random(4242)
    held_in = [brain.max_overlap(B.noisy(brain.patterns[k % 4], 0.15, r2)) for k in range(100)]
    held_out = [brain.max_overlap(B.rand_field(128, r2)) for _ in range(100)]
    geo = brain.geometry
    _S.clear()
    _S.update(seed=seed, brain=brain, tau0=tau, j=j, held_in=held_in,
              held_out=held_out, rounds={}, waves={},
              cut=R.cut_geometry(geo),
              split=B.BrainGeometry(n=128, seed=seed, coupling=False))
    out = _geo_json(geo)
    out.update(seed=seed, tau=_num(tau), youden_j=_num(j), names=NAMES,
               seed_ids=list(brain.seed_ids), cross=len(geo.cross_edges),
               n_edges=len(geo.edges), version=B.__version__,
               levels=[{"name": L["name"], "sigma": L["sigma"]} for L in LEVELS],
               rounds_per_level=ROUNDS_PER_LEVEL, hint_cost=HINT_COST,
               rates=rates())
    return json.dumps(out)


def rates():
    t = _S["brain"].tau
    tpr = sum(1 for v in _S["held_in"] if v >= t) / len(_S["held_in"])
    fpr = sum(1 for v in _S["held_out"] if v >= t) / len(_S["held_out"])
    return {"tau": _num(t), "tpr": tpr, "fpr": fpr, "n": len(_S["held_in"])}


def rates_now():
    return json.dumps(rates())


def set_tau(tau):
    _S["brain"].tau = float(tau)
    return json.dumps(rates())


def reset_tau():
    return set_tau(_S["tau0"])


# ---------------------------------------------------------------- observe
def _geometry(mode):
    return {"intact": _S["brain"].geometry, "cut": _S["cut"],
            "split": _S["split"]}[mode]


def spread(exp, mode):
    """Wave from stored experience `exp` over the intact / cut / split graph."""
    brain = _S["brain"]
    geo = _geometry(mode)
    src = brain.seed_ids[int(exp)]
    delays = geo.delays_from(src)
    hemi = [n.hemisphere for n in geo.neurons]
    src_h = hemi[src]
    reached = [math.isfinite(d) for d in delays]
    cross0 = set(brain.geometry.cross_edges)
    opp = sorted(d for d, h in zip(delays, hemi) if h != src_h and math.isfinite(d))
    median = opp[len(opp) // 2] if opp else None
    # What the (intact-memory) gate says about the wave this graph produces.
    b2 = R.with_geometry(brain, geo)
    field = b2.wave(src)
    ovs = [abs(brain.overlaps(field)[i]) for i in range(4)]
    verdict, name, _ = brain.decide(field)
    amp, ph = _polar(field)
    return json.dumps({
        "mode": mode, "exp": int(exp), "src": src,
        "delays": [_num(d, 3) for d in delays],
        "edges": [[a, b, 1 if (a, b) in cross0 else 0] for a, b in geo.edges],
        "n_edges": len(geo.edges), "n_cross": len(geo.cross_edges),
        "reached": sum(reached), "unreachable": len(reached) - sum(reached),
        "opp_reached": len(opp), "opp_total": sum(1 for h in hemi if h != src_h),
        "median_opposite": _num(median, 2),
        "max_delay": _num(max(d for d in delays if math.isfinite(d)), 2),
        "overlaps": [_num(o) for o in ovs], "verdict": verdict, "name": name,
        "tau": _num(brain.tau), "amp": amp, "phase": ph})


# ---------------------------------------------------------------- name-it
def _pick_kind(level, rng):
    r, acc = rng.random(), 0.0
    for kind, w in LEVELS[level]["weights"]:
        acc += w
        if r < acc:
            return kind
    return LEVELS[level]["weights"][-1][0]


def _round(run_seed, level, idx):
    key = (int(run_seed), int(level), int(idx))
    if key in _S["rounds"]:
        return _S["rounds"][key]
    brain = _S["brain"]
    geo = brain.geometry
    rng = _stream("round:%d:%d:%d:%d" % (_S["seed"], key[0], key[1], key[2]))
    sigma = LEVELS[level]["sigma"]
    kind = _pick_kind(level, rng)
    label, src = None, None
    if kind == "pattern":
        label = rng.randrange(4)
        field = B.noisy(brain.patterns[label], sigma, rng)
    elif kind == "random":
        field = B.rand_field(brain.n, rng)
    else:
        seeds = [geo.neurons[s] for s in brain.seed_ids]
        far = [n.id for n in geo.neurons
               if min(math.hypot(n.x - s.x, n.y - s.y) for s in seeds) >= UNFAMILIAR_MIN_DIST]
        src = rng.choice(far)
        field = B.noisy(brain.wave(src), sigma, rng)
    amp, ph = _polar(field)
    rec = {"kind": kind, "label": label, "src": src, "sigma": sigma,
           "field": field, "amp": amp, "phase": ph}
    _S["rounds"][key] = rec
    return rec


def _points(correct, e, tau):
    h = 1.0 - min(1.0, abs(e - tau) / 0.5)   # 1 = right at the gate threshold
    return round(20 + 80 * h) if correct else -round(10 + 60 * (1.0 - h))


def new_round(run_seed, level, idx):
    r = _round(run_seed, level, idx)
    return json.dumps({"level": level, "idx": idx, "amp": r["amp"], "phase": r["phase"],
                       "sigma": r["sigma"]})


def hint(run_seed, level, idx):
    """The instrument read-out: |overlap| with each stored experience."""
    r = _round(run_seed, level, idx)
    return json.dumps({"overlaps": [_num(abs(m)) for m in _S["brain"].overlaps(r["field"])],
                       "tau": _num(_S["brain"].tau)})


def grade(run_seed, level, idx, choice, hinted):
    """choice: 0..3 = name that stored experience, -1 = refuse."""
    brain = _S["brain"]
    r = _round(run_seed, level, idx)
    ovs = [abs(m) for m in brain.overlaps(r["field"])]
    e = max(ovs)
    verdict, name, probs = brain.decide(r["field"])
    gate_choice = NAMES.index(name) if verdict == "accept" else -1
    truth = r["label"] if r["kind"] == "pattern" else -1
    tau = brain.tau
    you_ok = int(choice) == truth
    gate_ok = gate_choice == truth
    you_pts = _points(you_ok, e, tau) - (HINT_COST if hinted else 0)
    gate_pts = _points(gate_ok, e, tau)
    return json.dumps({
        "kind": r["kind"], "truth": truth, "src": r["src"],
        "truth_name": NAMES[truth] if truth >= 0 else None,
        "overlaps": [_num(o) for o in ovs], "e": _num(e), "tau": _num(tau),
        "verdict": verdict, "gate_choice": gate_choice,
        "you_ok": you_ok, "gate_ok": gate_ok,
        "you_points": you_pts, "gate_points": gate_pts})


# ---------------------------------------------------------------- break it
def _wave(src):
    if src not in _S["waves"]:
        _S["waves"][src] = _S["brain"].wave(src)
    return _S["waves"][src]


def _mix(src, alpha, sigma):
    rng = _stream("break:%d:%d:%.2f" % (_S["seed"], src, sigma))
    base = B.noisy(_wave(src), sigma, rng) if sigma > 0 else _wave(src)
    rnd = B.rand_field(128, rng)
    return B.normalize([alpha * a + (1.0 - alpha) * b for a, b in zip(base, rnd)])


def _nearest_seed(src):
    geo = _S["brain"].geometry
    s = geo.neurons[src]
    return min(math.hypot(s.x - geo.neurons[i].x, s.y - geo.neurons[i].y)
               for i in _S["brain"].seed_ids)


def attack(src, alpha, sigma):
    """Offer the gate a wave started from neuron `src`, diluted with random noise."""
    brain = _S["brain"]
    src, alpha, sigma = int(src), float(alpha), float(sigma)
    field = _mix(src, alpha, sigma)
    ovs = [abs(m) for m in brain.overlaps(field)]
    verdict, name, _ = brain.decide(field)
    dist = _nearest_seed(src)
    stored = src in brain.seed_ids
    fooled = verdict == "accept" and not stored and dist >= UNFAMILIAR_MIN_DIST
    amp, ph = _polar(field)
    pts = round(10 * dist) + round(100 * (1.0 - alpha)) if fooled else 0
    return json.dumps({"src": src, "alpha": alpha, "sigma": sigma, "stored": stored,
                       "overlaps": [_num(o) for o in ovs], "e": _num(max(ovs)),
                       "tau": _num(brain.tau), "verdict": verdict, "name": name,
                       "dist": _num(dist, 2), "fooled": fooled, "points": pts,
                       "amp": amp, "phase": ph})


def stealth(src, sigma):
    """Smallest wave share (grid of 0.01) at which the gate still accepts."""
    brain = _S["brain"]
    src, sigma = int(src), float(sigma)
    for k in range(0, 101):
        a = k / 100.0
        if brain.decide(_mix(src, a, sigma))[0] == "accept":
            return json.dumps({"src": src, "alpha_min": a})
    return json.dumps({"src": src, "alpha_min": None})


def scan(start, count, sigma):
    """Accept map: noisy wave from each neuron in [start, start+count)."""
    brain = _S["brain"]
    out = []
    for src in range(int(start), min(128, int(start) + int(count))):
        rng = _stream("scan:%d:%d:%.2f" % (_S["seed"], src, float(sigma)))
        f = B.noisy(_wave(src), float(sigma), rng)
        verdict, name, _ = brain.decide(f)
        out.append([src, 1 if verdict == "accept" else 0,
                    NAMES.index(name) if name else -1,
                    _num(brain.max_overlap(f))])
    return json.dumps(out)


# ---------------------------------------------------------------- checks
def _row(cid, label, expected, measured, ok, note=""):
    return {"id": cid, "label": label, "expected": expected, "measured": measured,
            "ok": bool(ok), "note": note}


def check_readme():
    m = R.e_reproduction()
    E = EXPECTED
    rows = [
        _row("neurons", "neurons", E["neurons"], m["neurons"], m["neurons"] == E["neurons"]),
        _row("edges", "edges", E["edges"], m["edges"], m["edges"] == E["edges"]),
        _row("cross", "cross-hemisphere edges", E["cross_edges"], m["cross_edges"],
             m["cross_edges"] == E["cross_edges"]),
        _row("median", "median left-front to right delay", "%.2f" % E["median_delay"],
             "%.2f" % m["median_delay"], round(m["median_delay"], 2) == E["median_delay"]),
        _row("split", "split toy cross edges", E["split_cross_edges"], m["split_cross_edges"],
             m["split_cross_edges"] == E["split_cross_edges"]),
        _row("tau", "gate tau", "%.3f" % E["tau"], "%.3f" % m["tau"],
             round(m["tau"], 3) == E["tau"]),
        _row("j", "Youden J (in-sample)", "%.3f" % E["youden_j"], "%.3f" % m["youden_j"],
             round(m["youden_j"], 3) == E["youden_j"]),
        _row("rec", "noisy recognition, sigma 0.15", "%d/%d" % (E["recognition_ok"], E["recognition_n"]),
             "%d/%d" % (m["recognition_ok"], m["recognition_n"]),
             m["recognition_ok"] == E["recognition_ok"] and m["recognition_n"] == E["recognition_n"]),
        _row("ref", "random fields refused", "%d/%d" % (E["refused"], E["refused_n"]),
             "%d/%d" % (m["refused"], m["refused_n"]),
             m["refused"] == E["refused"] and m["refused_n"] == E["refused_n"]),
        _row("clean", "clean left-front probe", "accept, " + E["clean_left_front"],
             "accept, %s" % m["clean_left_front"], m["clean_left_front"] == E["clean_left_front"]),
    ]
    return rows


def check_determinism():
    a = B.MembraneBrain(n=128, seed=42)
    b = B.MembraneBrain(n=128, seed=42)
    same = a.patterns == b.patterns and a.seed_ids == b.seed_ids
    fp = fingerprint(a.patterns)
    c = B.MembraneBrain(n=128, seed=43)
    differs = c.patterns != a.patterns
    return [
        _row("det_same", "two builds, seed 42: identical patterns (exact)", "identical",
             "identical" if same else "DIFFERENT", same),
        _row("det_seed", "seed 43 gives a different layout", "different",
             "different" if differs else "SAME", differs),
        _row("det_fp", "pattern fingerprint equals the CPython one", GOLDEN_FINGERPRINT, fp,
             fp == GOLDEN_FINGERPRINT,
             "sha-256 prefix of the seed-42 patterns rounded to 9 decimals"),
    ]


def null_control():
    """Shuffle the labels: recognition must fall to chance (25% for 4 classes)."""
    brain = B.MembraneBrain(n=128, seed=42)
    rng = _stream("game-null")
    labels, preds = [], []
    for k in range(400):
        lab = k % 4
        labels.append(lab)
        preds.append(brain.project(B.noisy(brain.patterns[lab], 0.15, rng))[0])
    true_acc = sum(p == l for p, l in zip(preds, labels)) / len(labels)
    accs = []
    for _ in range(200):
        sh = labels[:]
        rng.shuffle(sh)
        accs.append(sum(p == l for p, l in zip(preds, sh)) / len(sh))
    accs.sort()
    mean = sum(accs) / len(accs)
    lo, hi = accs[5], accs[194]
    return true_acc, mean, lo, hi


def check_null():
    true_acc, mean, lo, hi = null_control()
    return [
        _row("null_true", "400 noisy probes, true labels: argmax accuracy", ">= 95%",
             "%.1f%%" % (100 * true_acc), true_acc >= 0.95),
        _row("null_shuf", "same probes, labels shuffled (200 shuffles): mean accuracy",
             "about 25% (chance, 4 classes)", "%.1f%% (middle 95%%: %.1f to %.1f)" % (100 * mean, 100 * lo, 100 * hi),
             abs(mean - 0.25) <= 0.02 and lo <= 0.25 <= hi),
    ]


def check_unittests():
    import tests as T
    buf = StringIO()
    res = unittest.TextTestRunner(stream=buf, verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromModule(T))
    n = res.testsRun
    bad = len(res.failures) + len(res.errors)
    return [_row("unit", "the repository's own tests.py (unittest, live)", "all pass",
                 "%d tests, %d failed" % (n, bad), bad == 0 and n > 0)]


def run_checks(which):
    fn = {"readme": check_readme, "determinism": check_determinism,
          "null": check_null, "unit": check_unittests}[which]
    return json.dumps(fn())
