"""Benchmark ONE variant of the EOS26 setup: photon conservation and/or another resolution.

    python scaling/bench_variant.py --template scaling/templates/EOS26_v4.3_pc_alpha.toml --hii-dim 200 --n-threads 16
    python scaling/bench_variant.py --template ... --hii-dim 200 --phases coeval   # upstream already cached

Runs the production calls of run_scripts/sim_steps.py in order (ICs, PFs at all node
redshifts, halo catalogues, then the full coeval evolution) in one process and writes
scaling/results/variants/<label>_N<HII_DIM>.json with, per phase, wall and CPU time and
peak memory (VmHWM, reset at each phase); per coeval, its time; for the coevals, the
time of the photon-conservation set-up (its calibration simulation); the bytes it left in
the cache (node-redshift products vs. anything else, e.g. the calibration's PFs and
ionized boxes); and the global history (x_HI, T_b, T_s at each node redshift, tau_e),
so variants can be compared with each other.

Upstream boxes (ICs, PFs, halo catalogues) do not depend on the astrophysics, so they are
computed with PHOTON_CONS_TYPE = no-photoncons: 21cmFAST refuses to compute any
redshift-dependent box outside generate_coeval/run_lightcone while photon conservation is
on but not set up in the process, and the cache hashes are the same. Variants that differ
only in astrophysics (e.g. the photon-conservation types) share one cache directory
(<sim-root>/cell<cell size>_N<HII_DIM>), so only the first computes ICs, PFs and halos;
the others can run with --phases coeval.

Photon conservation with the EOS26 settings needs fixes in 21cmFAST 4.3.1 (and main as of
3 Nov 2026), see bug_reports/6_v4.3.1_photoncons_discrete_halos.md. Its calibration
simulation switches the sampler off (SOURCE_MODEL -> L-INTEGRAL), and
  1. keeps USE_UPPER_STELLAR_TURNOVER, which 21cmFAST only implements for discrete halos
     (NotImplementedError);
  2. then checks the ICs against inputs whose SOURCE_MODEL differs, which makes the
     sampler run's ICs "incompatible" (and building that error message itself fails on
     node_redshifts: "truth value of an array ... is ambiguous").
Unless --no-pc-fix, during the photon-conservation set-up only, the calibration's inputs get
USE_UPPER_STELLAR_TURNOVER = False (as drivers/global_evolution.py does; the analytic
history it is matched to has no turnover either), and boxes are checked for compatibility
as if the calibration had their SOURCE_MODEL. The variant templates also spell USE_MCGS /
RECOMB_MODEL instead of the deprecated USE_MINI_HALOS / INHOMO_RECO, which otherwise
contradict the calibration's overrides (ValueError).

Logging is INFO (DEBUG would add 21cmFAST's argument summaries to the timings).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import resource
import sys
import time
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "run_scripts"))

PHASES = ("ics", "pf", "phf", "coeval")

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--template", type=Path, required=True)
ap.add_argument("--hii-dim", type=int, required=True)
ap.add_argument("--n-threads", type=int, default=int(os.environ.get("PBS_NCPUS", 1)))
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--label", default=None, help="results name (default: template file name)")
ap.add_argument("--phases", default="all", help="all, or a comma list of ics,pf,phf,coeval")
ap.add_argument("--sim-root", type=Path, default=None,
                help="parent of the cache directories (default: $EOS26_DATA/EOS26_variant_sims on "
                     "Gadi, scaling/sims/variants elsewhere)")
ap.add_argument("--results-dir", type=Path, default=HERE / "results" / "variants")
ap.add_argument("--ignore-rbubble", action="store_true",
                help="allow R_BUBBLE_MAX > BOX_LEN/3 (tiny test boxes only)")
ap.add_argument("--no-pc-fix", dest="pc_fix", action="store_false",
                help="do not apply the photon-conservation fix described above (to see 4.3.1 fail)")
ap.add_argument("--pc-calibration-source-model", default=None, choices=("E-INTEGRAL",),
                help="source model of the photon-conservation calibration (4.3.1 uses L-INTEGRAL, "
                     "whose calibration never gets the EmissivityFields it needs)")
ap.add_argument("--log-file", type=Path, default=None)
args = ap.parse_args()

warnings.simplefilter("ignore")
label = args.label or args.template.stem.replace("EOS26_", "")
args.results_dir.mkdir(parents=True, exist_ok=True)
out_json = args.results_dir / f"{label}_N{args.hii_dim}.json"
log_file = args.log_file or args.results_dir / f"{label}_N{args.hii_dim}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
)
for name in ("py21cmfast", "sim_steps", "21cmFAST"):
    logging.getLogger(name).setLevel(logging.INFO)
log = logging.getLogger("bench")

import h5py  # noqa: E402
import numpy as np  # noqa: E402
import py21cmfast as p21c  # noqa: E402
from py21cmfast.io.caching import RunCache  # noqa: E402

import sim_steps  # noqa: E402

if args.ignore_rbubble:
    p21c.config["ignore_R_BUBBLE_MAX_error"] = True

inputs = p21c.InputParameters.from_template(
    str(args.template), HII_DIM=args.hii_dim, N_THREADS=args.n_threads, random_seed=args.seed)
upstream = inputs.evolve_input_structs(PHOTON_CONS_TYPE="no-photoncons")
so = inputs.simulation_options
cell = float(so.cell_size.value)
if args.sim_root is None:
    if os.environ.get("EOS26_DATA"):
        args.sim_root = Path(os.environ["EOS26_DATA"]) / "EOS26_variant_sims"
    elif Path("/g/data/qp00").is_dir():
        args.sim_root = Path("/g/data/qp00") / os.environ.get("USER", "user") / "EOS26_variant_sims"
    else:
        args.sim_root = HERE / "sims" / "variants"
sim_dir = args.sim_root / f"cell{cell:g}_N{args.hii_dim}_seed{args.seed}"
sim_dir.mkdir(parents=True, exist_ok=True)
cache = p21c.OutputCache(str(sim_dir))
node_z = sorted((float(z) for z in inputs.node_redshifts), reverse=True)
phases = PHASES if args.phases == "all" else tuple(p for p in PHASES if p in args.phases.split(","))
t_start = time.time()

result = json.loads(out_json.read_text()) if out_json.exists() else {}
result.update({
    "label": label,
    "template": str(args.template),
    "hii_dim": args.hii_dim,
    "dim": int(so.DIM),
    "cell_mpc": cell,
    "box_len_mpc": float(so.BOX_LEN),
    "n_threads": args.n_threads,
    "photon_cons_type": inputs.astro_options.PHOTON_CONS_TYPE,
    "py21cmfast_version": p21c.__version__,
    "sim_dir": str(sim_dir),
    "n_node_redshifts": len(node_z),
})
result.setdefault("phases", {})


def save():
    tmp = out_json.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=1, default=float))
    os.replace(tmp, out_json)


def reset_peak():
    """Reset the kernel's VmHWM (Linux); False if not possible."""
    try:
        Path("/proc/self/clear_refs").write_text("5")
        return True
    except OSError:
        return False


def peak_rss():
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024
    except OSError:
        pass
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


class Phase:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.exact = reset_peak()
        self.t0, self.c0 = time.perf_counter(), time.process_time()
        log.info(f"=== {self.name} ===")
        return self

    def __exit__(self, *exc):
        wall = time.perf_counter() - self.t0
        cpu = time.process_time() - self.c0
        rec = result["phases"].setdefault(self.name, {})
        rec.update(wall_s=wall, cpu_s=cpu, avg_cores=cpu / wall if wall else 0.0,
                   peak_rss_bytes=peak_rss(), peak_rss_exact=self.exact, ok=exc[0] is None)
        log.info(f"{self.name}: {wall / 60:.1f} min, {rec['avg_cores']:.2f} cores, "
                 f"peak RSS {rec['peak_rss_bytes'] / 2**30:.2f} GiB")
        save()
        return False


if "ics" in phases:
    with Phase("ics"):
        sim_steps.compute_initial_conditions(upstream, cache)

if "pf" in phases:
    with Phase("pf"):
        ics = RunCache.from_inputs(upstream, cache=cache).get_ics()
        for z in node_z:
            sim_steps.compute_perturbed_field(z, upstream, cache, ics).purge()
        del ics

if "phf" in phases:
    with Phase("phf"):
        sim_steps.evolve_halos(inputs=upstream, all_redshifts=upstream.node_redshifts, cache=cache,
                               initial_conditions=RunCache.from_inputs(upstream, cache=cache).get_ics(),
                               progressbar=False)

if "coeval" in phases:
    import py21cmfast.drivers.coeval as _coeval

    from py21cmfast.wrapper.inputs import InputParameters

    pc = {}
    _setup = _coeval.setup_photon_cons
    _evolve = InputParameters.evolve_input_structs

    def evolve_calibration(self, **kw):
        # the calibration simulation's overrides (wrapper/photoncons.py: calibrate_photon_cons)
        if kw.get("PHOTON_CONS_TYPE") == "no-photoncons" and "SOURCE_MODEL" in kw:
            kw.setdefault("USE_UPPER_STELLAR_TURNOVER", False)
            if args.pc_calibration_source_model:
                kw["SOURCE_MODEL"] = args.pc_calibration_source_model
                if args.pc_calibration_source_model == "E-INTEGRAL":
                    kw.setdefault("USE_EXP_FILTER", False)  # only with Lagrangian sources
        return _evolve(self, **kw)

    from py21cmfast.wrapper.outputs import OutputStruct

    _compat = OutputStruct._inputs_compatible_with

    from py21cmfast.wrapper.outputs import _HashType

    def compat_any_source_model(self, other):
        # the calibration runs with SOURCE_MODEL = L-INTEGRAL, which is part of the hash the
        # ICs (and PFs) are checked against: the sampler run's ICs would be "incompatible"
        # (they are the same field). Compare as if both had this box's SOURCE_MODEL.
        if isinstance(other, OutputStruct):
            level = _HashType(min(self._compat_hash.value, other._compat_hash.value))
            theirs = other.inputs
        elif isinstance(other, InputParameters):
            level, theirs = self._compat_hash, other
        else:
            return _compat(self, other)
        mine = self.inputs
        if (mine.matter_options is None or theirs.matter_options is None
                or mine.matter_options.SOURCE_MODEL == theirs.matter_options.SOURCE_MODEL):
            return _compat(self, other)
        align = {"SOURCE_MODEL": mine.matter_options.SOURCE_MODEL}
        if mine.astro_options is not None and theirs.astro_options is not None:
            # the turnover only exists with discrete halos, so it moves with SOURCE_MODEL
            align["USE_UPPER_STELLAR_TURNOVER"] = mine.astro_options.USE_UPPER_STELLAR_TURNOVER
            align["USE_EXP_FILTER"] = mine.astro_options.USE_EXP_FILTER
        theirs = theirs.evolve_input_structs(**align)
        return getattr(mine, f"_{level.name}_hash") == getattr(theirs, f"_{level.name}_hash")

    def timed_setup(*a, **k):
        t = time.perf_counter()
        if args.pc_fix:
            InputParameters.evolve_input_structs = evolve_calibration
            OutputStruct._inputs_compatible_with = compat_any_source_model
        try:
            data = _setup(*a, **k)
        finally:
            InputParameters.evolve_input_structs = _evolve
            OutputStruct._inputs_compatible_with = _compat
        pc["setup_s"] = time.perf_counter() - t
        pc["data"] = {key: np.asarray(v).tolist() for key, v in (data or {}).items()}
        log.info(f"photon-conservation set-up (calibration): {pc['setup_s'] / 60:.1f} min")
        return data

    _coeval.setup_photon_cons = timed_setup
    steps = []
    with Phase("coeval"):
        t = time.perf_counter()
        gen = sim_steps.generate_coevals(node_z, inputs, cache, progressbar=False)
        try:
            for coeval, is_output in gen:
                now = time.perf_counter()
                steps.append({"redshift": float(coeval.redshift), "s": now - t})
                log.info(f"coeval z={coeval.redshift:.3f}: {now - t:.1f} s")
                t = now
                if is_output:
                    coeval.prepare_for_next_snapshot(force=True)
        finally:
            gen.close()
    rec = result["phases"]["coeval"]
    rec["steps"] = steps
    rec["photoncons_setup_s"] = pc.get("setup_s", 0.0)
    rec["photoncons_fix"] = bool(args.pc_fix and inputs.astro_options.PHOTON_CONS_TYPE != "no-photoncons")
    rec["photoncons_calibration_source_model"] = args.pc_calibration_source_model or "21cmFAST default"
    rec["first_step_includes_setup"] = True
    result["photoncons_data"] = pc.get("data", {})
    save()

# what the run left in the cache: node-redshift products vs everything else (other variants'
# boxes in a shared cache directory are "already there"; anything else this run wrote, e.g. a
# calibration's boxes, is "written by this run")
rc = RunCache.from_inputs(inputs, cache=cache)
known = {}
for kind in ("InitialConditions", "PerturbedField", "HaloCatalog", "EmissivityFields", "TsBox",
             "IonizedBox", "BrightnessTemp"):
    v = getattr(rc, kind, None)
    for p in ([v] if not isinstance(v, dict) else v.values()) if v is not None else []:
        known[str(Path(p))] = kind
by_kind = {}
for p in sim_dir.rglob("*.h5"):
    kind = known.get(str(p))
    if kind is None:  # not a node-redshift box of this variant
        new = p.stat().st_mtime >= t_start
        kind = ("other, written by this run: " if new else "other, already there: ") + p.name.removesuffix(".h5")
    d = by_kind.setdefault(kind, {"files": 0, "bytes": 0})
    d["files"] += 1
    d["bytes"] += p.stat().st_size
result["cache_by_kind"] = by_kind

# global history of this variant (from its own cached boxes)
hist = {"redshift": [], "x_HI": [], "T_b_mK": [], "T_s_K": []}
for z in node_z:
    paths = {k: getattr(rc, k).get(z) for k in ("IonizedBox", "BrightnessTemp", "TsBox")}
    if not all(p and Path(p).exists() for p in paths.values()):
        continue
    vals = []
    for kind, field in (("IonizedBox", "neutral_fraction"), ("BrightnessTemp", "brightness_temp"),
                        ("TsBox", "spin_temperature")):
        with h5py.File(paths[kind], "r") as f:
            vals.append(float(np.mean(f[f"{kind}/OutputFields/{field}"][()], dtype=np.float64)))
    hist["redshift"].append(z)
    hist["x_HI"].append(vals[0])
    hist["T_b_mK"].append(vals[1])
    hist["T_s_K"].append(vals[2])
if len(hist["redshift"]) > 2:
    order = np.argsort(hist["redshift"])
    try:
        hist["tau_e"] = float(p21c.compute_tau(redshifts=np.array(hist["redshift"])[order],
                                               global_xHI=np.array(hist["x_HI"])[order], inputs=inputs))
    except Exception as e:  # noqa: BLE001
        hist["tau_e_error"] = str(e)
result["history"] = hist
save()
log.info(f"done -> {out_json}")
