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
from compare_EOS import compare_PF

job_start = time.perf_counter()
logger.info(f"Starting N PF run: z_idx_start={z_idx_start}, N={N}")
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _input_overrides = settings.inputs_for_run(args.test, args.compare)

cache = p21c.OutputCache(cache_dir)
inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **_input_overrides)
runcache = RunCache.from_inputs(inputs, cache=cache)

if N == -1:
    N = len(inputs.node_redshifts) - z_idx_start

for i in range(N):
    loop_start = time.perf_counter()
    z_idx = z_idx_start + i
    z = inputs.node_redshifts[z_idx]
    logger.info(f"PF {i + 1}/{N}: z_idx={z_idx}, z={z:.6f}")

    pf = p21c.perturb_field(
        redshift=z,
        write=True,
        cache=cache,
        regenerate=False,
        inputs=inputs,
        initial_conditions=runcache.get_ics(),
    )

    loop_dt = time.perf_counter() - loop_start
    logger.info(f"PF {i + 1}/{N} done in {loop_dt:.2f}s")
    # ↑ no need to append peak_rss_gb() — RicherHandler prints RSS on every line

    if args.compare:
        compare_PF(pf, z, z_idx)
    pf.purge()

job_dt = time.perf_counter() - job_start
logger.info(f"Completed N PF run in {job_dt:.2f}s")