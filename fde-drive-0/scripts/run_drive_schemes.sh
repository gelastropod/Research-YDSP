#!/usr/bin/env sh
# Run the drive encryption/decryption test for one or more schemes and write a
# per-scheme throughput CSV per run (same format as drive_throughput.csv).
#
# Usage:
#   scripts/run_drive_schemes.sh <encrypt|decrypt> <device> [offset_bytes] [count_bytes] [options]
#
# Options:
#   -s, --schemes <list>    Space- or comma-separated scheme names, or 'all'
#                           (default: all)
#   -o, --results-dir <dir> Directory for per-scheme CSV output (default: results)
#       --direct            Pass O_DIRECT batched I/O through to fde_test_drive
#       --bin <path>        fde_test_drive binary (default: build/fde_test_drive)
#
# Example:
#   scripts/run_drive_schemes.sh encrypt /dev/sda 0 0 --schemes "ecb xts" --direct
#   scripts/run_drive_schemes.sh encrypt /dev/sda --schemes all --direct
set -u

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"

HMAC_SCHEMES=$(sed -n 's/^[[:space:]]*X([^,]*,[[:space:]]*"\([^"]*\)".*/\1/p' include/fde.h | tr '\n' ' ')
ALL_SCHEMES="ecb xts ctr-aes ctr-blake3 cbc-aes cbc-blake3 xex-sha3 xex-blake2b xex-blake3 xex-siphash xex-kmac xex-blake2s $HMAC_SCHEMES xex-cmac xex-ghash"

bin="build/fde_test_drive"
results_dir="results"
schemes="all"
direct=0
positionals=""

usage() {
	cat >&2 <<EOF
Usage: $0 <encrypt|decrypt> <device> [offset_bytes] [count_bytes] [options]
  -s, --schemes <list>     scheme names or 'all' (default: all)
                           available: $ALL_SCHEMES
  -o, --results-dir <dir>  CSV output directory (default: results)
      --direct             use O_DIRECT batched I/O
      --bin <path>         fde_test_drive binary (default: build/fde_test_drive)
EOF
}

while [ $# -gt 0 ]; do
	case "$1" in
		-s|--schemes)       schemes="${2:?missing value for $1}"; shift 2 ;;
		--schemes=*)        schemes="${1#*=}"; shift ;;
		-o|--results-dir)   results_dir="${2:?missing value for $1}"; shift 2 ;;
		--results-dir=*)    results_dir="${1#*=}"; shift ;;
		--bin)              bin="${2:?missing value for $1}"; shift 2 ;;
		--bin=*)            bin="${1#*=}"; shift ;;
		--direct)           direct=1; shift ;;
		-h|--help)          usage; exit 0 ;;
		--)                 shift; while [ $# -gt 0 ]; do positionals="$positionals $1"; shift; done ;;
		-*)                 printf 'Unknown option: %s\n' "$1" >&2; usage; exit 1 ;;
		*)                  positionals="$positionals $1"; shift ;;
	esac
done

# shellcheck disable=SC2086
set -- $positionals
mode="${1:-}"
device="${2:-}"
offset="${3:-0}"
count="${4:-0}"

if [ "$mode" != "encrypt" ] && [ "$mode" != "decrypt" ]; then
	printf 'First argument must be encrypt or decrypt (got: %s)\n' "${mode:-<none>}" >&2
	usage
	exit 1
fi
if [ -z "$device" ]; then
	printf 'Missing device argument\n' >&2
	usage
	exit 1
fi
if [ ! -x "$bin" ]; then
	printf 'Binary %s not found or not executable; build it with: make test-drive\n' "$bin" >&2
	exit 1
fi

if [ "$schemes" = "all" ]; then
	schemes="$ALL_SCHEMES"
fi
schemes=$(printf '%s' "$schemes" | tr ',' ' ')

bad=0
for s in $schemes; do
	case " $ALL_SCHEMES " in
		*" $s "*) ;;
		*) printf 'Unknown scheme: %s (available: %s)\n' "$s" "$ALL_SCHEMES" >&2; bad=1 ;;
	esac
done
[ "$bad" -eq 0 ] || exit 1
[ -n "$schemes" ] || { printf 'No schemes selected\n' >&2; exit 1; }

mkdir -p "$results_dir"

if [ "$direct" -eq 1 ]; then direct_arg="direct"; else direct_arg=""; fi

succeeded=0
failed=0
for s in $schemes; do
	csv="$results_dir/drive_${mode}_${s}.csv"
	printf '\n===== Scheme: %s -> %s =====\n' "$s" "$csv"
	# shellcheck disable=SC2086
	if "$bin" --scheme "$s" "$mode" "$device" "$offset" "$count" "$csv" $direct_arg; then
		succeeded=$((succeeded + 1))
	else
		failed=$((failed + 1))
		printf 'Scheme %s failed; continuing with remaining schemes\n' "$s" >&2
	fi
done

printf '\nDone: %d succeeded, %d failed. CSVs in %s\n' "$succeeded" "$failed" "$results_dir"
[ "$failed" -eq 0 ]
