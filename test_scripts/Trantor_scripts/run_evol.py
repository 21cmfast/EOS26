import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import numpy as np
from template2input import create_params_from_template
from py21cmfast import generate_coeval
import gc

p21c.config['HALO_CATALOG_MEM_FACTOR'] = 2.

cache = p21c.OutputCache('/home/dbreitman/EOS25/TEST_L600_HIIDIM400_DIM1200_NO_PERTURN_ON_HIGH_RES')

inputs = p21c.InputParameters.from_template("/home/dbreitman/EOS25/TEST_L600_HIIDIM400_DIM1200_NO_PERTURN_ON_HIGH_RES/config-7dd812.toml", random_seed=1234)
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()
inputs = initial_conditions.inputs  # use the real inputs, with correct node_redshifts

for coeval, _ in p21c.generate_coeval(
    inputs = inputs,
    regenerate = False,
    write = True,
    cache = cache,
    initial_conditions = initial_conditions,
    progressbar = True,
):
    print("One coeval done")

    for ostruct in coeval.output_structs.values():
        for name, ary in ostruct.arrays.items():
            print(coeval.redshift, name, ary.state)
    
