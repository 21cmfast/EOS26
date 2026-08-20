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
    <th>EOS26 simulation step<br></th>
    <th colspan="2">Computation time [hrs]</th>
    <th colspan="2">Memory [TB]</th>
    <th colspan="2">Storage [TB]</th>
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
    <td>17+~3 write</td>
    <td>30</td>
    <td>2.63</td>
    <td>2.41</td>
    <td>1.42</td>
    <td>1.57</td>
    <td></td>
    <td></td>
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

When updated with `--update-readme`, each extrapolated value is the mean ± 1σ from all available scaling points. Each extrapolated quantity shows both its current model (affine `overhead + coefficient * HII_DIM^3` for peak RSS; free-exponent power law for time and storage) and a fixed-cubic `a=3` fit. The regression uncertainty is combined in quadrature with a fixed 10% relative measurement-uncertainty floor. EOS-1: HII\_DIM = 1500 (1.5 cMpc/cell, 2250 Mpc). EOS-2: HII\_DIM = 1200 (1.667 cMpc/cell, 2000 Mpc). Storage for PFs and coevals is the total across all 92 node redshifts; coeval storage includes retained IonizedBox and excludes transient XraySourceBox. The scaling-test fits are trained only on `HII_DIM<=500` and, for initial conditions, that range's fixed per-job overhead makes the fitted compute-time noticeably underestimate the production values now measured at both EOS target sizes (`elapsed_seconds` fit for HII_DIM=1500: 17h vs. 29.8h measured).

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
    <th>N=500</th>
    <th>N=100</th>
    <th>N=500</th>
    <th>N=100</th>
    <th>N=500</th>
  </tr>
</thead>
<tbody>
  <tr><td colspan="7"><em>Scaling tests (measured)</em></td></tr>
  <tr>
    <td>Initial conditions</td>
    <td>0.0374</td>
    <td>0.624</td>
    <td>0.939 GB</td>
    <td>97.2 GB</td>
    <td>0.464 GB</td>
    <td>58 GB</td>
  </tr>
  <tr>
    <td>One perturbed field</td>
    <td>0.0345</td>
    <td>0.0447</td>
    <td>0.334 GB</td>
    <td>20.2 GB</td>
    <td>0.016 GB</td>
    <td>2 GB</td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td>0.0498</td>
    <td>0.659</td>
    <td>0.564 GB</td>
    <td>51 GB</td>
    <td>0.207 GB</td>
    <td>25.4 GB</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td>0.00199</td>
    <td>0.423</td>
    <td>1.16 GB</td>
    <td>97.2 GB</td>
    <td>0.0601 GB x 92 = 5.53 GB</td>
    <td>n/a (partial run: 5/92 coevals)</td>
  </tr>
  <tr><td colspan="7"><em>Extrapolated to EOS (HII_DIM = 1500, 1.5 cMpc/cell, 2250 Mpc)</em></td></tr>
  <tr>
    <td>Initial conditions</td>
    <td>a=1.72: 3.04 ± 2.21</td>
    <td>a=3: 17 ± 1.83</td>
    <td>affine (overhead + a=3): 2.62 ± 0.262 TB</td>
    <td>a=3: 2.63 ± 0.263 TB</td>
    <td>a=3: 1.57 ± 0.149 TB</td>
    <td>a=3: 1.57 ± 0.157 TB</td>
  </tr>
  <tr>
    <td>One perturbed field</td>
    <td>a=0.152: 0.05 ± 0.0074</td>
    <td>a=3: 1.42 ± 0.832</td>
    <td>affine (overhead + a=3): 0.54 ± 0.054 TB</td>
    <td>a=3: 0.546 ± 0.0547 TB</td>
    <td>a=3: 0.0539 ± 0.00515 TB</td>
    <td>a=3: 0.054 ± 0.0054 TB</td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td>a=1.6: 2.84 ± 2.21</td>
    <td>a=3: 18.1 ± 2.07</td>
    <td>affine (overhead + a=3): 1.37 ± 0.137 TB</td>
    <td>a=3: 1.38 ± 0.138 TB</td>
    <td>a=2.99: 0.675 ± 0.0648 TB</td>
    <td>a=3: 0.686 ± 0.0686 TB</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td>a=3.26: 11 ± 7.78</td>
    <td>a=3: 11.1 ± 1.36</td>
    <td>affine (overhead + a=3): 2.59 ± 0.267 TB</td>
    <td>a=3: 2.65 ± 0.272 TB</td>
    <td>a=3: 0.202 ± 0.0193 TB x 92 = 18.6 ± 1.77 TB</td>
    <td>a=3: 0.203 ± 0.0203 TB x 92 = 18.6 ± 1.86 TB</td>
  </tr>
</tbody></table>


## EOS Fixed-Cubic Runtime Plan

Planning values use fixed `a=3` central estimates at `HII_DIM=1500`, a 1.5 h IC-read allowance per dependent job, and a 13 h IC-write time (measured production elapsed time minus the small-scale a=3 cubic fit's compute-only prediction at the same `HII_DIM`; see `estimate_ic_write_hours`) to infer output-write throughput. Coeval output excludes transient `XraySourceBox`. The table uses the 24 h maximum job walltime; coeval jobs are deliberately limited to 4 outputs for margin. Peak RSS is the per-phase process estimate; full-phase output totals all 92 PFs or coevals as applicable.

| Phase | Work unit | Units/job | Compute/unit [h] | IC read/job [h] | Write/unit [h] | Estimated job walltime [h] | Jobs for full phase | Serial phase walltime [h] | Peak RSS [TB] | Output, full phase [TB] |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial conditions | all ICs | 1 | 29.83 | 0.00 | 12.85 | 42.69 | 1 | 42.7 | 2.41 | 1.42 |
| Perturbed fields | one PF | 12 | 1.42 | 1.50 | 0.44 | 23.84 | 8 | 190.8 | 0.55 | 4.52 |
| Perturbed halo fields | all halo fields | 1 | 18.08 | 1.50 | 5.63 | 25.21 | 1 | 25.2 | 1.38 | 0.62 |
| Coevals | one coeval | 4 | 11.10 | 1.50 | 1.66 | 52.56 | 23 | 1208.9 | 2.65 | 16.95 |
