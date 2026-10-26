#!/bin/sh
# zoom.sh <view> <x> <y> <w> <h> <out.jpg> <renderdir> [scale] : photo crop | render crop side by side (full-res pixel
# coords; <renderdir>/<view>.png is a render_ref_views.py image of that view).  Run from anywhere inside the repo.
v=$1; x=$2; y=$3; w=$4; h=$5; out=$6; rd=$7; sc=${8:-1}
case $v in
  p016) ph=press2/telsa-roadster-2026-016.jpg ;;  p017) ph=press2/tesla-roadster-2026-017.jpg ;;
  p018) ph=press2/tesla-roadster-2026-018.jpg ;;  p013) ph=press2/tesla-roadster-2026-013-1.jpg ;;
  p014) ph=press2/tesla-roadster-2026-014.jpg ;;  p005) ph=press2/tesla-roadster-2026-005.jpg ;;
  p003) ph=press2/tesla-roadster-2026-003.jpg ;;  p011) ph=press2/tesla-roadster-2026-011.jpg ;;
  p001) ph=press2/tesla-roadster-2026-001.jpg ;;  p002) ph=press2/tesla-roadster-2026-002.jpg ;;
  p004) ph=press2/tesla-roadster-2026-004.jpg ;;  p012) ph=press2/tesla-roadster-2026-012.jpg ;;
  r81) ph=press/r81.png ;;  thrust) ph=press/2026-Tesla-Roadster-rear-thrusters.jpg ;;
  high) ph=press/2026-Tesla-Roadster-official-02.jpg ;;
  *) echo "zoom.sh: unknown view $v" >&2; exit 2 ;;
esac
ffmpeg -loglevel error -y -i "$(git rev-parse --show-toplevel)/refs/$ph" -i "$rd/$v.png" -filter_complex \
  "[0]crop=$w:$h:$x:$y,scale=iw*$sc:-2[a];[1]crop=$w:$h:$x:$y,scale=iw*$sc:-2[b];[a][b]hstack" -frames:v 1 -q:v 2 "$out"
