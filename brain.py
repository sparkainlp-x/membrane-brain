"""membrane-brain v0.1.0 — a sparkainlp-x membrane in a brain-shaped toy.

Stdlib-only Python, seeded, reproducible, AGPL-3.0-only.

Latest sparkainlp-x lineage, reused exactly
-------------------------------------------
1. membrane-capacity: complex oscillators; patterns stored as an
   outer-product holographic memory; recognition is one-shot
   projection — winner = argmax |overlap|, probs = |m|^2 / sum |m|^2.
2. refusing-membrane: REJECT iff max |overlap| < tau, tau calibrated
   once and frozen — with the midpoint-of-max-J improvement from
   membrane-vs-hopfield (first-best tau sits on the edge of the gap).
3. membrane-heart: a wave is stored as an ENVELOPED phasor field,
   not a pure phase wave. Pure phase snapshots differ only by a
   global phase, which |overlap| cannot see (that bug was caught by
   the membrane-heart tests: recognition 0.325 before the envelope,
   39/40 after). The envelope is kept here from the start.
4. holo-heart-neurons: seeded neurons, k-nearest-neighbour edges,
   Dijkstra propagation delays from a seed neuron.

The toy brain
-------------
128 neurons in two hemispheres (64 left, 64 right), each an ellipse,
connected by 4-nearest-neighbour edges, including cross-hemisphere
edges near the midline. Four stored "experiences" are wave fields,
each started from a different seed region (left-front, left-back,
right-front, right-back): amplitude decays with Dijkstra distance
from the seed, phase advances with distance, then normalised.

A probe is projected onto the four stored experiences: the membrane
names one, or the frozen gate refuses it. A random field is refused
instead of mislabelled. Cutting the cross-hemisphere edges (the toy
split) makes a left-started wave unreachable in the right hemisphere
— a structural fact of this graph, measured, not a claim about real
split-brain patients.

What this is NOT — read before any use
---------------------------------------
Not a human brain. Not neuroscience, not a neural model of cognition,
not a medical device, not a diagnosis, not a measurement of any real
person. No lobes, no cortex, no neurons with ion channels, no
learning in any biological sense. The "hemispheres" are two ellipses;
the "experiences" are four wave snapshots; the "thoughts" are unit
complex vectors. Synthetic, toy, educational — a demonstration that
the latest membrane frame can hold, recognise, and refuse activity
patterns on a two-lobed layout.
"""

import heapq
import math
import random

__version__ = "0.1.0"


# ---------------------------------------------------------------- helpers
def normalize(v):
    n = math.sqrt(sum(abs(c) ** 2 for c in v))
    if n == 0:
        raise ValueError("cannot normalize a zero vector")
    return [c / n for c in v]


def overlap(field, pattern):
    return sum(p.conjugate() * f for p, f in zip(pattern, field))


def noisy(field, sigma, rng):
    return normalize(
        [c + complex(rng.gauss(0, sigma), rng.gauss(0, sigma))
         for c in field]
    )


def rand_field(n, rng):
    return normalize(
        [complex(rng.gauss(0, 1), rng.gauss(0, 1)) for _ in range(n)]
    )


# ---------------------------------------------------------------- geometry
class Neuron:
    def __init__(self, nid, x, y, hemisphere):
        self.id = nid
        self.x = float(x)
        self.y = float(y)
        self.hemisphere = hemisphere  # 'left' or 'right'

    def __repr__(self):
        return (f"Neuron({self.id}, {self.x:.2f}, {self.y:.2f}, "
                f"{self.hemisphere!r})")


class BrainGeometry:
    """Two-ellipse neuron layout + k-NN edges + Dijkstra delays."""

    def __init__(self, n=128, seed=42, k=4, coupling=True):
        if n < 16 or n % 2 != 0:
            raise ValueError("n must be even and at least 16")
        self.n = n
        self.seed = seed
        self.k = k
        self.coupling = coupling
        rng = random.Random(seed)
        per = n // 2
        neurons = []
        for hemi, cx in (("left", -11.0), ("right", 11.0)):
            made = 0
            attempts = 0
            while made < per and attempts < 20000:
                attempts += 1
                x = rng.uniform(cx - 12.0, cx + 12.0)
                y = rng.uniform(-9.0, 9.0)
                if ((x - cx) / 12.0) ** 2 + (y / 9.0) ** 2 <= 1.0:
                    neurons.append(Neuron(len(neurons), x, y, hemi))
                    made += 1
            while made < per:  # fallback: centre jitter
                neurons.append(Neuron(len(neurons), cx, 0.0, hemi))
                made += 1
        self.neurons = neurons
        self.edges = self._connect(k)
        self.cross_edges = [
            (a, b) for a, b in self.edges
            if self.neurons[a].hemisphere != self.neurons[b].hemisphere
        ]

    def _connect(self, k):
        edges = set()
        for a in self.neurons:
            candidates = [
                b for b in self.neurons
                if b.id != a.id
                and (self.coupling
                     or b.hemisphere == a.hemisphere)
            ]
            dists = sorted(
                ((a.x - b.x) ** 2 + (a.y - b.y) ** 2, b.id)
                for b in candidates
            )
            for _, bid in dists[:k]:
                edges.add((min(a.id, bid), max(a.id, bid)))
        return sorted(edges)

    def neighbours(self, nid):
        out = []
        for a, b in self.edges:
            if a == nid:
                out.append(b)
            elif b == nid:
                out.append(a)
        return sorted(out)

    def delays_from(self, source):
        """Dijkstra delays from source; inf if unreachable (split)."""
        by_id = {neu.id: neu for neu in self.neurons}
        times = {neu.id: math.inf for neu in self.neurons}
        times[source] = 0.0
        heap = [(0.0, source)]
        while heap:
            t, nid = heapq.heappop(heap)
            if t > times[nid]:
                continue
            a = by_id[nid]
            for mid in self.neighbours(nid):
                b = by_id[mid]
                w = math.hypot(a.x - b.x, a.y - b.y)
                if t + w < times[mid]:
                    times[mid] = t + w
                    heapq.heappush(heap, (times[mid], mid))
        return [times[neu.id] for neu in self.neurons]

    def nearest_neuron(self, x, y):
        return min(
            self.neurons,
            key=lambda neu: (neu.x - x) ** 2 + (neu.y - y) ** 2,
        ).id


# ---------------------------------------------------------------- membrane
class MembraneBrain:
    """Brain-shaped membrane: store, project, refuse."""

    EXPERIENCE_NAMES = ("left-front", "left-back",
                        "right-front", "right-back")
    # Seed points for the four experiences (toy region centres).
    SEED_POINTS = ((-17.0, 5.0), (-17.0, -5.0),
                    (17.0, 5.0), (17.0, -5.0))

    def __init__(self, n=128, seed=42, width=12.0, period=40.0):
        if width <= 0 or period <= 0:
            raise ValueError("width and period must be positive")
        self.geometry = BrainGeometry(n=n, seed=seed)
        self.n = n
        self.width = width
        self.period = period
        self.seed_ids = [
            self.geometry.nearest_neuron(x, y)
            for x, y in self.SEED_POINTS
        ]
        self.patterns = [self.wave(sid) for sid in self.seed_ids]
        self.tau = None

    def wave(self, source):
        """Enveloped wave field started from neuron `source`."""
        delays = self.geometry.delays_from(source)
        out = []
        for d in delays:
            if math.isinf(d):
                out.append(0j)
                continue
            amp = math.exp(-(d * d) / (2.0 * self.width * self.width))
            phase = 2.0 * math.pi * d / self.period
            out.append(amp * complex(math.cos(phase),
                                     math.sin(phase)))
        return normalize(out)

    def overlaps(self, field):
        return [overlap(field, p) for p in self.patterns]

    def project(self, field):
        ms = self.overlaps(field)
        tot = sum(abs(m) ** 2 for m in ms)
        if tot == 0:
            return None, [0.0] * len(ms)
        probs = [abs(m) ** 2 / tot for m in ms]
        return max(range(len(ms)), key=lambda i: abs(ms[i])), probs

    def max_overlap(self, field):
        return max(abs(m) for m in self.overlaps(field))

    def calibrate(self, in_probes, ood_probes, grid=101):
        """Freeze tau: midpoint of the taus maximising Youden's J."""
        in_max = [self.max_overlap(f) for f in in_probes]
        ood_max = [self.max_overlap(f) for f in ood_probes]
        best_j, best_taus = -2.0, []
        for step in range(grid + 1):
            tau = step / grid
            tpr = sum(1 for v in in_max if v >= tau) / len(in_max)
            fpr = sum(1 for v in ood_max if v >= tau) / len(ood_max)
            j = tpr - fpr
            if j > best_j + 1e-12:
                best_j, best_taus = j, [tau]
            elif abs(j - best_j) <= 1e-12:
                best_taus.append(tau)
        self.tau = (best_taus[0] + best_taus[-1]) / 2.0
        return self.tau, best_j

    def decide(self, field):
        """('accept', experience_name, probs) or ('reject', None, probs)."""
        winner, probs = self.project(field)
        if winner is None:
            return "reject", None, probs
        if self.tau is not None and self.max_overlap(field) < self.tau:
            return "reject", None, probs
        return "accept", self.EXPERIENCE_NAMES[winner], probs

    def spread_time(self, source):
        """Median delay from `source` to the opposite hemisphere."""
        delays = self.geometry.delays_from(source)
        src_hemi = self.geometry.neurons[source].hemisphere
        other = [d for neu, d in zip(self.geometry.neurons, delays)
                 if neu.hemisphere != src_hemi and math.isfinite(d)]
        if not other:
            return math.inf
        other.sort()
        return other[len(other) // 2]
