#!/bin/zsh
# Before/after sheet: one row per shot name, before on the left, after on the right (cells 800×450).
#   tools/compare.sh out.jpg beforeDir afterDir name1 name2 ...
out=$1; b=$2; a=$3; shift 3
ins=(); f=""; i=0; rows=""
for n in "$@"; do
  ins+=(-i "$b/$n.png" -i "$a/$n.png")
  f+="[$((i*2)):v]scale=800:450[b$i];[$((i*2+1)):v]scale=800:450[a$i];[b$i][a$i]hstack=inputs=2[r$i];"
  rows+="[r$i]"; i=$((i+1))
done
ffmpeg -loglevel error -y "${ins[@]}" -filter_complex "${f}${rows}vstack=inputs=$i" -q:v 3 "$out"
