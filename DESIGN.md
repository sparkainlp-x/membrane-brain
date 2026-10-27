# DESIGN.md — membrane-brain v0.1.0

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
