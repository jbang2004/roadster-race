# model features for lines without a design2 curve: door seams, arch lips, front light bar, tail bar -> JSON (printed)
"""
Model features for the phase-2 lines that have no design2 curve (wheel-arch lips, front light bar, tail light bar), read from the built GLB:

  Blender -b --python tools/blender/calib/model_feat.py [-- --glb car_hi.raw.glb] [--out file.json]   -> calib/lines/model_feat.json  (used by lines_report.py)
"""
import bpy, sys, os, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
GLB = os.path.abspath(argv[argv.index('--glb') + 1]) if '--glb' in argv else os.path.join(HERE, '..', '..', '..', 'public', 'assets', 'car', 'car_hi.raw.glb')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
sys.path.insert(0, os.path.join(HERE, '..')); import wingpose; wingpose.apply('stow', GLB)
bpy.context.view_layer.update()
def verts(objpref=None, mat=None):
    out = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or (objpref and not o.name.startswith(objpref)):
            continue
        mw = o.matrix_world; me = o.data
        if mat is None:
            out += [tuple(mw @ v.co) for v in me.vertices]; continue
        idx = {i for i, s in enumerate(o.material_slots) if s.material and s.material.name.startswith(mat)}
        vs = set()
        for p in me.polygons:
            if p.material_index in idx:
                vs.update(p.vertices)
        out += [tuple(mw @ me.vertices[i].co) for i in vs]
    return np.array(out) if out else np.zeros((0, 3))
R = {}
B = verts('Body')
for ax, x0 in (('F', -1.487), ('R', 1.61)):
    pts = []
    for x in np.linspace(x0 - 0.36, x0 + 0.36, 25):
        S = B[(np.abs(B[:, 0] - x) < 0.01) & (np.abs(B[:, 1]) > 0.97) & (B[:, 2] > 0.45) & (B[:, 2] < 0.95)]
        if len(S):
            pts.append([float(x), float(np.abs(S[np.argmin(S[:, 2])][1])), float(S[:, 2].min())])
    R['arch_' + ax] = pts
H = verts(mat='HeadDRL')
if len(H):
    H = H[H[:, 1] >= -1e-6]
    ys = np.linspace(0, H[:, 1].max(), 12)
    R['lamp_bar'] = [[float(np.mean(H[np.abs(H[:, 1] - y) < 0.03][:, 0])), float(y), float(np.mean(H[np.abs(H[:, 1] - y) < 0.03][:, 2]))] for y in ys if (np.abs(H[:, 1] - y) < 0.03).any()]
T = verts(mat='TailLamp')
if len(T):
    T = T[T[:, 1] >= -1e-6]
    ys = np.linspace(0, T[:, 1].max(), 12)
    R['tail_bar'] = [[float(np.max(T[np.abs(T[:, 1] - y) < 0.03][:, 0])), float(y), float(np.mean(T[np.abs(T[:, 1] - y) < 0.03][:, 2]))] for y in ys if (np.abs(T[:, 1] - y) < 0.03).any()]
json.dump(R, open(os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(HERE, 'lines', 'model_feat.json'), 'w'), indent=1)
print('wrote', os.path.join(HERE, 'lines', 'model_feat.json'), sorted(R))
