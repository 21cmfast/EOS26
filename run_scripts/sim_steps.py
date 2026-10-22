"""Shared py21cmfast phase-call helpers.

Both the production run scripts (run_ICs.py, run_PFs.py, run_N_PFs.py,
run_PHFs.py, run_N_coevals.py) and the scaling-test harness
(scaling/_worker.py) need to make the *exact* same py21cmfast calls,
with the exact same config, for each simulation step (initial conditions,
perturbed field, halo evolution, coeval generation). Duplicating those
calls independently in each script is how config drift creeps in silently
-- e.g. HALO_CATALOG_MEM_FACTOR being set in the scaling harness but left
at py21cmfast's unsafe default in production, or an invalid keyword
argument surviving in one script but not another. Importing these helpers
instead makes each step's call signature and config a single source of
truth.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Iterable, Iterator

import attrs
import py21cmfast as p21c
from py21cmfast.io.caching import CacheConfig

_log = logging.getLogger(__name__)

# py21cmfast's default (1.2) under-allocates the halo-catalog buffer and
# raises ArgumentValueError at large HII_DIM (confirmed empirically at
# HII_DIM=300). 2.0 avoids that crash.
HALO_CATALOG_MEM_FACTOR = 2.0

_halo_catalog_mem_factor_applied = False


def apply_halo_catalog_mem_factor() -> None:
    """Set py21cmfast's HALO_CATALOG_MEM_FACTOR to the validated safe value.

    Called automatically by evolve_halos() and generate_coevals() (the two
    steps that build halo catalogs), so callers don't need to remember to
    set it themselves.
    """
    global _halo_catalog_mem_factor_applied
    p21c.config["HALO_CATALOG_MEM_FACTOR"] = HALO_CATALOG_MEM_FACTOR
    _halo_catalog_mem_factor_applied = True


def apply_fftw_wisdoms_path() -> Path:
    """Point 21cmFAST's FFTW wisdom directory at one shared place, and create it.

    $EOS26_WISDOMS if set, else <DATA_ROOT>/fftw_wisdoms (run_scripts/settings.py;
    /g/data/qp00/$USER/fftw_wisdoms on Gadi). 21cmFAST 4.3.x saves the FFTW_PATIENT
    plans it makes (USE_FFTW_WISDOM) to config["wisdoms_path"], but does not create
    that directory and ignores a failed save; without it, every process plans its
    FFTs from scratch again. Files are named by FFT size and thread count
    (r2c_DIM<n>_DIM<n>_NTHREADS<t>), so production, tests and scaling can share them.
    """
    if os.environ.get("EOS26_WISDOMS"):
        path = Path(os.environ["EOS26_WISDOMS"])
    else:
        import settings  # run_scripts/ is on sys.path for every caller

        path = Path(settings.DATA_ROOT) / "fftw_wisdoms"
    p21c.config["wisdoms_path"] = path
    path = path.expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


# ------------------------------------------------- run-time-only coeval settings
# N_THREADS (SimulationOptions) and USE_FFTW_WISDOM (MatterOptions) are part of the
# 21cmFAST cache hash, and a box read from the cache must have the same inputs as
# the run, so changing either in EOS26.toml loses every cached box. In the coeval
# phase neither changes the physics: no random numbers are drawn after the halo
# catalogs, only the order of OpenMP sums and the FFT algorithm change (round-off).
# So for coevals we keep the template values for hashing and checks, and change only
# what the C code runs with:
#   EOS26_RUN_THREADS=32       OpenMP and FFTW threads of the C code
#   EOS26_RUN_FFTW_WISDOM=1    FFTW wisdom (FFTW_PATIENT plans, made once and saved)
# Not for ICs or halo catalogs: their random numbers are drawn per thread
# (rng.c: one stream per thread), so the thread count changes the realisation.
_runtime_overrides: dict[str, Any] | None = None


def apply_coeval_runtime_overrides() -> dict[str, Any]:
    """Apply EOS26_RUN_THREADS / EOS26_RUN_FFTW_WISDOM to the C backend (coevals only)."""
    global _runtime_overrides
    if _runtime_overrides is not None:
        return _runtime_overrides
    n_threads = int(os.environ["EOS26_RUN_THREADS"]) if os.environ.get("EOS26_RUN_THREADS") else None
    wisdom = bool(int(os.environ["EOS26_RUN_FFTW_WISDOM"])) if os.environ.get("EOS26_RUN_FFTW_WISDOM") else None
    _runtime_overrides = {}
    if n_threads is None and wisdom is None:
        return _runtime_overrides

    from py21cmfast.c_21cmfast import lib
    from py21cmfast.drivers import _global_initialization as gi

    original = gi.GlobalInitializationManager._broadcast_input_struct

    def _broadcast_input_struct(self):
        first = not self.inputs_are_broadcast
        if first:
            # The C globals point at these structs, so this is what the C code sees.
            # The Python attributes (hash, compatibility checks) are left alone.
            if n_threads is not None:
                self.inputs.simulation_options._cstruct.N_THREADS = n_threads
            if wisdom is not None:
                self.inputs.matter_options._cstruct.USE_FFTW_WISDOM = wisdom
        original(self)
        if first and wisdom and not self.inputs.matter_options.USE_FFTW_WISDOM:
            lib.CreateFFTWWisdoms()  # original() only does this for USE_FFTW_WISDOM=True inputs

    gi.GlobalInitializationManager._broadcast_input_struct = _broadcast_input_struct
    if n_threads is not None:
        os.environ["OMP_NUM_THREADS"] = str(n_threads)
        _runtime_overrides["N_THREADS"] = n_threads
    if wisdom is not None:
        _runtime_overrides["USE_FFTW_WISDOM"] = wisdom
        _runtime_overrides["wisdoms_path"] = str(apply_fftw_wisdoms_path())
    _log.warning("coeval run-time overrides (not in the cache hash): %s", _runtime_overrides)
    return _runtime_overrides


# ------------------------------------------------------------- damaged cache files
def h5_problem(path: str | Path) -> str | None:
    """None if the HDF5 file at `path` reads cleanly, else what is wrong with it.

    Opens every group and dataset, reads every attribute and the last element of every
    dataset, and checks that the file is at least as large as the data it claims to
    hold. That finds files cut short by a job killed while writing (e.g. h5py
    "address of object past end of allocation") without reading the whole file, so it
    is cheap even for the HII_DIM=1500 boxes.
    """
    import h5py

    path = Path(path)
    try:
        with h5py.File(path, "r") as f:
            stored = 0

            def visit(name, obj):
                nonlocal stored
                dict(obj.attrs)
                if isinstance(obj, h5py.Dataset):
                    stored += obj.id.get_storage_size()
                    if obj.size:
                        obj[(-1,) * obj.ndim] if obj.ndim else obj[()]

            dict(f.attrs)
            f.visititems(visit)
        if path.stat().st_size < stored:
            return f"file is {path.stat().st_size} bytes but holds {stored} bytes of data"
    except Exception as exc:  # noqa: BLE001  (h5py raises KeyError, OSError, RuntimeError, ...)
        return f"{type(exc).__name__}: {exc}"
    return None


def quarantine(path: str | Path) -> Path:
    """Rename a damaged cache file to <name>.corrupt-<time>, so it is recomputed (not deleted)."""
    import time

    path = Path(path)
    target = path.with_name(f"{path.name}.corrupt-{time.strftime('%Y%m%dT%H%M%S')}")
    path.rename(target)
    return target


def _retry_if_damaged(compute, cached_path):
    """Run `compute()`; if reading its cached file fails because the file is damaged,
    rename the file aside and compute again (once). Other errors are re-raised."""
    try:
        return compute()
    except (KeyError, OSError, RuntimeError):
        path = Path(cached_path())
        problem = h5_problem(path) if path.exists() else None
        if problem is None:
            raise
        moved = quarantine(path)
        _log.warning("damaged cache file %s (%s); moved to %s, computing it again", path, problem, moved.name)
        return compute()


def compute_initial_conditions(
    inputs: Any,
    cache: Any,
    *,
    regenerate: bool = False,
    write: bool = True,
) -> Any:
    """Compute (or load) the initial-conditions box."""
    apply_fftw_wisdoms_path()
    from py21cmfast.io.caching import RunCache

    return _retry_if_damaged(
        lambda: p21c.compute_initial_conditions(
            inputs=inputs,
            cache=cache,
            write=write,
            regenerate=regenerate,
        ),
        lambda: RunCache.from_inputs(inputs, cache=cache).InitialConditions,
    )


def compute_perturbed_field(
    redshift: float,
    inputs: Any,
    cache: Any,
    initial_conditions: Any | None = None,
    *,
    regenerate: bool = False,
    write: bool = True,
) -> Any:
    """Compute (or load) a single perturbed field at `redshift`.

    If `initial_conditions` is not given, py21cmfast loads it from `cache`.
    """
    apply_fftw_wisdoms_path()
    kwargs: dict[str, Any] = dict(
        redshift=redshift,
        inputs=inputs,
        cache=cache,
        write=write,
        regenerate=regenerate,
    )
    if initial_conditions is not None:
        kwargs["initial_conditions"] = initial_conditions
    from py21cmfast.io.caching import RunCache

    return _retry_if_damaged(
        lambda: p21c.perturb_field(**kwargs),
        lambda: RunCache.from_inputs(inputs, cache=cache).PerturbedField[redshift],
    )


def evolve_halos(
    inputs: Any,
    all_redshifts: Iterable[float],
    cache: Any,
    initial_conditions: Any,
    *,
    regenerate: bool = False,
    write: CacheConfig | None = None,
    progressbar: bool = True,
) -> Any:
    """Evolve halo catalogs across `all_redshifts`."""
    apply_halo_catalog_mem_factor()
    apply_fftw_wisdoms_path()
    return p21c.drivers.coeval.evolve_halos(
        inputs=inputs,
        all_redshifts=all_redshifts,
        cache=cache,
        initial_conditions=initial_conditions,
        write=CacheConfig() if write is None else write,
        regenerate=regenerate,
        progressbar=progressbar,
    )


def generate_coevals(
    out_redshifts: Iterable[float],
    inputs: Any,
    cache: Any,
    *,
    regenerate: bool = False,
    write: CacheConfig | None = None,
    progressbar: bool = True,
) -> Iterator[Any]:
    """Generate coeval boxes at `out_redshifts`.

    Reuses cached initial conditions, perturbed fields, and halo catalogs
    (regenerate applies only to the coeval-specific products).
    EOS26_RUN_THREADS / EOS26_RUN_FFTW_WISDOM are applied here (see above).
    """
    apply_halo_catalog_mem_factor()
    apply_fftw_wisdoms_path()
    apply_coeval_runtime_overrides()
    return p21c.generate_coeval(
        out_redshifts=out_redshifts,
        inputs=inputs,
        cache=cache,
        write=coeval_write_config() if write is None else write,
        regenerate=regenerate,
        progressbar=progressbar,
    )


def coeval_write_config() -> CacheConfig:
    """Cache every coeval product except the huge, transient X-ray box.

    21cmFAST v4.3 renamed XraySourceBox -> RadiationFields (CacheConfig field
    ``xray_source_box`` -> ``radiation_fields``). Pick whichever this version
    has, so the production call is identical for v4.2 and v4.3.
    """
    fields = {f.name for f in attrs.fields(CacheConfig)}
    if "radiation_fields" in fields:  # v4.3+
        return CacheConfig(radiation_fields=False)
    return CacheConfig(xray_source_box=False)  # v4.2
