"""Lightcones of ONE quantity of an EOS26 run: rectilinear, ring and/or full-sky HEALPix.

    python postprocess/lightcone/lightcone_quantity.py --quantity density --log-file logs/lc.log
    python postprocess/lightcone/lightcone_quantity.py --quantity brightness_temp --geometry rect ring --log-file ...
    python postprocess/lightcone/lightcone_quantity.py --quantity density --geometry healpix --nside 2048 --log-file ...
    python postprocess/lightcone/lightcone_quantity.py --quantity los_velocity --test --log-file ...

One pass over the node redshifts: the quantity's box is read once per redshift (13.5 GB
at HII_DIM=1500, ~25 s from gdata) and every requested geometry is filled from it. The
slices are those of 21cmFAST's run_lightcone; see lc_core.py and README.md for what differs
(only the cost). The job is resumable: rerun the same command and it continues from the
last finished node interval. With --partial it fills only the node intervals whose
boxes are cached, so it can run while the coeval jobs are still going; rerun it later
(without --clobber) to fill the rest.

Quantities: any coeval field (density, brightness_temp, tau_21, spin_temperature,
neutral_fraction, z_reion, J_21_LW, sfrd_acg, ...), plus los_velocity (needed with
brightness_temp and tau_21 for the dv/dr correction made by finalise_lightcones.py).

Output: <cache>/lightcones/{rect,ring,healpix_nside<N>}/<quantity>.h5 (or --out-dir).
It only reads the cache; without --partial it stops first if a box it needs is missing.
"""
import gc
gc.collect()
gc.disable()

import argparse  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(1, str(HERE.parents[1] / "run_scripts"))
sys.path.insert(1, str(HERE))
import settings  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
settings.add_common_args(parser)
parser.add_argument("--quantity", required=True, help="one coeval field, or los_velocity")
parser.add_argument("--geometry", nargs="+", choices=("rect", "ring", "healpix"), default=["rect", "ring"],
                    help="lightcones to fill in this pass (default: rect ring)")
parser.add_argument("--zmin", type=float, default=5.0, help="lowest redshift (default 5)")
parser.add_argument("--zmax", type=float, default=35.0, help="highest redshift (default 35)")
parser.add_argument("--n-lon", type=int, default=2**15,
                    help="ring: longitudes around the circle (default 2^15, as make_angular_lightcone.py)")
parser.add_argument("--nside", type=int, default=2048, help="healpix: Nside of the maps (default 2048)")
parser.add_argument("--oversample", type=int, default=1,
                    help="healpix: each pixel is the mean of its 4**oversample children (default 1)")
parser.add_argument("--order", choices=("ring", "nested"), default="ring",
                    help="healpix: pixel order of the stored maps (default ring)")
parser.add_argument("--shell-spacing", type=float, default=None,
                    help="healpix: Mpc between shells (default: the cell size, as the other lightcones)")
parser.add_argument("--threads", type=int, default=int(os.environ.get("PBS_NCPUS", os.cpu_count() or 1)),
                    help="threads for the angular sampling (default: $PBS_NCPUS)")
parser.add_argument("--out-dir", default=None, help="output directory (default <cache>/lightcones)")
parser.add_argument("--clobber", action="store_true", help="start again instead of resuming")
parser.add_argument("--partial", action="store_true",
                    help="skip node intervals whose boxes are not cached yet (while the coevals run)")
args = parser.parse_args()

logger = settings.setup_logging(args.log_file)

import numpy as np  # noqa: E402
import py21cmfast as p21c  # noqa: E402

import lc_core  # noqa: E402

job_start = time.perf_counter()
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")
cache_dir, overrides = settings.inputs_for_run(args.test, args.compare)
inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **overrides)
paths = lc_core.CachePaths(inputs, cache_dir)
out_dir = Path(args.out_dir) if args.out_dir else Path(cache_dir) / "lightcones"
if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")

geometries = []
for name in args.geometry:
    if name == "rect":
        geometries.append(lc_core.Rect(inputs, args.zmin, args.zmax))
    elif name == "ring":
        geometries.append(lc_core.Ring(inputs, args.zmin, args.zmax, n_lon=args.n_lon))
    else:
        geometries.append(lc_core.Healpix(inputs, args.zmin, args.zmax, nside=args.nside,
                                          oversample=args.oversample, order=args.order,
                                          shell_spacing=args.shell_spacing))
for g in geometries:
    shape = g.dataset_shape()
    size = 4 * int(np.prod(shape)) / 1e9
    logger.info(f"{g.name}: {shape} float32 = {size:.2f} GB -> "
                f"{lc_core.output_path(out_dir, g, args.quantity)}")

files = lc_core.make_lightcones(inputs, paths, args.quantity, geometries, out_dir,
                                threads=args.threads, clobber=args.clobber, partial=args.partial)
logger.info(f"Completed {args.quantity} ({' '.join(args.geometry)}) in "
            f"{time.perf_counter() - job_start:.1f}s -> {[str(f) for f in files]}")
