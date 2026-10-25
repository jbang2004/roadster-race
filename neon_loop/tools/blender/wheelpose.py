"""
Front-wheel steering of the photo views for the renders of a car GLB (render_ref_views.py, mask_views.py): in p016, p017 and p003 the press car's front wheels are
turned (CALIB.md: -18, +19, +23 deg), so the model's front wheels are turned the same way before such a view is rendered, or they cannot be compared.

  angle(view, spec)    deg for a view: spec 'auto' = the photo's solved angle (calib/result.json steer_deg; 0 for views not in it), 'off' = 0, or a number for every view
  apply(view, spec)    turns the front Wheel_* pivots (Wheel_FL, Wheel_FR) to that angle about a vertical axis PIVOT_IN inboard of their origin, from their imported
                       pose (calling it again for the next view replaces the turn); returns the angle

Sign as in calib/bundle.py circle_conic: + turns the wheel's front towards the car's left (-y), a right-handed turn about +z.  Both wheels get the same angle (no Ackermann:
the photos give one angle, solved on the near wheel).  LOD2 has no wheel pivots and is not turned.

The axis (2026-10-25, WHEELS): calib/bundle.py turns the rim circle about its own centre; the calib rim edge points of the steered photos do not fit that (rms 55 / 17 / 14 px
in p003 / p016 / p017).  Turned about a vertical axis 0.29 m inboard of the rim face they fit to 3.7 / 0.5 / 0.4 px, with the same rim plane (|y| 1.0925), radius and axle
height and steer angles within 0.5 deg of result.json: the steered rim's centre swings back 0.11 m in p003.  The model's rim face is Y_P = 0.113 outboard of the Wheel_*
origin (the tyre's mid-plane), so the axis is 0.178 inboard of it.  (The game turns the wheels about their origin.)
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
try:
    STEER = json.load(open(os.path.join(HERE, 'calib', 'result.json')))['steer_deg']
except (OSError, KeyError, ValueError):
    STEER = {}
PIVOT_IN = 0.178                # m: the steering axis inboard of the Wheel_* origin (0.291 inboard of the rim face, fitted on p003 / p016 / p017)
_BASE = {}


def angle(view, spec='auto'):
    if spec == 'auto':
        return float(STEER.get(view, 0.0))
    return 0.0 if spec == 'off' else float(spec)


def apply(view, spec='auto'):
    import bpy
    from mathutils import Matrix, Vector
    a = angle(view, spec)
    for o in bpy.data.objects:
        if o.name.split('.')[0] not in ('Wheel_FL', 'Wheel_FR'):
            continue
        M = _BASE.setdefault(o.name, o.matrix_world.copy())
        p = M.translation - Vector((0.0, math.copysign(PIVOT_IN, M.translation.y), 0.0))
        o.matrix_world = Matrix.Translation(p) @ Matrix.Rotation(math.radians(a), 4, 'Z') @ Matrix.Translation(-p) @ M
    bpy.context.view_layer.update()
    return a
