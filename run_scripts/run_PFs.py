import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import numpy as np
from template2input import create_params_from_template
import argparse
import logging

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

cache = p21c.OutputCache('/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2100_HIIDIM1400_DIM4200')

inputs = p21c.InputParameters.from_template("EOS25.toml", random_seed=1234)
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()
inputs = initial_conditions.inputs  # use the real inputs, with correct node_redshifts
z = inputs.node_redshifts[z_idx]

p21c.perturb_field(redshift=z, 
                   initial_conditions=initial_conditions,
                   write=True,
                   cache=cache,
)
    
