#!/bin/sh
# Run every demo, each against a freshly booted AGC.
#
# State carries over between demos (that is the point of a computer), so
# each one gets its own boot to keep the results independent.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)

for demo in t1_inject t2_1202 t3_calc t4_lockout; do
    echo
    echo "################################################################"
    echo "# $demo"
    echo "################################################################"
    pkill yaAGC 2>/dev/null || true
    sleep 2
    # --no-resume: start from truly cold erasable, not the last run's memory.
    rm -f "$HERE/core"
    cd "$HERE"
    "$HERE/build/virtualagc/yaAGC/yaAGC" \
        --core="$HERE/build/virtualagc/Comanche055/MAIN.agc.bin" \
        --port=19697 --no-resume >/dev/null 2>&1 &
    sleep 4
    python3 "$HERE/$demo.py"
done

pkill yaAGC 2>/dev/null || true
echo
echo "All demos complete."
