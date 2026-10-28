"""Slice through the initial conditions of the EOS26 run (production cache by default).

    python postprocess/plot_ics.py                        # lowres density, plane x=0
    python postprocess/plot_ics.py --zoom --vel           # first 100x100 cells, with velocity arrows
    python postprocess/plot_ics.py --field hires_density --zoom 300
    python postprocess/plot_ics.py --test                 # the HII_DIM=200 test reference

Reads only the plane x0 of the field from the cached InitialConditions file (eos_boxes),
so it needs little memory even at HII_DIM=1500. Output: plots/ICs_<run>[_<field>][_zoom<N>][_vel].png
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(1, str(Path(__file__).resolve().parents[1] / "run_scripts"))
import settings  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--test", action="store_true", help=f"the HII_DIM={settings.TEST_HII_DIM} test reference")
parser.add_argument("--field", default="lowres_density", help="InitialConditions field (default lowres_density)")
parser.add_argument("--x0", type=int, default=0,
                    help="plane to plot: index along the first axis, in cells of that field's grid")
parser.add_argument("--zoom", type=int, nargs="?", const=100, default=None,
                    help="show only the first N x N cells (N=100 if no value)")
parser.add_argument("--vel", action="store_true", help="overlay the lowres velocity field (in-plane components)")
parser.add_argument("--vmax", type=float, default=None, help="colour scale -vmax..vmax (default: 99.5th percentile)")
args = parser.parse_args()

settings.setup_logger()
log = logging.getLogger("21cmFAST")

import eos_boxes as eb  # noqa: E402

run = eb.Run(test=args.test)
ics = run.path("InitialConditions")
if ics is None:
    sys.exit(f"no InitialConditions in {run.cache_dir}")
plane = eb.read_plane(ics, "InitialConditions", args.field, x0=args.x0)
vel = None
if args.vel:
    comps = ("lowres_vy", "lowres_vz")
    if all(eb.has_field(ics, "InitialConditions", c) for c in comps):
        vel = tuple(eb.read_plane(ics, "InitialConditions", c, x0=args.x0) for c in comps)
        if vel[0].shape != plane.shape:
            log.warning("velocity planes are lowres, the field is not: no arrows")
            vel = None
    else:
        log.warning(f"{ics.name} has no {comps}: no arrows")

out = f"{eb.PLOTS}/ICs_{run.tag}"
out += "" if args.field == "lowres_density" else f"_{args.field}"
out += f"_zoom{args.zoom}" if args.zoom else ""
out += "_vel" if vel is not None else ""
eb.slice_figure(
    plane, float(run.inputs.simulation_options.BOX_LEN), out + ".png",
    title=f"{run.tag} initial conditions, {args.field}, plane x={args.x0} (21cmFAST {run.version})",
    label=r"$\delta$" if "density" in args.field else args.field,
    vel=vel, zoom=args.zoom, vmax=args.vmax,
)
