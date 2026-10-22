"""
wingpose.py  --  the wing's pose in a Blender scene that holds the imported car GLB (REAR region; used by mask_views.py, overlay_views.py and render_ref_views.py).

  module   import wingpose;  wingpose.apply(mode, glb_path)     mode = 'stow' | 'deploy' | 'hide' | a number 0..1 (deploy fraction)
           call it right after bpy.ops.import_scene.gltf(); it reads car_meta.json (next to the GLB) and understands BOTH meta.wing formats:

           new  (meta.wing has `deploy`; REAR round 1+): the 'Wing' node is built STOWED = a copy of the shell's deck faces; `WingWell` (GlossBlack recess, same footprint) sits on
                the deck.  stow  -> Wing, WingPlates and WingWell hidden (the shell's own deck is all there is);
                deploy d -> both shown, Wing moved by  Translation(dx, 0, dy*e + 3 mm) @ rotation about the pivot (rotZ*e, trailing edge up), e = smoothstep(d);  the child
                WingPlates scaled laterally (tips slide out, over d 0..0.65) and vertically (endplates + struts drop, over d 0.4..1) from plates.stow up to 1  -- the same law as
                src/car/index.js.
           old  (only meta.wing.stow): the node is built DEPLOYED; stow = lower by stow.dy, pitch stow.rotZ, retract the blade (spanScale), collapse WingPlates*.

  command line (a viewing helper, Workbench):
      blender -b --python tools/blender/wingpose.py -- --glb <car.raw.glb> --out <dir> [--d 0,0.5,1] [--cams side,rear,high,top]
      -> <dir>/pose_<cam>_dNN.png   (grey room; `high` is the matched camera of the official-02 photo; side / rear / top are free cameras at the tail)
"""
import os, sys, json, math

try:
    import bpy
    from mathutils import Vector, Matrix, Euler
except ImportError:          # (plain python: nothing to do, the module can still be read)
    bpy = None


def _smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _show(objs, on):
    for o in objs:
        if o is not None:
            o.hide_render = not on
            o.hide_viewport = not on


def apply(mode, glb):
    """pose the wing (see the module doc).  `glb` = path of the imported GLB (its car_meta.json is read).  Returns the deploy fraction used (0 = stowed)."""
    wing = bpy.data.objects.get('Wing')
    if wing is None:
        return 0.0
    well = bpy.data.objects.get('WingWell')
    kids = list(wing.children)
    if mode == 'hide':
        _show([wing, well] + kids, False)
        return 0.0
    meta = json.load(open(os.path.join(os.path.dirname(os.path.abspath(glb)), 'car_meta.json')))['wing']
    px, py, pz = meta['pivot']                                       # GLB frame -> Blender frame
    P = Vector((px, -pz, py))
    d = 1.0 if mode == 'deploy' else 0.0 if mode == 'stow' else float(mode)
    bpy.context.view_layer.update()
    dp = meta.get('deploy')
    if dp is None:                                                    # ---- old format: built deployed, stow folds it into the deck
        if mode != 'stow' and d >= 1.0:
            return 1.0
        dz, rz = meta['stow']['dy'], meta['stow']['rotZ']
        Q = P + Vector((0, 0, dz))
        sp = meta['stow'].get('spanScale', 1.0)
        wing.matrix_world = (Matrix.Translation(Q) @ Matrix.Scale(sp, 4, Vector((0, 1, 0))) @ Matrix.Translation(-Q) @ Matrix.Translation((0, 0, dz))
                             @ Matrix.Translation(P) @ Matrix.Rotation(-rz, 4, 'Y') @ Matrix.Translation(-P) @ wing.matrix_world)
        bpy.context.view_layer.update()
        ps = meta['plates']['stow']
        sx, sy, sz = ps.get('scaleX', 1.0), ps['scaleY'], ps.get('scaleZ', 1.0)
        for c in kids:
            if c.name.startswith('WingPlates'):
                c.matrix_world = (Matrix.Translation(Q) @ Matrix.Scale(sy, 4, Vector((0, 0, 1))) @ Matrix.Scale(sz, 4, Vector((0, 1, 0)))
                                  @ Matrix.Scale(sx, 4, Vector((1, 0, 0))) @ Matrix.Translation(-Q) @ c.matrix_world)
        return 0.0
    # ---- new format
    on = d > 0.002
    _show([wing, well] + kids, on)
    if not on:
        return 0.0
    e = _smooth(0, 1, d)
    wing.matrix_world = (Matrix.Translation((dp.get('dx', 0.0) * e, 0.0, dp['dy'] * e + 0.003)) @ Matrix.Translation(P) @ Matrix.Rotation(-dp['rotZ'] * e, 4, 'Y')
                         @ Matrix.Translation(-P) @ wing.matrix_world)
    bpy.context.view_layer.update()
    ps = meta['plates']['stow']
    sy = ps.get('scaleY', 1.0) + (1 - ps.get('scaleY', 1.0)) * _smooth(0.4, 1.0, d)             # vertical (GLB y = Blender z)
    sz = ps.get('scaleZ', 1.0) + (1 - ps.get('scaleZ', 1.0)) * _smooth(0.0, 0.65, d)            # lateral
    for c in kids:
        c.scale = (ps.get('scaleX', 1.0), sz, sy)                                                 # (the children keep their own location = the node origin)
    _show(kids, d > 0.03)
    return d


# ---------------------------------------------------------------------------------------------------------------- command line
CAM = {          # name: (location, target, lens mm, (w, h), shift_y)
    'side': ((2.45, -5.2, 1.25), (2.35, 0.0, 1.05), 70, (1600, 900), 0.0),
    'side3': ((6.0, -4.5, 1.9), (2.3, 0.0, 1.0), 60, (1600, 900), 0.0),
    'rear': ((9.0, 0.0, 0.95), (2.3, 0.0, 0.95), 70, (1600, 900), 0.0),
    'high': ((11.97, 0.0, 7.01), (2.33, 0.0, 0.75), 85, (2048, 1365), 0.10),      # = VIEWS['high'] of render_ref_views.py
    'top': ((2.3, 0.0, 9.0), (2.3, 0.0, 1.0), 85, (1600, 900), 0.0),
}


def _main(argv):
    arg = lambda n, d: argv[argv.index(n) + 1] if n in argv else d
    glb = os.path.abspath(arg('--glb', ''))
    out = os.path.abspath(arg('--out', '.'))
    os.makedirs(out, exist_ok=True)
    for d in [float(v) for v in arg('--d', '0,1').split(',')]:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=glb)
        apply(d, glb)
        sc = bpy.context.scene
        sc.render.engine = 'BLENDER_WORKBENCH'
        sc.display.shading.light = 'STUDIO'
        sc.display.shading.color_type = 'MATERIAL'
        sc.display.shading.show_cavity = True
        sc.display.shading.cavity_type = 'WORLD'
        sc.world = bpy.data.worlds.new('w')
        sc.world.use_nodes = False
        sc.world.color = (0.45, 0.45, 0.47)
        for n in arg('--cams', 'side,rear,high').split(','):
            loc, tgt, lens, (w, h), sy = CAM[n]
            cd = bpy.data.cameras.new(n)
            cd.lens, cd.sensor_width, cd.shift_y = lens, 36, sy
            cam = bpy.data.objects.new(n, cd)
            sc.collection.objects.link(cam)
            cam.location = loc
            cam.rotation_euler = (Vector(tgt) - Vector(loc)).normalized().to_track_quat('-Z', 'Y').to_euler() if n != 'top' else Euler((0, 0, math.pi / 2))
            sc.camera = cam
            sc.render.resolution_x, sc.render.resolution_y = w, h
            sc.render.filepath = os.path.join(out, 'pose_%s_d%02d.png' % (n, int(round(d * 100))))
            bpy.ops.render.render(write_still=True)
            print('POSE', sc.render.filepath)


if bpy is not None and '--' in sys.argv and os.path.basename(sys.argv[sys.argv.index('--python') + 1] if '--python' in sys.argv else '') == 'wingpose.py':
    _main(sys.argv[sys.argv.index('--') + 1:])
