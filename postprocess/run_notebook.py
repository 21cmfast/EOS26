"""Run the code cells of a notebook in order, as one Python program, without Jupyter.

    python postprocess/run_notebook.py postprocess/plot_all_summaries.ipynb
    python postprocess/run_notebook.py postprocess/plot_all_summaries.ipynb --set TEST=False

The code runs in the notebook's own folder, as in Jupyter, with the non-interactive matplotlib
backend: figures are only written by the notebook's own plt.savefig calls, and printed output
goes to stdout. --set NAME=VALUE replaces the first top-level line `NAME = ...` of the notebook's
code before it runs. The run stops at the first error and names the cell (its 0-based index
among all the notebook's cells, markdown included).
"""
import argparse
import json
import os
import re
import sys
import time
import traceback
import warnings
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("notebook", type=Path)
ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE", help="e.g. --set TEST=False")
args = ap.parse_args()

os.environ.setdefault("MPLBACKEND", "Agg")
warnings.filterwarnings("ignore", message=".*non-interactive.*")  # plt.show() with Agg

nb_path = args.notebook.resolve()
cells = [(i, "".join(c["source"])) for i, c in enumerate(json.load(open(nb_path))["cells"]) if c["cell_type"] == "code"]
for item in args.set:
    name, value = item.split("=", 1)
    pattern = re.compile(rf"^{re.escape(name)}\s*=.*$", re.M)
    hits = [k for k, (_, src) in enumerate(cells) if pattern.search(src)]
    if not hits:
        sys.exit(f"--set {item}: no line '{name} = ...' in {nb_path.name}")
    k = hits[0]
    cells[k] = (cells[k][0], pattern.sub(lambda _: f"{name} = {value}", cells[k][1], count=1))
    print(f"--set: {name} = {value} (cell {cells[k][0]})")

os.chdir(nb_path.parent)
sys.path.insert(0, str(nb_path.parent))
namespace = {"__name__": "__main__"}
t0 = time.time()
for n, (i, src) in enumerate(cells):
    print(f"===== cell {i} ({n + 1}/{len(cells)} code cells, {time.time() - t0:.0f} s)", flush=True)
    try:
        exec(compile(src, f"{nb_path.name}, cell {i}", "exec"), namespace)
    except Exception:
        traceback.print_exc()
        sys.exit(f"stopped: error in cell {i} of {nb_path.name}")
    if "matplotlib.pyplot" in sys.modules:
        sys.modules["matplotlib.pyplot"].close("all")
    sys.stdout.flush()
print(f"===== {nb_path.name}: done in {time.time() - t0:.0f} s")
