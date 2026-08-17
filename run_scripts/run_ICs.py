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
import sim_steps
from compare_EOS import compare_ICs

job_start = time.perf_counter()
print(f"Starting ICs")
print(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

import os

print("OMP_NUM_THREADS:", os.environ.get("OMP_NUM_THREADS"))
print("OMP_PROC_BIND:", os.environ.get("OMP_PROC_BIND"))
print("OMP_PLACES:", os.environ.get("OMP_PLACES"))

if hasattr(os, "sched_getaffinity"):
    print("Allowed CPUs:", sorted(os.sched_getaffinity(0)))

if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _input_overrides = settings.inputs_for_run(args.test, args.compare)
cache = p21c.OutputCache(cache_dir)

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
    **_input_overrides,
    )

logger.info(f"Inputs prepared with {len(inputs.node_redshifts)} redshifts")

ics_start = time.perf_counter()
ics_cpu_start = time.process_time()
with settings.RssSampler() as rss_sampler:
    initial_conditions = sim_steps.compute_initial_conditions(inputs, cache)
ics_dt = time.perf_counter() - ics_start
ics_average_cores = settings.average_cpu_cores(time.process_time() - ics_cpu_start, ics_dt)
logger.info(
    f"Initial conditions done in {ics_dt:.2f}s "
    f"(average CPU cores: {ics_average_cores:.2f}; peak RSS: {rss_sampler.format_peak()})"
)
if args.compare:
    compare_ICs(initial_conditions, cache, inputs)

