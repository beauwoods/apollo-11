#!/bin/sh
# Build the Virtual AGC toolchain and assemble the Comanche055 rope.
#
# Requires: gcc, make, git.  Everything is fetched and built into ./build,
# which is gitignored.  Nothing in this repo is modified.
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD="$HERE/build"
mkdir -p "$BUILD"

if [ ! -d "$BUILD/virtualagc" ]; then
    echo "==> cloning Virtual AGC"
    git clone --depth 1 https://github.com/virtualagc/virtualagc "$BUILD/virtualagc"
fi

cd "$BUILD/virtualagc"

# The Makefiles use lowercase ${cc} for the C compiler and ${CC} for C++.
echo "==> building yaYUL (assembler)"
make -C yaYUL cc=gcc CC=g++ >/dev/null

echo "==> building yaAGC (emulator)"
make -C yaAGC cc=gcc CC=g++ NOGUI=yes >/dev/null

echo "==> assembling Comanche055"
cd Comanche055
../yaYUL/yaYUL MAIN.agc > "$BUILD/listing.txt" 2>&1
ls -l MAIN.agc.bin

echo
echo "Done.  Start the emulator with:"
echo "  $HERE/run_agc.sh"
echo "then run a demo, e.g.:"
echo "  python3 $HERE/t2_1202.py"
