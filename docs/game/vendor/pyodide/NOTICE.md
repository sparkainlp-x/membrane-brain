# Vendored Pyodide 0.26.1 (unmodified)

The five files next to this notice are the **unmodified** `pyodide/` files of the
official release asset `pyodide-core-0.26.1.tar.bz2`:
<https://github.com/pyodide/pyodide/releases/tag/0.26.1>

They are vendored (not loaded from a CDN) so that the game makes no request to
any third-party host: no CDN, no tracking, works offline once the page is open.

| file | role |
|---|---|
| `pyodide.js` | loader |
| `pyodide.asm.js`, `pyodide.asm.wasm` | CPython 3.12 compiled to WebAssembly |
| `python_stdlib.zip` | the Python standard library |
| `pyodide-lock.json` | package lock (no extra packages are loaded) |

`SHA256SUMS` records the SHA-256 of each file; `tests_game.py` re-checks it, and
the same digests were obtained from the official release asset and from
`cdn.jsdelivr.net/pyodide/v0.26.1/full/` on 2026-10-26.
To verify by hand: `cd docs/game/vendor/pyodide && sha256sum -c SHA256SUMS`.

Licences of the vendored components: Pyodide is MPL-2.0
(<https://github.com/pyodide/pyodide/blob/0.26.1/LICENSE>); it embeds CPython
(PSF licence) and Emscripten runtime code. Their source is available from the
Pyodide release linked above. The membrane-brain code in `../../py/` and the
game itself are AGPL-3.0-only (see the repository `LICENSE`).
