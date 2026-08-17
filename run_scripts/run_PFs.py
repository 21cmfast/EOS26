import gc
gc.collect()
gc.disable()

import time
import argparse
import settings

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
parser.add_argument("--z_idx", type=int)
args = parser.parse_args()
z_idx = args.z_idx

logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import sim_steps
from compare_EOS import compare_PF

job_start = time.perf_counter()
logger.info(f"Starting single PF run: z_idx={z_idx}")
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

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
                                            **_input_overrides)
z = inputs.node_redshifts[z_idx]
logger.info(f"Running PF at z_idx={z_idx}, z={z:.6f}")

pf_start = time.perf_counter()
pf_cpu_start = time.process_time()
with settings.RssSampler() as rss_sampler:
    pf = sim_steps.compute_perturbed_field(z, inputs, cache)
pf_dt = time.perf_counter() - pf_start
pf_average_cores = settings.average_cpu_cores(time.process_time() - pf_cpu_start, pf_dt)
if args.compare:
   compare_PF(pf, z, z_idx, cache, inputs)
del pf

job_dt = time.perf_counter() - job_start
logger.info(
    f"Completed single PF run in {job_dt:.2f}s "
    f"(PF average CPU cores: {pf_average_cores:.2f}; peak RSS: {rss_sampler.format_peak()})"
)
    
