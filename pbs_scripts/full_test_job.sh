#!/bin/bash
#PBS -N EOS26_full_test
#PBS -q normal
#PBS -l ncpus=16
#PBS -l mem=22gb
#PBS -l walltime=5:00:00
#PBS -l storage=scratch/qp00+gdata/qp00

# Run the complete EOS pipeline end-to-end in test mode (HII_DIM=200).
# Usage: qsub pbs_scripts/full_test_job.sh

export PATH="$HOME/.local/bin:$PATH"
export OMP_PROC_BIND="TRUE"
cd "$PBS_O_WORKDIR"

set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"
pwd

#ROOT="/scratch/qp00/$USER/EOS26"
source /scratch/qp00/db9528/venvs/EOS26-intel/bin/activate
set -euo pipefail

module purge
module load intel-compiler/2021.8.0
module load gsl/2.7.1
module load fftw3/3.3.10

module list

JID="${PBS_JOBID%%.*}"
#LOG_OUT="logs/full_test_${JID}.out"
#LOG_ERR="logs/full_test_${JID}.err"
#exec >"$LOG_OUT" 2>"$LOG_ERR"

echo "=========================================="
echo " Full test simulation (job ${JID})"
echo "=========================================="

echo ""
echo "=== Writing test parameter template ==="
rm -f "test_template.toml"
uv run --no-sync --active --project "$ROOT" 21cmfast template create \
    --param-file EOS26.toml \
    --mode minimal \
    --hii-dim 200 \
    --nodez.min 5.0 \
    --nodez.step 1.02 \
    --random-seed 42 \
    --out "test_template.toml"

echo ""
echo "=== Step 1/4: ICs ==="
uv run --no-sync --active --project "$ROOT" run_scripts/run_ICs.py \
    --log-file "logs/full_test_${JID}_ICs.log" \
    --test

echo ""
echo "=== Step 2/4: PFs ==="
uv run --no-sync --active --project "$ROOT" run_scripts/run_N_PFs.py \
    --z_idx_start 0 \
    --N "30" \
    --log-file "logs/full_test_${JID}_PFs.log" \
    --test

uv run --no-sync --active --project "$ROOT" run_scripts/run_N_PFs.py \
    --z_idx_start 30 \
    --N "30" \
    --log-file "logs/full_test_${JID}_PFs.log" \
    --test
uv run --no-sync --active --project "$ROOT" run_scripts/run_N_PFs.py \
    --z_idx_start 60 \
    --N "-1" \
    --log-file "logs/full_test_${JID}_PFs.log" \
    --test

echo ""
echo "=== Step 3/4: PHFs ==="
uv run --no-sync --active --project "$ROOT" run_scripts/run_PHFs.py \
    --log-file "logs/full_test_${JID}_PHFs.log" \
    --test

echo ""
echo "=== Step 4/4: Coevals ==="
uv run --no-sync --active --project "$ROOT" run_scripts/run_N_coevals.py \
    --log-file "logs/full_test_${JID}_coevals.log" \
    --N "50" \
    --test

uv run --no-sync --active --project "$ROOT" run_scripts/run_N_coevals.py \
    --log-file "logs/full_test_${JID}_coevals.log" \
    --N "-1" \
    --test

echo ""
echo "=== Full test simulation complete ==="
echo ""
echo "=== Postprocessing: Lightcone ==="
uv run --no-sync --active --project "$ROOT" postprocess/make_lightcone.py \
    --log-file "logs/full_test_${JID}_lightcone.log" \
    --test

uv run --no-sync --active --project "$ROOT" postprocess/plot_lightcone.py \
    --log-file "logs/full_test_${JID}_lightcone.log" \
    --test
