# membrane-brain v0.1.0

**A sparkainlp-x membrane in a brain-shaped toy — not a brain.**

Stdlib-only Python, seeded, reproducible, AGPL-3.0-only.

## Latest lineage reused

- **membrane-capacity**: complex oscillators, outer-product
  holographic memory, one-shot projection (argmax |overlap|).
- **refusing-membrane**: REJECT iff max |overlap| < tau, tau
  calibrated once via Youden's J and frozen, with the
  midpoint-of-best-taus improvement from membrane-vs-hopfield.
- **membrane-heart**: waves stored as ENVELOPED phasor fields
  (amplitude decays from the seed, phase advances with distance).
  Pure phase waves were falsified there (recognition 0.325, because
  |overlap| is blind to global phase) and are not repeated here.
- **holo-heart-neurons**: seeded neurons, k-nearest-neighbour
  edges, Dijkstra propagation delays.

## Run

```bash
python demo.py    # numbers + gate + recognition + split toy
python tests.py   # 7 tests
```

## The toy, in one paragraph

128 neurons in two ellipses (64 left, 64 right), 4-nearest-neighbour
edges including cross-hemisphere edges near the midline. Four stored
"experiences" are wave fields started from four seed regions
(left-front, left-back, right-front, right-back). A probe is
projected onto them: the membrane names one, or the frozen gate
refuses it. Cutting the cross edges (the toy split) makes a
left-started wave unreachable on the right — a measured property
of this graph.

## Measured (demo, seed 42)

- 128 neurons, 314 edges, 12 cross-hemisphere edges
- Spread: left-front wave reaches the right hemisphere in median
  36.41 distance units; split toy: 0 cross edges, right side
  unreachable from the left seed
- Gate calibrated: tau = 0.238, Youden J = 1.000 (frozen)
- Fresh noisy recognition (sigma = 0.15): 40/40
- Fresh random fields refused: 50/50
- Clean left-front probe: accept, left-front

## Honest limits — read before any use

- **Not a human brain.** No lobes, cortex, ion channels, synapses
  with plasticity, or cognition. The "hemispheres" are two ellipses;
  the "experiences" are four wave snapshots.
- **Not neuroscience, not a medical device, not a diagnosis, not
  a measurement of any real person.** The split toy says nothing
  about real split-brain patients.
- "Holographic" here = outer-product associative memory, the
  membrane meaning — not a laser hologram and not a display.
- Delays are in distance units, not milliseconds. Nothing here
  transfers to a real brain without a real neural model and real
  data, neither of which this package has or claims.

## Files

- `brain.py` — geometry, wave, membrane, gate
- `demo.py` — measured demo
- `tests.py` — 7 tests
- `DESIGN.md` — decisions, falsified designs, limits
- `LICENSE` — AGPL-3.0-only
