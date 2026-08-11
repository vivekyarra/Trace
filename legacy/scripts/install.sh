#!/usr/bin/env bash
# Install dependencies using public PyPI only (no Artifactory).
set -e
cd "$(dirname "$0")/.."
pip install -r requirements.txt -i https://pypi.org/simple
