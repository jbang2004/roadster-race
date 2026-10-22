"""
Studio renders of wedge_car.blend matched to the reference sheet's four views,
plus side-by-side / overlay comparison sheets.

Run:  blender -b wedge_car.blend --python render_views.py -- <ref_full.png> <out_dir> [views] [samples]
"""
import bpy, math, os, sys
import numpy as np
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:]
REF, OUT = argv[0], argv[1]
VIEWS = argv[2].split(",") if len(argv) > 2 else ["side", "top", "front", "q34"]
SAMPLES = int(argv[3]) if len(argv) > 3 else 64
os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene

# ------------------------------------------------------------- engine
scene.render.engine = 'CYCLES'
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.cycles.device = 'GPU'
except Exception as e:
    print("GPU setup failed:", e)
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'

ENV_LO, ENV_MID, ENV_HI = 0.22, 0.48, 0.78
KEY_W, FILL_W = 22, 12
# ------------------------------------------------------------- world: white for camera, horizon gradient for reflections
w = bpy.data.worlds.new("Studio")
scene.world = w
w.use_nodes = True
nt = w.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld")
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB")
env = nt.nodes.new("ShaderNodeBackground")
white = nt.nodes.new("ShaderNodeBackground")
lp = nt.nodes.new("ShaderNodeLightPath")
mix = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(tc.outputs["Generated"], sep.inputs[0])
nt.links.new(sep.outputs["Z"], ramp.inputs[0])
cr = ramp.color_ramp
cr.elements[0].position = 0.0
cr.elements[0].color = (ENV_LO, ENV_LO, ENV_LO, 1)
cr.elements[1].position = 0.6
cr.elements[1].color = (ENV_HI, ENV_HI, ENV_HI, 1)
mid = cr.elements.new(0.15)
mid.color = (ENV_MID, ENV_MID, ENV_MID, 1)
nt.links.new(ramp.outputs["Color"], env.inputs["Color"])
env.inputs["Strength"].default_value = 1.0
white.inputs["Color"].default_value = (1, 1, 1, 1)
white.inputs["Strength"].default_value = 1.0
nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
nt.links.new(env.outputs[0], mix.inputs[1])
nt.links.new(white.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], out.inputs["Surface"])

# ------------------------------------------------------------- lights + shadow catcher
def area(name, loc, rot, size, power):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.shape = 'RECTANGLE'
    ld.size, ld.size_y = size
    ld.energy = power
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_euler = rot
    scene.collection.objects.link(ob)
    return ob

key = area("KeyTop", (0, 0, 7.0), (0, 0, 0), (14, 8), KEY_W)
key.visible_glossy = False
area("FillFront", (-7, -3, 3.5), (math.radians(60), 0, math.radians(-110)), (4, 3), FILL_W)

bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "ShadowCatcher"
ground.is_shadow_catcher = True

# ------------------------------------------------------------- reference helpers
def load_px(path):
    img = bpy.data.images.load(path)
    W, H = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)[::-1]
    bpy.data.images.remove(img)
    return a


REFPX = load_px(REF)


def resize(a, w, h):
    H, W = a.shape[:2]
    ys = (np.arange(h) + 0.5) * H / h - 0.5
    xs = (np.arange(w) + 0.5) * W / w - 0.5
    y0 = np.clip(np.floor(ys).astype(int), 0, H - 1); y1 = np.clip(y0 + 1, 0, H - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, W - 1); x1 = np.clip(x0 + 1, 0, W - 1)
    fy = np.clip(ys - y0, 0, 1)[:, None, None]; fx = np.clip(xs - x0, 0, 1)[None, :, None]
    top = a[y0][:, x0] * (1 - fx) + a[y0][:, x1] * fx
    bot = a[y1][:, x0] * (1 - fx) + a[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy


def save_px(a, path):
    h, w = a.shape[:2]
    img = bpy.data.images.new("tmp", w, h, alpha=True)
    if a.shape[2] == 3:
        a = np.concatenate([a, np.ones((h, w, 1), np.float32)], axis=2)
    img.pixels = np.ascontiguousarray(a[::-1]).ravel()
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


# ------------------------------------------------------------- cameras
CAR_VERTS = []
dg = bpy.context.evaluated_depsgraph_get()
for ob in scene.objects:
    if ob.type == 'MESH' and ob.name != "ShadowCatcher":
        ev = ob.evaluated_get(dg)
        mw = ob.matrix_world
        CAR_VERTS += [mw @ v.co for v in ev.data.vertices]
CAR_VERTS = CAR_VERTS[::3]


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def make_cam(name):
    cd = bpy.data.cameras.new(name)
    ob = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(ob)
    cd.clip_end = 200
    return ob


def proj_bbox(cam):
    us, vs = [], []
    for v in CAR_VERTS:
        p = world_to_camera_view(scene, cam, v)
        us.append(p.x); vs.append(p.y)
    return min(us), max(us), min(vs), max(vs)


def fit_persp(cam, tgt, res):
    """tgt = (x0, y0, x1, y1) pixel bbox (y down) the car should fill."""
    rx, ry = res
    tu0, tu1 = tgt[0] / rx, tgt[2] / rx
    tv0, tv1 = 1 - tgt[3] / ry, 1 - tgt[1] / ry
    for _ in range(8):
        u0, u1, v0, v1 = proj_bbox(cam)
        cam.data.lens *= (tu1 - tu0) / (u1 - u0)
        u0, u1, v0, v1 = proj_bbox(cam)
        cam.data.shift_x += 0.5 * (u0 + u1) - 0.5 * (tu0 + tu1)
        cam.data.shift_y += (v1 - tv1) * (ry / rx)


# landmark calibration: reference-sheet pixel <-> model point
LANDMARKS = {
    "front": [  # hood front corners, windscreen-base corners, A-pillar feet, lamp-triangle apexes
        ((85, 258), (-2.375, 0.66, 0.50)), ((355, 258), (-2.375, -0.66, 0.50)),
        ((127, 185), (-1.55, 0.53, 0.84)), ((317, 185), (-1.55, -0.53, 0.84)),
        ((58, 161), (-1.40, 0.93, 0.912)), ((385, 161), (-1.40, -0.93, 0.912)),
        ((71, 220), (-2.05, 0.78, 0.638)), ((372, 220), (-2.05, -0.78, 0.638)),
        ((221, 74), (0.30, 0.0, 1.339)),
    ],
    "q34": [
        ((700, 652), (-2.375, -0.66, 0.50)), ((540, 634), (-2.375, 0.66, 0.50)),
        ((851, 648), (-1.487, -1.0, 0.39)), ((1116, 614), (1.61, -1.0, 0.39)),
        ((1065, 502), (1.197, -0.695, 1.19)), ((922, 590), (-0.907, -1.08, 0.724)),
    ],
}


def calibrate(cam, name, box, k, res, tgt, azs, els, dists):
    rx, ry = res
    x0, y0 = box[0], box[1]
    obs = np.array([((px - x0) * k, (py - y0) * k) for (px, py), _ in LANDMARKS[name]], float)
    P = np.array([p for _, p in LANDMARKS[name]], float)
    xo = obs[:, 0] / rx - 0.5
    yo = (ry / 2 - obs[:, 1]) / rx
    tgt = Vector(tgt)
    best = None
    for az in azs:
        for el in els:
            d = Vector((-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
            q = (-d).to_track_quat('-Z', 'Y')
            R = np.array(q.to_matrix())          # camera axes in world (columns)
            for dist in dists:
                loc = np.array(tgt + d * dist)
                C = (P - loc) @ R                 # camera-space coords
                a = C[:, 0] / -C[:, 2]
                b = C[:, 1] / -C[:, 2]
                n = len(P)
                A = np.zeros((2 * n, 3)); y = np.zeros(2 * n)
                A[:n, 0] = a; A[:n, 1] = 1; y[:n] = xo
                A[n:, 0] = b; A[n:, 2] = 1; y[n:] = yo
                sol, *_ = np.linalg.lstsq(A, y, rcond=None)
                r = float(np.sum((A @ sol - y) ** 2))
                if best is None or r < best[0]:
                    best = (r, az, el, dist, sol, loc, q)
    r, az, el, dist, sol, loc, q = best
    cam.location = Vector(loc)
    cam.rotation_euler = q.to_euler()
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36
    cam.data.lens = sol[0] * 36
    cam.data.shift_x, cam.data.shift_y = -sol[1], -sol[2]
    rms_px = math.sqrt(r / len(P) / 2) * rx
    print(f"CALIB {name}: az={math.degrees(az):.1f} el={math.degrees(el):.1f} dist={dist:.2f} "
          f"lens={cam.data.lens:.1f} rms={rms_px:.1f}px")


SIDE_PX_M = 770 / 4.75          # reference side view: 770 px for the car length
VIEWDEF = {
    # name: (ref crop box in sheet px, render scale)
    "side":  ((460, 100, 1245, 335), 2),
    "top":   ((0, 445, 500, 700), 3),
    "front": ((20, 65, 425, 325), 3),
    "q34":   ((530, 470, 1165, 720), 2),
}


def setup_view(name):
    (x0, y0, x1, y1), k = VIEWDEF[name]
    rx, ry = (x1 - x0) * k, (y1 - y0) * k
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    scene.render.resolution_percentage = 100
    cam = make_cam("Cam_" + name)
    scene.camera = cam
    if name == "side":
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = (x1 - x0) / SIDE_PX_M
        cx = (0.5 * (x0 + x1) - 466) / SIDE_PX_M - 2.375
        cz = (330 - 0.5 * (y0 + y1)) / SIDE_PX_M
        cam.location = (cx, -20, cz)
        cam.rotation_euler = (math.radians(90), 0, 0)
    elif name == "top":
        s = 489 / 4.75
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = (x1 - x0) / s
        cx = (0.5 * (x0 + x1) - 1) / s - 2.375
        cy = -(0.5 * (y0 + y1) - 569) / s
        cam.location = (cx, cy, 20)
        cam.rotation_euler = (0, 0, 0)
    elif name == "front":
        cam.data.type = 'PERSP'
        calibrate(cam, "front", (x0, y0), k, (rx, ry), (0, 0, 0.62), [math.pi / 2],
                  np.radians(np.arange(1, 32, 0.5)), np.arange(5, 30, 0.25))
    elif name == "q34":
        cam.data.type = 'PERSP'
        calibrate(cam, "q34", (x0, y0), k, (rx, ry), (0.15, 0, 0.55),
                  np.radians(np.arange(20, 60, 1.0)), np.radians(np.arange(3, 30, 1.0)),
                  np.arange(4, 20, 0.25))
    return cam, (x0, y0, x1, y1), (rx, ry)


def render_rear34():
    rx, ry = 1600, 900
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    cam = make_cam("Cam_rear34")
    scene.camera = cam
    cam.data.type = 'PERSP'
    tgt = Vector((0.1, 0, 0.55))
    az, el, dist = math.radians(-130.0), math.radians(14.0), 9.5
    cam.location = tgt + Vector((-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
    look_at(cam, tgt)
    bpy.context.view_layer.update()
    cam.data.lens = 50
    fit_persp(cam, (150, 170, 1450, 760), (rx, ry))
    raw = os.path.join(OUT, "_raw_rear34.png")
    scene.render.filepath = raw
    bpy.ops.render.render(write_still=True)
    a = load_px(raw)
    save_px(a[..., :3] * a[..., 3:4] + (1 - a[..., 3:4]), os.path.join(OUT, "render_rear34.png"))
    print("RENDERED rear34")


def compose_sheet():
    """Model renders placed exactly where the reference sheet has its four views (2x)."""
    H, W = REFPX.shape[:2]
    k = 2
    sheet = np.ones((H * k, W * k, 3), np.float32)
    for name, ((x0, y0, x1, y1), _) in VIEWDEF.items():
        p = os.path.join(OUT, f"render_{name}.png")
        if not os.path.exists(p):
            continue
        img = load_px(p)[..., :3]
        sheet[y0 * k:y1 * k, x0 * k:x1 * k] = resize(img, (x1 - x0) * k, (y1 - y0) * k)
    save_px(sheet, os.path.join(OUT, "model_four_view_sheet.png"))
    ref2 = resize(REFPX[..., :3], W * k, H * k)
    save_px(np.concatenate([ref2, np.ones((H * k, 24, 3), np.float32), sheet], axis=1),
            os.path.join(OUT, "reference_vs_model_sheet.png"))
    print("SHEET done")


def render(name):
    cam, box, (rx, ry) = setup_view(name)
    raw = os.path.join(OUT, f"_raw_{name}.png")
    scene.render.filepath = raw
    bpy.ops.render.render(write_still=True)
    a = load_px(raw)
    rgb, al = a[..., :3], a[..., 3:4]
    comp = rgb * al + (1 - al)
    save_px(comp, os.path.join(OUT, f"render_{name}.png"))
    x0, y0, x1, y1 = box
    ref = resize(REFPX[y0:y1, x0:x1, :3], rx, ry)
    side = np.concatenate([ref, np.ones((ry, 12, 3), np.float32), comp], axis=1)
    save_px(side, os.path.join(OUT, f"compare_{name}.png"))
    over = 0.5 * ref + 0.5 * comp
    save_px(over, os.path.join(OUT, f"overlay_{name}.png"))
    print("RENDERED", name, cam.data.lens if cam.data.type == 'PERSP' else cam.data.ortho_scale)


for v in VIEWS:
    if v == "rear34":
        render_rear34()
    elif v == "sheet":
        compose_sheet()
    else:
        render(v)
