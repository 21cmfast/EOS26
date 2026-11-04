"""Angular ring lightcone of an EOS26 run, the input of postprocess/plot_lightcone_square.py.

    python postprocess/make_angular_lightcone.py --log-file logs/ring_lightcone.log          # EOS26
    python postprocess/make_angular_lightcone.py --log-file logs/ring_lightcone_test.log --test

21cmFAST's AngularLightconer with every pixel on one great circle: latitude 0 and --n-lon
longitudes evenly spaced over 2 pi, seen by an observer at the centre of the box. The circle lies
in the box's x-y plane through the centre, and the box is tiled periodically along it, so each
quantity is a (n_lon, n_slices) array, with the slices one cell apart from z = 5 to 35 (2557 of
them at 1.5 cMpc). With the default 2^15 longitudes (1.5 cMpc apart at z = 5) that is 0.34 GB per
quantity at any HII_DIM. Around the circle the box repeats 2 pi D(z) / L times: 22 times at
z = 5 for EOS26, and 167 times for the 300 cMpc test box.

Like make_lightcone.py it reads the cached coevals (regenerate=False). It never computes them:
it stops first if any box it needs is missing.

Output: <cache>/lightcone_ring_v<21cmFAST version>.h5, a 21cmFAST AngularLightcone file plus a
'ring' group with the longitudes, latitudes and origin.
"""
import gc
gc.collect()
gc.disable()

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(1, str(Path(__file__).resolve().parents[1] / "run_scripts"))
import settings  # noqa: E402
import sim_steps  # noqa: E402

# the quantities of postprocess/plot_lightcone_square.py
QUANTITIES = ("density", "sfrd_acg", "kinetic_temp_neutral", "J_21_LW",
              "neutral_fraction", "brightness_temp", "spin_temperature", "cumulative_recombinations")

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
settings.add_common_args(parser)
parser.add_argument("--quantities", nargs="+", default=list(QUANTITIES),
                    help=f"coeval fields to put on the ring (default: {' '.join(QUANTITIES)})")
parser.add_argument("--n-lon", type=int, default=2**15,
                    help="number of longitudes around the circle (default 2^15 = 32768)")
parser.add_argument("--zmin", type=float, default=5.0, help="lowest redshift (default 5)")
parser.add_argument("--zmax", type=float, default=35.0, help="highest redshift (default 35)")
args = parser.parse_args()

logger = settings.setup_logging(args.log_file)

import h5py  # noqa: E402
import numpy as np  # noqa: E402
import py21cmfast as p21c  # noqa: E402
from astropy import units  # noqa: E402

import eos_boxes as eb  # noqa: E402


def ring_lightcone_path(cache_dir) -> Path:
    """<cache>/lightcone_ring_v<version>.h5 -- the same name as in plot_lightcone_square.py."""
    p = Path(settings.lightcone_path(cache_dir))
    return p.with_name(p.name.replace("lightcone_", "lightcone_ring_", 1))


job_start = time.perf_counter()
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")
if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
run = eb.Run(test=args.test, compare=args.compare)
inputs = run.inputs
lc_path = ring_lightcone_path(run.cache_dir)

# every box the lightcone reads must already be in the cache
unknown = [q for q in args.quantities if q not in eb.FIELD_KIND]
if unknown:
    sys.exit(f"{unknown} are not coeval fields; known: {sorted(eb.FIELD_KIND)}")
kinds = {"PerturbedField", "IonizedBox", "BrightnessTemp"} | {eb.FIELD_KIND[q] for q in args.quantities}
if inputs.astro_options.USE_TS_FLUCT:
    kinds.add("TsBox")
missing = [(k, z) for k in sorted(kinds) for z in run.redshifts if run.path(k, z) is None]
if run.path("InitialConditions") is None:
    missing.insert(0, ("InitialConditions", None))
if missing:
    logger.error(f"{len(missing)} boxes are not cached yet, e.g. {missing[:5]}; "
                 "run the coeval jobs first (this script does not compute boxes)")
    sys.exit(1)

# the ring: latitude 0, observer at the centre of the box
n = inputs.simulation_options.HII_DIM
lon = np.arange(args.n_lon) * (2 * np.pi / args.n_lon)
lat = np.zeros_like(lon)
origin = np.full(3, n / 2) * units.pixel
lcn = p21c.AngularLightconer.between_redshifts(
    min_redshift=args.zmin,
    max_redshift=args.zmax,
    resolution=inputs.simulation_options.cell_size,
    cosmo=inputs.cosmo_params.cosmo,
    quantities=args.quantities,
    latitude=lat,
    longitude=lon,
    origin=origin,
)
n_slices = len(lcn.lc_distances)
logger.info(f"Ring lightcone: {args.n_lon} longitudes x {n_slices} slices = "
            f"{4 * args.n_lon * n_slices / 1e9:.2f} GB per quantity, quantities {args.quantities} "
            f"(+ tau_21 and los_velocity for the dv/dr correction) -> {lc_path}")

lc = p21c.run_lightcone(
    lightconer=lcn,
    inputs=inputs,
    initial_conditions=run.rc.get_ics(),
    cache=p21c.OutputCache(run.cache_dir),
    regenerate=False,
    # Read the cached coevals; as in make_lightcone.py, the RadiationFields are not written.
    write=sim_steps.coeval_write_config(),
    progressbar=True,
)
lc.save(lc_path, clobber=True)
with h5py.File(lc_path, "a") as fl:
    ring = fl.create_group("ring")
    ring["longitude"] = lon
    ring["latitude"] = lat
    ring.attrs["origin_pixels"] = origin.to_value(units.pixel)
    ring.attrs["about"] = ("AngularLightconer on the great circle latitude = 0 (the box x-y plane through "
                           "origin_pixels); lightcones/<q> are (longitude, distance) arrays")

logger.info(f"Completed the ring lightcone in {time.perf_counter() - job_start:.2f}s -> {lc_path}")
