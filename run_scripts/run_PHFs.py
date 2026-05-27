import gc
gc.collect()
gc.disable()

import time
import argparse
import py21cmfast as p21c
from py21cmfast.io.caching import RunCache, CacheConfig
from compare_EOS import compare_PHFs
import settings
from settings import now_str, peak_rss_gb

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
args = parser.parse_args()

logger = settings.setup_logging(args.log_file)


job_start = time.perf_counter()
print(f"[{now_str()}] Starting PHFs run")
print(f"[{now_str()}] gc.isenabled() = {gc.isenabled()} (expected: False)")

p21c.config['HALO_CATALOG_MEM_FACTOR'] = 1.6

if args.test:
    print(f"[{now_str()}] TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _box_overrides = settings.resolve_run_config(args.test, settings.CACHE_FULL)
cache = p21c.OutputCache(cache_dir)


inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
        node_redshifts=p21c.get_logspaced_redshifts(min_redshift=5.0, z_step_factor=1.02, max_redshift=35.0),
        random_seed=settings.RANDOM_SEED,
        **settings.TEMPLATE_BOX_KWARGS,
        **_box_overrides)
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
    
