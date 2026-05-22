import gc
gc.collect()
gc.disable()

import os
import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import numpy as np
from template2input import create_params_from_template
from py21cmfast import generate_coeval
import argparse
import logging
import time
import psutil
from datetime import datetime
from compare_EOS import compare_coeval

parser = argparse.ArgumentParser()
parser.add_argument("--N", type=int, default=10)
parser.add_argument("--log-file", type=str, required=True)
args = parser.parse_args()
N = args.N

logger = logging.getLogger("21cmFAST")
logger.setLevel(logging.DEBUG)
logger.handlers.clear()
logger.propagate = False
file_handler = logging.FileHandler(args.log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

PROCESS = psutil.Process(os.getpid())
PEAK_RSS_BYTES = PROCESS.memory_info().rss


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def peak_rss_gb() -> float:
    global PEAK_RSS_BYTES
    rss = PROCESS.memory_info().rss
    if rss > PEAK_RSS_BYTES:
        PEAK_RSS_BYTES = rss
    return PEAK_RSS_BYTES / (1024.0 ** 3)


job_start = time.perf_counter()
print(f"[{now_str()}] Starting N coeval run: N={N}")
print(f"[{now_str()}] gc.isenabled() = {gc.isenabled()} (expected: False)")

#p21c.config['HALO_CATALOG_MEM_FACTOR'] = 2.

cache = p21c.OutputCache('/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2100_HIIDIM1400_DIM4200')

inputs = p21c.InputParameters.from_template("EOS25.toml", random_seed=1234)
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()
# use the real inputs, with correct node_redshifts
inputs = p21c.InputParameters.from_template("EOS25.toml", 
                                            random_seed=1234,
                                            node_redshifts=initial_conditions.inputs.node_redshifts)  


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

    
