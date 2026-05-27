import gc
gc.collect()
gc.disable()

import time
import argparse
import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
from template2input import create_params_from_template
from py21cmfast import generate_coeval
from compare_EOS import compare_coeval
import settings
from settings import now_str, peak_rss_gb

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
parser.add_argument("--N", type=int, default=10)
args = parser.parse_args()
N = args.N

logger = settings.setup_logging(args.log_file)


job_start = time.perf_counter()
print(f"[{now_str()}] Starting N coeval run: N={N}")
print(f"[{now_str()}] gc.isenabled() = {gc.isenabled()} (expected: False)")

#p21c.config['HALO_CATALOG_MEM_FACTOR'] = 2.

if args.test:
    print(f"[{now_str()}] TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _box_overrides = settings.resolve_run_config(args.test, settings.CACHE_ALT)
cache = p21c.OutputCache(cache_dir)

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
                                            random_seed=settings.RANDOM_SEED_ALT,
                                            **_box_overrides)
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()
# use the real inputs, with correct node_redshifts
inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
                                            random_seed=settings.RANDOM_SEED_ALT,
                                            **_box_overrides)


count = 0
prev_tick = time.perf_counter()
for coeval, _ in p21c.generate_coeval(
    inputs = inputs,
    regenerate = False,
    write = True,
    cache = cache,
    initial_conditions = initial_conditions,
    progressbar = True,
):
    now_tick = time.perf_counter()
    loop_dt = now_tick - prev_tick
    z_val = getattr(coeval, "redshift", None)
    if z_val is None:
        print(f"[{now_str()}] coeval {count + 1}/{N}: redshift unavailable")
    else:
        print(f"[{now_str()}] coeval {count + 1}/{N}: z={z_val:.6f}")

    count += 1
    print(f"[{now_str()}] coeval {count}/{N} done in {loop_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")
    compare_coeval(coeval, cache, inputs)
    prev_tick = now_tick
    if count >= N:
        break

job_dt = time.perf_counter() - job_start
print(f"[{now_str()}] Completed N coeval run in {job_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")

    
