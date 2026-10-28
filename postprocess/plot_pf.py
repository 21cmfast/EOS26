"""Slices through the perturbed density of the EOS26 run (production cache by default).

    python postprocess/plot_pf.py --redshift 15.1               # closest node redshift
    python postprocess/plot_pf.py --redshift 5 10 15 --zoom     # several, first 100x100 cells
    python postprocess/plot_pf.py --redshift 10 --vel           # with velocity arrows
    python postprocess/plot_pf.py --test --redshift 10          # the HII_DIM=200 test reference

Reads only the plane x0 from the cached PerturbedField files (eos_boxes), so it needs
little memory even at HII_DIM=1500. One file per redshift:
plots/PF_<run>_z<z>[_<field>][_zoom<N>][_vel].png
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(1, str(Path(__file__).resolve().parents[1] / "run_scripts"))
import settings  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--test", action="store_true", help=f"the HII_DIM={settings.TEST_HII_DIM} test reference")
parser.add_argument("--redshift", type=float, nargs="+", default=[15.1],
                    help="redshift(s) to plot; the closest node redshift is used")
parser.add_argument("--field", default="density", help="PerturbedField field (default density)")
parser.add_argument("--x0", type=int, default=0, help="plane (index along the first axis) to plot")
parser.add_argument("--zoom", type=int, nargs="?", const=100, default=None,
                    help="show only the first N x N cells (N=100 if no value)")
parser.add_argument("--vel", action="store_true", help="overlay the velocity field (in-plane components)")
parser.add_argument("--vmax", type=float, default=None, help="colour scale -vmax..vmax (default: 99.5th percentile)")
args = parser.parse_args()

settings.setup_logger()
log = logging.getLogger("21cmFAST")

import eos_boxes as eb  # noqa: E402

run = eb.Run(test=args.test)
for z_req in args.redshift:
    z = run.nearest_z(z_req)
    pf = run.path("PerturbedField", z)
    if pf is None:
        log.warning(f"no PerturbedField at z={z:.4f} in {run.cache_dir}")
        continue
    log.info(f"Requested z={z_req:.4f}; closest node redshift z={z:.4f}")
    plane = eb.read_plane(pf, "PerturbedField", args.field, x0=args.x0)
    vel = None
    if args.vel:
        comps = ("velocity_y", "velocity_z")
        if all(eb.has_field(pf, "PerturbedField", c) for c in comps):
            vel = tuple(eb.read_plane(pf, "PerturbedField", c, x0=args.x0) for c in comps)
        else:
            log.warning(f"{pf.name} at z={z:.4f} has no {comps}: no arrows")
    out = f"{eb.PLOTS}/PF_{run.tag}_z{z:05.2f}"
    out += "" if args.field == "density" else f"_{args.field}"
    out += f"_zoom{args.zoom}" if args.zoom else ""
    out += "_vel" if vel is not None else ""
    eb.slice_figure(
        plane, float(run.inputs.simulation_options.BOX_LEN), out + ".png",
        title=f"{run.tag} perturbed field, {args.field}, z = {z:.2f} (requested {z_req:.2f}), "
              f"plane x={args.x0} (21cmFAST {run.version})",
        label=r"$\delta$" if args.field == "density" else args.field,
        vel=vel, zoom=args.zoom, vmax=args.vmax,
    )
