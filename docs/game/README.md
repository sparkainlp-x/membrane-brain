# The Gate: a browser game that runs the real code

A single-page game for **membrane-brain** (a synthetic toy, not a brain). The page
runs the repository's own `brain.py` (unchanged) in your browser through Pyodide
(Python compiled to WebAssembly, vendored in `vendor/pyodide/`; no CDN).

Live on GitHub Pages (`main` / `/docs`): <https://sparkainlp-x.github.io/membrane-brain/game/>.
To try it now: `python -m http.server --directory docs/game 8000` and open
<http://localhost:8000/>.

## Modes

1. **Observe**: pick a stored experience and watch the wave spread over the graph.
   Compare the intact graph, a true **cut** (the 12 cross-hemisphere edges deleted)
   and the module's `coupling=False` **split** (a re-wired graph, not a cut).
2. **Be the gate**: 24 probes in 3 levels (noise sigma 0.10 / 0.20 / 0.30). Name the
   stored experience a noisy probe came from, or refuse it. You are scored against the
   real gate with the same rule, computed from the real overlaps. You can move tau.
3. **Break the gate**: tap a neuron to start a wave there, dilute it with random noise,
   and try to make the real gate accept a wave that was never stored. "Scan" paints
   which neurons' waves the gate accepts.
4. **Test the code**: runs, live, in the browser: the README / `RESULTS.md` section 1
   numbers at seed 42 (PASS/FAIL badges), a determinism check (including a fingerprint
   of the stored patterns computed under CPython), a shuffled-label null control
   (about 25% for 4 classes) and the repository's own `tests.py`.

## Files

| path | what |
|---|---|
| `index.html`, `game.css`, `game.js` | the page (strict CSP, no inline script/style, no storage) |
| `py/bridge.py` | JSON plumbing, round generation and scoring; imports `brain.py` / `rigor.py` |
| `py/brain.py`, `py/rigor.py`, `py/tests.py` | **byte-identical copies** of the repository root files (Pages serves only `docs/`); `tests_game.py` fails if they drift |
| `vendor/pyodide/` | Pyodide 0.26.1, unmodified, with `SHA256SUMS` and `NOTICE.md` |

## Honesty notes

* Toy, synthetic, no neuroscience, no clinical meaning; "hemisphere", "cut" and
  "experience" are labels for two ellipses, a graph operation and four wave snapshots.
* Scores are a game rule on top of measured overlaps, not a measure of anything real.
* Pyodide's own files have no subresource-integrity attribute (the loader fetches them);
  integrity is provided by vendoring plus `SHA256SUMS`, checked in CI.
* First load downloads about 14 MB uncompressed (about 5.7 MB if the server gzips it; measured with gzip -9), then the browser caches it.

Tests: `python -m unittest tests_game -v` (CPython, no browser) and, with Playwright
and a Chromium available, `python -m unittest tests_game_browser -v` (set `MB_GAME_URL` to the live page to run the same checks against it).
