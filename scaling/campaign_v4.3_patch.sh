#!/bin/bash
# The v4.3 scaling campaign (same configurations as campaign_v4.3.sh) with 21cmFAST
# 4.3.0 + envs/patches/v4.3.0_sfr_allzero.patch (bug_reports/5_v4.3_sfrd_history_reloaded.md).
#
#   bash envs/create_venv_v4.3_patch.sh gadi          # once: build the patched venv
#   bash scaling/campaign_v4.3_patch.sh --dry-run
#   bash scaling/campaign_v4.3_patch.sh --follow
#   python3 scaling/summarize.py --label v4.3_patch
#
# Results: scaling/results/v4.3_patch/HII_DIM_XXXX_NT_YY/ (scaling/results/v4.3/ is
# left alone); simulation caches under $SC_SIM_ROOT/v4.3_patch/.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SC_CAMPAIGN_LABEL=v4.3_patch exec bash "$HERE/campaign_v4.3.sh" "$@"
