# Changelog

## 0.2.0 (2026-11-17)

Light injection: an 808 nm PBM-style light dose coupled into the toy
(`light.py`, stdlib only, seeded). One mechanism — ATP lowers the
effective probe noise (`sigma_eff = sigma * (1 + 1.5*stress) / atp`),
ATP is hormetic (peak at dose 50, declines after), wavelength
efficiency is a wide Gaussian peaked at 808 nm, and light before
stress onset protects more than the same light after onset (stress
already accumulated is never removed). Four claims pre-registered
with frozen thresholds in `tests_light.py` (14 tests); all four PASS
at the frozen protocol (sigma 0.40, 200 trials, seed 20261117) —
measured numbers in `results/results_light.json`, claim table in the
README. `demo.py` gains a light section; the v0.1.0 demo numbers
reproduce exactly. Copyright header
(`SPDX-License-Identifier: AGPL-3.0-only` + `Copyright (c) 2026
Jean-Francois Brisson (Spark AI NLP)`) added to every Python source
file, including the `docs/game/py/` copies of `brain.py`, `rigor.py`
and `tests.py`, which stay byte-identical to the root files; game
behaviour unchanged. `light` added to `pyproject.toml` modules.

No v0.2.0 Zenodo DOI exists yet — none is invented. Until Zenodo
mints one on release, `CITATION.cff` `doi` points at the concept DOI
(10.5281/zenodo.23680726, all versions); the v0.1.0 version DOI
(10.5281/zenodo.23680727) stays listed in identifiers. On release,
set `doi` to the new version DOI and add it to identifiers.

## 0.1.0 (2026-10-27)

Initial packaged release of the toy. `brain.py`, `demo.py` and `tests.py`
are unchanged from the supplied version.

### Added
- `rigor.py`: multi-seed recognition and refusal with Wilson and seed
  bootstrap intervals, noise sweep, null and structural controls, tau
  sensitivity with ROC/AUC and structured out-of-distribution probes,
  split-toy statistics over layouts, and recognition with the cross edges
  removed. Standard library only.
- `render_results.py` and `RESULTS.md` (generated from `results/results.json`).
- `tests_rigor.py`: tests for the statistics helpers, the control variants,
  determinism, the committed results and the packaging metadata.
- `pyproject.toml`, CI workflow (Python 3.10 to 3.13), `CITATION.cff`,
  `.zenodo.json` (no DOI; none has been issued), `.gitignore`.
- README section pointing to the results; DESIGN.md addendum.
- Author affiliation in `CITATION.cff` and `.zenodo.json`, copied from membrane-arena-3x3.
- `docs/game/`: "The Gate", a single-page browser game that runs the real
  `brain.py` in a vendored Pyodide 0.26.1 (WebAssembly; no CDN, no tracking), with a
  "Test the code" panel that reproduces the README numbers live. Tests:
  `tests_game.py` (CPython, golden values at seed 42) and `tests_game_browser.py`
  (headless Chromium, compares the page with CPython); a `game-browser` CI job.
  GitHub Pages is not enabled by this change.
- `scripts/release_check.py` and `tests_release.py`: version, licence, ORCID,
  Zenodo-metadata and no-invented-DOI consistency check (stdlib only, offline).
- `.zenodo.json`: related identifier (the repository, `isSupplementTo`) and a
  `Python` keyword; `CITATION.cff`: `repository-code` and the same keyword.

### Findings recorded (see RESULTS.md)
- All README numbers reproduce at seed 42.
- Not reproduced in this toy: the 0.325 recognition for pure phase waves
  quoted from membrane-heart (98.5% here); and recognition does not depend
  on the brain-shaped layout.
- The refusal gate does not refuse structured unfamiliar input.
- `BrainGeometry(coupling=False)` re-wires rather than cuts.
