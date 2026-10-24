"""blender -b wedge_car.blend --python export_glb.py -- <out.glb>  (curves -> meshes, then glTF binary)"""
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
for ob in list(bpy.data.objects):
    if ob.type == 'CURVE':
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.convert(target='MESH')
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True)
print("GLB", out)
