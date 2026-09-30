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
COEVAL_STRUCTS = ("BrightnessTemp", "IonizedBox", "TsBox", "HaloBox", "XraySourceBox")


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
        "--n-threads",
        type=int,
        default=None,
        help="Override N_THREADS from the parameter template (default: template value)",
    )
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
        "--max-coevals",
        type=int,
        default=None,
        help=(
            "Stop the coeval-history measurement after this many yielded coevals. "
            "The JSON is checkpointed after every coeval regardless."
        ),
    )
    parser.add_argument(
        "--reuse-cache",
        action="store_true",
        help="Reuse cached products instead of forcing recomputation",
    )
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help=(
            "Re-measure phases even if this results JSON already contains a measurement. "
            "By default, existing measurements are preserved on resumed jobs."
        ),
    )
    args = parser.parse_args()
    args.phases = tuple(part.strip() for part in args.phases.split(",") if part.strip())
    invalid = set(args.phases) - set(PHASES)
    if invalid:
        parser.error(f"Unknown phases: {', '.join(sorted(invalid))}")
    if (
        args.hii_dim <= 0
        or args.rss_interval <= 0
        or (args.n_threads is not None and args.n_threads <= 0)
        or (args.max_coevals is not None and args.max_coevals <= 0)
    ):
        parser.error("--hii-dim, --rss-interval, --n-threads, and --max-coevals must be positive")
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
    wall_started = time.perf_counter()
    cpu_started = time.process_time()

    with RssSampler(interval_seconds) as sampler:
        action()

    elapsed = time.perf_counter() - wall_started
    cpu_seconds = time.process_time() - cpu_started

    memory = sampler.measurement()
    files = phase_files(runcache, name, redshift)

    average_cores = cpu_seconds / elapsed if elapsed else 0.0

    print(
        f"[{name}] "
        f"wall={elapsed:.2f}s "
        f"cpu={cpu_seconds:.2f}s "
        f"average_cores={average_cores:.2f}",
        flush=True,
    )

    return {
        "elapsed_seconds": elapsed,
        "cpu_seconds": cpu_seconds,
        "average_cpu_cores": average_cores,
        "peak_rss_bytes": memory.peak_rss_bytes,
        "rss_above_baseline_bytes": memory.added_rss_bytes,
        "files": files,
        "total_file_bytes": sum(item["bytes"] for item in files.values()),
    }



def load_existing_phases(output: Path) -> dict[str, dict[str, object]]:
    """Load already-recorded phase measurements from an existing results JSON."""
    if not output.exists():
        return {}
    with output.open() as handle:
        return json.load(handle).get("phases", {})


def phase_cache_complete(
    runcache: RunCache,
    phase: str,
    redshift: float,
    inputs: p21c.InputParameters,
) -> bool:
    """Return whether the cache contains the full product expected for a phase."""
    try:
        files = phase_files(runcache, phase, redshift)
    except (AttributeError, KeyError, TypeError, ValueError):
        return False

    if phase == "ics":
        item = files.get("InitialConditions", {})
        return item.get("file_count", 0) >= 1 and item.get("bytes", 0) > 0

    if phase == "pf":
        item = files.get("PerturbedField", {})
        return item.get("file_count", 0) >= 1 and item.get("bytes", 0) > 0

    if phase == "phf":
        item = files.get("HaloCatalog", {})
        return (
            item.get("file_count", 0) >= len(inputs.node_redshifts)
            and item.get("bytes", 0) > 0
        )

    return False


def should_preserve_phase_measurement(
    *,
    phase: str,
    existing_phases: dict[str, dict[str, object]],
    force_rerun: bool,
) -> bool:
    """Whether an existing timing/memory measurement must not be overwritten."""
    return not force_rerun and phase in existing_phases


def write_results_json(
    output: Path,
    *,
    args: argparse.Namespace,
    inputs: p21c.InputParameters,
    redshift: float,
    new_results: dict[str, dict[str, object]],
) -> None:
    """Merge phase results into the scaling JSON and write it atomically."""
    existing_phases: dict[str, dict[str, object]] = {}
    if output.exists():
        with output.open() as handle:
            existing_phases = json.load(handle).get("phases", {})

    existing_phases.update(new_results)
    payload = {
        "hii_dim": args.hii_dim,
        "box_len_mpc": float(inputs.simulation_options.BOX_LEN),
        "lowres_cell_size_mpc": float(inputs.simulation_options._LOWRES_CELL_SIZE_MPC),
        "n_threads": int(inputs.simulation_options.N_THREADS),
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

    # Atomic replacement means a walltime kill cannot leave a truncated JSON.
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(output)


def measure_coevals_incrementally(
    *,
    args: argparse.Namespace,
    inputs: p21c.InputParameters,
    cache: p21c.OutputCache,
    runcache: RunCache,
    redshift: float,
    output: Path,
) -> dict[str, object]:
    """Measure coeval evolution and checkpoint statistics after every yielded coeval."""
    process = psutil.Process()
    phase_baseline_rss = process.memory_info().rss
    phase_peak_rss = phase_baseline_rss

    total_elapsed = 0.0
    total_cpu = 0.0
    completed = 0
    samples: list[dict[str, object]] = []
    target = len(inputs.node_redshifts)
    limit = target if args.max_coevals is None else min(args.max_coevals, target)

    generator = sim_steps.generate_coevals(
        [redshift],
        inputs,
        cache,
        # Reuse the IC, PF, and PHF products measured in earlier phases.
        regenerate=False,
        progressbar=True,
    )

    try:
        while completed < limit:
            wall_started = time.perf_counter()
            cpu_started = time.process_time()

            # Advancing the generator performs exactly one yielded coeval step,
            # so each step gets its own wall/CPU/RSS measurement.
            with RssSampler(args.rss_interval) as sampler:
                try:
                    yielded = next(generator)
                except StopIteration:
                    break

            elapsed = time.perf_counter() - wall_started
            cpu_seconds = time.process_time() - cpu_started
            memory = sampler.measurement()

            completed += 1
            total_elapsed += elapsed
            total_cpu += cpu_seconds
            phase_peak_rss = max(phase_peak_rss, memory.peak_rss_bytes)

            sample: dict[str, object] = {
                "index": completed,
                "elapsed_seconds": elapsed,
                "cpu_seconds": cpu_seconds,
                "average_cpu_cores": cpu_seconds / elapsed if elapsed else 0.0,
                "peak_rss_bytes": memory.peak_rss_bytes,
            }
            if isinstance(yielded, tuple) and yielded:
                first = yielded[0]
                if isinstance(first, (int, float, str, bool)) or first is None:
                    sample["yielded_step"] = first
            samples.append(sample)

            files = phase_files(runcache, "coeval", redshift)
            result: dict[str, object] = {
                # Keep elapsed_seconds compatible with the old output:
                # it is the mean walltime per completed coeval.
                "elapsed_seconds": total_elapsed / completed,
                # Keep cpu_seconds cumulative, as in the previous implementation.
                "cpu_seconds": total_cpu,
                "average_cpu_cores": total_cpu / total_elapsed if total_elapsed else 0.0,
                "peak_rss_bytes": phase_peak_rss,
                "rss_above_baseline_bytes": max(phase_peak_rss - phase_baseline_rss, 0),
                "files": files,
                "total_file_bytes": sum(item["bytes"] for item in files.values()),
                "coevals_completed": completed,
                "coevals_target": target,
                "total_elapsed_seconds": total_elapsed,
                "samples": samples,
            }

            write_results_json(
                output,
                args=args,
                inputs=inputs,
                redshift=redshift,
                new_results={"coeval": result},
            )
            print(
                f"[coeval {completed}/{target}] "
                f"wall={elapsed:.2f}s "
                f"cpu={cpu_seconds:.2f}s "
                f"cores={sample['average_cpu_cores']:.2f} "
                f"avg_wall={result['elapsed_seconds']:.2f}s "
                f"avg_cores={result['average_cpu_cores']:.2f} "
                f"peak_rss={phase_peak_rss / 1e9:.2f}GB",
                flush=True,
            )

        if completed == 0:
            raise RuntimeError("generate_coevals produced no coevals")

        return result
    finally:
        close = getattr(generator, "close", None)
        if close is not None:
            close()


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
    if args.n_threads is not None:
        common += ["--n-threads", str(args.n_threads)]
    if args.coeval_redshift is not None:
        common += ["--coeval-redshift", str(args.coeval_redshift)]
    if args.max_coevals is not None:
        common += ["--max-coevals", str(args.max_coevals)]
    if args.reuse_cache:
        common.append("--reuse-cache")
    if args.force_rerun:
        common.append("--force-rerun")
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
    input_overrides = {
        "HII_DIM": args.hii_dim,
        "random_seed": args.seed,
    }
    if args.n_threads is not None:
        input_overrides["N_THREADS"] = args.n_threads
    inputs = p21c.InputParameters.from_template(args.template, **input_overrides)
    cache = p21c.OutputCache(cache_dir)
    runcache = RunCache.from_inputs(inputs, cache=cache)
    redshift = args.coeval_redshift if args.coeval_redshift is not None else min(inputs.node_redshifts)
    regenerate = not args.reuse_cache
    results: dict[str, dict[str, object]] = {}
    output = args.results_dir / f"scaling_HII_DIM_{args.hii_dim}_N_THREADS_{args.n_threads}.json"
    existing_phases = load_existing_phases(output)

    def initial_conditions() -> None:
        sim_steps.compute_initial_conditions(inputs, cache, regenerate=regenerate)

    if "ics" in args.phases:
        cached = phase_cache_complete(runcache, "ics", redshift, inputs)
        if should_preserve_phase_measurement(
            phase="ics", existing_phases=existing_phases, force_rerun=args.force_rerun
        ):
            if cached:
                print("[ics] Existing JSON measurement and cache found; preserving both and skipping.", flush=True)
            else:
                print(
                    "[ics] Existing JSON measurement found but cache is missing; "
                    "rebuilding cache WITHOUT replacing the recorded timing/memory measurement.",
                    flush=True,
                )
                initial_conditions()
        elif args.reuse_cache and cached:
            print(
                "[ics] Cached IC already exists but no prior JSON measurement is available; "
                "skipping rather than recording cache-read time as a scaling measurement.",
                flush=True,
            )
        else:
            results["ics"] = measure_phase(
                "ics", initial_conditions, runcache, redshift, args.rss_interval
            )

    if "pf" in args.phases:
        def perturb_field() -> None:
            sim_steps.compute_perturbed_field(
                redshift,
                inputs,
                cache,
                runcache.get_ics(),
                regenerate=regenerate,
            )

        cached = phase_cache_complete(runcache, "pf", redshift, inputs)
        if should_preserve_phase_measurement(
            phase="pf", existing_phases=existing_phases, force_rerun=args.force_rerun
        ):
            if cached:
                print("[pf] Existing JSON measurement and cache found; preserving both and skipping.", flush=True)
            else:
                print(
                    "[pf] Existing JSON measurement found but cache is missing; "
                    "rebuilding cache WITHOUT replacing the recorded timing/memory measurement.",
                    flush=True,
                )
                perturb_field()
        elif args.reuse_cache and cached:
            print(
                "[pf] Cached PF already exists but no prior JSON measurement is available; "
                "skipping rather than recording cache-read time as a scaling measurement.",
                flush=True,
            )
        else:
            results["pf"] = measure_phase(
                "pf", perturb_field, runcache, redshift, args.rss_interval
            )

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

        cached = phase_cache_complete(runcache, "phf", redshift, inputs)
        if should_preserve_phase_measurement(
            phase="phf", existing_phases=existing_phases, force_rerun=args.force_rerun
        ):
            if cached:
                print("[phf] Existing JSON measurement and cache found; preserving both and skipping.", flush=True)
            else:
                print(
                    "[phf] Existing JSON measurement found but cache is missing; "
                    "rebuilding cache WITHOUT replacing the recorded timing/memory measurement.",
                    flush=True,
                )
                evolve_halos()
        elif args.reuse_cache and cached:
            print(
                "[phf] Cached halo catalogs already exist but no prior JSON measurement is available; "
                "skipping rather than recording cache-read time as a scaling measurement.",
                flush=True,
            )
        else:
            results["phf"] = measure_phase(
                "phf", evolve_halos, runcache, redshift, args.rss_interval
            )

    if "coeval" in args.phases:
        # A partial coeval checkpoint is already a valid scaling measurement.  Do not
        # restart the coeval evolution and overwrite it on a resumed job.  This is
        # especially important for discrete-halo runs, where 21cmFAST may need to
        # restart the redshift evolution rather than resume from the last cached node.
        if should_preserve_phase_measurement(
            phase="coeval", existing_phases=existing_phases, force_rerun=args.force_rerun
        ):
            completed = existing_phases["coeval"].get("coevals_completed")
            if completed is None:
                print("[coeval] Existing JSON measurement found; preserving it and skipping.", flush=True)
            else:
                print(
                    f"[coeval] Existing checkpoint contains {completed} measured coeval(s); "
                    "preserving it and skipping. Use --force-rerun to replace it.",
                    flush=True,
                )
        else:
            results["coeval"] = measure_coevals_incrementally(
                args=args,
                inputs=inputs,
                cache=cache,
                runcache=runcache,
                redshift=redshift,
                output=output,
            )

    write_results_json(
        output,
        args=args,
        inputs=inputs,
        redshift=redshift,
        new_results=results,
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()