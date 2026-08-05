#!/usr/bin/env bash
VENV="/scratch/qp00/$USER/EOS26/.venv"

PACKAGE_DIR=$(
    "$VENV/bin/python" - <<'PY'
from pathlib import Path
import py21cmfast

print(Path(py21cmfast.__file__).resolve().parent)
PY
)

find "$PACKAGE_DIR" -type f -name '*.so' -print0 |
while IFS= read -r -d '' library; do
    echo
    echo "=== $library ==="
    ldd "$library" |
        grep -E 'fftw|gomp|omp|gsl' || true
done
