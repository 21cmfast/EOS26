import gc
gc.collect()
gc.disable()

import time
import argparse
import settings

# Parse args and set up logging BEFORE other imports
parser = argparse.ArgumentParser()
settings.add_common_args(parser)
parser.add_argument("--z_idx_start", type=int)
parser.add_argument("--N", type=int, default=10)
args = parser.parse_args()
z_idx_start = args.z_idx_start
N = args.N
logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import sim_steps
from compare_EOS import compare_PF

job_start = time.perf_counter()
logger.info(f"Starting N PF run: z_idx_start={z_idx_start}, N={N}")
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

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
inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **_input_overrides)
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()

if N == -1:
    N = len(inputs.node_redshifts) - z_idx_start

for i in range(N):
    loop_start = time.perf_counter()
    loop_cpu_start = time.process_time()
    z_idx = z_idx_start + i
    z = inputs.node_redshifts[z_idx]
    logger.info(f"PF {i + 1}/{N}: z_idx={z_idx}, z={z:.6f}")

    with settings.RssSampler() as rss_sampler:
        pf = sim_steps.compute_perturbed_field(z, inputs, cache, initial_conditions)

    loop_dt = time.perf_counter() - loop_start
    loop_average_cores = settings.average_cpu_cores(time.process_time() - loop_cpu_start, loop_dt)
    logger.info(
        f"PF {i + 1}/{N} done in {loop_dt:.2f}s "
        f"(average CPU cores: {loop_average_cores:.2f}; peak RSS: {rss_sampler.format_peak()})"
    )

    if args.compare:
        compare_PF(pf, z, z_idx, cache, inputs)
    pf.purge()
    del pf
    gc.collect()

job_dt = time.perf_counter() - job_start
logger.info(f"Completed N PF run in {job_dt:.2f}s")
