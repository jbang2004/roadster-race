"""
Clean studio renders of the exported game car for comparing the rear against the Tesla Roadster 2026 press photos.

  /Applications/Blender.app/Contents/MacOS/Blender -b --python tools/blender/render_ref_views.py -- \
      [--glb public/assets/car/car_hi.raw.glb] [--out shots/rear_rework/round1/studio] [--views r81,thrust,high,...] [--samples 48]

The GLB is imported back into Blender's own frame (x toward the rear, y lateral with -y = driver / left, z up), the paint
is swapped for a plain light pearl so forms read like the (white) press car, and the car is lit by a soft key, two strip
lights and a rim light over a dark grey floor.  Cameras are placed to match the viewpoints of the four reference photos
(see VIEWS): lens in mm on a 36 mm sensor, `shift` moves the frame without changing the perspective.

Options:  --wing deploy|stow|hide   wing pose (the r81 / thrusters photos show it stowed, official-02 deployed)
          --glass-dark              glass without specular reflection (a flat pane would otherwise mirror the studio rim light as a white sheet at a grazing angle)
          --hide A,B                hide objects by name prefix
          --extra-views "{...}"     more cameras, same tuple format as VIEWS
          --bands N                 (with --reflect) stripe pairs per revolution, default 24 (7.5 deg bands)
          --reflect h|v|hv          reflection-line check: the paint becomes a perfect mirror under a striped sky (24 bands per
                                    revolution; h = horizontal bands, v = vertical, hv = both), no lights.  A clean surface
                                    gives smooth, parallel stripes; pinches / ripples / creases show as kinks and whorls.
"""
import bpy, json, math, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(name, default):
    return argv[argv.index(name) + 1] if name in argv else default


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
GLB = os.path.abspath(arg('--glb', os.path.join(ROOT, 'public', 'assets', 'car', 'car_hi.raw.glb')))
OUT = os.path.abspath(arg('--out', os.path.join(ROOT, 'shots', 'rear_rework', 'studio')))
SAMPLES = int(arg('--samples', '48'))
SCALE = float(arg('--scale', '1.0'))
os.makedirs(OUT, exist_ok=True)

# name: (camera location, target, lens mm, (w, h) px, (shift_x, shift_y))   Blender frame, car faces -x
VIEWS = {
    # straight rear, eye level, long lens (r81.png 1920x1317)
    'r81':    ((20.9, 0.0, 1.25), (2.0, 0.0, 1.25), 85, (1920, 1317), (0.0, 0.0)),
    # low rear quarter close-up from the left (2026-Tesla-Roadster-rear-thrusters.jpg 2048x1536)
    'thrust': ((4.64, -1.84, 0.71), (2.33, 0.0, 0.75), 59, (2048, 1536), (0.113, -0.05)),
    # high rear (official-02.jpg 2048x1365)
    'high':   ((11.97, 0.0, 7.01), (2.33, 0.0, 0.75), 85, (2048, 1365), (0.0, 0.10)),
    # extra inspection views
    'side':   ((2.3, -9.0, 0.75), (2.0, 0.0, 0.70), 85, (1600, 900), (0.0, 0.0)),
    'top':    ((2.0, 0.0, 12.0), (2.0, 0.0, 0.0), 85, (1600, 1000), (0.0, 0.0)),
    'rear34': ((7.0, -4.5, 1.7), (2.0, 0.0, 0.62), 60, (1600, 1000), (0.0, 0.0)),
    'lobe': ((3.9, -1.0, 0.62), (2.3, -0.45, 0.72), 60, (1600, 1000), (0.0, 0.0)),
    'quarter': ((2.6, -4.2, 0.75), (2.15, -1.0, 0.65), 60, (1600, 1000), (0.0, 0.0)),
    'corner3': ((5.2, -1.9, 0.9), (2.3, -0.75, 0.80), 50, (1600, 1000), (0.0, 0.0)),
    'corner': ((3.9, -2.3, 0.95), (2.2, -0.85, 0.72), 40, (1600, 1000), (0.0, 0.0)),
    'corner2': ((3.2, -2.6, 0.55), (2.1, -0.95, 0.60), 40, (1600, 1000), (0.0, 0.0)),
    # whole-car press set (refs/press2, electrive 1800x1200), cameras solved from wheel / lamp / plate points;
    # optional 6th element = camera roll in degrees.  All four show the wing stowed.
    'p016': ((-8.130, -4.773, 1.059), (-1.383, -0.488, 0.706), 65.26, (1800, 1200), (0.0, 0.0), -0.88),   # front-left 3/4, studio (FRONT refit 2026-10-19; was (-6.772, -4.276, 0.597), (-0.24, 0.342, 0.721), 51.58, roll -4.62)
    'p017': ((6.665, -6.044, 0.973), (0.956, -0.452, 0.609), 55.59, (1800, 1200), (0.0, 0.0)),          # rear-left 3/4, studio
    'p018': ((0.0, -10.0, 0.61), (0.0, 0.0, 0.61), 51.2, (1800, 1200), (0.0, 0.0)),                     # left profile, studio
    # R1e3: re-matched by cam_fit.py on the features the nose round does not touch (tail edge, lit side, side glass): height 10.5 m, lens 61.5 mm (was 30 m / 188 mm, x0 .018: rms 5.39 px -> 4.44 px).
    #       the height is only weakly determined (rms 4.44-4.46 px for 9-12 m, 4.94 at 30 m); nose-edge residual of the R1e2 model: +18 px (old camera) -> -4 px
    'p013': ((0.0262, -0.0042, 10.5), (0.0262, -0.0042, 0.0), 61.47, (1800, 1200), (0.0, 0.0)),            # straight down, nose left (desert)
    # R2 front-end close-ups (refs/press2 014 / 005 / 003, 1800x1200); cameras solved from the cowl corners, the wheel and the door-front junction (matching by eye)
    'p014': ((-4.768, 0.0, 1.563), (2.349, 0.0, 0.165), 23.83, (1800, 1200), (0.0, 0.0), 0.0),            # night front, high: the light bar
    'p005': ((-1.822, 0.29, 2.709), (-2.2, -1.226, -0.8), 50.0, (1800, 1200), (0.0, 0.0), 127.37),        # front-left corner from above: flap, hood seam
    'p003': ((-4.648, -4.2, 2.297), (-1.174, -0.813, 0.399), 85.0, (1800, 1200), (0.0, 0.0), 0.0),        # front-left wheel close-up: side-marker assembly
}
VIEWS.update(eval(arg('--extra-views', '{}')))
names = arg('--views', 'r81,thrust,high').split(',')
WING = arg('--wing', 'deploy')      # deploy | stow | hide : the matched r81 / thrust photos show the wing stowed, official-02 deployed
LAMPS = arg('--lamps', 'night' if arg('--views', '') == 'p014' else 'day')      # head lamps: 'night' (p014) | 'day'
REFLECT = arg('--reflect', '')      # '' | h | v | hv : reflection-line check: mirror paint under a striped sky (h = horizontal bands, v = vertical bands)
BANDS = float(arg('--bands', '24'))   # (--reflect) stripe pairs per revolution: 24 = bands of 7.5 deg; 72 = 2.5 deg, for the flatter panels
GLASS_DARK = '--glass-dark' in argv       # glass without any specular reflection (see the Glass material below)
HIDE = [h for h in arg('--hide', '').split(',') if h]      # object-name prefixes to hide (e.g. TailLower,TailCheek to see the bare body)

# ------------------------------------------------------------------ scene
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.image_settings.file_format = 'PNG'
_vts = [e.identifier for e in bpy.types.ColorManagedViewSettings.bl_rna.properties['view_transform'].enum_items]
scene.view_settings.view_transform = 'AgX' if 'AgX' in _vts else ('Filmic' if 'Filmic' in _vts else 'Standard')
scene.view_settings.exposure = float(arg('--exposure', '0.0'))

for o in bpy.data.objects:
    if any(o.name.startswith(h) for h in HIDE):
        o.hide_render = True

# q8 (2026-10-21): the hood decal is livery vinyl (stripes / number, transparent elsewhere in the game); with no atlas here it rendered as a brushed-alu
# plate on the hood (a light rectangle + a line parallel to L7).  Keep only the rear plate: drop Decal faces ahead of x 1.5 (car frame, world space).
# 2026-10-24: the door decals (x -0.70 .. 0.22: race number / sponsor vinyl) were kept by the old x < -1.5 test and read as a grey plate stuck on each door.
import bmesh
for o in bpy.data.objects:
    if o.type != 'MESH' or not any(s.material and s.material.name.startswith('Decal') for s in o.material_slots):
        continue
    bm = bmesh.new(); bm.from_mesh(o.data); mw = o.matrix_world
    dead = [f for f in bm.faces if (o.material_slots[f.material_index].material or bpy.data.materials[0]).name.startswith('Decal')
            and (mw @ f.calc_center_median()).x < 1.5]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context='FACES'); bm.to_mesh(o.data); print('[ref] hood / door decal faces dropped:', o.name, len(dead))
    bm.free()

def srgb_lin(h):
    c = [((h >> 16) & 255) / 255.0, ((h >> 8) & 255) / 255.0, (h & 255) / 255.0]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c) + (1.0,)


# materials: the game's livery-0 paint (0xc6c9ce, metalness 0.7, roughness 0.3, clear coat), vertex-coloured Nozzle, smoked lamps
for m in bpy.data.materials:
    if not m.use_nodes:
        continue
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    if b is None:
        continue
    if m.name.startswith('Paint') and REFLECT:
        b.inputs['Base Color'].default_value = (0.9, 0.9, 0.92, 1)
        b.inputs['Metallic'].default_value = 1.0
        b.inputs['Roughness'].default_value = 0.0
        if 'Coat Weight' in b.inputs:
            b.inputs['Coat Weight'].default_value = 0.0
    elif m.name.startswith('Paint'):
        b.inputs['Base Color'].default_value = srgb_lin(0xc6c9ce)
        b.inputs['Metallic'].default_value = 0.7
        b.inputs['Roughness'].default_value = 0.30
        if 'Coat Weight' in b.inputs:
            b.inputs['Coat Weight'].default_value = 1.0
            b.inputs['Coat Roughness'].default_value = 0.06
    elif m.name.startswith('PanelGap'):             # FRONT r2: matte black with no specular (the glTF import keeps Principled's default 0.5: studio lights then turn the intake liner / seams grey)
        b.inputs['Roughness'].default_value = 1.0
        for _k in ('Specular IOR Level', 'Specular'):
            if _k in b.inputs:
                b.inputs[_k].default_value = 0.0
    elif m.name.startswith('Carbon'):               # FRONT r4: the lip / skirts read black in every press view (p018 lip side 19-29 / 255); the glTF's coat (0.6, mirror-sharp) turned the studio key light into a silver block on the lip (80-129).
        b.inputs['Base Color'].default_value = srgb_lin(0x1d1e22)          # (the game's own twill colour, materials.js; the game's metal 0.25 / rough 0.34 without the coat still gave 77-104: our strip lights are not the photo's)
        b.inputs['Metallic'].default_value = 0.0
        b.inputs['Roughness'].default_value = 0.5
        for _k in ('Specular IOR Level', 'Specular'):                      # (tuned on p018: lip side 27 / 26 / 45 vs the photo's 29 / 19 / 29; specular 0.05 gave 48-57, 0.15 gave 66-73)
            if _k in b.inputs:
                b.inputs[_k].default_value = 0.0
        if 'Coat Weight' in b.inputs:
            b.inputs['Coat Weight'].default_value = 0.0
    elif m.name.startswith('Tyre'):                 # FRONT r3: black rubber with a faint satin sheen like the photos (p018 sidewall 5-13 / 255); the game's tyre is 0x0b0b0c, roughness 0.6 (materials.js)
        b.inputs['Base Color'].default_value = srgb_lin(0x090909)
        b.inputs['Roughness'].default_value = 0.62          # (tuned on p018: sidewall mean 10.4 vs the photo's 10.8 of 255; 0.58 / spec 0.35 gave 21, the old 0.018 / 0.72 gave 39.5)
        for _k in ('Specular IOR Level', 'Specular'):
            if _k in b.inputs:
                b.inputs[_k].default_value = 0.12
    elif m.name.startswith('Nozzle'):
        cn = nt.nodes.new('ShaderNodeVertexColor')
        cn.layer_name = 'Color'
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(cn.outputs['Color'], b.inputs['Base Color'])
        # alpha = roughness code: > 0.7 -> non-metal
        lt = nt.nodes.new('ShaderNodeMath')
        lt.operation = 'LESS_THAN'
        lt.inputs[1].default_value = 0.7
        nt.links.new(cn.outputs['Alpha'], lt.inputs[0])
        nt.links.new(lt.outputs[0], b.inputs['Metallic'])
        nt.links.new(cn.outputs['Alpha'], b.inputs['Roughness'])
    elif m.name.startswith('Rim'):                 # the game's vertex-code table (materials.js 'rim'): alpha = code -> metalness / roughness per part; body code = neutral white-grey panels
        cn = next((n for n in nt.nodes if n.type == 'VERTEX_COLOR'), None) or nt.nodes.new('ShaderNodeVertexColor')
        cn.layer_name = 'Color'

        def _ramp(vals):                            # constant ramp over the code: [(code from, value)]
            r = nt.nodes.new('ShaderNodeValToRGB')
            r.color_ramp.interpolation = 'CONSTANT'
            els = r.color_ramp.elements
            els.remove(els[1])
            for i, (pos, v) in enumerate(vals):
                e = els[0] if i == 0 else els.new(pos)
                e.position, e.color = pos, (v, v, v, 1)
            nt.links.new(cn.outputs['Alpha'], r.inputs['Fac'])
            return r
        #                    rubber, gloss, graphite, body, bright satin, chrome, accent
        mt = _ramp([(0.0, 0.0), (0.075, 0.0), (0.2, 0.45), (0.35, 0.2), (0.48, 0.55), (0.68, 1.0), (0.9, 0.55)])
        rg = _ramp([(0.0, 0.74), (0.075, 0.12), (0.2, 0.48), (0.35, 0.42), (0.48, 0.36), (0.68, 0.08), (0.9, 0.30)])
        bm_ = _ramp([(0.0, 0.0), (0.35, 1.0), (0.48, 0.0)])
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        nt.links.new(bm_.outputs['Color'], mx.inputs[0])
        nt.links.new(cn.outputs['Color'], mx.inputs[6])
        mx.inputs[7].default_value = (0.60, 0.60, 0.60, 1.0)
        for l in list(b.inputs['Base Color'].links):
            nt.links.remove(l)
        nt.links.new(mx.outputs[2], b.inputs['Base Color'])
        nt.links.new(mt.outputs['Color'], b.inputs['Metallic'])
        nt.links.new(rg.outputs['Color'], b.inputs['Roughness'])
    elif m.name.startswith('Glass'):               # dark smoked glass over the bronze deck: no studio ceiling in it at grazing angles
        b.inputs['Base Color'].default_value = (0.02, 0.012, 0.007, 1)
        b.inputs['Alpha'].default_value = 0.8
        b.inputs['Roughness'].default_value = 0.25
        b.inputs['IOR'].default_value = 1.05          # (a grazing view of glass would reflect the studio's key light as a white sheet)
        if 'Specular IOR Level' in b.inputs:
            b.inputs['Specular IOR Level'].default_value = 0.2
        if GLASS_DARK:                              # --glass-dark: no specular at all.  A FLAT pane (R1d's rear window) at a grazing angle mirrors the studio's rim light as a white sheet, which the press
            b.inputs['IOR'].default_value = 1.0     # photos (black studio) do not show; the glass then reads as the dark smoked pane it is.  Default off: the R1c sheets were rendered without it.
            if 'Specular IOR Level' in b.inputs:
                b.inputs['Specular IOR Level'].default_value = 0.0
            if 'Coat Weight' in b.inputs:
                b.inputs['Coat Weight'].default_value = 0.0
    elif m.name.startswith('Decal'):                # the plate: no atlas in the studio, show brushed aluminium instead of white
        b.inputs['Base Color'].default_value = srgb_lin(0x9a9da2)
        b.inputs['Metallic'].default_value = 0.6
        b.inputs['Roughness'].default_value = 0.45
    elif m.name.startswith('ReverseLamp'):         # lamps off: smoked grey, like the game (0x3a3d42)
        b.inputs['Base Color'].default_value = srgb_lin(0x3a3d42)
        b.inputs['Emission Strength'].default_value = 0.0
    elif m.name.startswith(('TailLamp', 'BrakeLamp')):
        b.inputs['Emission Strength'].default_value = 4.0
    elif m.name.startswith('HeadLens'):             # FRONT r2: the lens strips are near-black and never glow, day or night (the photo's night view has ONE line lit, the light bar)
        b.inputs['Base Color'].default_value = srgb_lin(0x0b0c0f)          # (the game's own lamp colour: materials.js)
        b.inputs['Emission Strength'].default_value = 0.0
    elif m.name.startswith('HeadDRL'):              # the light bar: bright white strip in every press view; at night it carries the whole headlight output (game: x1.6 of the old 40)
        b.inputs['Base Color'].default_value = srgb_lin(0x303640)
        b.inputs['Emission Strength'].default_value = 64.0 if LAMPS == 'night' else 6.0
    elif m.name.startswith('SideMarker'):
        b.inputs['Emission Strength'].default_value = 4.0

# the wing: stowed / deployed / hidden per car_meta.json (wingpose.py handles the old meta.wing.stow format and the new meta.wing.deploy + WingWell one)
sys.path.insert(0, HERE); import wingpose
wingpose.apply(WING, GLB)

# floor + world
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
fl = bpy.context.object
fm = bpy.data.materials.new('Floor')
fm.use_nodes = True
fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.028, 0.028, 0.031, 1)     # a dark room like the press photos: nothing bright for the glass to mirror at grazing angles
fm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.55
fl.data.materials.append(fm)
world = bpy.data.worlds.new('W')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.0015, 0.0015, 0.002, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
scene.world = world
if REFLECT:
    # striped sky: bands of 7.5 degrees in elevation (h) and / or azimuth (v); the floor stays dark
    nt = world.node_tree
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    terms = []
    if 'h' in REFLECT:
        el = nt.nodes.new('ShaderNodeMath'); el.operation = 'ARCSINE'
        nt.links.new(sep.outputs['Z'], el.inputs[0])
        terms.append(el)
    if 'v' in REFLECT:
        az = nt.nodes.new('ShaderNodeMath'); az.operation = 'ARCTAN2'
        nt.links.new(sep.outputs['Y'], az.inputs[0]); nt.links.new(sep.outputs['X'], az.inputs[1])
        terms.append(az)
    st = None
    for t_ in terms:
        mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = BANDS
        nt.links.new(t_.outputs[0], mul.inputs[0])
        sn = nt.nodes.new('ShaderNodeMath'); sn.operation = 'SINE'
        nt.links.new(mul.outputs[0], sn.inputs[0])
        gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = 0.0
        nt.links.new(sn.outputs[0], gt.inputs[0])
        if st is None:
            st = gt
        else:
            x_ = nt.nodes.new('ShaderNodeMath'); x_.operation = 'ADD'
            nt.links.new(st.outputs[0], x_.inputs[0]); nt.links.new(gt.outputs[0], x_.inputs[1])
            st = x_
    bg = nt.nodes['Background']
    nt.links.new(st.outputs[0], bg.inputs['Strength'])
    bg.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)


def area(name, loc, target, size, energy, shape='RECTANGLE', size_y=None, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.shape = shape
    ld.size = size
    if shape == 'RECTANGLE':
        ld.size_y = size_y or size
    ld.energy = energy
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob


C = Vector((2.0, 0.0, 0.7))
if not REFLECT:
  area('key', (7.0, -3.0, 6.5), C, 6.0, 1300, size_y=4.0)
  area('stripL', (4.0, -6.5, 1.8), C, 1.2, 420, size_y=5.0, color=(0.85, 0.9, 1.0))
  area('stripR', (4.0, 6.5, 1.8), C, 1.2, 330, size_y=5.0, color=(1.0, 0.95, 0.9))
  area('rim', (-5.0, 0.0, 3.0), C, 3.0, 500, size_y=6.0)
  area('back', (11.0, 0.0, 3.8), C, 4.0, 120, size_y=2.0)      # high enough (12 deg) that the glass roof / rear window don't mirror it at grazing angles

for _n in [v for v in os.environ.get('NOLIGHT', '').split(',') if v]:       # debug: switch named studio lights off
    bpy.data.objects[_n].hide_render = True

for n in names:
    loc, tgt, lens, (w, h), (sx, sy), *roll = VIEWS[n]
    cd = bpy.data.cameras.new(n)
    cd.lens = lens
    cd.sensor_width = 36
    cd.sensor_fit = 'HORIZONTAL'
    cd.shift_x, cd.shift_y = sx, sy
    cd.clip_start, cd.clip_end = 0.05, 200
    cam = bpy.data.objects.new(n, cd)
    scene.collection.objects.link(cam)
    cam.location = loc
    from mathutils import Quaternion, Euler
    _d = (Vector(tgt) - Vector(loc)).normalized()
    _r = math.radians(roll[0]) if roll else 0.0
    cam.rotation_euler = Euler((0, 0, _r)) if abs(_d.z) > 0.999 else (_d.to_track_quat('-Z', 'Y') @ Quaternion((0, 0, 1), _r)).to_euler()
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = int(w * SCALE), int(h * SCALE)
    scene.render.filepath = os.path.join(OUT, f'{n}.png')
    if '--info' in argv:
        from bpy_extras.object_utils import world_to_camera_view
        bpy.context.view_layer.update()
        pts = {'plate': (2.33, 0, 0.753), 'noz1': (2.37, -0.405, 0.536), 'noz2': (2.37, -0.135, 0.536), 'noz3': (2.37, 0.135, 0.536),
               'noz4': (2.37, 0.405, 0.536), 'barL': (2.30, -0.93, 0.9565), 'barR': (2.30, 0.93, 0.9565)}
        for k, v in pts.items():
            u, w, _ = world_to_camera_view(scene, cam, Vector(v))
            print('PROJ', n, k, round(u * scene.render.resolution_x), round((1 - w) * scene.render.resolution_y))
    bpy.ops.render.render(write_still=True)
    print('RENDERED', scene.render.filepath)
