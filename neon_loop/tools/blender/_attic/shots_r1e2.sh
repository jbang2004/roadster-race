#!/bin/zsh
# R1e2 shots from the exported car (public/assets/car/car_hi.raw.glb): studio sheets p013/p016/p018, Workbench overlays, reflect h/v for p016, nose zooms, U / L unchanged-check (old cyan dashed, new red),
# residual tables R1e2 vs R1e, plan curvature report of L / U, aft / forward proofs.          tools/blender/shots_r1e2.sh   (from the project root, after build_game_car.py has exported)
B=/Applications/Blender.app/Contents/MacOS/Blender; T=tools/blender; R=shots/full_rework/r1e2; G=public/assets/car/car_hi.raw.glb; P=../refs/press2; W=$R/work; OLD=../backup/r1e2_pre
mkdir -p $R/zoom $R/ov $W
$B -b --python $T/render_ref_views.py -- --glb $G --out $R --views p013,p016,p018 --wing stow --samples 64 --hide Decals | grep -E "Traceback|Error"
$T/full_sheets.sh $R $R p013,p016,p018
$B -b --python $T/overlay_views.py -- --glb $G --out $R/ov --views p013,p016,p018 --wing stow | grep -E "Traceback|Error"
for m in h v; do d=reflect; [[ $m == v ]] && d=reflect_v
  $B -b --python $T/render_ref_views.py -- --glb $G --out $R/$d --views p016 --wing stow --reflect $m --samples 48 --hide Decals | grep -E "Traceback|Error"; done
$B -b --python $T/mask_views.py -- --glb $G --out $W/masks_final --views p013,p016,p018 --wing stow | grep -E "Traceback|Error"
python3 $T/measure_nose.py $W/masks_final --save $W/report_r1e2.json > $R/residuals_r1e2.txt
( echo; echo "---- R1e (previous round, for comparison; shots/full_rework/r1e/residuals_r1e.txt) ----"; cat shots/full_rework/r1e/residuals_r1e.txt ) >> $R/residuals_r1e2.txt
ffmpeg -loglevel error -y -f lavfi -i color=c=0x3a3a3c:s=1800x1200 -i $R/ov/p013_wb.png -filter_complex "[0][1]overlay=0:0:format=auto" -frames:v 1 $W/p013_wb_bg.png
$T/zoom_pair.sh $P/tesla-roadster-2026-013-1.jpg $W/p013_wb_bg.png 640:740:80:230 1.5 $R/zoom/nose_plan_p013.jpg h
python3 $T/outline_overlay.py p013 80,230,720,960 2 $R/zoom/nose_plan_p013_outline.jpg shots/full_rework/r1e/work/masks_final:3060ff $W/masks_final:ff2020
python3 $T/outline_overlay.py p018 150,520,450,720 4 $R/zoom/nose_p018_outline.jpg shots/full_rework/r1e/work/masks_final:3060ff $W/masks_final:ff2020
$T/zoom_pair.sh $P/telsa-roadster-2026-016.jpg $R/p016.png 760:520:180:400 1.4 $R/zoom/nose_p016.jpg v
$T/zoom_pair.sh $P/tesla-roadster-2026-018.jpg $R/p018.png 560:300:150:500 1.8 $R/zoom/nose_p018.jpg v
$T/zoom_pair.sh $P/tesla-roadster-2026-013-1.jpg $R/p013.png 640:740:80:230 1.5 $R/zoom/nose_plan_p013_render.jpg h
python3 $T/dump_lines.py $OLD $W/lines_old.json > /dev/null; python3 $T/dump_lines.py $T $W/lines_new.json > /dev/null
python3 $T/nose_overlay.py p016 $P/telsa-roadster-2026-016.jpg $R/p016.png $W/lines_old.json $W/lines_new.json 0,380,1000,900 1.5 $R/zoom/lines_p016.png
python3 $T/nose_overlay.py p018 $P/tesla-roadster-2026-018.jpg $R/p018.png $W/lines_old.json $W/lines_new.json 100,480,700,760 2.5 $R/zoom/lines_p018.png
python3 $T/nose_overlay.py p013 $P/tesla-roadster-2026-013-1.jpg $R/p013.png $W/lines_old.json $W/lines_new.json 60,200,760,960 1.5 $R/zoom/lines_p013.png both
python3 $T/plan_report.py $R/plan_curvature.png > $R/plan_curvature.txt
cat $R/residuals_r1e2.txt
