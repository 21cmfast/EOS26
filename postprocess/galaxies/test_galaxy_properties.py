"""Check galaxy_properties.py against 21cmFAST on a small run.

    python postprocess/galaxies/test_galaxy_properties.py --cache /tmp/lc_test   # ~2 min, 1 core

Runs (or reuses, from --cache: the same run as postprocess/lightcone/test_against_21cmfast.py)
a 32^3 'minihalos-discrete' + 'size-tiny' simulation with minihalos, Lyman-Werner,
relative-velocity and photoheating feedback, as EOS26. Then:

* writes the galaxy properties of every node redshift with galaxy_properties.run_galaxies,
  checks that they are at 21cmFAST's cache path, readable, with the halos and masses of the
  HaloCatalog, and equal to a direct perturb_halo_catalog call; a second call writes
  nothing, --clobber everything again; a file of other input parameters stops the script;
* compares them with the run: at every node redshift with halos, 21cmFAST's EmissivityFields
  computed from the cached boxes must equal the cached ones (so the boxes of the previous
  node are those of the run), and their halo part (the EmissivityFields minus those computed
  with every halo mass set to zero, which 21cmFAST skips) must equal the galaxy properties
  (SFRs of ACGs and MCGs, n_ion, X-ray luminosity) gridded as 21cmFAST grids them
  (cloud-in-cell at the Eulerian positions, per cell volume). The stellar masses enter
  through these (with EXTRA_EMISSIVITY_FIELDS off, 21cmFAST grids no stellar mass).
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(1, str(Path(__file__).resolve().parent))

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--cache", required=True, help="cache directory (reused if it has the boxes)")
args = parser.parse_args()

warnings.simplefilter("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("galaxies")

import py21cmfast as p21c  # noqa: E402
from py21cmfast.io.caching import RunCache  # noqa: E402
from py21cmfast.io.h5 import read_output_struct  # noqa: E402

import galaxy_properties as gp  # noqa: E402

# the run of postprocess/lightcone/test_against_21cmfast.py
inputs = p21c.InputParameters.from_template(
    ["minihalos-discrete", "size-tiny"], random_seed=1, HII_DIM=32, BOX_LEN=48.0,
    ZPRIME_STEP_FACTOR=1.03, Z_HEAT_MAX=35.0, N_THREADS=1,
    KEEP_3D_VELOCITIES=True)
cache = p21c.OutputCache(args.cache)
run = RunCache.from_inputs(inputs, cache=cache)
if not all(Path(p).exists() for p in run.BrightnessTemp.values()):
    log.info("making the coevals")
    p21c.run_lightcone(lightconer=p21c.RectilinearLightconer.between_redshifts(
        min_redshift=6.0, max_redshift=34.0, resolution=inputs.simulation_options.cell_size,
        cosmo=inputs.cosmo_params.cosmo, quantities=["density"]),
        inputs=inputs, cache=cache, write=p21c.CacheConfig(), progressbar=False)
    run = RunCache.from_inputs(inputs, cache=cache)

ao = inputs.astro_options
log.info(f"USE_MCGS={ao.USE_MCGS} USE_REIONIZATION_PHOTOHEATING_FEEDBACK="
         f"{ao.USE_REIONIZATION_PHOTOHEATING_FEEDBACK} V_CB_MODEL={inputs.matter_options.V_CB_MODEL} "
         f"SOURCE_MODEL={inputs.matter_options.SOURCE_MODEL} HMF={inputs.matter_options.HMF}")

failures = []


def check(label, ok, detail=""):
    log.info(f"{'OK  ' if ok else 'FAIL'} {label} {detail}")
    if not ok:
        failures.append(label)


plan = gp.plan_nodes(inputs)
for p in [gp.output_path(args.cache, inputs, z) for z, _ in plan]:
    p.unlink(missing_ok=True)

# ── writing, resuming, clobber ────────────────────────────────────────────────
written = gp.run_galaxies(inputs, args.cache, log=log)
check("all node redshifts written", len(written) == len(plan), f"({len(written)} of {len(plan)})")
paths = [gp.output_path(args.cache, inputs, z) for z, _ in plan]
check("at 21cmFAST's cache path, next to the HaloCatalog",
      all(p.exists() and p.parent == Path(run.HaloCatalog[z]).parent for p, (z, _) in zip(paths, plan)))
check("no temporary files left", not list(Path(args.cache).rglob("*.partial")))
check("resume writes nothing", gp.run_galaxies(inputs, args.cache, log=log) == [])
zs_part = [z for z, _ in plan][10:13]
again = gp.run_galaxies(inputs, args.cache, zmin=min(zs_part), zmax=max(zs_part), clobber=True, log=log)
check("--clobber in [zmin, zmax] writes those again", len(again) == 3)

other = inputs.evolve_input_structs(F_ESC10_ACG=inputs.astro_params.F_ESC10_ACG + 0.1)
try:
    gp.is_complete(paths[-1], other, 0)
    check("file of other astro parameters stops the script", False)
except SystemExit as e:
    check("file of other astro parameters stops the script", True, f"({str(e)[:60]}...)")

# ── contents ──────────────────────────────────────────────────────────────────
ics = run.get_ics()
n_with_halos = 0
for (z, z_prev), path in zip(plan, paths):
    gal = read_output_struct(path)
    gal.load_all()
    halos = run.get_output_struct_at_z("HaloCatalog", z=z)
    halos.load_all()
    n = halos.n_halos
    ok = gal.n_halos == n and np.array_equal(gal.get("halo_masses")[:n], halos.get("halo_masses")[:n])
    direct, _ = gp.make_node(run, inputs, ics, z, z_prev)
    same = all(np.array_equal(gal.get(k)[:n], direct.get(k)[:n]) for k in gal.arrays)
    if not (ok and same):
        check(f"z={z:.3f} halos and masses of the HaloCatalog, equal to a direct call", False)
    if n:
        n_with_halos += 1
        pos = gal.get("halo_coords")[:n]
        # wrapped in double precision, stored in float32: a few land exactly on BOX_LEN
        if not (np.all(pos >= 0) and np.all(pos <= inputs.simulation_options.BOX_LEN)):
            check(f"z={z:.3f} Eulerian positions inside the box", False)
check("every file: n_halos and halo masses of the HaloCatalog; equal to a direct call; positions in box",
      not failures, f"({len(plan)} node redshifts, {n_with_halos} with halos)")

# ── against the run's EmissivityFields ────────────────────────────────────────
# fesc_weighted_sfr is left out: with the integral below SAMPLER_MIN_MASS, 21cmFAST replaces the
# whole fesc_weighted_sfrd grid by n_ion times a constant (map_mass.c), so its halo part is
# not the gridded fesc_weighted_sfr of the halos
GRID = {"sfr_acg": "sfrd_acg", "sfr_mcg": "sfrd_mcg", "n_ion": "n_ion",
        "xray_luminosity": "xray_emissivity"}
so = inputs.simulation_options
dim = (so.HII_DIM, so.HII_DIM, so.HII_DIM)
cell = so.BOX_LEN / so.HII_DIM


def cic(pos_cells, values):
    """21cmFAST's do_cic_interpolation: cell i centred at i, periodic."""
    out = np.zeros(dim)
    i0 = np.floor(pos_cells).astype(int)
    d = pos_cells - i0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = ((d[:, 0] if dx else 1 - d[:, 0]) * (d[:, 1] if dy else 1 - d[:, 1])
                     * (d[:, 2] if dz else 1 - d[:, 2]))
                idx = ((i0[:, 0] + dx) % dim[0], (i0[:, 1] + dy) % dim[1], (i0[:, 2] + dz) % dim[2])
                np.add.at(out, idx, values * w)
    return out / cell**3


worst_ef, worst_tot, worst_cell, n_cmp = 0.0, 0.0, 0.0, 0
for (z, z_prev), path in zip(plan, paths):
    halos = run.get_output_struct_at_z("HaloCatalog", z=z)
    if halos.n_halos == 0:
        continue
    halos.load_all()
    kw = {"inputs": inputs, "initial_conditions": ics, "redshift": z,
          "perturbed_field": run.get_output_struct_at_z("PerturbedField", z=z)}
    if z_prev is not None:
        kw["previous_spin_temp"] = run.get_output_struct_at_z("TsBox", z=z_prev)
        kw["previous_ionize_box"] = run.get_output_struct_at_z("IonizedBox", z=z_prev)
    full = p21c.compute_emissivity_fields(halo_catalog=halos, **kw)
    cached = run.get_output_struct_at_z("EmissivityFields", z=z)
    cached.load_all()
    no_halos = run.get_output_struct_at_z("HaloCatalog", z=z)
    no_halos.load_all()
    no_halos.get("halo_masses")[:] = 0.0
    integral = p21c.compute_emissivity_fields(halo_catalog=no_halos, **kw)
    gal = read_output_struct(path)
    gal.load_all()
    n = gal.n_halos
    pos = gal.get("halo_coords")[:n].astype(np.float64) / cell
    for k, f in GRID.items():
        if k not in gal.arrays or f not in full.arrays:
            continue
        a, c = full.get(f).astype(np.float64), cached.get(f).astype(np.float64)
        worst_ef = max(worst_ef, np.max(np.abs(a - c)) / max(np.max(np.abs(c)), 1e-300))
        halo_part = a - integral.get(f).astype(np.float64)
        mine = cic(pos, gal.get(k)[:n].astype(np.float64))
        tot = abs(mine.sum() - halo_part.sum()) / max(abs(halo_part.sum()), 1e-300)
        # per cell, relative to the largest cell of the run's field: the halo part is the
        # difference of two float32 grids (MCGs: mostly below SAMPLER_MIN_MASS), and the float32
        # positions move the CIC weights by ~1e-6 of a cell
        rel = np.max(np.abs(mine - halo_part)) / np.max(np.abs(a))
        worst_tot, worst_cell = max(worst_tot, tot), max(worst_cell, rel)
        n_cmp += 1
check("EmissivityFields from the cached boxes = the run's", worst_ef < 1e-6, f"(max rel {worst_ef:.1e})")
check("halo part of the EmissivityFields = gridded galaxy properties, totals", worst_tot < 1e-4,
      f"(max rel {worst_tot:.1e}, {n_cmp} field-redshift pairs)")
check("... per cell, relative to the largest cell of the run's field", worst_cell < 1e-5,
      f"(max {worst_cell:.1e})")

log.info("ALL OK" if not failures else f"{len(failures)} FAILED: {failures}")
sys.exit(1 if failures else 0)
