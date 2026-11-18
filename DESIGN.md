# DESIGN.md — membrane-brain v0.2.0

## Decisions

- **Two ellipses, not a traced brain.** A traced outline would look
  anatomical while adding nothing checkable. Two ellipses give a
  left/right structure, a midline, and cross edges — the only
  structure the experiments actually use.
- **Wave snapshots as experiences, not random patterns.** Random
  patterns (membrane-capacity style) would be easier, but they would
  sever the link between layout and memory. Wave fields tie each
  stored pattern to a seed region, so recognition means "this
  activity started over there" — the one interpretable statement
  the toy can make.
- **Envelope from the start.** membrane-heart proved pure phase
  waves indistinguishable to |overlap| (0.325 recognition). The
  envelope (amplitude decays with distance from the seed) is
  therefore not a tweak but a precondition, and it is documented
  as such in the module docstring.
- **Midpoint tau.** Same improvement as membrane-heart and
  membrane-vs-hopfield: the midpoint of the maximal-J taus, not
  the first best, so the frozen gate is not sitting on a gap edge.
- **Split as a graph cut, labelled a toy.** Cutting cross edges
  and measuring unreachable delays is a clean structural fact.
  It is never mapped to a clinical condition in code, docs, or
  demo output.

## Falsified / rejected designs

- **Learning / plasticity.** Rejected for v0.1.0: Hebbian updates
  exist in membrane-crystallization, but adding them here would
  blur storage and learning into one claim. This package stores
  four fixed patterns and measures recognition and refusal only.
- **Region names from anatomy (frontal, occipital, …).**
  Rejected: the ellipses have no lobes. Seed regions are named by
  position (left-front, left-back, …) so no anatomical knowledge
  is implied.
- **A "consciousness" or "thought" score.** Rejected: the membrane
  returns a winner and probabilities. Those numbers are overlaps,
  not thoughts, and no summary score is invented from them.
- **EEG-like output.** Rejected, as with membrane-heart's ECG:
  synthesising a clinical-looking trace from a toy would be
  misleading. Outputs are counts, overlaps, and delays.

## Limits, restated

Synthetic only. Width 12, period 40, delays in distance units —
none of these are biological parameters. The refusal rate is a
property of this toy's random fields, not a sensitivity or
specificity for anything real.

## v0.2.0 — light injection (see light.py, tests_light.py)

Decisions, in the order they were fixed — before the claim thresholds
were frozen and the official measurement run:

- **One coupling only: energy lowers effective noise.** Light dose
  enters recall through a single channel,
  `sigma_eff = sigma * (1 + 1.5*stress) / atp`. A single channel keeps
  the four claims attributable: if recall moves, it moved through the
  noise, not through three knobs at once.
- **Hormetic ATP curve, `atp = 1 + 0.03*dose*exp(-dose/50)*eff`.**
  `dose*exp(-dose/dose_opt)` is the simplest biphasic shape with an
  interior optimum: it rises, peaks exactly at DOSE_OPT = 50, and
  decays back toward baseline instead of saturating. Constants were
  chosen during design so the toy's effects sit on the steep part of
  the measured recall-vs-noise curve (baseline sigma 0.40, recall
  0.77, slope about −0.13 per 0.05 sigma): with GAIN = 0.03 the
  optimum-dose recall is 0.97 and the 3x-optimum recall 0.855, so the
  biphasic gaps are measurable, not ceiling- or floor-bound.
- **Wavelength as a wide Gaussian (width 300 nm), not a sharp peak.**
  Efficiency 0.70 at 630 nm and 0.72 at 980 nm vs 1.0 at 808 nm makes
  wavelength a weak modulation by construction, so claim (iii) tests
  the design (dose is the strong predictor) rather than a knife-edge.
- **Stress as a noise multiplier, not pattern fragmentation.** Stress
  multiplies effective noise by up to 2.5x. Fragmenting the stored
  patterns was rejected (below): a multiplier is one term, checkable
  in isolation, and monotone in stress by construction.
- **Timing as an irreversible accumulator.** Stress is 0 before
  onset, +0.10/step after, capped at 1. Light multiplies later
  increments by (1 − protection) with protection = 1 − 1/atp, and
  stress already accumulated is never removed. Early light therefore
  ends with less stress than the same dose applied late — the whole
  content of claim (iv). Steps 12, onset 2, early step 0, late step
  10: final stress 0.644 early vs 0.929 late.
- **One frozen protocol for all four claims** (sigma 0.40, 200 trials,
  seed 20261117) and one seeded rng stream per measurement, so the
  same underlying noise directions are reused across conditions and
  the recall-vs-noise curve is smooth rather than sampling-noisy.
  Thresholds were frozen in tests_light.py after the design above was
  fixed; the design was checked for robustness across probe seeds
  (1, 7, 99, 12345) during design — all four claims held on every
  seed — but the thresholds were never adjusted after measuring.
- **Results as a recomputable JSON.** `light.measure_all()` returns
  the full grids plus verdicts; `results/results_light.json` is the
  committed output and `tests_light.py` asserts it equals a fresh
  computation.

Rejected for v0.2.0:

- **Scaling pattern amplitude instead of noise.** Multiplying the
  stored patterns by the ATP factor would change overlaps directly,
  but after `normalize()` in `noisy()` the amplitude mostly cancels
  — the effect would be small, indirect, and hard to attribute.
  Noise coupling is the honest channel in this code.
- **Stress as pattern fragmentation.** Blending stored patterns
  toward random fields would make stress a second, independent
  degradation channel alongside the noise multiplier. Two channels
  would blur which one any claim tests. Kept as a possible later
  variant, not in v0.2.0.
- **Light restoring fragmented patterns.** Letting late light undo
  accumulated stress would erase the early-vs-late distinction the
  timing claim is about, and would smuggle in a recovery claim the
  toy has no basis for. Late light only slows further accumulation.
- **A sharp wavelength peak.** A narrow Gaussian would make claim
  (iii) trivially pass by construction and would overstate the
  evidence (dose matters more than wavelength alone). The wide peak
  is the conservative choice.
- **A clinical dose unit.** Doses are toy units, not J/cm²; no
  irradiance, no session length, no device. Any mapping to a real
  PBM protocol would be invented, so none is made.

## Addendum after the rigor experiments (see RESULTS.md)

Added without editing the decisions above. Measured in `rigor.py`:

- **Envelope as a precondition: not shown in this toy.** Pure phase
  waves from different seeds are recognised at about the same rate as
  enveloped ones; the 0.325 quoted from membrane-heart does not
  reproduce here. The global-phase blindness of |overlap| is real, but
  these waves do not differ only by a global phase. The envelope is kept
  because it lowers pattern overlaps and makes the spread statistics
  well defined, not because recognition needs it.
- **Split as a graph cut.** `BrainGeometry(coupling=False)` re-wires the
  midline neurons (it drops cross candidates before the k-nearest step),
  so it is not the intact graph minus its cross edges. "Unreachable"
  after either operation is true by construction.
- **Refusal.** The gate is calibrated and tested against the same two
  generators. It refuses isotropic random fields, not unfamiliar
  structure.
