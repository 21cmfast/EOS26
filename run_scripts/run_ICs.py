import gc
gc.collect()
gc.disable()

import os
import py21cmfast as p21c
import numpy as np
import argparse
import logging
import time
import psutil
from datetime import datetime
from compare_EOS import compare_ICs, compare_PF

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
print(f"[{now_str()}] Starting ICs + PFs run")
print(f"[{now_str()}] gc.isenabled() = {gc.isenabled()} (expected: False)")

cache = p21c.OutputCache('/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2000_HIIDIM1200_DIM3600/')

inputs = p21c.InputParameters.from_template("EOS25.toml",
        node_redshifts=p21c.wrapper.inputs.get_logspaced_redshifts(
            min_redshift=5.0,
            z_step_factor=1.02,
            max_redshift=35.0,
        ),
        random_seed=42,
    ) 

print(f"[{now_str()}] Inputs prepared with {len(inputs.node_redshifts)} redshifts")

ics_start = time.perf_counter()
initial_conditions = p21c.compute_initial_conditions(
    inputs=inputs, cache=cache, write=True, regenerate=False,
)
ics_dt = time.perf_counter() - ics_start
print(f"[{now_str()}] Initial conditions done in {ics_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")
compare_ICs(initial_conditions)

for idx, z in enumerate(inputs.node_redshifts):
    loop_start = time.perf_counter()
    print(f"[{now_str()}] PF {idx + 1}/{len(inputs.node_redshifts)}: z_idx={idx}, z={z:.6f}")
    pf = p21c.perturb_field(
    redshift=z,
    initial_conditions=initial_conditions,
    write=True, cache=cache, regenerate=False,
    )
    loop_dt = time.perf_counter() - loop_start
    print(f"[{now_str()}] PF {idx + 1}/{len(inputs.node_redshifts)} done in {loop_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")
    compare_PF(pf, z, idx)

job_dt = time.perf_counter() - job_start
print(f"[{now_str()}] Completed ICs + PFs run in {job_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")
