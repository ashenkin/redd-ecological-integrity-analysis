#!/usr/bin/env bash
# Run the full pipeline: fetch metadata → load sensitivity data → plot.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Step 1: Fetch project metadata from registries ==="
python3 "$SCRIPT_DIR/fetch_project_metadata.py"

echo ""
echo "=== Step 2: Load sensitivity data from Zenodo ==="
python3 "$SCRIPT_DIR/load_sensitivity_data.py"

echo ""
echo "=== Step 3: Plot outcomes over time (rv_q proxy) ==="
python3 "$SCRIPT_DIR/plot_outcomes_over_time.py"

echo ""
echo "Done. Results in results/"
echo ""
echo "To plot with real effect sizes once you have source data:"
echo "  python3 plot_outcomes_over_time.py --use-effect-sizes"
