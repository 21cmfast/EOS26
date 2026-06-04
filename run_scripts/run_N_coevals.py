import gc
gc.collect()
gc.disable()

import time
import argparse
import settings
from settings import now_str

logger = settings.setup_logging(args.log_file)

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
parser.add_argument("--N", type=int, default=10)
args = parser.parse_args()
N = args.N

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
from py21cmfast import generate_coeval
from compare_EOS import compare_coeval

job_start = time.perf_counter()
logger.info(f"Starting N coeval run: N={N}")
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

#p21c.config['HALO_CATALOG_MEM_FACTOR'] = 2.

if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
    cache_dir, _box_overrides = settings.CACHE_TEST, {"HII_DIM": settings.TEST_HII_DIM}
else:
    _box_overrides = {}
    cache_dir = settings.CACHE_FULL
cache = p21c.OutputCache(cache_dir)

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
                                            **_box_overrides)

count = 0
prev_tick = time.perf_counter()
for coeval, _ in p21c.generate_coeval(
    inputs = inputs,
    regenerate = False,
    write = True,
    cache = cache,
    progressbar = True,
):
    now_tick = time.perf_counter()
    loop_dt = now_tick - prev_tick
    z_val = getattr(coeval, "redshift", None)
    if z_val is None:
        logger.info(f"coeval {count + 1}/{N}: redshift unavailable")
    else:
        logger.info(f"coeval {count + 1}/{N}: z={z_val:.6f}")

    count += 1
    logger.info(f"coeval {count}/{N} done in {loop_dt:.2f}s")
    if not args.test:
        compare_coeval(coeval, cache, inputs)
    prev_tick = now_tick
    if count >= N:
        break

job_dt = time.perf_counter() - job_start
logger.info(f"Completed N coeval run in {job_dt:.2f}s")

    
