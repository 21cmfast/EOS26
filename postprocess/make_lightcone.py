import gc
gc.collect()
gc.disable()

import time
import argparse
import sys
sys.path.insert(1, 'run_scripts/')
import settings
import sim_steps

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
parser.add_argument("--all-quantities", action="store_true", default=False,
                    help="Every field of the coeval boxes (default: the main ones)")
args = parser.parse_args()

logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
from py21cmfast import run_lightcone

job_start = time.perf_counter()
logger.info(f"Starting make lightcone:")
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

#p21c.config['HALO_CATALOG_MEM_FACTOR'] = 2.

if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _input_overrides = settings.inputs_for_run(args.test, args.compare)
cache = p21c.OutputCache(cache_dir)

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
                                            **_input_overrides)
runcache = RunCache.from_inputs(inputs, cache=cache)


prev_tick = time.perf_counter()
lc_path = settings.lightcone_path(cache_dir)
QUANTITIES = (
    "brightness_temp",
    "spin_temperature",
    "neutral_fraction",
    "cumulative_recombinations",
    "z_reion",
    "ionisation_rate_G12",
    "J_21_LW",
    "density",
)
ALL_QUANTITIES = QUANTITIES + (
    "tau_21",                  # BrightnessTemp
    "kinetic_temp_neutral",    # TsBox
    "xray_ionised_fraction",
    "velocity_z",              # PerturbedField
    "sfrd_acg",                # EmissivityFields
    "sfrd_mcg",
    "xray_emissivity",
    "n_ion",
    "fesc_weighted_sfrd",
)
quantities = ALL_QUANTITIES if args.all_quantities else QUANTITIES
logger.info(f"Lightcone quantities: {quantities} -> {lc_path}")
lcn = p21c.RectilinearLightconer.between_redshifts(
    min_redshift=5.0,
    max_redshift=35.0,
    quantities=quantities,
    resolution=inputs.simulation_options.cell_size,
)

lc = p21c.run_lightcone(
    lightconer=lcn,
    inputs=inputs,
    initial_conditions=runcache.get_ics(),
    cache=cache,
    regenerate=False,
    # Read the cached coevals. The default CacheConfig() would recompute the
    # RadiationFields at every redshift (they are never cached) and write them.
    write=sim_steps.coeval_write_config(),
    progressbar=True,
)
lc.save(lc_path, clobber=True)

job_dt = time.perf_counter() - job_start
logger.info(f"Completed lightcone run in {job_dt:.2f}s")
