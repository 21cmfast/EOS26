#!/usr/bin/env bash
# Run local 21cmFAST scaling measurements, then fit their scaling relations.
# Usage: bash scaling/scaling_job.sh [HII_DIM ...]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -eq 0 ]]; then
    dimensions=(200 300)
else
    dimensions=("$@")
fi

uv sync --frozen
for hii_dim in "${dimensions[@]}"; do
    echo "=== Scaling measurement: HII_DIM=${hii_dim} ==="
    uv run --no-sync scaling/run_scaling.py --hii-dim "$hii_dim"
done

uv run --no-sync scaling/run_scalingrelation.py
echo "Reports: scaling/reports/"
