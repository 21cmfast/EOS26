import gc
gc.collect()
gc.disable()

import time
import argparse
from glob import glob
from pathlib import Path
import numpy as np
import settings

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
parser.add_argument("--N", type=int, default=10)
args = parser.parse_args()
N = args.N
logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import sim_steps
from compare_EOS import compare_coeval

job_start = time.perf_counter()
logger.info(f"Starting N coeval run: N={N}")
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _input_overrides = settings.inputs_for_run(args.test, args.compare)
cache = p21c.OutputCache(cache_dir)

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
                                            **_input_overrides)
coevals_done = glob(cache_dir + "*/*/*/*/*/BrightnessTemp.h5")
n_coevals_done = len(coevals_done)
redshifts_done = sorted([float(cpath.split("/")[-3]) for cpath in coevals_done])
logger.info(f"Already have {n_coevals_done} coevals done, at redshifts: {redshifts_done}")
not_done = np.array([np.round(z,4) not in redshifts_done for z in inputs.node_redshifts])
if args.N == -1:
    N = np.sum(not_done)
this_batch_redshifts = sorted(np.array(inputs.node_redshifts)[not_done][:N])[::-1]
logger.info(f"Redshifts for this batch: {this_batch_redshifts[0]:.2f} to {this_batch_redshifts[-1]:.2f}")
count = 0
prev_tick = time.perf_counter()
coeval_generator = sim_steps.generate_coevals(
    this_batch_redshifts,
    inputs,
    cache,
    progressbar=True,
)
while count < N:
    coeval_cpu_start = time.process_time()
    with settings.RssSampler() as rss_sampler:
        try:
            coeval, _ = next(coeval_generator)
        except StopIteration:
            break
    now_tick = time.perf_counter()
    loop_dt = now_tick - prev_tick
    coeval_average_cores = settings.average_cpu_cores(time.process_time() - coeval_cpu_start, loop_dt)
    z_val = getattr(coeval, "redshift", None)
    if z_val is None:
        logger.info(f"coeval {count + 1}/{N}: redshift unavailable")
    else:
        logger.info(f"coeval {count + 1}/{N}: z={z_val:.6f}")

    count += 1
    logger.info(
        f"coeval {count}/{N} done in {loop_dt:.2f}s "
        f"(average CPU cores: {coeval_average_cores:.2f}; peak RSS: {rss_sampler.format_peak()})"
    )
    if args.compare:
        compare_coeval(coeval, cache, inputs)

    # Keep the XraySourceBox belonging to the coeval just completed, delete previous ones.

    xray_paths = list(Path(cache_dir).glob("**/XraySourceBox.h5"))

    z_current = getattr(coeval, "redshift", None)

    if z_current is not None:
        # The cache redshift is encoded in the same path component used
        # above when identifying completed coevals.
        z_current_rounded = round(float(z_current), 4)

        current_xray_paths = []
        old_xray_paths = []

        for xray_path in xray_paths:
            try:
                z_path = float(xray_path.parts[-3])
            except (ValueError, IndexError):
                # If this isn't a cache path with the expected structure,
                # don't delete it.
                continue

            if round(z_path, 4) == z_current_rounded:
                current_xray_paths.append(xray_path)
            else:
                old_xray_paths.append(xray_path)

        # Delete XRSBs from all older coevals, retaining the current one.
        for xray_path in old_xray_paths:
            xray_path.unlink()

        logger.info(
            "XraySourceBox cleanup: retained %d current XraySourceBox file(s) "
            "at z=%.6f; removed %d older file(s)",
            len(current_xray_paths),
            float(z_current),
            len(old_xray_paths),
        )
    else:
        logger.warning(
            "Could not determine current coeval redshift; "
            "leaving all XraySourceBox files untouched."
        )
    coeval.purge()
    prev_tick = now_tick

job_dt = time.perf_counter() - job_start
logger.info(f"Completed N coeval run in {job_dt:.2f}s")

    

