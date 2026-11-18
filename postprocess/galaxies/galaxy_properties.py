"""Galaxy properties of an EOS26 run at every node redshift, written into its cache.

    python postprocess/galaxies/galaxy_properties.py --log-file logs/galaxies.log
    python postprocess/galaxies/galaxy_properties.py --test --log-file ...        # HII_DIM=200 test
    python postprocess/galaxies/galaxy_properties.py --zmax 8 --log-file ...      # some node redshifts

The cached HaloCatalog of a node redshift holds the halo masses, the Lagrangian halo
positions and the random numbers of the scatter, but not the galaxy properties: 21cmFAST
computes those while it grids the halos (EmissivityFields) and does not keep them. This
script computes them again with py21cmfast.perturb_halo_catalog, as tuesday's [CII] code
does, from the cached InitialConditions, the HaloCatalog and the TsBox and IonizedBox of
the previous node redshift (the Lyman-Werner, relative-velocity and photoheating feedback
on the turnover masses). It writes one PerturbedHaloCatalog per node redshift into the
run's cache, with, for every halo above SAMPLER_MIN_MASS: the Eulerian position (cMpc), halo
mass, stellar masses and SFRs of ACGs and MCGs, ionising emissivity (n_ion), X-ray
luminosity and f_esc-weighted SFR (computed per halo; the run grids n_ion times a constant
instead). These are the galaxies of the line-intensity maps and of the galaxy catalogue.

They are the properties 21cmFAST used in the run, to float32 round-off: the run reads the
turnover masses at the double-precision halo positions, perturb_halo_catalog at the float32
positions it stores. test_galaxy_properties.py checks this on a small run. Needs
py21cmfast >= 4.3.2 (the v4.3_post venv): in 4.3.1 perturb_halo_catalog does not set up the
tables it needs and crashes. The C code of 4.3.1 and 4.3.2 is the same.

The files go where 21cmFAST caches a PerturbedHaloCatalog,
<cache>/<matter-cosmo hash>/<seed>/<z-grid hash>/<z>/PerturbedHaloCatalog.h5, next to the
HaloCatalog. That path does not depend on the astrophysical parameters, but the galaxy
properties do, so the files belong to the cache of their own run only: link_upstream.py
links the HaloCatalog files, not these, and an existing file with other astrophysical
parameters stops the script. Size: ~1 TB for EOS26 (2.2e10 halos at 44 bytes; 73 GB at z=5).

Resumable: node redshifts whose file is complete are skipped; each file is written under a
temporary name and renamed once complete. Otherwise it only reads the cache, and stops
first if a box it needs is missing. 21cmFAST runs with $EOS26_RUN_THREADS threads, as the
coevals do (run_scripts/sim_steps.py). No random numbers are drawn here and each halo is
computed on its own, so the number of threads does not change the result.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIND = "PerturbedHaloCatalog"


def plan_nodes(inputs, zmin: float | None = None, zmax: float | None = None) -> list[tuple[float, float | None]]:
    """(z, previous node redshift or None) for the node redshifts in [zmin, zmax], high to low.

    As in 21cmFAST's redshift loop, the feedback comes from the boxes of the previous node
    redshift, and only below Z_HEAT_MAX.
    """
    zs = sorted(inputs.node_redshifts, reverse=True)
    z_heat_max = inputs.simulation_options.Z_HEAT_MAX
    plan = []
    for i, z in enumerate(zs):
        if (zmin is not None and z < zmin - 1e-6) or (zmax is not None and z > zmax + 1e-6):
            continue
        plan.append((z, zs[i - 1] if i > 0 and z < z_heat_max else None))
    return plan


def output_path(cache_dir: str | Path, inputs, z: float) -> Path:
    """21cmFAST's cache path of the PerturbedHaloCatalog at z."""
    from py21cmfast.io.caching import OutputCache

    rel = OutputCache._fill_path_template(kind=KIND, inputs=inputs, redshift=z, all_seeds=False)
    return Path(cache_dir) / rel


def _hashes(inputs) -> dict:
    from py21cmfast.io.caching import OutputCache

    return OutputCache._get_hashes(inputs)


def missing_boxes(run, plan) -> list[Path]:
    """Cached boxes that the planned node redshifts need and that are not there."""
    need = [Path(run.InitialConditions)]
    for z, z_prev in plan:
        need.append(Path(run.HaloCatalog[z]))
        if z_prev is not None:
            need += [Path(run.TsBox[z_prev]), Path(run.IonizedBox[z_prev])]
    return [p for p in need if not p.exists()]


def is_complete(path: Path, inputs, n_halos: int) -> bool:
    """True if path holds the PerturbedHaloCatalog of these inputs with n_halos halos.

    Raises SystemExit if it was computed with other inputs (e.g. the other EOS26 run's
    astrophysical parameters), which share its cache path.
    """
    from py21cmfast.io.h5 import read_output_struct

    if not path.exists():
        return False
    try:
        old = read_output_struct(path)
    except Exception:  # damaged: compute it again
        return False
    if _hashes(old.inputs) != _hashes(inputs):
        raise SystemExit(f"{path} was computed with other input parameters (another run?); "
                         "move it away or remove it")
    return old.n_halos == n_halos


def make_node(run, inputs, ics, z: float, z_prev: float | None):
    """The PerturbedHaloCatalog at z, and the HaloCatalog it comes from."""
    import py21cmfast as p21c

    import numpy as np

    halos = run.get_output_struct_at_z("HaloCatalog", z=z)
    if halos.n_halos == 0:
        # no halos yet (EOS26: above z ~ 23): perturb_halo_catalog would crash on the empty
        # arrays, so write an empty catalogue
        galaxies = p21c.PerturbedHaloCatalog.new(inputs=inputs, redshift=z, buffer_size=0)
        for name, array in galaxies.arrays.items():
            galaxies.set(name, np.zeros(array.shape, dtype=array.dtype))
        galaxies.n_halos = 0
        return galaxies, halos
    # perturb_halo_catalog reads every halo array, but loads only some from disk itself
    halos.load_all()
    previous = {}
    if z_prev is not None:
        previous["previous_spin_temp"] = run.get_output_struct_at_z("TsBox", z=z_prev)
        previous["previous_ionize_box"] = run.get_output_struct_at_z("IonizedBox", z=z_prev)
    galaxies = p21c.perturb_halo_catalog(initial_conditions=ics, inputs=inputs, halo_catalog=halos,
                                         **previous)
    for box in previous.values():
        box.purge()
    if galaxies.n_halos != halos.n_halos:
        raise RuntimeError(f"z={z}: {halos.n_halos} halos in the HaloCatalog, {galaxies.n_halos} perturbed")
    return galaxies, halos


def write_atomic(struct, path: Path) -> None:
    """Write struct to path under a temporary name, then rename it."""
    from py21cmfast.io.h5 import write_output_to_hdf5

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".partial")
    tmp.unlink(missing_ok=True)
    write_output_to_hdf5(struct, path=tmp)
    os.replace(tmp, path)


def run_galaxies(inputs, cache_dir: str | Path, zmin=None, zmax=None, clobber=False,
                 log=None, rss=None) -> list[Path]:
    """Write the PerturbedHaloCatalog of every planned node redshift; return the files written."""
    import contextlib
    import gc
    import logging

    import numpy as np
    import py21cmfast as p21c
    from py21cmfast.io.caching import RunCache

    from packaging.version import Version

    if Version(p21c.__version__) < Version("4.3.2"):
        raise SystemExit(f"py21cmfast {p21c.__version__}: perturb_halo_catalog needs >= 4.3.2 "
                         "(EOS26_VERSION=v4.3_post)")
    log = log or logging.getLogger(__name__)
    run = RunCache.from_inputs(inputs, cache=p21c.OutputCache(str(cache_dir)))
    plan = plan_nodes(inputs, zmin, zmax)
    if not plan:
        raise SystemExit(f"no node redshift in [{zmin}, {zmax}]")
    missing = missing_boxes(run, plan)
    if missing:
        raise SystemExit(f"{len(missing)} cached boxes missing in {cache_dir}, e.g. {missing[0]}")

    ics = None
    written = []
    n_total = 0
    for i, (z, z_prev) in enumerate(plan, 1):
        path = output_path(cache_dir, inputs, z)
        n_halos = run.get_output_struct_at_z("HaloCatalog", z=z).n_halos
        if not clobber and is_complete(path, inputs, n_halos):
            log.info(f"[{i}/{len(plan)}] z={z:.4f}: complete ({n_halos} halos)")
            continue
        t0 = time.perf_counter()
        if ics is None:
            ics = run.get_ics()  # read once: its arrays stay in memory for every node redshift
        sampler = rss() if rss else contextlib.nullcontext()
        with sampler:
            galaxies, halos = make_node(run, inputs, ics, z, z_prev)
            write_atomic(galaxies, path)
        sums = {k: float(np.sum(galaxies.get(k)[: galaxies.n_halos], dtype=np.float64))
                for k in ("stellar_masses_acg", "sfr_acg") if k in galaxies.arrays}
        log.info(f"[{i}/{len(plan)}] z={z:.4f}: {galaxies.n_halos} halos, "
                 + ", ".join(f"sum {k} {v:.4e}" for k, v in sums.items())
                 + f"; {path.stat().st_size / 1e9:.2f} GB in {time.perf_counter() - t0:.1f}s"
                 + (f" (peak RSS {sampler.format_peak()})" if rss else ""))
        n_total += galaxies.n_halos
        written.append(path)
        galaxies.purge()
        halos.purge()
        del galaxies, halos
        gc.collect()
    size = sum(p.stat().st_size for p in written)
    log.info(f"wrote {len(written)} of {len(plan)} files ({n_total} halos, {size / 1e9:.2f} GB)")
    return written


def main() -> None:
    import argparse
    import gc

    sys.path.insert(1, str(HERE.parents[1] / "run_scripts"))
    import settings  # noqa: E402

    gc.collect()
    gc.disable()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    settings.add_common_args(parser)
    parser.add_argument("--zmin", type=float, default=None, help="lowest node redshift (default: all)")
    parser.add_argument("--zmax", type=float, default=None, help="highest node redshift (default: all)")
    parser.add_argument("--clobber", action="store_true", help="compute complete node redshifts again")
    args = parser.parse_args()
    logger = settings.setup_logging(args.log_file)

    import py21cmfast as p21c
    import sim_steps

    t0 = time.perf_counter()
    overrides_rt = sim_steps.apply_coeval_runtime_overrides()  # $EOS26_RUN_THREADS
    cache_dir, overrides = settings.inputs_for_run(args.test, args.compare)
    inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **overrides)
    logger.info(f"{settings.RUN_NAME}{' TEST' if args.test else ''}: galaxy properties "
                f"(py21cmfast {p21c.__version__}), cache {cache_dir}; run-time {overrides_rt or 'template'}")
    run_galaxies(inputs, cache_dir, zmin=args.zmin, zmax=args.zmax, clobber=args.clobber,
                 log=logger, rss=settings.RssSampler)
    logger.info(f"Completed in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
