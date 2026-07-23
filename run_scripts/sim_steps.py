"""Shared py21cmfast phase-call helpers.

Both the production run scripts (run_ICs.py, run_PFs.py, run_N_PFs.py,
run_PHFs.py, run_N_coevals.py) and the scaling-test harness
(scaling/run_scaling.py) need to make the *exact* same py21cmfast calls,
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

from typing import Any, Iterable, Iterator

import py21cmfast as p21c
from py21cmfast.io.caching import CacheConfig

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


def compute_initial_conditions(
    inputs: Any,
    cache: Any,
    *,
    regenerate: bool = False,
    write: bool = True,
) -> Any:
    """Compute (or load) the initial-conditions box."""
    return p21c.compute_initial_conditions(
        inputs=inputs,
        cache=cache,
        write=write,
        regenerate=regenerate,
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
    kwargs: dict[str, Any] = dict(
        redshift=redshift,
        inputs=inputs,
        cache=cache,
        write=write,
        regenerate=regenerate,
    )
    if initial_conditions is not None:
        kwargs["initial_conditions"] = initial_conditions
    return p21c.perturb_field(**kwargs)


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
    """
    apply_halo_catalog_mem_factor()
    return p21c.generate_coeval(
        out_redshifts=out_redshifts,
        inputs=inputs,
        cache=cache,
        write=CacheConfig(xray_source_box=False) if write is None else write,
        regenerate=regenerate,
        progressbar=progressbar,
    )
