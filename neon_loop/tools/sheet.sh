#!/bin/zsh
# Contact sheet (2×2) with ffmpeg: tools/sheet.sh out.png a.png b.png c.png d.png   (cells 800×450, order: TL TR BL BR)
out=$1; shift
ff=(); i=0; lab=""
for f in "$@"; do ff+=(-i "$f"); n=${f:t:r}; lab+="[$i:v]scale=800:450[v$i];"; i=$((i+1)); done
ffmpeg -loglevel error -y "${ff[@]}" -filter_complex "${lab}[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0" "$out"
