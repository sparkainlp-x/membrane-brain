"""Reproducible benchmarks for membrane-brain.

Measures construction, wave generation, and projection while recording
wall time, CPU time, peak RSS, environment metadata, and a checksum of
numerical output.

Run:
    python benchmark.py --sizes 64 128 256 --seed 42 \
        --out results/benchmark.json
"""

import argparse
import hashlib
import json
import platform
import resource
import sys
import time

from brain import MembraneBrain


def checksum_pattern(pattern):
    payload = repr([(c.real, c.imag) for c in pattern]).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_case(n, seed):
    start = time.perf_counter()
    cpu_start = time.process_time()
    brain = MembraneBrain(n=n, seed=seed)
    construction_seconds = time.perf_counter() - start

    start = time.perf_counter()
    patterns = [brain.wave(source) for source in brain.seed_ids]
    wave_seconds = time.perf_counter() - start

    start = time.perf_counter()
    projections = [brain.project(pattern) for pattern in patterns]
    projection_seconds = time.perf_counter() - start

    peak_rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    return {
        "n": n,
        "seed": seed,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "construction_seconds": construction_seconds,
        "wave_seconds": wave_seconds,
        "projection_seconds": projection_seconds,
        "peak_rss_kib": peak_rss_kib,
        "first_pattern_sha256": checksum_pattern(patterns[0]),
        "winner_ids": [winner for winner, _ in projections],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark membrane-brain construction and recall."
    )
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=[64, 128, 256],
        help="Neuron counts to benchmark.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out", default="results/benchmark.json", help="JSON output path."
    )
    args = parser.parse_args()

    if any(n < 16 or n % 2 for n in args.sizes):
        parser.error("every size must be even and at least 16")

    report = [run_case(n, args.seed) for n in args.sizes]

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(f"Wrote {len(report)} benchmark cases to {args.out}")


if __name__ == "__main__":
    main()
