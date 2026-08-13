#!/bin/sh
# Start the emulated Apollo Guidance Computer running the Comanche055 rope.
# Listens on port 19697 for peripherals (DSKY, uplink).
HERE=$(cd "$(dirname "$0")" && pwd)
BUILD="$HERE/build/virtualagc"

pkill yaAGC 2>/dev/null || true
sleep 1

# --no-resume is essential.  By default yaAGC restores erasable memory from a
# "core" resume file written every 10s, so without it each run would inherit
# the previous run's memory and every before/after comparison would be a lie.
rm -f "$HERE/core"
cd "$HERE"
"$BUILD/yaAGC/yaAGC" --core="$BUILD/Comanche055/MAIN.agc.bin" --port=19697 --no-resume "$@"
