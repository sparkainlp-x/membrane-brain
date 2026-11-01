# GitHub Copilot instructions — membrane-brain

## Project intent

This repository is a **synthetic, classical, stdlib-only Python research toy** for a brain-shaped holographic associative membrane. It is **not** neuroscience, a brain model, a medical device, quantum computing, or a claim of quantum advantage.

Preserve the existing scientific-honesty framing:

- Label all outputs as SYNTHETIC.
- Do not imply biological, clinical, neurological, or quantum-hardware validity.
- Preserve negative results and refusal behavior; do not tune them away.
- Keep the implementation standard-library-only unless the user explicitly approves a dependency.

## Non-negotiable engineering rules

- Maintain seeded reproducibility. Never introduce hidden global randomness.
- Prefer pure functions and explicit `random.Random` instances.
- Preserve deterministic ordering of neurons, edges, patterns, and probabilities.
- Use `math.fsum` for numerically sensitive real-valued reductions where practical.
- Validate numerical inputs and fail loudly on NaN, infinity, zero norms, and empty calibration sets.
- Do not silently clamp, coerce, or substitute values without documenting the policy.
- Keep public APIs backward compatible unless the user asks for a breaking change.

## Performance rules

- Do not scan the full edge list inside per-node graph algorithms.
- Precompute adjacency lists once in `BrainGeometry.__init__`.
- Use `heapq.nsmallest` for k-nearest-neighbour construction.
- Keep Dijkstra at approximately `O(E log V)` using an adjacency list and lazy heap deletion.
- Add or update benchmarks in `benchmark.py` for any algorithmic change affecting `BrainGeometry`, `MembraneBrain.wave`, `project`, `overlaps`, or `calibrate`.
- Report wall time, CPU time, peak RSS, input size, seed, Python version, and a checksum of numerical outputs.

## Numerical rules

- Use a documented epsilon policy for norms and degenerate projections.
- Reject zero or non-finite vectors in `normalize`.
- Make `project` explicitly return `None` for a degenerate zero-overlap field.
- Use deterministic tie-breaking in `max` operations.
- Do not compare floating-point values with `==`; use `math.isclose` or explicit tolerances.
- Preserve unit norms for stored patterns and normalized probes.

## Testing rules

- Add tests beside behavioral changes; update `tests.py` or add a focused `tests_*.py` module.
- Cover:

  - `normalize`, `overlap`, `noisy`, and `rand_field`
  - zero-vector and non-finite input rejection
  - unit-norm invariants
  - deterministic tie-breaking
  - empty calibration inputs
  - graph connectivity and split behavior
  - benchmark output schema and checksum stability

- Keep tests deterministic and seeded.
- Do not weaken an existing assertion merely to make a test pass.

## Documentation rules

- Update `README.md`, `RESULTS.md`, and `CHANGELOG.md` for user-visible behavior, performance characteristics, numerical policy, or reproducibility changes.
- State complexity in Big-O terms when changing graph or projection algorithms.
- Include exact commands to reproduce benchmarks and tests.
- Never describe the toy as evidence about real brains, quantum devices, or clinical systems.

## Preferred workflow

1. Refactor one numerical or graph bottleneck per pull request.
2. Add regression tests first or alongside the change.
3. Run:

   ```bash
   python tests.py
   python tests_rigor.py
   python benchmark.py --sizes 64 128 256 --seed 42 --out results/benchmark.json
   ```

4. Include before/after timing, memory, checksum, and behavioral-test results in the PR description.
5. Do not merge if checksums change without an explicit, documented numerical-policy change.
