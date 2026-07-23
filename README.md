# EOS26
## Description
All scripts to run the EOS26 simulation with 21cmFASTv4.2.
EOS26 is run phase by phase i.e. ICs first, then PFs, then PHFs, and finally coevals.

## How to run
All scripts accept an optional `--test` flag to run a small test box (HII_DIM=200).

### Comparison workflow

- Generate the reference once with `--test` and no `--compare`. It is written to
`EOS26_test_HIIDIM200/`.
- Run the production workflow with `--compare` to check
each output against that reference.
- For a local workflow check, use both flags:
`--test --compare`. Candidate files then go to
`EOS26_test_HIIDIM200_compare/`, so the reference is never overwritten. Both
test modes use the same input parameters and random seed (`42`).

### End-to-end test
- `sbatch sbatch_scripts/full_test_job.sh` — runs all three pipeline steps sequentially in test mode.
- `qsub pbs_scripts/full_test_job.sh` — PBS equivalent of the end-to-end test.

### Scaling Measurements

- Run `bash scaling/scaling_job.sh` to measure the default `HII_DIM=200` and
`HII_DIM=300` cases. Each run disables garbage collection, records peak process
RSS with `psutil`, and amortizes the full node-redshift coeval evolution over its
outputs, then writes a phase-by-phase JSON record under
`scaling/results/`. To benchmark other dimensions, pass them as arguments, for
example `bash scaling/scaling_job.sh 200 300 400`.

- After at least two measurements, `scaling/run_scalingrelation.py` fits power
laws for time, peak memory, phase storage, and every stored HDF5 structure. It
writes plots, `README_scaling_values.md`, and `scaling_fits.json` to
`scaling/reports/`. The generated Markdown file is the source for updating the
scaling table below. To apply direct measurements from the smallest and largest
completed `HII_DIM` runs plus fitted extrapolation intervals from every available
scaling result, run `uv run --no-sync scaling/run_scalingrelation.py
--update-readme`; it relabels the two measured columns and updates both EOS
extrapolation sections.

### Production run (in order)
1. **Initial conditions (ICs):**
   - `sbatch sbatch_scripts/ICs_job.sh [--test]`
  - `qsub pbs_scripts/ICs_job.sh [--test]` on PBS.
   - Writes `EOS26.toml` (full template with embedded node redshifts and random seed) and `EOS26_minimal.toml`, then runs `run_scripts/run_ICs.py`.
2. **Perturbed fields (PFs):**
   - `bash sbatch_scripts/submit_PF_jobs.sh [--test]` — submits one job per PF (indices 0–91) (not used for production).
   - `sbatch sbatch_scripts/N_PF_job.sh <z_idx> [N] [--test]` — runs a batch of N PFs (default N=10) starting from redshift index `z_idx`.
  - `bash pbs_scripts/submit_PF_jobs.sh [--test]` and `qsub pbs_scripts/N_PF_job.sh <z_idx> [N] [--test]` are the PBS equivalents.
3. **Perturbed halo fields (PHFs):**
   - `sbatch sbatch_scripts/PHFs_job.sh [--test]` — runs `run_scripts/run_PHFs.py`.
  - `qsub pbs_scripts/PHFs_job.sh [--test]` on PBS.
4. **Coevals:**
   - `sbatch sbatch_scripts/N_coeval_job.sh [N] [--test]` — runs a batch of N coevals (default N=10) with `run_scripts/run_N_coevals.py`.
  - `qsub pbs_scripts/N_coeval_job.sh [N] [--test]` on PBS.
## Table

<table><thead>
  <tr>
    <th>EOS25 simulation step<br></th>
    <th colspan="2">Computation time [hrs]</th>
    <th colspan="2">Memory [Tb]</th>
    <th colspan="2">Storage [Tb]</th>
    <th colspan="2">SUs</th>
  </tr></thead>
<tbody>
  <tr>
    <td></td>
    <td>Estimated</td>
    <td>Actual</td>
    <td>Estimated</td>
    <td>Actual</td>
    <td>Estimated</td>
    <td>Actual</td>
    <td>Estimated</td>
    <td>Actual</td>
  </tr>
  <tr>
    <td>Initial conditions</td>
    <td>13.5 + 2.75 <br>for writing to disk<br><br></td>
    <td></td>
    <td>1.1</td>
    <td>1.3</td>
    <td>652 Gb</td>
    <td>747 Gb</td>
    <td></td>
    <td>864 EM <br> for ICs + PFs<br></td>
  </tr>
  <tr>
    <td>One perturbed field<br></td>
    <td>0.6<br></td>
    <td></td>
    <td>25 Gb<br></td>
    <td>26 Gb</td>
    <td>25Gb x 92 = 2.3Tb</td>
    <td>2.4Tb</td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td>22 hrs</td>
    <td></td>
    <td>0.71</td>
    <td>0.77</td>
    <td>~330 G</td>
    <td>33 G</td>
    <td>720 EM</td>
    <td>617 EM</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td>7</td>
    <td></td>
    <td>3.65</td>
    <td></td>
    <td>2.6Tb x 92 = 240 Tb<br>0.215 x 92 = 20Tb without XRS<br></td>
    <td></td>
    <td>672 EM x 92 = 62k</td>
    <td></td>
  </tr>
</tbody></table>

## Scaling test results

When updated with `--update-readme`, each extrapolated value is the mean ± 1σ from a regression fit to all available scaling points: peak RSS uses an affine model (`overhead + coefficient * HII_DIM^3`, physically motivated by fixed per-process overhead plus volume-scaling grid buffers) fit by ordinary least squares, while time and storage use a free-exponent power-law fit in log-log space. In both cases the regression's own confidence interval on the mean is combined in quadrature with a fixed 10% relative per-point measurement-uncertainty floor. EOS-1: HII\_DIM = 1400 (1.5 cMpc/cell, 2100 Mpc). EOS-2: HII\_DIM = 1200 (1.667 cMpc/cell, 2000 Mpc). Storage for PFs and coevals is the total across all 92 node redshifts; coeval storage excludes IonizedBox.

<table><thead>
  <tr>
    <th>EOS26 simulation step</th>
    <th colspan="2">Computation time [hrs]</th>
    <th colspan="2">Memory</th>
    <th colspan="2">Storage</th>
  </tr>
  <tr>
    <th></th>
    <th>N=100</th>
    <th>N=300</th>
    <th>N=100</th>
    <th>N=300</th>
    <th>N=100</th>
    <th>N=300</th>
  </tr>
</thead>
<tbody>
  <tr><td colspan="7"><em>Scaling tests (measured)</em></td></tr>
  <tr>
    <td>Initial conditions</td>
    <td>0.00349</td>
    <td>0.045</td>
    <td>1.58 GB</td>
    <td>12.3 GB</td>
    <td>0.464 GB</td>
    <td>12.5 GB</td>
  </tr>
  <tr>
    <td>One perturbed field</td>
    <td>0.00252</td>
    <td>0.00311</td>
    <td>0.425 GB</td>
    <td>4.91 GB</td>
    <td>0.016 GB</td>
    <td>0.432 GB</td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td>0.00693</td>
    <td>0.0437</td>
    <td>0.786 GB</td>
    <td>13.6 GB</td>
    <td>0.207 GB</td>
    <td>5.49 GB</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td>0.000529</td>
    <td>0.0214</td>
    <td>1.4 GB</td>
    <td>16.5 GB</td>
    <td>0.0441 GB x 92 = 4.06 GB</td>
    <td>1.19 GB x 92 = 109 GB</td>
  </tr>
  <tr><td colspan="7"><em>Extrapolated to EOS-1 (HII_DIM = 1400, 1.5 cMpc/cell, 2100 Mpc)</em></td></tr>
  <tr>
    <td>Initial conditions</td>
    <td colspan="2">1.24 ± 1.28</td>
    <td colspan="2">1.06 ± 0.317 TB</td>
    <td colspan="2">1.27 ± 0.122 TB</td>
  </tr>
  <tr>
    <td>One perturbed field</td>
    <td colspan="2">0.00409 ± 0.000474</td>
    <td colspan="2">0.473 ± 0.0473 TB</td>
    <td colspan="2">0.0438 ± 0.00418 TB</td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td colspan="2">0.467 ± 0.356</td>
    <td colspan="2">1.34 ± 0.142 TB</td>
    <td colspan="2">0.542 ± 0.0522 TB</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td colspan="2">3.18 ± 2.15</td>
    <td colspan="2">1.49 ± 0.427 TB</td>
    <td colspan="2">0.12 ± 0.0115 TB x 92 = 11.1 ± 1.06 TB</td>
  </tr>
  <tr><td colspan="7"><em>Extrapolated to EOS-2 (HII_DIM = 1200, 1.667 cMpc/cell, 2000 Mpc)</em></td></tr>
  <tr>
    <td>Initial conditions</td>
    <td colspan="2">0.875 ± 0.824</td>
    <td colspan="2">0.668 ± 0.199 TB</td>
    <td colspan="2">0.802 ± 0.0765 TB</td>
  </tr>
  <tr>
    <td>One perturbed field</td>
    <td colspan="2">0.00398 ± 0.00045</td>
    <td colspan="2">0.298 ± 0.0298 TB</td>
    <td colspan="2">0.0276 ± 0.00263 TB</td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td colspan="2">0.363 ± 0.255</td>
    <td colspan="2">0.846 ± 0.0894 TB</td>
    <td colspan="2">0.342 ± 0.0329 TB</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td colspan="2">1.91 ± 1.19</td>
    <td colspan="2">0.941 ± 0.268 TB</td>
    <td colspan="2">0.0758 ± 0.00724 TB x 92 = 6.97 ± 0.666 TB</td>
  </tr>
</tbody></table>

## Projected maximum simulation size

Evolving astrophysics for one coeval is the most memory-intensive phase at every measured `HII_DIM` (see table above), so it sets the ceiling for the largest simulation a single node can run. Peak memory for 3D simulation grids is physically fixed per-process overhead (interpreter, shared libraries, lookup tables) plus a term that scales with box volume (`HII_DIM^3`), so peak RSS is fit as `overhead + coefficient * HII_DIM^3` by ordinary least squares using *all* measured points (`HII_DIM` = 100, 200, 300), rather than a free-exponent log-log power law, which is biased low by that same fixed overhead when it is not negligible at small `HII_DIM` (the same effect documented above for compute time). Resolution is fixed at 1.5 cMpc/cell, matching all current scaling points; only `HII_DIM` is varied. The "Max HII_DIM" columns require the upper end of the fit's 1-sigma band to stay within the memory budget, so the true peak should stay at or below the stated value.

<table><thead>
  <tr>
    <th>Memory budget</th>
    <th>Max HII_DIM</th>
    <th>Box length [Mpc]</th>
    <th>Predicted peak RSS (coeval)</th>
  </tr>
</thead>
<tbody>
  <tr>
    <td>3.0 TB</td>
    <td>1624</td>
    <td>2436</td>
    <td>2.33 ± 0.668 TB</td>
  </tr>
  <tr>
    <td>2.7 TB (90% safety margin)</td>
    <td>1568</td>
    <td>2352</td>
    <td>2.1 ± 0.601 TB</td>
  </tr>
</tbody></table>

Predicted coeval peak RSS at the current EOS target sizes (affine `overhead + coefficient * HII_DIM^3` fit on all measured points):

<table><thead>
  <tr><th>EOS target</th><th>HII_DIM</th><th>Predicted peak RSS (coeval)</th></tr>
</thead>
<tbody>
  <tr><td>EOS-1</td><td>1400</td><td>1.49 ± 0.427 TB</td></tr>
  <tr><td>EOS-2</td><td>1200</td><td>0.941 ± 0.268 TB</td></tr>
</tbody></table>

With only 3 measured points, the affine fit above is pulled noticeably off the data by whichever point dominates the linear-space sum of squares. A free-exponent power-law fit (the same form used for time and storage; see `fit_power_law`) tracks the coeval measurements markedly better, so it is shown here for comparison -- the affine model above remains the one used for the Max HII_DIM budget table:

<table><thead>
  <tr><th>EOS target</th><th>HII_DIM</th><th>Predicted peak RSS, affine</th><th>Predicted peak RSS, power law</th></tr>
</thead>
<tbody>
  <tr><td>EOS-1</td><td>1400</td><td>1.49 ± 0.427 TB</td><td>0.64 ± 0.453 TB</td></tr>
  <tr><td>EOS-2</td><td>1200</td><td>0.941 ± 0.268 TB</td><td>0.45 ± 0.293 TB</td></tr>
</tbody></table>

**Caveats:** this projection extrapolates well beyond the largest measured `HII_DIM` (300) to production scale, so treat it as an order-of-magnitude estimate rather than a precise bound. Run an additional scaling point at `HII_DIM = 400` (or larger) on the cluster and check whether the residuals from the affine fit stay small -- growing residuals at larger `HII_DIM` would mean memory grows faster than the assumed overhead-plus-cubic form and this projection is optimistic. Consider also profiling one run with `memray` to see the full memory-vs-redshift curve and confirm the RSS sampler is not missing any brief spikes.
