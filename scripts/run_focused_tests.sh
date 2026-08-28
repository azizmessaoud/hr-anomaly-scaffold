#!/usr/bin/env bash
set -euo pipefail

python -m pytest -q tests/ingestion tests/pipeline tests/anomalies tests/api tests/test_health.py -m 'not integration'
