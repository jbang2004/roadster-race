#!/bin/zsh
# R1e shots from the exported car (public/assets/car/car_hi.raw.glb): studio sheets p013/p016/p018, Workbench overlays, reflect h/v for p016, nose zooms, residuals.
#   tools/blender/shots_r1e.sh            (run from the project root, after build_game_car.py has exported)
B=/Applications/Blender.app/Contents/MacOS/Blender; T=tools/blender; R=shots/full_rework/r1e; G=public/assets/car/car_hi.raw.glb; P=../refs/press2; W=$R/work
mkdir -p $R/zoom $W
$B -b --python $T/render_ref_views.py -- --glb $G --out $R --views p013,p016,p018 --wing stow --samples 64 --hide Decals | grep -E "Traceback|Error"
$T/full_sheets.sh $R $R p013,p016,p018
$B -b --python $T/overlay_views.py -- --glb $G --out $R/ov --views p013,p016,p018 --wing stow | grep -E "Traceback|Error"
for m in h v; do d=reflect; [[ $m == v ]] && d=reflect_v
  $B -b --python $T/render_ref_views.py -- --glb $G --out $R/$d --views p016 --wing stow --reflect $m --samples 48 --hide Decals | grep -E "Traceback|Error"; done
$B -b --python $T/mask_views.py -- --glb $G --out $W/masks_final --views p013,p016,p018 --wing stow | grep -E "Traceback|Error"
python3 $T/measure_nose.py $W/masks_final --save $W/report_r1e.json > $R/residuals_r1e.txt
python3 $T/measure_nose.py $W/masks_r1c --r1c --save $W/report_r1c.json > $R/residuals_r1c.txt
ffmpeg -loglevel error -y -f lavfi -i color=c=0x3a3a3c:s=1800x1200 -i $R/ov/p013_wb.png -filter_complex "[0][1]overlay=0:0:format=auto" -frames:v 1 $W/p013_wb_bg.png
$T/zoom_pair.sh $P/tesla-roadster-2026-013-1.jpg $W/p013_wb_bg.png 640:740:80:230 1.5 $R/zoom/nose_plan_p013.jpg h
python3 $T/outline_overlay.py p013 80,230,720,960 2 $R/zoom/nose_plan_p013_outline.jpg $W/masks_r1c:3060ff $W/masks_final:ff2020
python3 $T/outline_overlay.py p018 150,520,450,720 4 $R/zoom/nose_p018_outline.jpg $W/masks_r1c:3060ff $W/masks_final:ff2020
$T/zoom_pair.sh $P/telsa-roadster-2026-016.jpg $R/p016.png 760:520:180:400 1.4 $R/zoom/nose_p016.jpg v
$T/zoom_pair.sh $P/tesla-roadster-2026-018.jpg $R/p018.png 560:300:150:500 1.8 $R/zoom/nose_p018.jpg v
cat $R/residuals_r1e.txt
