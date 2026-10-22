"""
Fast loop for the panel shell (tools/blender/shell2.py): builds the shell only (no car), cuts the arches, adds simple tyres and exports a GLB that
render_ref_views.py can render (studio or --reflect h|v).

  Blender -b --python tools/blender/shell2_view.py -- --out <dir> [--no-bevel] [--no-arch] [--fillet 0.008] [--obj file.obj] [--unlock a,b]

Writes <out>/shell2.glb and prints the panel table, the watertightness check and the triangle count.
"""
import bpy, math, os, sys, json
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(n, d):
    return argv[argv.index(n) + 1] if n in argv else d


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.abspath(arg('--out', '/tmp/shell2_view'))
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
import shell2 as S2
import importlib
importlib.reload(S2)
if arg('--fillet', ''):
    S2.FILLET = float(arg('--fillet', '0.008'))
ob, info = S2.build_shell2(bevel='--no-bevel' not in argv, check=False)
print('SHELL2 panels', info['panels'])
print('SHELL2 open_edges', info['open_edges'], 'nonmanifold', info['nonmanifold'], 'bad_winding', info['bad_winding'], 'beveled_edges', info['beveled'])
if '--no-arch' not in argv:
    S2.cut_arches(ob)
S2.add_floor(ob)
me = ob.data
print('SHELL2 verts', len(me.vertices), 'tris', sum(len(p.vertices) - 2 for p in me.polygons))
if '--debug-panels' in argv:                    # one flat colour per panel (studio view) to see which panel is which
    import colorsys
    names = list(ob['panel_names'])
    pid = [a.value for a in me.attributes['panel'].data]
    for i, nm in enumerate(names):
        m = bpy.data.materials.new('Dbg.' + nm)
        m.use_nodes = True
        r, g, b = colorsys.hsv_to_rgb((i * 0.37) % 1.0, 0.75, 0.9)
        m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (r, g, b, 1.0)
        m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.6
        me.materials.append(m)
    for p, k in zip(me.polygons, pid):
        p.material_index = k
else:
  for nm, rgb in (('Paint', (0.80, 0.80, 0.82)), ('Glass', (0.05, 0.03, 0.02)), ('Trim', (0.03, 0.03, 0.035))):
    m = bpy.data.materials.new(nm)
    m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*rgb, 1.0)
    me.materials.append(m)
# shading: faces smooth, edges sharper than 30 degrees hard (as build_game_car.mark_sharp)
import bmesh
bm = bmesh.new(); bm.from_mesh(me)
for e in bm.edges:
    e.smooth = (e.calc_face_angle(0.0) < math.radians(30)) if len(e.link_faces) == 2 else True
bm.to_mesh(me); bm.free()
for p in me.polygons:
    p.use_smooth = True
# tyres (simple black cylinders) so the arches read
tm = bpy.data.materials.new('Trim.tyre'); tm.use_nodes = True
tm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.01, 0.01, 0.012, 1)
for xh, sd in ((-1.487, -1), (-1.487, 1), (1.61, -1), (1.61, 1)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.39, depth=0.284, location=(xh, sd * 0.885, 0.39), rotation=(math.pi / 2, 0, 0))
    t = bpy.context.object
    t.data.materials.append(tm)
    bpy.ops.object.shade_smooth()
if arg('--obj', ''):
    bpy.ops.wm.obj_export(filepath=arg('--obj', ''))
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'shell2.glb'), export_format='GLB', export_yup=True)
print('SHELL2 glb', os.path.join(OUT, 'shell2.glb'))
