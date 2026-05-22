import py21cmfast as p21c
from py21cmfast.io.caching import RunCache, CacheConfig
import numpy as np
import argparse
import logging

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

p21c.config['HALO_CATALOG_MEM_FACTOR'] = 1.6

cache = p21c.OutputCache('/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2000_HIIDIM1200_DIM3600/')


inputs = p21c.InputParameters.from_template("EOS25.toml", random_seed=42,  node_redshifts=p21c.get_logspaced_redshifts(min_redshift=5.0,z_step_factor=1.02, max_redshift=35.0))
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()
inputs = initial_conditions.inputs  # use the real inputs, with correct node_redshifts
print("Got ICs, starting evolve perturb halos")
p21c.drivers.coeval.evolve_halos(inputs=inputs,
                    initial_conditions=initial_conditions,
                    regenerate=False,
                    all_redshifts=inputs.node_redshifts,
                    write=CacheConfig(),
                    cache=cache,
                    progressbar=True,
                    free_cosmo_tables=False,
)
    
