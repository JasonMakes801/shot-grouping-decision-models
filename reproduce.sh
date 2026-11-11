#!/usr/bin/env bash
# Reproduce the numbers in the write-up.
#   ./reproduce.sh          score the saved answers against the hand labels (no API key, no cost)
#   ./reproduce.sh --run    ask Jev again through OpenRouter first (needs OPENROUTER_API_KEY, about $0.08)
#   ./reproduce.sh --clef   also run Cloudflare's Clef through OpenRouter (about $1, about 7 minutes)
set -euo pipefail
cd "$(dirname "$0")"
export DATASET=tos
if [[ "${1:-}" == "--run" || "${1:-}" == "--clef" ]]; then
  python3 run_pairs.py scene2                      # pass 1: every pair, same scene?
  python3 group.py scene2 0.6                      # cluster into scenes
  python3 run_pairs.py grade --within scene2       # pass 2: pairs inside each scene, same grade?
fi
if [[ "${1:-}" == "--clef" ]]; then
  WORKERS=12 python3 clef_pairs.py scene2
  python3 group.py clef_scene2 0.6
  WORKERS=12 python3 clef_pairs.py grade --within clef_scene2
fi
echo "== Jev, lighting wording (the one in the write-up)"
python3 score_labels.py data/tos/labels/tos_labels.json | grep -v wrote
echo "== Jev, first wording (story time), scenes only"
python3 score_labels.py data/tos/labels/tos_labels.json --scene-kind scene | grep "^scene\|shots in" | sed 's/ | in the right grade group.*//'
echo "== Clef"
python3 score_labels.py data/tos/labels/tos_labels.json --prefix clef_ | grep -v wrote
