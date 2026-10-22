#!/usr/bin/env bash
# Linux / cloud setup: Blender 5.2 (headless), Node deps, Playwright's Chromium, numpy.
# Run from anywhere:  bash cloud-setup.sh      then  export BLENDER="$HOME/blender/blender"
# Needs network access to download.blender.org, registry.npmjs.org, the Playwright CDN and PyPI.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)
BV=5.2.0
BDIR=${BLENDER_DIR:-$HOME/blender}

SUDO=""; if [ "$(id -u)" != 0 ] && sudo -n true 2>/dev/null; then SUDO=sudo; fi

# Blender's shared libraries on a bare container (needed even with -b)
if command -v apt-get >/dev/null; then
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq xz-utils libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libgl1 libegl1 >/dev/null
fi

if [ ! -x "$BDIR/blender" ]; then
  mkdir -p "$BDIR"
  curl -fsSL "https://download.blender.org/release/Blender${BV%.*}/blender-$BV-linux-x64.tar.xz" | tar -xJ -C "$BDIR" --strip-components=1
fi

cd "$ROOT/neon_loop"
npm ci
npx playwright-core install --with-deps chromium
python3 -m pip install --quiet numpy 2>/dev/null || python3 -m pip install --quiet --break-system-packages numpy

"$BDIR/blender" --version | head -1
echo "export BLENDER=\"$BDIR/blender\""
