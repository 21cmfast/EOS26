import gc
gc.collect()
gc.disable()

import time
import argparse
import numpy as np
import settings

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
parser.add_argument("--N", type=int, default=10)
args = parser.parse_args()
N = args.N
logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c
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
# Scope the "already done" lookup to the current inputs' cache hash (matter_cosmo/
# seed/zgrid/astro_flag). An unscoped glob would silently pick up coevals from a
# stale/mismatched cache (e.g. built with different simulation options), making us
# believe redshifts are already done when they actually belong to an incompatible run.
coevals_done = cache.list_datasets(kind="BrightnessTemp", inputs=inputs, all_seeds=False)
n_coevals_done = len(coevals_done)
redshifts_done = sorted([float(cpath.parts[-3]) for cpath in coevals_done])
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
generator_exhausted = False
try:
    while count < N:
        # generate_coeval() yields every redshift step needed to re-establish the
        # halo/ionization evolution history (per inputs.node_redshifts), not just
        # the redshifts we asked for in `this_batch_redshifts` (out_redshifts).
        # It flags which yields are actually requested outputs via the second
        # tuple element; intermediate steps must be skipped here (not counted,
        # not compared, not purged) -- py21cmfast purges them internally once the
        # next step is produced.
        coeval_cpu_start = time.process_time()
        coeval = None
        with settings.RssSampler() as rss_sampler:
            while True:
                try:
                    coeval, is_output = next(coeval_generator)
                except StopIteration:
                    generator_exhausted = True
                    break
                if is_output:
                    break
                logger.debug(
                    f"Skipping intermediate coeval at z={coeval.redshift:.6f} "
                    "(required for redshift evolution, not part of this batch)"
                )
        if generator_exhausted:
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

        # Coeval has no purge() method -- the real API for releasing an output
        # struct's in-memory arrays is prepare_for_next_snapshot(). We're done with
        # this coeval entirely (about to move to the next one), so purge everything.
        coeval.prepare_for_next_snapshot(force=True)

        # gc.collect() here consistently finds 0 collectible objects after the
        # first coeval (measured directly, both locally and on the cluster), so
        # per-coeval Python reference cycles were never the source of the
        # peak-RSS growth we originally saw with --compare. That growth (~25-90
        # MB/coeval) was root-caused instead to compare_EOS.py's _hdf5_histogram:
        # it read HDF5 slabs with an explicit stepped slice (`ds[i, ::step, ::step]`),
        # which h5py's fast read path doesn't support, silently falling back to
        # a slow generic selection path that leaked a new HDF5 type object on
        # every call (visible via tracemalloc at h5py/_hl/dataset.py, never
        # freed). Fixed in compare_EOS.py by reading each slab contiguously
        # (fast path) and doing the step-subsampling in NumPy afterwards. A
        # glibc malloc_trim(0) fragmentation-based fix was tried first and
        # confirmed (via real cluster logs) to NOT reduce the growth rate --
        # heap fragmentation was never the actual mechanism. gc.collect() is
        # kept here as cheap insurance against the one-time startup garbage.
        n_collected = gc.collect()
        logger.debug(f"gc.collect() after coeval {count}/{N} collected {n_collected} objects")
        prev_tick = now_tick
finally:
    # coeval_generator wraps py21cmfast's _redshift_loop_generator, whose entire
    # body (all yields included) runs inside a `with rich.progress.Progress(...)`
    # block that owns a live background refresh thread. If we stop calling next()
    # early (e.g. once we've collected our N coevals) without closing the
    # generator, it's left suspended mid-`with`, keeping that thread alive.
    # coeval_generator.close() only closes the *outer* generator (py21cmfast's
    # `high_level_func` wrapper); the inner `_redshift_loop_generator` is reached
    # via a plain `for ... in _redshift_loop_generator(...): yield ...` (not
    # `yield from`), so closing the outer one doesn't cascade to it explicitly --
    # it relies on refcounting to drop the inner generator when the outer's frame
    # unwinds. But generator frames referencing OutputStruct/Coeval objects that
    # reference back to the frame form a reference cycle, so refcounting alone
    # can't free it; only a real GC pass can. We run with gc.disable() (both here
    # and internally in py21cmfast) for the whole script to avoid glibc memory
    # fragmentation, so that GC pass never happens naturally -- it's deferred all
    # the way to Py_Finalize's forced final collection, where resuming the
    # cyclic-garbage generator to close it calls Progress's thread.join(), which
    # hangs because it's running during interpreter shutdown (confirmed via lldb:
    # main thread stuck in gc_collect_main -> gen_close -> ... -> Thread.join()).
    # Force that collection ourselves now, while the interpreter is still fully
    # alive, so the hang happens here (it doesn't) instead of at exit.
    coeval_generator.close()
    gc.collect()

job_dt = time.perf_counter() - job_start
logger.info(f"Completed N coeval run in {job_dt:.2f}s")

    

