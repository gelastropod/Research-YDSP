#!/usr/bin/env sh
# Run every scheme on a drive: encrypt then decrypt the same region, and check the
# region's SHA-256 is unchanged after each scheme. Run from fde-drive-0/.
# WARNING: writes to the device in place. Use a scratch drive.
set -eu
DEV=${1:-/dev/sda}
OFF=${2:-0}              # bytes; keep 4096-aligned for direct I/O
CNT=${3:-1073741824}     # bytes; 1 GiB as in RESULTS.md (0 = whole drive)
OUT=${4:-results}
mkdir -p "$OUT"

region_hash() {
  if [ "$CNT" -eq 0 ]; then
    sudo cat "$DEV" | sha256sum | cut -d' ' -f1
  else
    sudo dd if="$DEV" bs=1M iflag=skip_bytes,count_bytes skip="$OFF" count="$CNT" status=none \
      | sha256sum | cut -d' ' -f1
  fi
}

SCHEMES=$(sh scripts/run_drive_schemes.sh --help 2>&1 | sed -n 's/.*available: //p')
echo "Schemes: $SCHEMES"
BEFORE=$(region_hash); echo "Initial SHA-256: $BEFORE"

for s in $SCHEMES; do
  echo "===== $s ====="
  sudo build/fde_test_drive --scheme "$s" encrypt "$DEV" "$OFF" "$CNT" "$OUT/drive_encrypt_$s.csv" direct
  sudo build/fde_test_drive --scheme "$s" decrypt "$DEV" "$OFF" "$CNT" "$OUT/drive_decrypt_$s.csv" direct
  AFTER=$(region_hash)
  if [ "$AFTER" != "$BEFORE" ]; then
    echo "FAIL: $s did not restore the drive (hash $AFTER). Stopping." >&2
    exit 1
  fi
  echo "OK: $s round-trips"
done
echo "All schemes round-tripped on $DEV."
