#!/bin/zsh
# photo | Blender studio render sheets for the whole-car press views (render_ref_views.py --views p016,p017,p018,p013,p014,p005,p003).
#   tools/blender/full_sheets.sh <dir with p016.png ...> <out dir> [views]
# top = press photo, bottom = our render, same camera, both 1800x1200 -> scaled to 1200x800.
studio=$1; out=$2; views=${3:-p016,p017,p018,p013,p014,p005,p003}; mkdir -p $out
P=${0:A:h}/../../../refs/press2
typeset -A PH; PH=(p016 telsa-roadster-2026-016.jpg p017 tesla-roadster-2026-017.jpg p018 tesla-roadster-2026-018.jpg p013 tesla-roadster-2026-013-1.jpg p014 tesla-roadster-2026-014.jpg p005 tesla-roadster-2026-005.jpg p003 tesla-roadster-2026-003.jpg)
for v in ${(s:,:)views}; do
  [[ -f $studio/$v.png ]] || continue
  ffmpeg -loglevel error -y -i $P/$PH[$v] -i $studio/$v.png -filter_complex "[0]scale=1200:800[a];[1]scale=1200:800[b];[a][b]vstack" $out/sheet_$v.jpg
done
