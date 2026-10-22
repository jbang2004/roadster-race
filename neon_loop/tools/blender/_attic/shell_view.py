"""
Fast loop for the new exterior shell (tools/blender/shell.py): builds the cage + subdivision only (no car), renders Workbench views from the
matched press cameras and overlays them at 55 % on the photos; optionally a mirror-paint reflection check.

  Blender -b --python tools/blender/shell_view.py -- --out <dir> [--views p016,p017,p018,p013] [--levels 3] [--wire] [--obj file.obj]

Writes <view>_ov.jpg (photo + render), <view>_wb.png, <view>_flat.png (flat-lit render, to judge planes) and <out>/lines.json (feature lines).
"""
import bpy, ast, math, os, sys, json, subprocess
from mathutils import Vector, Euler, Quaternion

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(n, d): return argv[argv.index(n) + 1] if n in argv else d
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
OUT = os.path.abspath(arg('--out', os.path.join(ROOT, 'shots', 'full_rework', 'shell'))); os.makedirs(OUT, exist_ok=True)
NAMES = [v for v in arg('--views', 'p016,p017,p018,p013').split(',') if v]
LEVELS = int(arg('--levels', '3'))
REFS = os.path.abspath(os.path.join(ROOT, '..', 'refs'))
PHOTO = {'p016': 'press2/telsa-roadster-2026-016.jpg', 'p017': 'press2/tesla-roadster-2026-017.jpg', 'p018': 'press2/tesla-roadster-2026-018.jpg',
         'p013': 'press2/tesla-roadster-2026-013-1.jpg', 'p014': 'press2/tesla-roadster-2026-014.jpg', 'p005': 'press2/tesla-roadster-2026-005.jpg', 'p003': 'press2/tesla-roadster-2026-003.jpg', 'r81': 'press/r81.png', 'thrust': 'press/2026-Tesla-Roadster-rear-thrusters.jpg',
         'high': 'press/2026-Tesla-Roadster-official-02.jpg'}
src = open(os.path.join(HERE, 'render_ref_views.py')).read()
VIEWS = next(ast.literal_eval(n.value) for n in ast.parse(src).body
             if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'VIEWS')

VIEWS.update(eval(arg('--extra-views', '{}')))
bpy.ops.wm.read_factory_settings(use_empty=True)
import shell
import importlib
importlib.reload(shell)
cage, info = shell.build_shell()
lines = shell.feature_lines(info['P'])
json.dump(lines, open(os.path.join(OUT, 'lines.json'), 'w'))
ob = shell.subdivided(cage, LEVELS) if LEVELS > 0 else cage
if ob is not cage:
    bpy.data.objects.remove(cage, do_unlink=True)
if '--noarch' not in argv:
    shell.cut_arches(ob)
    shell.add_floor(ob)
me = ob.data
json.dump(shell.sharp_lines(ob), open(os.path.join(OUT, 'sharp.json'), 'w'))
print('SHELL verts', len(me.vertices), 'faces', len(me.polygons), 'tris', sum(len(p.vertices) - 2 for p in me.polygons))
for nm, rgb in (('Paint', (0.80, 0.80, 0.82)), ('Glass', (0.35, 0.22, 0.12)), ('Trim', (0.05, 0.05, 0.06))):
    m = bpy.data.materials.new(nm); m.diffuse_color = (*rgb, 1.0); me.materials.append(m)
# flat shading everywhere except across creases (angle based)
for p in me.polygons:
    p.use_smooth = True
if hasattr(me, 'set_sharp_from_angle'):
    me.set_sharp_from_angle(angle=math.radians(float(arg('--sharp', '25'))))
if arg('--obj', ''):
    bpy.ops.wm.obj_export(filepath=arg('--obj', ''), export_selected_objects=False)

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
sc.display.shading.show_cavity = False; sc.display.shading.show_specular_highlight = False
sc.render.film_transparent = True
sc.view_settings.view_transform = 'Standard'
for n in NAMES:
    loc, tgt, lens, (w, h), (sx, sy), *roll = VIEWS[n]
    cd = bpy.data.cameras.new(n); cd.lens = lens; cd.sensor_width = 36; cd.sensor_fit = 'HORIZONTAL'; cd.shift_x, cd.shift_y = sx, sy
    cam = bpy.data.objects.new(n, cd); sc.collection.objects.link(cam); cam.location = loc
    d = (Vector(tgt) - Vector(loc)).normalized(); r = math.radians(roll[0]) if roll else 0.0
    cam.rotation_euler = Euler((0, 0, r)) if abs(d.z) > 0.999 else (d.to_track_quat('-Z', 'Y') @ Quaternion((0, 0, 1), r)).to_euler()
    sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.filepath = os.path.join(OUT, f'{n}_wb.png'); bpy.ops.render.render(write_still=True)
    if n not in PHOTO:
        sc.render.film_transparent = False
        bpy.context.scene.world = bpy.data.worlds.new('W'); bpy.context.scene.world.color = (0.5, 0.5, 0.55)
        sc.render.filepath = os.path.join(OUT, f'{n}.png'); bpy.ops.render.render(write_still=True)
        sc.render.film_transparent = True
    if n in PHOTO:
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', os.path.join(REFS, PHOTO[n]), '-i', sc.render.filepath, '-filter_complex',
                        f'[0:v]scale={w}:{h}[p];[1:v]format=rgba,colorchannelmixer=aa=0.55[r];[p][r]overlay=0:0', '-frames:v', '1',
                        os.path.join(OUT, f'{n}_ov.jpg')], check=False)
    print('VIEW', n, os.path.join(OUT, f'{n}_ov.jpg'))
