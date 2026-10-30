# membrane-brain v0.1.0

**A sparkainlp-x membrane in a brain-shaped toy — not a brain.**

Stdlib-only Python, seeded, reproducible, AGPL-3.0-only.

## Latest lineage reused

- **membrane-capacity**: complex oscillators, overlap recall,
  one-shot projection (argmax |overlap|).
- **refusing-membrane**: REJECT iff max |overlap| < tau, tau
  calibrated once via Youden's J and frozen, with the
  midpoint-of-best-taus improvement from membrane-vs-hopfield.
- **membrane-heart**: waves stored as ENVELOPED phasor fields
  (amplitude decays from the seed, phase advances with distance).
  There, pure phase waves were reported to fail (recognition 0.325,
  attributed to |overlap| being blind to a global phase), so this toy
  uses the enveloped form. A pure-phase control run here recognises
  98.5% of noisy probes (seed 95% interval 98.1 to 98.9), so the 0.325
  was not reproduced in this toy; that is a different construction and
  neither confirms nor refutes the membrane-heart result (see
  RESULTS.md).
- **holo-heart-neurons**: seeded neurons, k-nearest-neighbour
  edges, Dijkstra propagation delays.

## Archive and citation

Archived on Zenodo. Software DOI for v0.1.0:
[10.5281/zenodo.23680727](https://doi.org/10.5281/zenodo.23680727) (all versions: [10.5281/zenodo.23680726](https://doi.org/10.5281/zenodo.23680726)).
Cite via `CITATION.cff` (GitHub's "Cite this repository").

## Run

```bash
python demo.py    # numbers + gate + recognition + split toy
python tests.py   # 7 tests (the original suite)
python tests_rigor.py   # experiment helpers, determinism, packaging checks
python rigor.py --write # the rigor experiments (about 3 minutes) -> RESULTS.md
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

## Rigor experiments and what they found

`rigor.py` (stdlib only, seeded) repeats the demo over 200 random layouts
with confidence intervals, sweeps the noise, runs null and structural
controls, scans the gate threshold, and measures the split toy over
layouts. Everything is in **[RESULTS.md](RESULTS.md)**, generated from
`results/results.json`, with a "what was falsified" section. In short
(numbers and intervals are in RESULTS.md):

- Every number above reproduces at seed 42 on Python 3.10 to 3.13.
- Over 200 layouts the recognition and refusal rates stay near the demo's,
  but the demo is one layout, and Youden J = 1.000 is in-sample
  separability of two easy classes (held-out J is slightly below 1).
- The gate refuses isotropic random fields, **not** unfamiliar structure
  (waves from other neurons are accepted about half the time).
- Recognition does not depend on the brain-shaped layout (random wiring
  and random patterns do as well). Pure phase waves were recognised at
  98.5% in this toy, so the design note's rationale for the envelope
  (the 0.325 from membrane-heart) was not reproduced here.
- "Unreachable after the split" is true by construction; the number of
  cross edges does not predict the median delay; the cut leaves
  recognition unchanged at the default envelope width.

## Play it, and test the code in a browser

`docs/game/` is a single-page game, **The Gate**, that runs this repository's own
`brain.py` (unchanged) in your browser through a vendored Pyodide
(WebAssembly): watch a wave spread and cut the cross edges, play the refusal
gate against the real one, try to break it, and press "Test the code" to
reproduce the README numbers live with PASS/FAIL badges. Locally:
`python -m http.server --directory docs/game 8000`. It is a toy like the rest;
details in `docs/game/README.md`. Live (GitHub Pages) at
<https://sparkainlp-x.github.io/membrane-brain/game/>.

## Honest limits — read before any use

- **Not a human brain.** No lobes, cortex, ion channels, synapses
  with plasticity, or cognition. The "hemispheres" are two ellipses;
  the "experiences" are four wave snapshots.
- **Not neuroscience, not a medical device, not a diagnosis, not
  a measurement of any real person.** The split toy says nothing
  about real split-brain patients.
- "Holographic" here = overlap recall over stored patterns, the
  membrane meaning — not a laser hologram and not a display.
- Delays are in distance units, not milliseconds. Nothing here
  transfers to a real brain without a real neural model and real
  data, neither of which this package has or claims.

## Files

- `brain.py` — geometry, wave, membrane, gate
- `demo.py` — measured demo
- `tests.py` — 7 tests
- `rigor.py`, `render_results.py`, `tests_rigor.py` — rigor experiments,
  their rendering to `RESULTS.md`, and their tests
- `RESULTS.md`, `results/results.json` — measured results
- `CHANGELOG.md`, `CITATION.cff`, `.zenodo.json`, `pyproject.toml`
- `scripts/release_check.py`, `tests_release.py` — version / licence / ORCID /
  Zenodo-metadata consistency check to run before tagging a release
- `docs/game/`, `tests_game.py`, `tests_game_browser.py` — the browser game and its tests
- `DESIGN.md` — decisions, falsified designs, limits
- `LICENSE` — AGPL-3.0-only
