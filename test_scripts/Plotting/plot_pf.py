import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
from tuesday.core import (coeval2slice_x, plot_coeval_slice)
from astropy import units as un
import matplotlib.pyplot as plt
from tuesday.core import (
    coeval2slice_x,
    plot_coeval_slice,
)

test=False
zoom=False
if test:
    path = "/home/dbreitman/EOS25/TEST_JAMES_L600_HIIDIM400_DIM1200_NO_PERTURN_ON_HIGH_RES"
    L=600*un.Mpc
    toml = path+"/config-448e84.toml"
    out = "/home/dbreitman/EOS25/PF"
else:
    path = '/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2100_HIIDIM1400_DIM4200'
    L=2100*un.Mpc
    toml = "/jet/home/breitman/EOSv4/EOS25.toml"
    out = "/jet/home/breitman/EOSv4/Results/PF"

cache = p21c.OutputCache(path)

inputs = p21c.InputParameters.from_template(toml, random_seed=1234, node_redshifts=p21c.get_logspaced_redshifts(min_redshift=5.0,z_step_factor=1.02, max_redshift=35.0))
runcache = RunCache.from_inputs(inputs, cache=cache)
perturbed_field = runcache.get_output_struct_at_z("PerturbedField", z=33.9596, match_z_within=0.1)


box = perturbed_field.get("density")*un.dimensionless_unscaled
HII_DIM = box.shape[0]
if zoom:
    box = box[:100,:100,:100]
    out+="_zoom"


fig, ax = plt.subplots(1,1, layout="constrained")
ax = plot_coeval_slice(
    box,
    L/HII_DIM*box.shape[0],
    transform2slice=coeval2slice_x(idx=0),
    ax=ax, vmin=-0.5, vmax = 0.5,
    title="z = 34"
)
plt.savefig(out, dpi=300)



