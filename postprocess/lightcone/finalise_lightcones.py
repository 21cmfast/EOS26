"""Finish the lightcones of postprocess/lightcone/: dv/dr-corrected brightness temperature + index files.

    python postprocess/lightcone/finalise_lightcones.py --log-file logs/lc_finalise.log
    python postprocess/lightcone/finalise_lightcones.py --test --log-file ...

For every geometry folder in <cache>/lightcones/ (rect, ring, healpix_nside<N>):
  * brightness_temp_dvdr.h5, when brightness_temp, tau_21 and los_velocity are complete
    there: 21cmFAST's include_dvdr_in_tau21, as run_lightcone applies it by default;
  * <cache>/lightcones/lightcone_<geometry>_v<version>.h5, an index that links to every
    complete quantity file. rect and ring have the layout of a 21cmFAST lightcone file
    (lightcones/brightness_temp = the dv/dr-corrected one, as in run_lightcone), so e.g.
    plot_lightcone_square.py --lightcone <cache>/lightcones/lightcone_ring_v4.3.1.h5 works.
See lc_finalise.py.
"""
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(1, str(HERE.parents[1] / "run_scripts"))
sys.path.insert(1, str(HERE))
import settings  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
settings.add_common_args(parser)
parser.add_argument("--out-dir", default=None, help="lightcone directory (default <cache>/lightcones)")
parser.add_argument("--clobber", action="store_true", help="redo brightness_temp_dvdr.h5 if it exists")
args = parser.parse_args()

logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c  # noqa: E402

import lc_finalise  # noqa: E402

t0 = time.perf_counter()
cache_dir, overrides = settings.inputs_for_run(args.test, args.compare)
inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **overrides)
out_dir = Path(args.out_dir) if args.out_dir else Path(cache_dir) / "lightcones"
geom_dirs = sorted(d for d in out_dir.iterdir() if d.is_dir()) if out_dir.is_dir() else []
if not geom_dirs:
    sys.exit(f"no lightcone folders in {out_dir}")
for d in geom_dirs:
    t = time.perf_counter()
    lc_finalise.make_dvdr(d, inputs, clobber=args.clobber)
    index = lc_finalise.write_index(d, inputs)
    logger.info(f"{d.name}: index {index} ({time.perf_counter() - t:.1f}s)")
logger.info(f"Completed in {time.perf_counter() - t0:.1f}s")
