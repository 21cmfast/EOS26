import gc
gc.collect()
gc.disable()

import os
import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import numpy as np
import argparse
import logging
import time
import psutil
from datetime import datetime
from compare_EOS import compare_PF

parser = argparse.ArgumentParser()
parser.add_argument("--z_idx", type = int)
parser.add_argument("--log-file", type=str, required=True)
args = parser.parse_args()
z_idx = args.z_idx

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
print(f"[{now_str()}] Starting single PF run: z_idx={z_idx}")
print(f"[{now_str()}] gc.isenabled() = {gc.isenabled()} (expected: False)")

cache = p21c.OutputCache('/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2100_HIIDIM1400_DIM4200')

inputs = p21c.InputParameters.from_template("EOS25.toml", random_seed=1234)
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()
inputs = initial_conditions.inputs  # use the real inputs, with correct node_redshifts
z = inputs.node_redshifts[z_idx]
print(f"[{now_str()}] Running PF at z_idx={z_idx}, z={z:.6f}")

pf = p21c.perturb_field(redshift=z,
                   initial_conditions=initial_conditions,
                   write=True,
                   cache=cache,
                   regenerate=False,
)
compare_PF(pf, z, z_idx)

job_dt = time.perf_counter() - job_start
print(f"[{now_str()}] Completed single PF run in {job_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")
    
