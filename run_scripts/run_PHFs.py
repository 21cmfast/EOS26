import gc
gc.collect()
gc.disable()

import os
import py21cmfast as p21c
from py21cmfast.io.caching import RunCache, CacheConfig
import numpy as np
import argparse
import logging
import time
import psutil
from datetime import datetime
from compare_EOS import compare_PHFs

parser = argparse.ArgumentParser()
parser.add_argument("--log-file", type=str, required=True)
args = parser.parse_args()

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
print(f"[{now_str()}] Starting PHFs run")
print(f"[{now_str()}] gc.isenabled() = {gc.isenabled()} (expected: False)")

p21c.config['HALO_CATALOG_MEM_FACTOR'] = 1.6

cache = p21c.OutputCache('/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2000_HIIDIM1200_DIM3600/')


inputs = p21c.InputParameters.from_template("EOS25.toml", random_seed=42,  node_redshifts=p21c.get_logspaced_redshifts(min_redshift=5.0,z_step_factor=1.02, max_redshift=35.0))
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()
inputs = initial_conditions.inputs  # use the real inputs, with correct node_redshifts
print(f"[{now_str()}] Got ICs, evolving halos for {len(inputs.node_redshifts)} redshifts")
halo_start = time.perf_counter()
p21c.drivers.coeval.evolve_halos(inputs=inputs,
                    initial_conditions=initial_conditions,
                    regenerate=False,
                    all_redshifts=inputs.node_redshifts,
                    write=CacheConfig(),
                    cache=cache,
                    progressbar=True,
                    free_cosmo_tables=False,
)
halo_dt = time.perf_counter() - halo_start
job_dt = time.perf_counter() - job_start
print(f"[{now_str()}] Halo evolution done in {halo_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")
print(f"[{now_str()}] Completed PHFs run in {job_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")
compare_PHFs(cache, inputs)
    
