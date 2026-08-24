#!/bin/bash
#!/bin/bash
#PBS -N EOS26_ICs
#PBS -q megamem
#PBS -l ncpus=1
#PBS -l mem=16gb
#PBS -l walltime=1:00:00
#PBS -l storage=scratch/qp00+gdata/qp00

# Run the ICs for the production-size EOS26 simulation with HII_DIM=1400.
# Usage: qsub pbs_scripts/ICs_job.sh

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"

set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"
pwd

source /scratch/qp00/db9528/venvs/EOS26-intel/bin/activate
set -euo pipefail

module purge
module load intel-compiler/2021.8.0
module load gsl/2.7.1
module load fftw3/3.3.10

module list

uv run --no-sync --active --project "$ROOT" postprocess/plot_ics.py
uv run --no-sync --active --project "$ROOT" postprocess/plot_pf.py
wait


