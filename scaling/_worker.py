#!/usr/bin/env python3
"""Measure ONE phase of ONE scaling configuration in a fresh process.

Internal: launched by ``measure.py`` (never run this by hand unless debugging).

Each phase runs in its own interpreter, just like production where ICs, PFs,
PHFs and coevals are separate jobs. The phase makes *exactly* the py21cmfast
calls of the production scripts (via ``run_scripts/sim_steps.py`` plus the same
per-step clean-up as ``run_N_PFs.py`` / ``run_N_coevals.py``), so the memory we
measure is the memory production needs.

Phases
------
setup   Load inputs, write the fully-resolved inputs TOML, self-test the
        memory tracker, report library versions and which phase products
        already exist in the simulation cache. Measures nothing.
ics     compute_initial_conditions
pf      compute_perturbed_field at *every* node redshift (production
        computes all 92; the old harness only did one, so the coeval phase
        silently computed the other 91 and was contaminated).
phf     evolve_halos over all node redshifts
coeval  generate_coeval over *all* node redshifts: the full astrophysical
        evolution, one measured step per redshift. The peak is the maximum
        over the whole evolution (memory grows as halos form).

Before a phase is measured, its own products and those of every downstream
phase are deleted from the cache, so 21cmFAST can never silently read a
previous (partial) attempt instead of computing. After the phase, all expected
products must exist *and* have been written during this attempt, otherwise
the phase fails.
"""

# Production parity: every run_scripts/run_*.py disables the cyclic GC before
# anything else is imported (glibc fragmentation mitigation). Memory depends on
# this, so the measurement must do the same.
import gc

gc.collect()
gc.disable()

import argparse  # noqa: E402
import contextlib  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import warnings  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Iterator  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    EOS26_ROOT,
    PHASES,
    SCHEMA_VERSION,
    Timer,
    append_jsonl,
    fmt_bytes,
    fmt_seconds,
    host_info,
    read_json,
    sha256_file,
    sha256_text,
    utc_now,
    write_json_atomic,
)
from _memory import PeakTracker, RssSampler, current_rss, process_max_rss  # noqa: E402

log = logging.getLogger("scaling.worker")

# Coeval-phase structs that production never writes (CacheConfig(...=False)):
# they are wiped if present but not required for completeness.
_UNCACHED_COEVAL_KINDS = {"XraySourceBox", "RadiationFields"}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def setup_logging(level: str) -> None:
    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    for name in ("scaling", "py21cmfast"):
        lg = logging.getLogger(name)
        lg.handlers[:] = [handler]
        lg.setLevel(level)
        lg.propagate = False
    # 21cmFAST emits many DeprecationWarnings for renamed v4.3 parameters; keep
    # them in the log once, but do not let them flood it.
    warnings.simplefilter("once")
    logging.captureWarnings(True)


class PhaseMeter:
    """Exact peak memory of a phase and of each of its steps.

    Every instant of the phase belongs to exactly one interval (a step or the
    gap between steps), and the high-water mark is reset at each interval
    boundary, so ``phase_peak`` is the true maximum over the whole phase and
    each step's peak is exact as well.
    """

    def __init__(self, tracker: PeakTracker, sampler: RssSampler, steps_file: Path) -> None:
        self.tracker = tracker
        self.sampler = sampler
        self.steps_file = steps_file
        self.phase_peak = 0
        self.steps: list[dict[str, Any]] = []
        self.tracker.start_interval()

    def _fold_gap(self) -> None:
        self.phase_peak = max(self.phase_peak, self.tracker.interval_peak())

    @contextlib.contextmanager
    def step(self, label: str, **meta: Any) -> Iterator[dict[str, Any]]:
        self._fold_gap()
        self.sampler.set_step(label)
        record: dict[str, Any] = {"index": len(self.steps), "step": label, **meta}
        record["rss_before_bytes"] = current_rss()
        record["started_utc"] = utc_now()
        self.tracker.start_interval()
        with Timer() as timer:
            yield record  # the body may add fields (e.g. redshift)
        peak = self.tracker.interval_peak()
        self.phase_peak = max(self.phase_peak, peak)
        record.update(
            wall_s=timer.wall,
            cpu_s=timer.cpu,
            avg_cores=timer.cores,
            peak_rss_bytes=peak,
            rss_after_bytes=current_rss(),
            cgroup_peak_sampled_bytes=self.sampler.cgroup_interval_peak(),
        )
        self.steps.append(record)
        append_jsonl(self.steps_file, record)
        log.info(
            "step %-3d %-22s%s wall=%-8s cores=%5.2f peak=%s after=%s",
            record["index"],
            record["step"],
            f" z={record['redshift']:.3f}" if "redshift" in record else "",
            fmt_seconds(timer.wall),
            timer.cores,
            fmt_bytes(peak),
            fmt_bytes(record["rss_after_bytes"]),
        )
        self.sampler.set_step("gap")
        self.tracker.start_interval()

    def finish(self) -> int:
        self._fold_gap()
        return self.phase_peak


def product_map(runcache: Any) -> tuple[dict[str, list[Path]], dict[str, list[Path]], dict[str, str], dict[str, float]]:
    """Map each phase to its cache files, derived from RunCache.

    Derived dynamically so it works for v4.2 (HaloBox/XraySourceBox) and v4.3
    (EmissivityFields/RadiationFields) without hard-coding struct names.

    Returns (all_files, required_files, kind_of_each_file, redshift_of_each_file).
    """
    import attrs

    all_files: dict[str, list[Path]] = {p: [] for p in PHASES}
    required: dict[str, list[Path]] = {p: [] for p in PHASES}
    kind_of: dict[str, str] = {}
    file_z: dict[str, float] = {}
    for field in attrs.fields(type(runcache)):
        value = getattr(runcache, field.name, None)
        if field.name == "InitialConditions" and value is not None:
            files, phase = [Path(value)], "ics"
        elif isinstance(value, dict) and value:
            files = [Path(p) for _, p in sorted(value.items(), key=lambda kv: -kv[0])]
            file_z.update({str(Path(p)): float(z) for z, p in value.items()})
            phase = {"PerturbedField": "pf", "HaloCatalog": "phf"}.get(field.name, "coeval")
        else:
            continue
        all_files[phase] += files
        if field.name not in _UNCACHED_COEVAL_KINDS:
            required[phase] += files
        kind_of.update({str(f): field.name for f in files})
    return all_files, required, kind_of, file_z


def product_status(files: list[Path], newer_than: float | None = None) -> dict[str, Any]:
    present = [f for f in files if f.exists() and f.stat().st_size > 0]
    fresh = present if newer_than is None else [f for f in present if f.stat().st_mtime >= newer_than]
    return {
        "n_expected": len(files),
        "n_present": len(present),
        "n_fresh": len(fresh),
        "bytes": sum(f.stat().st_size for f in present),
        # An empty list means the phase has nothing to write (e.g. no discrete halos).
        "complete": len(fresh) == len(files),
    }


def products_by_kind(files: list[Path], kind_of: dict[str, str]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for f in files:
        if f.exists():
            k = out.setdefault(kind_of.get(str(f), "?"), {"count": 0, "bytes": 0})
            k["count"] += 1
            k["bytes"] += f.stat().st_size
    return out


def wipe(phases: list[str], all_files: dict[str, list[Path]]) -> None:
    """Delete cache files of the given phases (only files RunCache knows about)."""
    for phase in phases:
        n = 0
        for f in all_files[phase]:
            if f.exists():
                f.unlink()
                n += 1
        if n:
            log.warning("wiped %d stale %s product file(s) before measuring", n, phase)


def library_info(p21c: Any) -> dict[str, Any]:
    import importlib.metadata as md
    import json

    version = getattr(p21c, "__version__", "unknown")
    info: dict[str, Any] = {
        "py21cmfast_version": version,
        "py21cmfast_file": str(Path(p21c.__file__).resolve()),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
    }
    match = re.search(r"\+g([0-9a-f]{7,40})", version)
    if match:
        info["py21cmfast_git_commit"] = match.group(1)
    for dist in ("21cmFAST", "21cmfast"):
        try:
            d = md.distribution(dist)
        except md.PackageNotFoundError:
            continue
        direct = d.read_text("direct_url.json")
        if direct:
            info["py21cmfast_install_source"] = json.loads(direct)
        break
    for name in ("numpy", "scipy", "h5py", "cffi", "classy", "hmf", "astropy", "psutil"):
        try:
            info[f"{name}_version"] = md.version(name)
        except md.PackageNotFoundError:
            pass
    return info


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config-dir", type=Path, required=True)
    ap.add_argument("--phase", required=True, choices=("setup", *PHASES))
    ap.add_argument("--attempt", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True, help="where to write this worker's JSON result")
    ap.add_argument("--batch-index", type=int, default=-1,
                    help="coeval phase in production-like batches: index of this batch (0 wipes the phase)")
    args = ap.parse_args()

    req = read_json(args.config_dir / "request.json")
    setup_logging(req.get("log_level", "INFO"))
    log.info("worker start: phase=%s attempt=%d pid=%d host=%s", args.phase, args.attempt, os.getpid(), host_info()["hostname"])

    # Import exactly the production call wrappers.
    sys.path.insert(0, str(EOS26_ROOT / "run_scripts"))
    import py21cmfast as p21c
    from py21cmfast.io.caching import RunCache

    import sim_steps

    overrides = {"HII_DIM": req["hii_dim"], "N_THREADS": req["n_threads"], "random_seed": req["random_seed"]}
    inputs = p21c.InputParameters.from_template(req["template"], **overrides)
    sim_dir = Path(req["sim_dir"])
    sim_dir.mkdir(parents=True, exist_ok=True)
    cache = p21c.OutputCache(sim_dir)
    runcache = RunCache.from_inputs(inputs, cache=cache)
    all_files, required, kind_of, file_z = product_map(runcache)
    node_z = list(inputs.node_redshifts)

    if args.phase == "setup":
        return do_setup(args, req, p21c, sim_steps, inputs, required)

    phase = args.phase
    batch = int(req.get("coeval_batch", 0)) if phase == "coeval" else 0
    tag = f"{phase}.attempt{args.attempt}"
    out_z = node_z
    if batch > 0:
        if args.batch_index < 0:
            raise SystemExit("coeval_batch > 0 requires --batch-index")
        tag += f".batch{args.batch_index:02d}"
    if batch <= 0 or args.batch_index == 0:
        # Invalidate this phase and everything downstream (see module docstring).
        wipe(list(PHASES[PHASES.index(phase):]), all_files)
    if batch > 0:
        # Exactly like run_N_coevals.py: the next `batch` node redshifts without
        # a BrightnessTemp (all were wiped at batch 0, so these are ours).
        done = {z for z, f in runcache.BrightnessTemp.items() if Path(f).exists()}
        out_z = sorted([z for z in node_z if z not in done][:batch], reverse=True)
        if not out_z:
            raise SystemExit(f"batch {args.batch_index}: no coeval redshifts left to compute")
        log.info("coeval batch %d: %d redshifts %.3f .. %.3f (%d already done)",
                 args.batch_index, len(out_z), out_z[0], out_z[-1], len(done))

    steps_file = args.config_dir / "phases" / f"{tag}.steps.jsonl"
    rss_csv = args.config_dir / "rss" / f"{tag}.csv"
    steps_file.unlink(missing_ok=True)
    started_epoch = time.time()
    started_utc = utc_now()
    baseline = current_rss()

    with RssSampler(rss_csv, req.get("sample_interval_s", 1.0)) as sampler:
        tracker = PeakTracker(sampler)
        log.info("memory method: %s; baseline RSS %s", tracker.method, fmt_bytes(baseline))
        meter = PhaseMeter(tracker, sampler, steps_file)
        with Timer() as total:
            if phase == "ics":
                # run_ICs.py
                with meter.step("initial_conditions"):
                    initial_conditions = sim_steps.compute_initial_conditions(inputs, cache)
                del initial_conditions

            elif phase == "pf":
                # run_N_PFs.py, over all node redshifts
                initial_conditions = runcache.get_ics()
                for i, z in enumerate(node_z):
                    with meter.step("perturbed_field", redshift=z, z_index=i):
                        pf = sim_steps.compute_perturbed_field(z, inputs, cache, initial_conditions)
                        pf.purge()
                        del pf
                        gc.collect()
                del initial_conditions

            elif phase == "phf":
                # run_PHFs.py (return value discarded, as in production)
                with meter.step("evolve_halos", n_redshifts=len(node_z)):
                    sim_steps.evolve_halos(
                        inputs=inputs,
                        all_redshifts=inputs.node_redshifts,
                        cache=cache,
                        initial_conditions=runcache.get_ics(),
                        progressbar=False,
                    )

            elif phase == "coeval":
                measure_coevals(meter, sim_steps, inputs, cache, runcache, out_z)

        phase_peak = meter.finish()
        sampler_peak = sampler.peak
        cgroup_info = sampler.cgroup.snapshot()
        if cgroup_info is not None:
            cgroup_info["phase_peak_sampled_bytes"] = sampler.cgroup_peak

    check_files = required[phase]
    if batch > 0:  # this batch must have written its own redshifts
        zs = set(out_z)
        check_files = [f for f in required[phase] if file_z.get(str(f)) in zs]
    status = product_status(check_files, newer_than=started_epoch - 2.0)
    result: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "phase": phase,
        "attempt": args.attempt,
        "label": req["label"],
        "hii_dim": req["hii_dim"],
        "n_threads": req["n_threads"],
        "started_utc": started_utc,
        "finished_utc": utc_now(),
        "wall_s": total.wall,
        "cpu_s": total.cpu,
        "avg_cores": total.cores,
        "baseline_rss_bytes": baseline,
        "peak_rss_bytes": max(phase_peak, sampler_peak),
        # vmhwm_reset: exact kernel high-water mark per interval (max'ed with the
        # sampler); sampler: background sampling only (may miss short spikes).
        "peak_rss_method": tracker.method,
        "sampler_peak_rss_bytes": sampler_peak,
        "process_lifetime_max_rss_bytes": process_max_rss(),
        # The job's memory cgroup (what PBS enforces): RSS of all processes in
        # the job + page cache. max_usage_bytes is cumulative over the PBS job.
        "cgroup": cgroup_info,
        "n_steps": len(meter.steps),
        "peak_step": max(meter.steps, key=lambda s: s["peak_rss_bytes"], default=None),
        "steps": meter.steps,
        "products": products_by_kind(all_files[phase], kind_of),
        "product_check": status,
        "rss_csv": str(rss_csv.relative_to(args.config_dir)),
        "coeval_batch": batch,
        "gc_enabled": gc.isenabled(),
        "host": host_info(),
        **library_info(p21c),
    }
    result["product_bytes_total"] = sum(k["bytes"] for k in result["products"].values())
    if batch > 0:
        result.update(batch_index=args.batch_index, batch_redshifts=out_z,
                      all_coevals_present=product_status(required[phase])["n_present"] == len(required[phase]))
    write_json_atomic(args.out, result)

    log.info(
        "phase %s done: wall=%s cores=%.2f PEAK RSS=%s (%s) products=%d/%d fresh",
        phase, fmt_seconds(total.wall), total.cores, fmt_bytes(result["peak_rss_bytes"]), tracker.method,
        status["n_fresh"], status["n_expected"],
    )
    if not status["complete"]:
        log.error("phase %s did not (re)write all expected products: %s", phase, status)
        return 3
    return 0


def measure_coevals(meter: PhaseMeter, sim_steps: Any, inputs: Any, cache: Any, runcache: Any,
                    out_z: list[float]) -> None:
    """Coeval evolution with ``out_z`` as outputs, one measured step per yield.

    Mirrors run_N_coevals.py: consume the generator until all requested
    outputs are produced, release every output coeval with
    ``prepare_for_next_snapshot(force=True)`` + ``gc.collect()``, then close the
    generator. With out_z = all node redshifts this is the full evolution in one
    process. In batch mode (out_z = the next N redshifts) the generator first
    re-establishes the history from the cache (yields with is_output=False),
    exactly like a production batch job. The first step also contains the
    generator's set-up (reading ICs, PFs and halo catalogs from the cache).
    """
    halo_files = getattr(runcache, "HaloCatalog", None) or {}
    gen = sim_steps.generate_coevals(out_z, inputs, cache, progressbar=False)
    n_out, exhausted = 0, False
    try:
        while n_out < len(out_z):
            first = not meter.steps
            with meter.step("coeval (+setup)" if first else "coeval", includes_setup=first) as rec:
                try:
                    coeval, is_output = next(gen)
                except StopIteration:
                    exhausted = True
                    rec["step"] = "generator exhausted"
                else:
                    z = float(coeval.redshift)
                    rec.update(redshift=z, is_output=bool(is_output))
                    hc = halo_files.get(z)
                    if hc is not None and Path(hc).exists():
                        rec["halo_catalog_bytes"] = Path(hc).stat().st_size
                    if is_output:
                        n_out += 1
                        coeval.prepare_for_next_snapshot(force=True)
                        gc.collect()
            if exhausted:
                break
    finally:
        # See run_N_coevals.py: close the generator and collect while the
        # interpreter is fully alive (avoids a hang in Py_Finalize).
        gen.close()
        gc.collect()
    if n_out != len(out_z):
        raise RuntimeError(f"coeval evolution yielded {n_out} outputs, expected {len(out_z)}")


def do_setup(args: argparse.Namespace, req: dict, p21c: Any, sim_steps: Any, inputs: Any, required: dict) -> int:
    inputs_path = args.config_dir / "inputs_full.toml"
    tmp = inputs_path.with_name(f".{inputs_path.name}.{os.getpid()}.tmp")
    p21c.write_template(inputs, tmp)
    os.replace(tmp, inputs_path)
    # Hash without comment lines (write_template adds a creation timestamp).
    body = "\n".join(line for line in inputs_path.read_text().splitlines() if not line.lstrip().startswith("#"))

    with RssSampler(None, 0.5) as sampler:
        method = PeakTracker(sampler).method

    so = inputs.simulation_options
    result = {
        "schema": SCHEMA_VERSION,
        "phase": "setup",
        "created_utc": utc_now(),
        "inputs_sha256": sha256_text(body),
        "template_sha256": sha256_file(Path(req["template"])),
        "sim_steps_sha256": sha256_file(EOS26_ROOT / "run_scripts" / "sim_steps.py"),
        "halo_catalog_mem_factor": getattr(sim_steps, "HALO_CATALOG_MEM_FACTOR", None),
        "memory_method": method,
        "inputs_summary": {
            "HII_DIM": int(so.HII_DIM),
            "DIM": int(so.DIM),
            "BOX_LEN_Mpc": float(so.BOX_LEN),
            "N_THREADS": int(so.N_THREADS),
            "random_seed": int(inputs.random_seed),
            "n_node_redshifts": len(inputs.node_redshifts),
            "z_max": float(max(inputs.node_redshifts)),
            "z_min": float(min(inputs.node_redshifts)),
            "has_discrete_halos": bool(inputs.matter_options.has_discrete_halos),
            "USE_TS_FLUCT": bool(inputs.astro_options.USE_TS_FLUCT),
            "MINIMIZE_MEMORY": bool(inputs.matter_options.MINIMIZE_MEMORY),
        },
        "product_status": {p: product_status(required[p]) for p in PHASES},
        "host": host_info(),
        **library_info(p21c),
    }
    write_json_atomic(args.out, result)
    log.info("setup ok: py21cmfast %s, BOX_LEN=%.1f Mpc, %d node redshifts, memory method=%s",
             result["py21cmfast_version"], so.BOX_LEN, len(inputs.node_redshifts), method)
    return 0


if __name__ == "__main__":
    sys.exit(main())
