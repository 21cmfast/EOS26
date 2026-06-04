# EOS26
## Description
All scripts to run the EOS26 simulation with 21cmFASTv4.2.

## How to run
All scripts accept an optional `--test` flag to run a small test box (HII_DIM=200).

### End-to-end test
- `sbatch sbatch_scripts/full_test_job.sh` — runs all three pipeline steps sequentially in test mode.

### Production run (in order)
1. **Initial conditions (ICs):**
   - `sbatch sbatch_scripts/ICs_job.sh [--test]`
   - Writes `EOS26.toml` (full template with embedded node redshifts and random seed) and `EOS26_minimal.toml`, then runs `run_scripts/run_ICs.py`.
2. **Perturbed fields (PFs):**
   - `bash sbatch_scripts/submit_PF_jobs.sh [--test]` — submits one job per PF (indices 0–91) (not used for production).
   - `sbatch sbatch_scripts/N_PF_job.sh <z_idx> [N] [--test]` — runs a batch of N PFs (default N=10) starting from redshift index `z_idx`.
3. **Perturbed halo fields (PHFs):**
   - `sbatch sbatch_scripts/PHFs_job.sh [--test]` — runs `run_scripts/run_PHFs.py`.
4. **Coevals:**
   - `sbatch sbatch_scripts/N_coeval_job.sh [N] [--test]` — runs a batch of N coevals (default N=10) with `run_scripts/run_N_coevals.py`.
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

Extrapolated using $a = 3$ from each test box. EOS-1: HII\_DIM = 1400 (1.5 cMpc/cell, 2100 Mpc). EOS-2: HII\_DIM = 1200 (1.667 cMpc/cell, 2000 Mpc). Storage for PFs and coevals is the total across all 92 node redshifts; coeval storage excludes IonizedBox.

<table><thead>
  <tr>
    <th>EOS26 simulation step</th>
    <th colspan="2">Computation time [hrs]</th>
    <th colspan="2">Memory [TB]</th>
    <th colspan="2">Storage</th>
    <th colspan="2">SUs (96 cores)</th>
  </tr>
  <tr>
    <th></th>
    <th>N=120</th>
    <th>N=240</th>
    <th>N=120</th>
    <th>N=240</th>
    <th>N=120</th>
    <th>N=240</th>
    <th>N=120</th>
    <th>N=240</th>
  </tr>
</thead>
<tbody>
  <tr><td colspan="9"><em>Scaling tests (measured)</em></td></tr>
  <tr>
    <td>Initial conditions</td>
    <td>0.01</td><td>0.04</td>
    <td>0.002</td><td>0.010</td>
    <td>1 Gb</td><td>6 Gb</td>
    <td>0.5</td><td>4.1</td>
  </tr>
  <tr>
    <td>One perturbed field</td>
    <td>&lt;0.01</td><td>&lt;0.01</td>
    <td>0.001</td><td>0.007</td>
    <td>&lt;1 Gb</td><td>&lt;1 Gb</td>
    <td>&lt;0.1</td><td>0.1</td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td>0.03</td><td>0.06</td>
    <td>0.002</td><td>0.010</td>
    <td>&lt;1 Gb</td><td>&lt;1 Gb</td>
    <td>2.5</td><td>6.0</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td>&lt;0.01</td><td>0.03</td>
    <td>0.002</td><td>0.012</td>
    <td>&lt;1 Gb</td><td>1 Gb</td>
    <td>0.3</td><td>2.5</td>
  </tr>
  <tr><td colspan="9"><em>Extrapolated to EOS-1 (HII_DIM = 1400, 1.5 cMpc/cell, 2100 Mpc)</em></td></tr>
  <tr>
    <td>Initial conditions</td>
    <td colspan="2">8.5 – 9.1</td>
    <td colspan="2">2.04 – 2.74</td>
    <td colspan="2">1.16 Tb</td>
    <td colspan="2">813 – 869</td>
  </tr>
  <tr>
    <td>One perturbed field</td>
    <td colspan="2">0.14 – 0.17</td>
    <td colspan="2">1.30 – 1.98</td>
    <td colspan="2">0.043 Tb × 92 = 3.95 Tb</td>
    <td colspan="2">14 – 17</td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td colspan="2">12.5 – 41</td>
    <td colspan="2">2.05 – 2.90</td>
    <td colspan="2">1.31 – 3.92 Tb</td>
    <td colspan="2">1200 – 3978</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td colspan="2">4.9 – 5.2</td>
    <td colspan="2">2.44 – 3.52</td>
    <td colspan="2">0.13 – 0.16 Tb × 92 = 12.3 – 15.1 Tb</td>
    <td colspan="2">469 – 502</td>
  </tr>
  <tr><td colspan="9"><em>Extrapolated to EOS-2 (HII_DIM = 1200, 1.667 cMpc/cell, 2000 Mpc)</em></td></tr>
  <tr>
    <td>Initial conditions</td>
    <td colspan="2">5.3 – 5.7</td>
    <td colspan="2">1.28 – 1.72</td>
    <td colspan="2">0.73 Tb</td>
    <td colspan="2">512 – 547</td>
  </tr>
  <tr>
    <td>One perturbed field</td>
    <td colspan="2">0.09 – 0.11</td>
    <td colspan="2">0.82 – 1.25</td>
    <td colspan="2">0.027 Tb × 92 = 2.49 Tb</td>
    <td colspan="2">9 – 11</td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td colspan="2">7.9 – 26</td>
    <td colspan="2">1.29 – 1.82</td>
    <td colspan="2">0.83 – 2.47 Tb</td>
    <td colspan="2">756 – 2506</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td colspan="2">3.1 – 3.3</td>
    <td colspan="2">1.54 – 2.22</td>
    <td colspan="2">0.08 – 0.10 Tb × 92 = 7.7 – 9.5 Tb</td>
    <td colspan="2">295 – 316</td>
  </tr>
</tbody></table>
