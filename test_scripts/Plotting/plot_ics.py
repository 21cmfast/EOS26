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
zoom=True
vel=True
if test:
    path = "/home/dbreitman/EOS25/TEST_JAMES_L600_HIIDIM400_DIM1200_NO_PERTURN_ON_HIGH_RES"
    L=600*un.Mpc
    toml = path+"/config-448e84.toml"
    out = "/home/dbreitman/EOS25/ICs"
else:
    path = '/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2100_HIIDIM1400_DIM4200'
    L=2100*un.Mpc
    toml = "/jet/home/breitman/EOSv4/EOS25.toml"
    out = "/jet/home/breitman/EOSv4/Results/ICs"

cache = p21c.OutputCache(path)

inputs = p21c.InputParameters.from_template(toml, random_seed=1234)
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()

box = initial_conditions.get("lowres_density")*un.dimensionless_unscaled
HII_DIM = box.shape[0]
if zoom:
    box = initial_conditions.get("lowres_density")[:100,:100,:100]*un.dimensionless_unscaled 
    out+="_zoom"

if vel:
    v_x=initial_conditions.get("lowres_vx")[0,...]*un.m / un.s
    v_y=initial_conditions.get("lowres_vy")[0,...]*un.m / un.s
    out += "_wvel"
    if zoom:
        v_x = v_x[:100,:100]
        v_y = v_y[:100,:100]
else:
    v_x = None
    v_y = None

fig, ax = plt.subplots(1,1, layout="constrained")
ax = plot_coeval_slice(
    box,
    L/HII_DIM*box.shape[0],
    transform2slice=coeval2slice_x(idx=0),
    ax=ax, vmin=-17, vmax = 17,
    v_x=v_x,
    v_y=v_y,
    quiver_decimate_factor=10 if zoom else 18,
)
plt.savefig(out, dpi=300)



