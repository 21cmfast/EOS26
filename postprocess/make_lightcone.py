import gc
gc.collect()
gc.disable()

import time
import argparse
import sys
sys.path.insert(1, 'run_scripts/')
import settings

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
args = parser.parse_args()

logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
from py21cmfast import run_lightcone

job_start = time.perf_counter()
print(f"Starting make lightcone:")
print(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

#p21c.config['HALO_CATALOG_MEM_FACTOR'] = 2.

if args.test:
    print(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
    cache_dir, _box_overrides = settings.CACHE_TEST, {"HII_DIM": settings.TEST_HII_DIM}
else:
    _box_overrides = {}
    cache_dir = settings.CACHE_FULL
cache = p21c.OutputCache(cache_dir)

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
                                            **_box_overrides)
runcache = RunCache.from_inputs(inputs, cache=cache)


prev_tick = time.perf_counter()
lc_path = str(cache_dir + "lc")
lcn = p21c.RectilinearLightconer.between_redshifts(
    min_redshift=5.0,
    max_redshift=35.0,
    quantities=(
        "brightness_temp",
        "spin_temperature",
        "neutral_fraction",
        "cumulative_recombinations",
        "z_reion",
        "ionisation_rate_G12",
        "J_21_LW",
        "density",
    ),
    resolution=inputs.simulation_options.cell_size,
)

lc = p21c.run_lightcone(
    lightconer=lcn,
    inputs=inputs,
    initial_conditions=runcache.get_ics(),
    cache=cache,
    regenerate=False,
    progressbar=True,
)
lc.save(lc_path)

job_dt = time.perf_counter() - job_start
print(f"Completed lightcone run in {job_dt:.2f}s")

    
