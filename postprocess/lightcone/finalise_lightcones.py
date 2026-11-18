"""Finish the lightcones of an EOS26 run with tuesday: dv/dr, RSDs, linked files.

    python postprocess/lightcone/finalise_lightcones.py --log-file logs/lc_finalise.log
    python postprocess/lightcone/finalise_lightcones.py --test --log-file ...

For every geometry directory of the run's lightcones (rect, angular_plane,
healpix_nside<N>, patch_nside<N>; see lightcone_quantity.py for where they are):
  * brightness_temp_dvdr.h5, when brightness_temp, tau_21 and los_velocity are complete
    there: 21cmFAST's dv/dr correction, as run_lightcone applies it by default
    (tuesday's include_dvdr_on_disk);
  * with RSDs (the default; --no-rsds if the lightcones were made without):
    brightness_temp_dvdr_with_rsds.h5, T_b with dv/dr and RSDs (tuesday's
    apply_rsds_on_disk);
  * <dir>.h5 next to the directory: a 21cmFAST lightcone file that links to the complete
    files (tuesday's link_lightcone_file). It reads with p21c.LightCone.from_file, but
    only next to its directory: moved alone, or with the files deleted, it cannot be read.
    As in run_lightcone's output, brightness_temp_with_rsds is T_b with dv/dr and RSDs and
    brightness_temp_no_dvdr is T_b without either;
  * with RSDs, once brightness_temp_dvdr_with_rsds.h5 is complete: tau_21.h5 and
    brightness_temp_dvdr.h5 (not released) moved to <out>/intermediate/<dir>/ and left
    out of <dir>.h5. Delete <out>/intermediate to save space (~0.9 TB per run).
  * with --degrade-nside N (not for EOS26): the full-sky maps averaged to Nside N.
Safe to rerun: what is complete is kept.
"""
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(1, str(HERE.parents[1] / "run_scripts"))
sys.path.insert(1, str(HERE))
import settings  # noqa: E402

import eos_lightcones as el  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
settings.add_common_args(parser)
parser.add_argument("--out-dir", default=None, help="lightcone directory (default: as lightcone_quantity.py)")
parser.add_argument("--rsds", action=argparse.BooleanOptionalAction, default=None,
                    help=f"as the lightcones were made (default {el.RSDS})")
parser.add_argument("--degrade-nside", type=int, default=0,
                    help="Nside of averaged full-sky maps (default 0: none)")
parser.add_argument("--zmin", type=float, default=None, help="as lightcone_quantity.py (for --rsds)")
parser.add_argument("--zmax", type=float, default=None, help="as lightcone_quantity.py (for --rsds)")
parser.add_argument("--healpix-nside", type=int, default=None, help="as lightcone_quantity.py")
parser.add_argument("--max-memory-gb", type=float, default=8.0,
                    help="memory for the dv/dr and RSD blocks (default 8)")
parser.add_argument("--clobber", action="store_true", help="redo the dv/dr, RSD and linked files")
args = parser.parse_args()

logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c  # noqa: E402

t0 = time.perf_counter()
cache_dir, overrides = settings.inputs_for_run(args.test, args.compare)
inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **overrides)
out_dir = Path(args.out_dir) if args.out_dir else el.default_out_dir(cache_dir)
if not out_dir.is_dir():
    sys.exit(f"no lightcones in {out_dir}")
opts = el.default_options(zmin=args.zmin, zmax=args.zmax, healpix_nside=args.healpix_nside,
                          rsds=args.rsds)
links = el.finalise(out_dir, inputs, opts, max_memory=args.max_memory_gb * 1e9,
                    degrade_nside=args.degrade_nside or None, clobber=args.clobber)
for name, path in links.items():
    logger.info(f"{name}: {path}")
logger.info(f"Completed in {time.perf_counter() - t0:.1f}s")
