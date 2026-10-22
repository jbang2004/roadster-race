#!/bin/zsh
# shots.sh  --  the one shot script of the car (replaces shots_r1d*.sh, shots_r1e*.sh, full_sheets.sh, rear_sheets.sh, zoom_pair.sh, loop_nose.sh).  Run it from the project root.
#
#   tools/blender/shots.sh --round <name> --views a,b,c [--live <region>|--glb <file>] [--masks] [--ov] [--sheets] [--reflect] [--zoom <spec>]... [options]
#
# what to do (any combination; nothing is done unless asked):
#   --masks         CHEAP LOOP (~3 s): flat-colour masks of the views (mask_views.py), then `check.py nose` when p013, p016 and p018 are all among the views
#   --ov            Workbench overlays, model 55 % over the photo (overlay.py views), ~3 s per view
#   --sheets        Cycles studio renders of the views + photo | render sheets (sheet_<view>.jpg: photo over render for p0xx, side by side for r81 / thrust / high)
#   --reflect       reflection-line check: Cycles mirror-paint renders, horizontal bands (reflect/) and vertical bands (reflect_v/)
#   --zoom SPEC     crop pair photo | render, repeatable.  SPEC = view:w:h:x:y:scale[:h|v]  (h = side by side (default), v = stacked), e.g. p018:900:300:1000:330:1.5:v
# where the car comes from:
#   --live <r>      build first: build_game_car.py --live <r> --only all --raw --out <build> (log <build>/build.log, REPORT printed); r = front|side|rear|all|none|a,b
#   --build <dir>   where --live builds (default <out>/build; region agents: shots/regions/<r>/build)
#                   (--only all because car_meta.json, which holds the wing pose the shot tools need, is written only by a full build; ~15 s)
#   --glb <file>    shoot this GLB (default public/assets/car/car_hi.raw.glb; read only)
#   --renders <dir> use existing studio PNGs <dir>/<view>.png for --sheets / --zoom instead of rendering (no Cycles)
# options:
#   --out <dir>     output directory (default shots/rounds/<round>; region agents: --round <region>/rN --out shots/regions/<region>/rN)
#   --views a,b,c   views of render_ref_views.py VIEWS (default p016,p017,p018)      --samples N (64)      --glass-dark      --hide A,B (default Decals)
#   --wing stow|deploy|hide   wing pose (default stow; the view `high` is shot deployed in --sheets, in this pose in --reflect, as the old round scripts did)
#
# examples:
#   tools/blender/shots.sh --round r1 --out shots/regions/rear/r1 --live rear --views p017,r81,high --masks --ov      # cheap loop: build + masks + overlays
#   tools/blender/shots.sh --round r1 --out shots/regions/rear/r1 --glb shots/regions/rear/build/car_hi.raw.glb --views p017,r81,high --sheets --reflect --glass-dark
B=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
D=${0:A:h}                       # tools/blender
REFS=$D/../../../refs
round=x; out=; build=; views=p016,p017,p018; glb=; live=; renders=; samples=64; hide=Decals; wing=stow; glassdark=; masks=; ov=; sheets=; reflect=; zooms=()
while (( $# )); do
  case $1 in
    --round) round=$2; shift 2;;      --out) out=$2; shift 2;;          --views) views=$2; shift 2;;
    --glb) glb=$2; shift 2;;          --live) live=$2; shift 2;;        --renders) renders=$2; shift 2;;
    --build) build=$2; shift 2;;
    --samples) samples=$2; shift 2;;  --hide) hide=$2; shift 2;;        --wing) wing=$2; shift 2;;
    --glass-dark) glassdark=--glass-dark; shift;;
    --masks) masks=1; shift;;         --ov) ov=1; shift;;               --sheets) sheets=1; shift;;       --reflect) reflect=1; shift;;
    --zoom) zooms+=($2); shift 2;;
    -h|--help) sed -n '2,/^B=/p' $0 | sed '$d' | cut -c3-; exit 0;;
    *) echo "shots.sh: unknown option $1 (try --help)" >&2; exit 2;;
  esac
done
out=${out:-shots/rounds/$round}; mkdir -p $out
typeset -A PH
PH=(p016 press2/telsa-roadster-2026-016.jpg p017 press2/tesla-roadster-2026-017.jpg p018 press2/tesla-roadster-2026-018.jpg p013 press2/tesla-roadster-2026-013-1.jpg
    p014 press2/tesla-roadster-2026-014.jpg p005 press2/tesla-roadster-2026-005.jpg p003 press2/tesla-roadster-2026-003.jpg
    r81 press/r81.png thrust press/2026-Tesla-Roadster-rear-thrusters.jpg high press/2026-Tesla-Roadster-official-02.jpg)
vlist=(${(s:,:)views})
for v in $vlist; do [[ -n $PH[$v] ]] || { echo "shots.sh: no photo for view '$v' (known: ${(k)PH})" >&2; exit 2; }; done

# ---- the car
if [[ -n $live ]]; then
  build=${build:-$out/build}; mkdir -p $build
  echo "== build (--live $live) -> $build"
  $B -b --python $D/build_game_car.py -- --live $live --out ${build:A} --only all --raw > $build/build.log 2>&1
  grep -E "Traceback|Error|assert|lock|^REGIONS|^REPORT" $build/build.log | cut -c1-220
  glb=$build/car_hi.raw.glb
fi
glb=${glb:-public/assets/car/car_hi.raw.glb}
[[ -f $glb || -n $renders ]] || { echo "shots.sh: GLB $glb not found" >&2; exit 2; }
glb=${glb:A}
[[ -n $renders && -z $masks$ov$reflect ]] || [[ -f ${glb:h}/car_meta.json ]] || { echo "shots.sh: ${glb:h}/car_meta.json missing: build with --only all (car_meta.json holds the wing pose the shot tools read)" >&2; exit 2; }

# ---- cheap loop: masks + nose residuals
if [[ -n $masks ]]; then
  echo "== masks -> $out/masks"
  $B -b --python $D/mask_views.py -- --glb $glb --out $out/masks --views $views --wing $wing 2>&1 | grep -E "Traceback|Error"
  if (( ${vlist[(Ie)p013]} && ${vlist[(Ie)p016]} && ${vlist[(Ie)p018]} )); then python3 $D/check.py nose $out/masks
  else echo "   (nose check skipped: check.py nose needs the masks of p013, p016 and p018 together)"; fi
fi

# ---- Workbench overlays
if [[ -n $ov ]]; then
  echo "== overlays -> $out/ov"
  python3 $D/overlay.py views --glb $glb --out $out/ov --views $views --wing $wing 2>&1 | grep -E "Traceback|Error|^OVERLAY"
fi

# ---- Cycles renders
render() {    # render <outdir> <extra render_ref_views args...> : every view; `high` deployed (HIGHWING overrides), the others in $wing
  local d=$1; shift
  local rest=(); for v in $vlist; do [[ $v != high ]] && rest+=($v); done
  (( ${#rest} )) && $B -b --python $D/render_ref_views.py -- --glb $glb --out $d --views ${(j:,:)rest} --wing $wing --samples $samples --hide $hide $glassdark "$@" 2>&1 | grep -E "Traceback|Error"
  (( ${vlist[(Ie)high]} )) && $B -b --python $D/render_ref_views.py -- --glb $glb --out $d --views high --wing ${HIGHWING:-deploy} --samples $samples --hide $hide $glassdark "$@" 2>&1 | grep -E "Traceback|Error"
  return 0
}
if [[ -n $sheets && -z $renders ]]; then echo "== Cycles studio renders -> $out/studio"; render $out/studio; fi
if [[ -n $reflect ]]; then
  echo "== reflection check -> $out/reflect (horizontal bands), $out/reflect_v (vertical bands)"
  HIGHWING=$wing samples=48 render $out/reflect --reflect h; HIGHWING=$wing samples=48 render $out/reflect_v --reflect v
fi
rdir=${renders:-$out/studio}

# ---- photo | render sheets
if [[ -n $sheets ]]; then
  echo "== sheets -> $out/sheet_<view>.jpg"
  for v in $vlist; do
    [[ -f $rdir/$v.png ]] || { echo "   (no render $rdir/$v.png)"; continue; }
    case $v in
      r81)   ffmpeg -loglevel error -y -i $REFS/$PH[$v] -i $rdir/$v.png -filter_complex "[0]crop=1000:560:460:600,scale=-2:800[a];[1]crop=iw*0.52:ih*0.425:iw*0.24:ih*0.455,scale=-2:800[b];[a][b]hstack" $out/sheet_$v.jpg;;
      thrust|high) ffmpeg -loglevel error -y -i $REFS/$PH[$v] -i $rdir/$v.png -filter_complex "[0]scale=-2:800[a];[1]scale=-2:800[b];[a][b]hstack" $out/sheet_$v.jpg;;
      *)     ffmpeg -loglevel error -y -i $REFS/$PH[$v] -i $rdir/$v.png -filter_complex "[0]scale=1200:800[a];[1]scale=1200:800[b];[a][b]vstack" $out/sheet_$v.jpg;;
    esac
  done
fi

# ---- zoom pairs
n=0
for spec in $zooms; do
  parts=(${(s.:.)spec}); v=$parts[1]; box=$parts[2]:$parts[3]:$parts[4]:$parts[5]; sc=$parts[6]; mode=${parts[7]:-h}
  [[ -f $rdir/$v.png ]] || { echo "   (zoom $spec: no render $rdir/$v.png)"; continue; }
  mkdir -p $out/zoom; n=$((n+1)); st=hstack; [[ $mode == v ]] && st=vstack
  ffmpeg -loglevel error -y -i $REFS/$PH[$v] -i $rdir/$v.png -filter_complex "[0]crop=$box,scale=iw*$sc:-1[a];[1]crop=$box,scale=iw*$sc:-1[b];[a][b]$st" -frames:v 1 -q:v 2 $out/zoom/${v}_$n.jpg
  echo "== zoom -> $out/zoom/${v}_$n.jpg"
done
echo "== done: $out"; ls $out
