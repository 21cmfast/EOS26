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
from py21cmfast.io.caching import RunCache
import sim_steps
from compare_EOS import compare_PHFs

job_start = time.perf_counter()
logger.info(f"Starting PHFs run")
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _input_overrides = settings.inputs_for_run(args.test, args.compare)
cache = p21c.OutputCache(cache_dir)


inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
    **_input_overrides)
runcache = RunCache.from_inputs(inputs, cache=cache)
halo_start = time.perf_counter()
sim_steps.evolve_halos(
    inputs=inputs,
    all_redshifts=inputs.node_redshifts,
    cache=cache,
    initial_conditions=runcache.get_ics(),
    progressbar=True,
)
halo_dt = time.perf_counter() - halo_start
job_dt = time.perf_counter() - job_start
logger.info(f"Halo evolution done in {halo_dt:.2f}s")
logger.info(f"Completed PHFs run in {job_dt:.2f}s")
if args.compare:
    compare_PHFs(cache, inputs)
    
