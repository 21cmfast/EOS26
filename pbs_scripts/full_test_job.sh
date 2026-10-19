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
cd "$PBS_O_WORKDIR"

set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"
pwd

#ROOT="/scratch/qp00/$USER/EOS26"
# 21cmFAST environment: venv + modules (envs/use.sh; venv paths in scaling/config.sh).
# Default v4.3; submit with  qsub -v EOS26_VERSION=v4.2 ...  to use the old one.
EOS26_VERSION="${EOS26_VERSION:-v4.3}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail

module list

JID="${PBS_JOBID%%.*}"
#LOG_OUT="logs/full_test_${JID}.out"
#LOG_ERR="logs/full_test_${JID}.err"
#exec >"$LOG_OUT" 2>"$LOG_ERR"

echo "=========================================="
echo " Full test simulation (job ${JID})"
echo "=========================================="

export OMP_NUM_THREADS=16
export OMP_DYNAMIC=FALSE

unset OMP_PROC_BIND
unset OMP_PLACES

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
