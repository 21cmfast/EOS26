import gc
gc.collect()
gc.disable()

import time
import argparse
import settings

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
args = parser.parse_args()

logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache, CacheConfig
from compare_EOS import compare_PHFs

job_start = time.perf_counter()
logger.info(f"Starting PHFs run")
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

#p21c.config['HALO_CATALOG_MEM_FACTOR'] = 1.6

if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _input_overrides = settings.inputs_for_run(args.test, args.compare)
cache = p21c.OutputCache(cache_dir)


inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
    **_input_overrides)
runcache = RunCache.from_inputs(inputs, cache=cache)
halo_start = time.perf_counter()
p21c.drivers.coeval.evolve_halos(inputs=inputs,
                    regenerate=False,
                    all_redshifts=inputs.node_redshifts,
                    write=CacheConfig(),
                    cache=cache,
                    progressbar=True,
                    free_cosmo_tables=False,
                    initial_conditions=runcache.get_ics()
)
halo_dt = time.perf_counter() - halo_start
job_dt = time.perf_counter() - job_start
logger.info(f"Halo evolution done in {halo_dt:.2f}s")
logger.info(f"Completed PHFs run in {job_dt:.2f}s")
if args.compare:
    compare_PHFs(cache, inputs)
    
