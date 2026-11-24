#!/bin/bash
#PBS -N Mturn_bug
#PBS -q normal
#PBS -l ncpus=16
#PBS -l mem=64gb
#PBS -l walltime=3:00:00
#PBS -l storage=scratch/qp00+gdata/qp00

# One reionization history for the Mturn_bug comparison: EOS26_earlyEoR.toml in a
# 300 cMpc box (HII_DIM = 200 at 1.5 cMpc, N_THREADS = 16, seed 42) with one 21cmFAST
# version, then the plot is remade from every result present (Mturn_bug/Mturn_bug_xHI.png).
# Submit from the EOS26 root:
#   qsub -v VERSION=v4.2 Mturn_bug/run_job.sh       # before the fix
#   qsub -v VERSION=v4.3 Mturn_bug/run_job.sh       # 21cmFAST 4.3.1 (after the fix)
#   qsub -v VERSION=v4.2fix Mturn_bug/run_job.sh    # optional: 4.2 with only the fix
#   qsub -v VERSION=v4.2,HII_DIM=86 Mturn_bug/run_job.sh   # another box size
# The v4.2 / v4.2fix venvs come from Mturn_bug/make_venvs.sh.
# Nothing is cached; the HII_DIM = 200 EOS26 test needed 6 GB and 45 min on 16 cpus.
# Output: Mturn_bug/results/<VERSION>_HIIDIM<HII_DIM>_NT16.json, logs/Mturn_bug/<VERSION>_<jobid>.log

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

VERSION="${VERSION:?submit with qsub -v VERSION=v4.2|v4.2fix|v4.3}"
HII_DIM="${HII_DIM:-200}"
JID="${PBS_JOBID%%.*}"
source "$ROOT/Mturn_bug/env.sh" "$VERSION"
set -euo pipefail

export OMP_NUM_THREADS=16
export OMP_DYNAMIC=FALSE
unset OMP_PROC_BIND OMP_PLACES

mkdir -p logs/Mturn_bug
python Mturn_bug/run_history.py --label "$VERSION" --hii-dim "$HII_DIM" 2>&1 | tee "logs/Mturn_bug/${VERSION}_HIIDIM${HII_DIM}_${JID}.log"
python Mturn_bug/plot_history.py --hii-dim "$HII_DIM" 2>&1 | tee -a "logs/Mturn_bug/${VERSION}_HIIDIM${HII_DIM}_${JID}.log"
