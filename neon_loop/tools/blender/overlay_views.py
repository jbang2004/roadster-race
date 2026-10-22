"""
Fast geometry check: Workbench renders of a car GLB from the matched press-photo cameras (VIEWS in render_ref_views.py),
overlaid at 55 % on the photo.  ~3 s per view, so use it for every proportion / line-position change; use the Cycles
studio renders (render_ref_views.py, shots.sh --sheets) only to judge surfaces.

  /Applications/Blender.app/Contents/MacOS/Blender -b --python tools/blender/overlay_views.py -- \
      [--glb public/assets/car/car_hi.raw.glb] [--out shots/full_rework/ov] [--views p016,p017,p018,p013] [--wing stow|deploy|hide]

Writes <view>_wb.png (render, transparent background) and <view>_ov.jpg (photo + render).
"""
import bpy, ast, math, os, sys, json, subprocess
from mathutils import Vector, Euler, Quaternion

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(n, d): return argv[argv.index(n) + 1] if n in argv else d
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
GLB = os.path.abspath(arg('--glb', os.path.join(ROOT, 'public', 'assets', 'car', 'car_hi.raw.glb')))
OUT = os.path.abspath(arg('--out', os.path.join(ROOT, 'shots', 'full_rework', 'ov'))); os.makedirs(OUT, exist_ok=True)
NAMES = arg('--views', 'p016,p017,p018,p013').split(',')
WING = arg('--wing', 'stow')
REFS = os.path.abspath(os.path.join(ROOT, '..', 'refs'))
PHOTO = {'p016': 'press2/telsa-roadster-2026-016.jpg', 'p017': 'press2/tesla-roadster-2026-017.jpg', 'p018': 'press2/tesla-roadster-2026-018.jpg',
         'p013': 'press2/tesla-roadster-2026-013-1.jpg', 'p014': 'press2/tesla-roadster-2026-014.jpg', 'p005': 'press2/tesla-roadster-2026-005.jpg', 'p003': 'press2/tesla-roadster-2026-003.jpg', 'r81': 'press/r81.png', 'thrust': 'press/2026-Tesla-Roadster-rear-thrusters.jpg',
         'high': 'press/2026-Tesla-Roadster-official-02.jpg'}

src = open(os.path.join(HERE, 'render_ref_views.py')).read()
VIEWS = next(ast.literal_eval(n.value) for n in ast.parse(src).body
             if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'VIEWS')

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
sc = bpy.context.scene
# wing pose: same code as render_ref_views.py (car_meta.json wing.stow)
sys.path.insert(0, HERE); import wingpose             # the wing pose (stow / deploy / hide, old and new meta.wing format) lives in wingpose.py
wingpose.apply(WING, GLB)
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
sc.display.shading.show_cavity = True; sc.display.shading.cavity_type = 'WORLD'
sc.render.film_transparent = True
for n in NAMES:
    loc, tgt, lens, (w, h), (sx, sy), *roll = VIEWS[n]
    cd = bpy.data.cameras.new(n); cd.lens = lens; cd.sensor_width = 36; cd.sensor_fit = 'HORIZONTAL'; cd.shift_x, cd.shift_y = sx, sy
    cam = bpy.data.objects.new(n, cd); sc.collection.objects.link(cam); cam.location = loc
    d = (Vector(tgt) - Vector(loc)).normalized(); r = math.radians(roll[0]) if roll else 0.0
    cam.rotation_euler = Euler((0, 0, r)) if abs(d.z) > 0.999 else (d.to_track_quat('-Z', 'Y') @ Quaternion((0, 0, 1), r)).to_euler()
    sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.filepath = os.path.join(OUT, f'{n}_wb.png'); bpy.ops.render.render(write_still=True)
    if n in PHOTO:
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', os.path.join(REFS, PHOTO[n]), '-i', sc.render.filepath, '-filter_complex',
                        f'[0:v]scale={w}:{h}[p];[1:v]format=rgba,colorchannelmixer=aa=0.55[r];[p][r]overlay=0:0', '-frames:v', '1',
                        os.path.join(OUT, f'{n}_ov.jpg')], check=False)
    print('OVERLAY', n, os.path.join(OUT, f'{n}_ov.jpg'))
