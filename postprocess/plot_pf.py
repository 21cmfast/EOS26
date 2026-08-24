import gc
gc.collect()
gc.disable()

import argparse
import logging
import sys
sys.path.insert(1, 'run_scripts/')
import settings

parser = argparse.ArgumentParser()
parser.add_argument(
    "--test", action="store_true", default=False,
    help=f"Run a small test box (HII_DIM={settings.TEST_HII_DIM}) instead of the full EOS",
)
parser.add_argument(
    "--compare", action="store_true", default=False,
    help="Use the cache from a run with --compare",
)
parser.add_argument(
    "--zoom", action="store_true", default=False,
    help="Crop the plotted box to a 100^3 corner instead of the full volume",
)
parser.add_argument(
    "--vel", action="store_true", default=False,
    help="Overlay the velocity field as a quiver plot",
)
parser.add_argument(
    "--redshift", type=float, default=33.9596,
    help="Redshift to plot (the closest available node redshift is used)",
)
args = parser.parse_args()

settings.setup_logger()
logger = logging.getLogger("21cmFAST")

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
from astropy import units as un
import matplotlib.pyplot as plt
from tuesday.core import coeval2slice_x, plot_coeval_slice

if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _input_overrides = settings.inputs_for_run(args.test, args.compare)
cache = p21c.OutputCache(cache_dir)

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
    **_input_overrides,
    )

runcache = RunCache.from_inputs(inputs, cache=cache)
perturbed_field = runcache.get_output_struct_at_z(
    "PerturbedField", z=args.redshift, match_z_within=0.1,
)
logger.info(
    f"Requested z={args.redshift:.4f}; closest available redshift is "
    f"z={perturbed_field.redshift:.4f}"
)

HII_DIM = inputs.simulation_options.HII_DIM
L = inputs.simulation_options._LOWRES_CELL_SIZE_MPC * HII_DIM * un.Mpc

box = perturbed_field.get("density") * un.dimensionless_unscaled
if args.zoom:
    box = box[:100, :100, :10]
else:
    box = box[:,:,:10]
if args.vel:
    v_x = perturbed_field.get("velocity_x")[0, ...] * un.m / un.s
    v_y = perturbed_field.get("velocity_y")[0, ...] * un.m / un.s
    if args.zoom:
        v_x = v_x[:100, :100]
        v_y = v_y[:100, :100]
else:
    v_x = None
    v_y = None

plotspath = 'plots/'
out = plotspath + "PF"
if args.test:
    out += "_test"
if args.zoom:
    out += "_zoom"
if args.vel:
    out += "_wvel"

fig, ax = plt.subplots(1, 1, layout="constrained")
ax = plot_coeval_slice(
    box,
    L / HII_DIM * box.shape[0],
    transform2slice=coeval2slice_x(idx=0),
    ax=ax, vmin=-0.5, vmax=0.5,
    v_x=v_x,
    v_y=v_y,
    quiver_decimate_factor=10 if args.zoom else 18,
    title=f"z = {perturbed_field.redshift:.2f} (requested {args.redshift:.2f})",
)
plt.savefig(out, dpi=300)
logger.info(f"Saved PF plot to {out}")



