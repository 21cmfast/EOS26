import gc
gc.collect()
gc.disable()

import time
import argparse
import sys
sys.path.insert(1, 'run_scripts/')
import settings

# Parse args and set up logging BEFORE other imports
parser = argparse.ArgumentParser()
settings.add_common_args(parser)

args = parser.parse_args()
logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache

import numpy as np
import matplotlib.pyplot as plt

from matplotlib import rcParams
rcParams.update({"font.size":20, "font.family": 'serif'})
from matplotlib import colormaps, colors

eor_colour = colors.LinearSegmentedColormap.from_list(
    "EoR",
    [
        (0, "white"),
        (0.21, "yellow"),
        (0.42, "orange"),
        (0.63, "red"),
        (0.86, "black"),
        (0.9, "blue"),
        (1, "cyan"),
    ],
)
try:
    colormaps.register(cmap=eor_colour)
except:
    pass

job_start = time.perf_counter()
logger.info(f"Starting lightcone plotting")
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
    cache_dir, _box_overrides = settings.CACHE_TEST, {"HII_DIM": settings.TEST_HII_DIM}
else:
    _box_overrides = {}
    cache_dir = settings.CACHE_FULL

cache = p21c.OutputCache(cache_dir)
inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **_box_overrides)
HII_DIM = inputs.simulation_options.HII_DIM
BOX_LEN = inputs.simulation_options._LOWRES_CELL_SIZE_MPC * HII_DIM

plotspath = 'plots/'
lightcone = p21c.LightCone.from_file(cache_dir+"lc")
####################PLOT LC###################
keys = ["density", "brightness_temp", "cumulative_recombinations", "neutral_fraction", "spin_temperature", "tau_21", "J_21_LW"]
key_names = [r"$\delta$", r"$\delta T_{21}$ [mK]", "cumul recombs", "xHI", r"$T_S$ [K]", r"$\tau_{21}$", r"$J_{21,LW}$"]
cmaps = ["viridis", "EoR", "Reds", "hot","inferno","YlGnBu", "Blues"]
fig, axs = plt.subplots(nrows=1, ncols = 7, sharey=True, figsize = (24,17))
for i,k,k_name, c in zip(range(len(keys)), keys, key_names, cmaps):
    im = axs[i].pcolormesh(np.linspace(0, BOX_LEN, HII_DIM),
                     lightcone.lightcone_redshifts,
                     lightcone.lightcones[k][0,...].T,
                     vmin = np.nanpercentile(lightcone.lightcones[k][0,...],5) if c != "EoR" else -150,
                     vmax = np.nanpercentile(lightcone.lightcones[k][0,...],95) if c != "EoR" else 30,
                     cmap = c)
    cb = plt.colorbar(im,
            orientation="horizontal",
            ax=axs[i],
            label = k_name,
            pad=0.05,
        )
    axs[i].set_yscale("log")
axs[0].set_ylabel("Redshifts")
plt.savefig(plotspath+"lightcones_EOS25.png", bbox_inches='tight')
logger.info(f"Saved lightcone plot to {plotspath+'lightcones_EOS25.png'}")
