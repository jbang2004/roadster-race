#!/bin/zsh
# R1d shots from the exported car (public/assets/car/car_hi.raw.glb): studio renders r81 / high (wing deployed) / p013 / p017 / p018, photo | render sheets, the model's own rear curves on
# photo | render pairs (rear_overlay.py), reflect h / v for p017 and high, zooms of the ear and arc region, residual tables.     tools/blender/shots_r1d.sh   (from the project root)
B=/Applications/Blender.app/Contents/MacOS/Blender; T=tools/blender; R=shots/full_rework/r1d; G=public/assets/car/car_hi.raw.glb; P=../refs/press2; Q=../refs/press; W=$R/work
mkdir -p $R/zoom $R/ov $R/studio $W
$B -b --python $T/render_ref_views.py -- --glb $G --out $R/studio --views r81,p013,p017,p018 --wing stow --samples 64 --hide Decals 2>&1 | grep -E "Traceback|Error"
$B -b --python $T/render_ref_views.py -- --glb $G --out $R/studio --views high --wing deploy --samples 64 --hide Decals 2>&1 | grep -E "Traceback|Error"
cp $R/studio/{r81,high,p013,p017,p018}.png $R/
$T/full_sheets.sh $R/studio $R p017,p018,p013
ffmpeg -loglevel error -y -i $Q/r81.png -i $R/studio/r81.png -filter_complex "[0]crop=1000:560:460:600,scale=-2:800[a];[1]crop=iw*0.52:ih*0.425:iw*0.24:ih*0.455,scale=-2:800[b];[a][b]hstack" $R/sheet_r81.jpg
ffmpeg -loglevel error -y -i $Q/2026-Tesla-Roadster-official-02.jpg -i $R/studio/high.png -filter_complex "[0]scale=-2:800[a];[1]scale=-2:800[b];[a][b]hstack" $R/sheet_high.jpg
python3 $T/rear_overlay.py --out $R/ov --render-dir $R/studio --zoom 2 > $W/key_points.txt
python3 $T/rear_overlay.py --out $R/ov --render-dir $R/studio --ear >> $W/key_points.txt
for m in h v; do d=reflect; [[ $m == v ]] && d=reflect_v
  $B -b --python $T/render_ref_views.py -- --glb $G --out $R/$d --views p017,high --wing stow --reflect $m --samples 48 --hide Decals 2>&1 | grep -E "Traceback|Error"; done
$T/zoom_pair.sh $P/tesla-roadster-2026-018.jpg $R/p018.png 900:300:1000:330 1.5 $R/zoom/rear_p018.jpg v
$T/zoom_pair.sh $P/tesla-roadster-2026-017.jpg $R/p017.png 800:350:1000:300 1.5 $R/zoom/rear_p017.jpg v
$T/zoom_pair.sh $P/tesla-roadster-2026-013-1.jpg $R/p013.png 760:720:1000:240 1.2 $R/zoom/rear_p013.jpg h
$T/zoom_pair.sh $Q/r81.png $R/studio/r81.png 420:200:760:580 3 $R/zoom/ear_r81.jpg v
$T/zoom_pair.sh $Q/2026-Tesla-Roadster-official-02.jpg $R/studio/high.png 640:430:700:420 2 $R/zoom/ear_high.jpg h
python3 $T/measure_rear.py > $R/residuals_rear.txt
python3 $T/measure_roofline.py --old ../backup/r1e_done/design2.py --render $R/studio/p018.png > $R/residuals_roofline.txt
