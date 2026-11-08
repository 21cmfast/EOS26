"""Check postprocess/lightcone/ against 21cmFAST's own run_lightcone on a small simulation.

    python postprocess/lightcone/test_against_21cmfast.py --cache /tmp/lc_test   # ~10 min, 2 cores

Runs (or reuses, from --cache) a 32^3 'minihalos-discrete' + 'size-tiny' simulation
(KEEP_3D_VELOCITIES=True, as EOS26), makes
the rectilinear, ring and HEALPix (Nside 4, no oversampling) lightcones of a set of fields
with p21c.run_lightcone (the reference, default include_dvdr_in_tau21=True), makes them
again with lc_core + lc_finalise from the same cached coevals, and compares every array
and the global means. Rect must agree exactly; ring and HEALPix to rounding (the angular
slices are interpolated after sampling here, before sampling in 21cmFAST).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(1, str(Path(__file__).resolve().parent))

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--cache", required=True, help="cache directory (reused if it has the boxes)")
parser.add_argument("--out", default=None, help="output directory (default <cache>/lightcone_test)")
parser.add_argument("--threads", type=int, default=2)
args = parser.parse_args()

warnings.simplefilter("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("21cmFAST")

import py21cmfast as p21c  # noqa: E402
from astropy import units  # noqa: E402
from astropy_healpix import HEALPix  # noqa: E402

import lc_core  # noqa: E402
import lc_finalise  # noqa: E402

QUANTITIES = ["density", "brightness_temp", "spin_temperature", "neutral_fraction", "z_reion",
              "J_21_LW", "sfrd_acg", "kinetic_temp_neutral"]
ZMIN, ZMAX, N_LON, NSIDE = 6.0, 34.0, 64, 4

inputs = p21c.InputParameters.from_template(
    ["minihalos-discrete", "size-tiny"], random_seed=1, HII_DIM=32, BOX_LEN=48.0,
    ZPRIME_STEP_FACTOR=1.03, Z_HEAT_MAX=35.0, N_THREADS=1,
    KEEP_3D_VELOCITIES=True)  # as EOS26; needed by angular lightcones with dv/dr
cache = p21c.OutputCache(args.cache)
out = Path(args.out) if args.out else Path(args.cache) / "lightcone_test"
n = inputs.simulation_options.HII_DIM
cell = inputs.simulation_options.cell_size
cosmo = inputs.cosmo_params.cosmo
origin = np.full(3, n / 2)

lon_ring = np.arange(N_LON) * (2 * np.pi / N_LON)
lat_ring = np.zeros_like(lon_ring)
hp = HEALPix(nside=NSIDE, order="ring")
lon_hp, lat_hp = (a.to_value("rad") for a in hp.healpix_to_lonlat(np.arange(hp.npix)))

reference_lightconers = {
    "rect": p21c.RectilinearLightconer.between_redshifts(
        min_redshift=ZMIN, max_redshift=ZMAX, resolution=cell, cosmo=cosmo, quantities=QUANTITIES),
    "ring": p21c.AngularLightconer.between_redshifts(
        min_redshift=ZMIN, max_redshift=ZMAX, resolution=cell, cosmo=cosmo, quantities=QUANTITIES,
        latitude=lat_ring, longitude=lon_ring, origin=origin * units.pixel),
    "healpix": p21c.AngularLightconer.between_redshifts(
        min_redshift=ZMIN, max_redshift=ZMAX, resolution=cell, cosmo=cosmo, quantities=QUANTITIES,
        latitude=lat_hp, longitude=lon_hp, origin=origin * units.pixel),
}
write = p21c.CacheConfig(radiation_fields=False)
reference = {}
for name, lcn in reference_lightconers.items():
    t = time.time()
    reference[name] = p21c.run_lightcone(lightconer=lcn, inputs=inputs, cache=cache,
                                         regenerate=False, write=write, progressbar=False)
    log.info(f"reference {name}: {time.time() - t:.1f} s")

paths = lc_core.CachePaths(inputs, args.cache)
geometries = [lc_core.Rect(inputs, ZMIN, ZMAX), lc_core.Ring(inputs, ZMIN, ZMAX, n_lon=N_LON),
              lc_core.Healpix(inputs, ZMIN, ZMAX, nside=NSIDE, oversample=0, order="ring")]
t = time.time()
for q in [*QUANTITIES, "tau_21", "los_velocity"]:
    lc_core.make_lightcones(inputs, paths, q, geometries, out, threads=args.threads, clobber=True)
log.info(f"lc_core: {time.time() - t:.1f} s")
index = {}
for g in geometries:
    d = lc_core.output_path(out, g, "x").parent
    lc_finalise.make_dvdr(d, inputs, clobber=True)
    index[g.name] = lc_finalise.write_index(d, inputs)

# resume: a second call has nothing to do
lc_core.make_lightcones(inputs, paths, "density", geometries[:1], out, threads=1)

import h5py  # noqa: E402

failures = []
for name, ref in reference.items():
    with h5py.File(index[name], "r") as f:
        grp = f["maps" if name == "healpix" else "lightcones"]
        if name == "rect":  # the index must open as a 21cmFAST lightcone too
            p21c.LightCone.from_file(index[name])
        for q in [*QUANTITIES, "tau_21", "los_velocity"]:
            mine = grp[q][()]
            if name == "healpix":
                mine = mine.T
            theirs = np.asarray(ref.lightcones[q], dtype=np.float32)
            same = mine.shape == theirs.shape
            diff = np.abs(mine.astype(np.float64) - theirs) if same else np.array([np.inf])
            scale = np.max(np.abs(theirs)) or 1.0
            rel = float(np.max(diff) / scale)
            n_diff = int(np.count_nonzero(diff)) if same else -1
            ok = rel == 0 if name == "rect" else rel < 1e-6
            print(f"{name:8s} {q:22s} shape {mine.shape} max|diff|/max|ref| = {rel:.2e} "
                  f"({n_diff} values differ) {'ok' if ok else 'FAIL'}")
            if not ok:
                failures.append((name, q))
        for q, v in ref.global_quantities.items():
            if q in f["global_quantities"]:
                g = f["global_quantities"][q][()]
                rel = float(np.nanmax(np.abs(g - v)) / (np.max(np.abs(v)) or 1))
                okg = rel < 1e-6
                if not okg:
                    failures.append((name, f"global {q}"))
                print(f"{name:8s} global {q:15s} max rel diff {rel:.1e} {'ok' if okg else 'FAIL'}")

over = lc_core.Healpix(inputs, ZMIN, ZMAX, nside=NSIDE, oversample=2, order="ring")
lc_core.make_lightcones(inputs, paths, "density", [over], out / "oversample", threads=args.threads,
                        clobber=True)
with h5py.File(lc_core.output_path(out / "oversample", over, "density"), "r") as f:
    m2 = f["lightcone"][()]
m0 = np.asarray(reference["healpix"].lightcones["density"]).T
print(f"healpix oversample=2 vs 0: mean {m2.mean():.4f} vs {m0.mean():.4f}, "
      f"std {m2.std():.4f} vs {m0.std():.4f} (pixel averaging lowers the scatter)")
print("ALL OK" if not failures else f"FAILURES: {failures}")
sys.exit(1 if failures else 0)
