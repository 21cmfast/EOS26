"""Lightcones of ONE quantity of an EOS26 run, made with tuesday: rect, angular plane, full sky, patch.

    python postprocess/lightcone/lightcone_quantity.py --quantity density --geometry rect --log-file logs/lc.log
    python postprocess/lightcone/lightcone_quantity.py --quantity brightness_temp --geometry rect angular_plane \
        --log-file ...
    python postprocess/lightcone/lightcone_quantity.py --quantity density --geometry healpix --threads 48 \
        --log-file ...
    python postprocess/lightcone/lightcone_quantity.py --quantity los_velocity --geometry patch --test \
        --log-file ...

The geometries and their values (decision list of 17 Nov 2026) are in eos_lightcones.py:
no frame rotation, patch of 45 deg around (0, 0), RSDs on (the lightcones are made on the
few more slices that RSDs need). The options below override them; all lightcones of one
run must be made with the same values, and finalised with them.

One pass over the node redshifts (tuesday's make_lightcones_on_disk): each box the
lightcones need is read once and every requested geometry is filled from it. The
geometries and their defaults are in eos_lightcones.py. The run is the one of
$EOS26_TEMPLATE (EOS26 by default; e.g. EOS26_earlyEoR), as for the other run scripts.

Resumable: rerun the same command and it fills only what is missing. With --partial it
fills the node intervals whose boxes are cached, so it can run while the coeval jobs
are still going. HEALPix geometries are split into --threads parts filled in parallel;
their parts are joined into one file per quantity once complete.

Quantities: any coeval field (density, brightness_temp, tau_21, spin_temperature,
neutral_fraction, J_21_LW, sfrd_acg, ionisation_rate_G12, n_ion, ...), plus
los_velocity; the released ones are eos_lightcones.DEFAULT_QUANTITIES. The dv/dr
correction and RSDs (finalise_lightcones.py) need brightness_temp, tau_21 and
los_velocity.

Output: <out>/{rect,angular_plane,healpix_nside<N>,patch_nside<N>}/<quantity>.h5, where <out> is
--out-dir, or $EOS26_LIGHTCONE_DIR/<cache name>, or on Gadi
/scratch/qp00/$USER/lightcones/<cache name>, or <cache>/lightcones.
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

import eos_lightcones as el  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
settings.add_common_args(parser)
parser.add_argument("--quantity", required=True, help="one coeval field, or los_velocity")
parser.add_argument("--geometry", nargs="+", choices=el.GEOMETRIES, default=["rect", "angular_plane"],
                    help="lightcones to fill in this pass (default: rect angular_plane)")
parser.add_argument("--threads", type=int, default=int(os.environ.get("PBS_NCPUS", os.cpu_count() or 1)),
                    help="threads, i.e. parts of each HEALPix geometry (default: $PBS_NCPUS)")
parser.add_argument("--out-dir", default=None, help="output directory (default: see above)")
parser.add_argument("--partial", action="store_true",
                    help="skip node intervals whose boxes are not cached yet (while the coevals run)")
parser.add_argument("--clobber", action="store_true", help="start again instead of resuming")
parser.add_argument("--keep-parts", action="store_true", help="keep the HEALPix part files after joining them")
parser.add_argument("--rsds", action=argparse.BooleanOptionalAction, default=None,
                    help=f"make the lightcones on the longer distances that RSDs need (default {el.RSDS}); "
                         "finalise with the same choice; the lowest node redshift must leave room below "
                         "--zmin")
g = parser.add_argument_group("geometry options (defaults in eos_lightcones.py)")
g.add_argument("--zmin", type=float, default=None, help=f"lowest redshift (default {el.ZMIN})")
g.add_argument("--zmax", type=float, default=None, help=f"highest redshift (default {el.ZMAX})")
g.add_argument("--plane-n-lon", type=int, default=None,
               help=f"longitudes of the angular plane (default {el.PLANE_N_LON})")
g.add_argument("--healpix-nside", type=int, default=None, help=f"full-sky Nside (default {el.HEALPIX_NSIDE})")
g.add_argument("--healpix-level", type=int, default=None,
               help=f"full sky: each pixel the mean of 4**level sub-pixels (default {el.HEALPIX_LEVEL})")
g.add_argument("--patch-nside", type=int, default=None, help=f"patch Nside (default {el.PATCH_NSIDE})")
g.add_argument("--patch-level", type=int, default=None, help=f"patch sub-pixel level (default {el.PATCH_LEVEL})")
g.add_argument("--patch-radius", type=float, default=None, help=f"patch radius, deg (default {el.PATCH_RADIUS_DEG})")
g.add_argument("--patch-center", type=float, nargs=2, metavar=("LON", "LAT"), default=None,
               help=f"patch centre in the observer frame, deg (default {el.PATCH_CENTER_DEG})")
g.add_argument("--rotation", default=None,
               help="frame rotation 'SEQ:a,b,c' (scipy Euler angles in degrees, observer frame to box "
                    "axes) or 'none' (default none)")
args = parser.parse_args()

logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c  # noqa: E402

job_start = time.perf_counter()
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")
cache_dir, overrides = settings.inputs_for_run(args.test, args.compare)
inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **overrides)
out_dir = Path(args.out_dir) if args.out_dir else el.default_out_dir(cache_dir)
opts = el.default_options(
    zmin=args.zmin, zmax=args.zmax, plane_n_lon=args.plane_n_lon,
    healpix_nside=args.healpix_nside, healpix_level=args.healpix_level,
    patch_nside=args.patch_nside, patch_level=args.patch_level,
    patch_radius_deg=args.patch_radius,
    patch_center_deg=tuple(args.patch_center) if args.patch_center else None,
    rotation=args.rotation, rsds=args.rsds,
)
logger.info(f"{settings.RUN_NAME}{' TEST' if args.test else ''}: {args.quantity} "
            f"[{' '.join(args.geometry)}], cache {cache_dir} -> {out_dir}; options {opts}")

files = el.make_quantity(inputs, cache_dir, args.quantity, args.geometry, out_dir, opts,
                         threads=args.threads, partial=args.partial, clobber=args.clobber,
                         keep_parts=args.keep_parts)
logger.info(f"Completed {args.quantity} ({' '.join(args.geometry)}) in "
            f"{time.perf_counter() - job_start:.1f}s -> {files}")
