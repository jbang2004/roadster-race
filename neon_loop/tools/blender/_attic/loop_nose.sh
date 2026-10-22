#!/bin/zsh
# cheap R1e3 loop: export the hi car (raw), flat-colour masks of p013 / p016 / p018, nose residuals.      tools/blender/loop_nose.sh <tag>      (from the project root; masks in shots/full_rework/r1e3/work/masks_<tag>)
B=/Applications/Blender.app/Contents/MacOS/Blender; T=tools/blender; W=shots/full_rework/r1e3/work; tag=${1:-x}
export SHELL_UNLOCK=${SHELL_UNLOCK:-shoulder,wall,wall_black}
$B -b --python $T/build_game_car.py -- --out public/assets/car --only hi --raw 2>&1 | grep -E "Traceback|Error|assert|SHELL LOCK|EXPORTED car_hi" | cut -c1-200
$B -b --python $T/mask_views.py -- --glb public/assets/car/car_hi.raw.glb --out $W/masks_$tag --views p013,p016,p018 --wing stow 2>&1 | grep -E "Traceback|Error"
python3 $T/measure_nose.py $W/masks_$tag 2>&1 | grep -v Warn
