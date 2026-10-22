#!/bin/zsh
# photo | render, same crop box, scaled: tools/blender/zoom_pair.sh <photo> <render.png> <w:h:x:y> <scale> <out.jpg> [v|h]   (h = side by side (default), v = stacked)
photo=$1; render=$2; box=$3; sc=$4; out=$5; mode=${6:-h}
w=${box%%:*}; 
if [[ $mode == h ]]; then st=hstack; else st=vstack; fi
ffmpeg -loglevel error -y -i $photo -i $render -filter_complex "[0]crop=$box,scale=iw*$sc:-1[a];[1]crop=$box,scale=iw*$sc:-1[b];[a][b]$st" -frames:v 1 -q:v 2 $out
