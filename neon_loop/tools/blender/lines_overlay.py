"""
Draw 3D polylines (JSON) on the press photos through the matched cameras (VIEWS in render_ref_views.py).  No render: ~1 s.

  Blender -b --python tools/blender/lines_overlay.py -- --lines lines.json --out <dir> [--views p016,p017,p018,p013] [--crop x0,y0,x1,y1 --zoom 2]
                                                        [--hubs] [--only name1,name2]

lines.json: {"name": {"pts": [[x, y, z], ...], "col": [r, g, b]}, ...}   (Blender car frame, car faces -x)
Writes <view>_lines.png (photo darkened a little + lines).  --hubs also draws the four tyre circles.
"""
import bpy, ast, math, os, sys, json
import numpy as np
from mathutils import Vector, Euler, Quaternion

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(n, d): return argv[argv.index(n) + 1] if n in argv else d
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
REFS = os.path.abspath(os.path.join(ROOT, '..', 'refs'))
OUT = os.path.abspath(arg('--out', os.path.join(ROOT, 'shots', 'full_rework', 'lines'))); os.makedirs(OUT, exist_ok=True)
NAMES = arg('--views', 'p016,p017,p018,p013').split(',')
LINES = json.load(open(arg('--lines', 'lines.json'))) if arg('--lines', '') else {}
ONLY = [s for s in arg('--only', '').split(',') if s]
PHOTO = {'p016': 'press2/telsa-roadster-2026-016.jpg', 'p017': 'press2/tesla-roadster-2026-017.jpg', 'p018': 'press2/tesla-roadster-2026-018.jpg',
         'p013': 'press2/tesla-roadster-2026-013-1.jpg', 'p014': 'press2/tesla-roadster-2026-014.jpg', 'p005': 'press2/tesla-roadster-2026-005.jpg', 'p003': 'press2/tesla-roadster-2026-003.jpg', 'r81': 'press/r81.png', 'thrust': 'press/2026-Tesla-Roadster-rear-thrusters.jpg',
         'high': 'press/2026-Tesla-Roadster-official-02.jpg'}
src = open(os.path.join(HERE, 'render_ref_views.py')).read()
VIEWS = next(ast.literal_eval(n.value) for n in ast.parse(src).body
             if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'VIEWS')
crop = [int(v) for v in arg('--crop', '').split(',')] if arg('--crop', '') else None
zoom = float(arg('--zoom', '1'))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
from bpy_extras.object_utils import world_to_camera_view

if '--hubs' in argv:
    for tag, (wx, sy) in {'FL': (-1.487, -0.885), 'FR': (-1.487, 0.885), 'RL': (1.61, -0.885), 'RR': (1.61, 0.885)}.items():
        LINES['hub_' + tag] = {'pts': [[wx + 0.39 * math.cos(a), sy, 0.39 + 0.39 * math.sin(a)] for a in np.linspace(0, 2 * math.pi, 49)], 'col': [1, 1, 0]}


def draw(img, pts, col, th=1):
    for (a, b) in zip(pts[:-1], pts[1:]):
        if a is None or b is None:
            continue
        n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2) + 2
        t = np.linspace(0, 1, n)
        xs = a[0] + (b[0] - a[0]) * t
        ys = a[1] + (b[1] - a[1]) * t
        for dx in range(-th, th + 1):
            for dy in range(-th, th + 1):
                if dx * dx + dy * dy > th * th + 0.5:
                    continue
                xi = np.round(xs).astype(int) + dx
                yi = np.round(ys).astype(int) + dy
                ok = (xi >= 0) & (xi < img.shape[1]) & (yi >= 0) & (yi < img.shape[0])
                img[yi[ok], xi[ok], :3] = col


def make_cam(n):
    loc, tgt, lens, (w, h), (sx, sy), *roll = VIEWS[n]
    cd = bpy.data.cameras.new(n); cd.lens = lens; cd.sensor_width = 36; cd.sensor_fit = 'HORIZONTAL'; cd.shift_x, cd.shift_y = sx, sy
    cam = bpy.data.objects.new(n, cd); sc.collection.objects.link(cam); cam.location = loc
    d = (Vector(tgt) - Vector(loc)).normalized(); r = math.radians(roll[0]) if roll else 0.0
    cam.rotation_euler = Euler((0, 0, r)) if abs(d.z) > 0.999 else (d.to_track_quat('-Z', 'Y') @ Quaternion((0, 0, 1), r)).to_euler()
    sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = w, h
    bpy.context.view_layer.update()
    return cam, w, h


def unproject(n, pxy, axis, val):
    """pixel (px, py from the top-left) -> world point on the plane axis = val (axis in 'xyz')."""
    cam, w, h = make_cam(n)
    P = cam.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(), x=w, y=h)
    M = (P @ cam.matrix_world.inverted()).inverted()
    nx, ny = 2 * pxy[0] / w - 1, 1 - 2 * pxy[1] / h
    a = M @ Vector((nx, ny, -1, 1)); a = a.xyz / a.w
    b = M @ Vector((nx, ny, 1, 1)); b = b.xyz / b.w
    i = 'xyz'.index(axis)
    t = (val - a[i]) / (b[i] - a[i])
    return a + (b - a) * t


if arg('--unproj', ''):
    for item in arg('--unproj', '').split(';'):       # view:px,py,axis=val
        v, rest = item.split(':'); px_, py_, av = rest.split(',')
        ax_, val_ = av.split('=')
        p_ = unproject(v, (float(px_), float(py_)), ax_, float(val_))
        print('UNPROJ', item, '->', tuple(round(c, 3) for c in p_))
    sys.exit(0)

for n in NAMES:
    loc, tgt, lens, (w, h), (sx, sy), *roll = VIEWS[n]
    cd = bpy.data.cameras.new(n); cd.lens = lens; cd.sensor_width = 36; cd.sensor_fit = 'HORIZONTAL'; cd.shift_x, cd.shift_y = sx, sy
    cam = bpy.data.objects.new(n, cd); sc.collection.objects.link(cam); cam.location = loc
    d = (Vector(tgt) - Vector(loc)).normalized(); r = math.radians(roll[0]) if roll else 0.0
    cam.rotation_euler = Euler((0, 0, r)) if abs(d.z) > 0.999 else (d.to_track_quat('-Z', 'Y') @ Quaternion((0, 0, 1), r)).to_euler()
    sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = w, h
    bpy.context.view_layer.update()
    im = bpy.data.images.load(os.path.join(REFS, PHOTO[n]))
    iw, ih = im.size
    px = np.empty(iw * ih * 4, dtype=np.float32); im.pixels.foreach_get(px)
    img = px.reshape(ih, iw, 4)[::-1].copy()              # top row first
    if (iw, ih) != (w, h):
        raise SystemExit('photo size mismatch')
    img[..., :3] *= 0.8
    for name, L in LINES.items():
        if ONLY and not any(name.startswith(o) for o in ONLY):
            continue
        pp = []
        for p in L['pts']:
            u, v, dep = world_to_camera_view(sc, cam, Vector(p))
            pp.append(None if dep <= 0 else (u * w, (1 - v) * h))
        draw(img, pp, L.get('col', [1, 0, 0]), th=1)
    if crop:
        x0, y0, x1, y1 = crop
        img = img[y0:y1, x0:x1]
    out = np.clip(img[::-1], 0, 1).astype(np.float32)
    oi = bpy.data.images.new('o_' + n, out.shape[1], out.shape[0], alpha=True)
    oi.pixels.foreach_set(out.reshape(-1)); oi.update()
    path = os.path.join(OUT, f'{n}_lines.png')
    oi.filepath_raw = path; oi.file_format = 'PNG'; oi.save()
    if zoom != 1:
        import subprocess
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', path, '-vf', f'scale=iw*{zoom}:-1', path + '.z.png'], check=False)
        os.replace(path + '.z.png', path)
    print('LINES', n, path)
