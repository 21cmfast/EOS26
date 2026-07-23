#!/usr/bin/env python3
"""Run a reproducible 21cmFAST scaling measurement for one HII grid size.

Each selected phase is recomputed, while a background psutil sampler records
process RSS. Results are written as JSON for run_scalingrelation.py.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "run_scripts"))

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import sim_steps


PHASES = ("ics", "pf", "phf", "coeval")
SCRIPT_PATH = Path(__file__).resolve()
COEVAL_STRUCTS = ("BrightnessTemp", "IonizedBox", "TsBox", "HaloBox")


@dataclass
class MemoryMeasurement:
    baseline_rss_bytes: int
    peak_rss_bytes: int

    @property
    def added_rss_bytes(self) -> int:
        return max(self.peak_rss_bytes - self.baseline_rss_bytes, 0)


class RssSampler:
    """Track this process's peak resident set size while a phase executes."""

    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = interval_seconds
        self.process = psutil.Process()
        self.baseline_rss_bytes = 0
        self.peak_rss_bytes = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def __enter__(self) -> RssSampler:
        self.baseline_rss_bytes = self.process.memory_info().rss
        self.peak_rss_bytes = self.baseline_rss_bytes
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()
        self.peak_rss_bytes = max(self.peak_rss_bytes, self.process.memory_info().rss)

    def _sample(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.peak_rss_bytes = max(self.peak_rss_bytes, self.process.memory_info().rss)

    def measurement(self) -> MemoryMeasurement:
        return MemoryMeasurement(self.baseline_rss_bytes, self.peak_rss_bytes)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hii-dim", required=True, type=int, help="HII grid dimension")
    parser.add_argument(
        "--phases",
        default=",".join(PHASES),
        help=f"Comma-separated phases to measure (default: {','.join(PHASES)})",
    )
    parser.add_argument("--template", type=Path, default=ROOT / "EOS26.toml")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=ROOT / "scaling" / "cache",
        help="Directory containing isolated scaling caches",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=ROOT / "scaling" / "results",
    )
    parser.add_argument(
        "--rss-interval",
        type=float,
        default=0.1,
        help="psutil polling interval in seconds",
    )
    parser.add_argument(
        "--coeval-redshift",
        type=float,
        default=None,
        help="Final redshift of the amortized coeval-history measurement (default: lowest z)",
    )
    parser.add_argument(
        "--reuse-cache",
        action="store_true",
        help="Reuse cached products instead of forcing recomputation",
    )
    args = parser.parse_args()
    args.phases = tuple(part.strip() for part in args.phases.split(",") if part.strip())
    invalid = set(args.phases) - set(PHASES)
    if invalid:
        parser.error(f"Unknown phases: {', '.join(sorted(invalid))}")
    if args.hii_dim <= 0 or args.rss_interval <= 0:
        parser.error("--hii-dim and --rss-interval must be positive")
    return args


def paths_size(paths: list[Path]) -> dict[str, int]:
    existing = [path for path in paths if path.exists()]
    return {
        "file_count": len(existing),
        "bytes": sum(path.stat().st_size for path in existing),
    }


def closest_path(structs: dict[float, Path], redshift: float) -> Path:
    closest = min(structs, key=lambda value: abs(value - redshift))
    return Path(structs[closest])


def phase_files(runcache: RunCache, phase: str, redshift: float) -> dict[str, dict[str, int]]:
    if phase == "ics":
        return {"InitialConditions": paths_size([Path(runcache.InitialConditions)])}
    if phase == "pf":
        return {"PerturbedField": paths_size([closest_path(runcache.PerturbedField, redshift)])}
    if phase == "phf":
        return {"HaloCatalog": paths_size([Path(path) for path in runcache.HaloCatalog.values()])}
    return {
        struct: paths_size([closest_path(getattr(runcache, struct), redshift)])
        for struct in COEVAL_STRUCTS
        if getattr(runcache, struct, None)
    }


def measure_phase(
    name: str,
    action: Callable[[], None],
    runcache: RunCache,
    redshift: float,
    interval_seconds: float,
) -> dict[str, object]:
    started = time.perf_counter()
    with RssSampler(interval_seconds) as sampler:
        action()
    elapsed = time.perf_counter() - started
    memory = sampler.measurement()
    files = phase_files(runcache, name, redshift)
    return {
        "elapsed_seconds": elapsed,
        "peak_rss_bytes": memory.peak_rss_bytes,
        "rss_above_baseline_bytes": memory.added_rss_bytes,
        "files": files,
        "total_file_bytes": sum(item["bytes"] for item in files.values()),
    }


def run_phases_isolated(args: argparse.Namespace) -> None:
    """Run each requested phase in its own subprocess.

    Production runs each phase (ICs, PFs, PHFs, coevals) as a fully separate
    process (see sbatch_scripts/*_job.sh), each starting with a fresh,
    near-empty baseline RSS. Measuring multiple phases back-to-back in one
    process (the previous behaviour here) leaves earlier phases' allocations
    resident -- CPython's allocator does not reliably return freed arena
    memory to the OS, especially for large numpy arrays -- so a later
    phase's "peak_rss_bytes" ends up dominated by carryover from whichever
    phases ran before it in the same process, rather than that phase's own
    memory need. This carryover was also confirmed to vary sharply with
    HII_DIM (much more of it is retained at large HII_DIM than small), which
    is what made the fitted memory curves visibly worse than the time/
    storage curves: those two metrics are computed per-phase regardless of
    ambient RSS and are unaffected by this issue. Running one phase per
    subprocess makes every measurement match production's isolation exactly.
    """
    common = [
        sys.executable,
        str(SCRIPT_PATH),
        "--hii-dim", str(args.hii_dim),
        "--template", str(args.template),
        "--seed", str(args.seed),
        "--cache-root", str(args.cache_root),
        "--results-dir", str(args.results_dir),
        "--rss-interval", str(args.rss_interval),
    ]
    if args.coeval_redshift is not None:
        common += ["--coeval-redshift", str(args.coeval_redshift)]
    if args.reuse_cache:
        common.append("--reuse-cache")
    for phase in args.phases:
        subprocess.run(common + ["--phases", phase], check=True)


def main() -> None:
    args = parse_args()
    if len(args.phases) > 1:
        run_phases_isolated(args)
        return
    gc.collect()
    gc.disable()
    if gc.isenabled():
        raise RuntimeError("Garbage collection must be disabled during scaling measurements")

    cache_dir = args.cache_root / f"HII_DIM_{args.hii_dim}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    inputs = p21c.InputParameters.from_template(
        args.template,
        HII_DIM=args.hii_dim,
        random_seed=args.seed,
    )
    cache = p21c.OutputCache(cache_dir)
    runcache = RunCache.from_inputs(inputs, cache=cache)
    redshift = args.coeval_redshift if args.coeval_redshift is not None else min(inputs.node_redshifts)
    regenerate = not args.reuse_cache
    results: dict[str, dict[str, object]] = {}

    def initial_conditions() -> None:
        sim_steps.compute_initial_conditions(inputs, cache, regenerate=regenerate)

    if "ics" in args.phases:
        results["ics"] = measure_phase("ics", initial_conditions, runcache, redshift, args.rss_interval)

    if "pf" in args.phases:
        def perturb_field() -> None:
            sim_steps.compute_perturbed_field(
                redshift,
                inputs,
                cache,
                runcache.get_ics(),
                regenerate=regenerate,
            )

        results["pf"] = measure_phase("pf", perturb_field, runcache, redshift, args.rss_interval)

    if "phf" in args.phases:
        def evolve_halos() -> None:
            sim_steps.evolve_halos(
                inputs=inputs,
                all_redshifts=inputs.node_redshifts,
                cache=cache,
                initial_conditions=runcache.get_ics(),
                regenerate=regenerate,
                progressbar=True,
            )

        results["phf"] = measure_phase("phf", evolve_halos, runcache, redshift, args.rss_interval)

    if "coeval" in args.phases:
        def coeval() -> None:
            for _, _ in sim_steps.generate_coevals(
                [redshift],
                inputs,
                cache,
                # Reuse the IC, PF, and PHF products measured in earlier phases.
                regenerate=False,
                progressbar=True,
            ):
                pass

        results["coeval"] = measure_phase("coeval", coeval, runcache, redshift, args.rss_interval)
        results["coeval"]["elapsed_seconds"] /= len(inputs.node_redshifts)

    output = args.results_dir / f"scaling_HII_DIM_{args.hii_dim}.json"
    existing_phases: dict[str, dict[str, object]] = {}
    if output.exists():
        with output.open() as handle:
            existing_phases = json.load(handle).get("phases", {})
    existing_phases.update(results)

    payload = {
        "hii_dim": args.hii_dim,
        "box_len_mpc": float(inputs.simulation_options.BOX_LEN),
        "lowres_cell_size_mpc": float(inputs.simulation_options._LOWRES_CELL_SIZE_MPC),
        "random_seed": args.seed,
        "coeval_redshift": float(redshift),
        "coevals_averaged": len(inputs.node_redshifts),
        "gc_enabled": gc.isenabled(),
        "pid": os.getpid(),
        "phases": existing_phases,
        "max_peak_rss_bytes": max(
            (phase["peak_rss_bytes"] for phase in existing_phases.values()),
            default=0,
        ),
        "max_rss_above_baseline_bytes": max(
            (phase["rss_above_baseline_bytes"] for phase in existing_phases.values()),
            default=0,
        ),
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
