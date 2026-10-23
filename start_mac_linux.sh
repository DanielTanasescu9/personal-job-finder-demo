#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
: "${JOB_FINDER_PORT:=7860}"
export JOB_FINDER_PORT
exec python3 main.py
