import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import numpy as np
from template2input import create_params_from_template
from py21cmfast import generate_coeval
import gc
import argparse
import logging

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
for coeval, _ in p21c.generate_coeval(
    inputs = inputs,
    regenerate = False,
    write = True,
    cache = cache,
    initial_conditions = initial_conditions,
    progressbar = True,
):
    print("One coeval done")
    count += 1
    if count >= N:
        break

    
