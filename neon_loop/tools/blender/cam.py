"""
numpy-only replica of the matched press-photo cameras (VIEWS in render_ref_views.py): project(view, P) -> (px, py) from the top-left of the photo, unproject(view, px, py, axis, val).
(Blender camera: look at tgt from loc, roll about the view axis, 36 mm sensor, horizontal fit, shift in units of the image width.)  No bpy needed.
"""
import ast, os, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _views():
    src = open(os.path.join(HERE, 'render_ref_views.py')).read()
    return next(ast.literal_eval(n.value) for n in ast.parse(src).body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'VIEWS')


VIEWS = _views()


class Cam:
    def __init__(self, name):
        loc, tgt, lens, (w, h), (sx, sy), *roll = VIEWS[name]
        self.name, self.w, self.h = name, w, h
        self.loc = np.array(loc, float)
        d = np.array(tgt, float) - self.loc
        d /= np.linalg.norm(d)
        up = np.array([0.0, 0.0, 1.0])
        if abs(d[2]) > 0.999999:          # (only an exactly vertical view: render_ref_views.py, overlay_views.py, mask_views.py and lines_overlay.py use the same test)
            right = np.array([1.0, 0.0, 0.0]); u = np.cross(right, d) if False else np.array([0.0, 1.0, 0.0])
            right = np.cross(d, u)
        else:
            right = np.cross(d, up); right /= np.linalg.norm(right)
            u = np.cross(right, d)
        r = math.radians(roll[0]) if roll else 0.0
        # roll: rotate (right, u) about the view axis (Blender: quaternion about local Z = -d, positive = counter-clockwise seen from behind the camera)
        c, s = math.cos(r), math.sin(r)
        self.right = c * right + s * u
        self.up = -s * right + c * u
        self.d = d
        self.f = lens / 36.0 * w
        self.cx = w / 2 - sx * w          # (Blender: a positive shift moves the frame right / up, i.e. the scene left / down)
        self.cy = h / 2 + sy * w

    def project(self, P):
        P = np.asarray(P, float)
        v = P - self.loc
        zc = v @ self.d
        return np.stack([self.cx + self.f * (v @ self.right) / zc, self.cy - self.f * (v @ self.up) / zc], -1)

    def ray(self, px, py):
        dv = self.d + ((px - self.cx) / self.f) * self.right - ((py - self.cy) / self.f) * self.up
        return self.loc, dv / np.linalg.norm(dv)

    def unproject(self, px, py, axis, val):
        o, dv = self.ray(px, py)
        i = 'xyz'.index(axis)
        t = (val - o[i]) / dv[i]
        return o + t * dv


if __name__ == '__main__':
    import sys
    for n in ('r81', 'high', 'thrust', 'p013', 'p017', 'p018', 'p016'):
        c = Cam(n)
        print(n, c.project([[2.33, 0, 0.753], [0.0, -1.0, 1.0], [2.41, 0.4, 1.04]]).round(1).tolist())
