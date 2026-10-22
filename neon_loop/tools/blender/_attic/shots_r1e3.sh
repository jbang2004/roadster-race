#!/bin/zsh
# R1e3 hand-back shots from the exported car (public/assets/car/car_hi.raw.glb, made by loop_nose.sh / build_game_car.py --only hi --raw): studio sheets p013 / p016 / p018 (Cycles, once),
# flat-colour masks, residual tables R1e3 vs R1e2, p013 camera table, outline zooms (p013 nose, p016 far corner, p018 nose), U / L unchanged-check (R1e2 cyan dashed, R1e3 red), plan curvature report, lock and aft proofs.
#   tools/blender/shots_r1e3.sh      (from the project root)
B=/Applications/Blender.app/Contents/MacOS/Blender; T=tools/blender; R=shots/full_rework/r1e3; G=public/assets/car/car_hi.raw.glb; P=../refs/press2; W=$R/work; R2=shots/full_rework/r1e2
mkdir -p $R/zoom $W
export SHELL_UNLOCK=shoulder,wall,wall_black
$B -b --python $T/render_ref_views.py -- --glb $G --out $R --views p013,p016,p018 --wing stow --samples 64 --hide Decals | grep -E "Traceback|Error"
$T/full_sheets.sh $R $R p013,p016,p018
$B -b --python $T/mask_views.py -- --glb $G --out $W/masks_final --views p013,p016,p018 --wing stow | grep -E "Traceback|Error"
# residual table: R1e3, then R1e2 as delivered (old p013 camera) and R1e2 judged with the new p013 camera (p013 rows only: p016 / p018 rows are the same)
( echo "==== R1e3 (this round; p013 camera re-matched; N = nose corner, see design2.NOSE_XN) ===="; python3 $T/measure_nose.py $W/masks_final --detail --save $W/report_r1e3.json | grep -v series
  echo; echo "==== R1e2 as delivered (old p013 camera; the p016 far-corner row is the new metric on the R1e2 export) ===="; python3 $T/measure_nose.py $W/masks_r1e2 | grep -v "light-bar\|bar, centre"
  grep -E "light-bar|bar, centre" $R2/residuals_r1e2.txt | head -2
  echo; echo "==== R1e2 export judged with the NEW p013 camera (p013 rows) ===="; python3 $T/measure_nose.py $W/masks_r1e2_newcam | grep -E "p013|shape" ) > $R/residuals_r1e3.txt
python3 $T/outline_overlay.py p013 80,230,720,960 2 $R/zoom/nose_plan_p013_outline.jpg $W/masks_r1e2_newcam:3060ff $W/masks_final:ff2020
python3 $T/outline_overlay.py p016 120,520,520,860 3 $R/zoom/nose_p016_far_corner_outline.jpg $W/masks_r1e2_newcam:3060ff $W/masks_final:ff2020
python3 $T/outline_overlay.py p018 150,520,450,720 4 $R/zoom/nose_p018_outline.jpg $W/masks_r1e2_newcam:3060ff $W/masks_final:ff2020
python3 $T/dump_lines.py $T $W/lines_new.json > /dev/null
python3 $T/nose_overlay.py p016 $P/telsa-roadster-2026-016.jpg $R/p016.png $R2/work/lines_new.json $W/lines_new.json 0,380,1000,900 1.5 $R/zoom/lines_p016.png
python3 $T/nose_overlay.py p018 $P/tesla-roadster-2026-018.jpg $R/p018.png $R2/work/lines_new.json $W/lines_new.json 100,480,700,760 2.5 $R/zoom/lines_p018.png
python3 $T/nose_overlay.py p013 $P/tesla-roadster-2026-013-1.jpg $R/p013.png $R2/work/lines_new.json $W/lines_new.json 60,200,760,960 1.5 $R/zoom/lines_p013.png both
python3 $T/plan_report.py $R/plan_curvature.png > $R/plan_curvature.txt
cat $R/residuals_r1e3.txt
