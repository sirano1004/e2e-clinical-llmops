#!/bin/bash

# ==============================================================================
# End-to-End Medical Data Pipeline Orchestrator
# Location: /data_pipeline/run_pipeline.sh
# ==============================================================================

set -e

# 1. Get the directory where THIS script is located (e.g., .../project/data_pipeline)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 2. Get the Project Root by going one level up (e.g., .../project)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📂 Script Location: $SCRIPT_DIR"
echo "🏠 Project Root:    $PROJECT_ROOT"

# 3. Set PYTHONPATH to Project Root
# This ensures python can find 'data_pipeline' module no matter where you run this script from.
export PYTHONPATH=$PROJECT_ROOT

echo ""
echo "🚀 Starting Pipeline..."

# ------------------------------------------------------------------------------
# Step 1: Parsing
# ------------------------------------------------------------------------------
echo "👉 [Step 1] Ingest & Parsing"
python -m data_pipeline.parsing

# ------------------------------------------------------------------------------
# Step 2: Deduplication
# ------------------------------------------------------------------------------
echo "👉 [Step 2] Deduplication"
python -m data_pipeline.dedup.pipeline

# ------------------------------------------------------------------------------
# Step 3: Quality Assurance
# ------------------------------------------------------------------------------
echo "👉 [Step 3] QA & Filtering"
python -m data_pipeline.qa.quality_check

# ------------------------------------------------------------------------------
# Step 4: Formatting
# ------------------------------------------------------------------------------
echo "👉 [Step 4] Formatting SFT/DPO"
python -m data_pipeline.formatting.build_dataset

echo ""
echo "🎉 Pipeline Finished Successfully!"