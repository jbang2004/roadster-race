#!/bin/zsh
# photo | Blender studio render side-by-side sheets for the three rear viewpoints.
#   tools/blender/rear_sheets.sh <dir with r81.png thrust.png high.png> <out dir>
# left = press photo, right = our render (both scaled to 800 px high; the r81 pair is cropped to the car).
studio=$1; out=$2; mkdir -p $out
P=${0:A:h}/../../../refs/press
ffmpeg -loglevel error -y -i $P/r81.png -i $studio/r81.png -filter_complex "[0]crop=1000:560:460:600,scale=-2:800[a];[1]crop=iw*0.52:ih*0.425:iw*0.24:ih*0.455,scale=-2:800[b];[a][b]hstack" $out/sheet_r81_rear.jpg
ffmpeg -loglevel error -y -i $P/2026-Tesla-Roadster-rear-thrusters.jpg -i $studio/thrust.png -filter_complex "[0]scale=-2:800[a];[1]scale=-2:800[b];[a][b]hstack" $out/sheet_thrusters_lowquarter.jpg
ffmpeg -loglevel error -y -i $P/2026-Tesla-Roadster-official-02.jpg -i $studio/high.png -filter_complex "[0]scale=-2:800[a];[1]scale=-2:800[b];[a][b]hstack" $out/sheet_official02_high.jpg
