#!/usr/bin/env sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"

make clean
make test
make sanitize
make clean
make all
./scripts/capture_environment.sh results
./build/fde_bench --all results

printf 'Tests and benchmarks completed successfully.\n'
