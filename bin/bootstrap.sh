#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$(realpath "$0")")/.."
make setup
make render