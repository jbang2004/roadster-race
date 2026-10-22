"""
Project 3D polylines (Blender car frame) through the matched press-photo cameras (cam.py) and draw them on a photo or on a render of the same view (numpy + imgio only; no bpy).

  as a module:   draw(view, img_path, lines, crop=(x0, y0, x1, y1), zoom=3, out=path, both_sides=False)
                 lines = {name: (pts Nx3, (r, g, b))}   (crop in the camera's pixel frame, 1800 px wide for p0xx; the image may be scaled: scale = image width / camera width)
  as a script:   python3 tools/blender/proj_overlay.py <view> <image> <crop x0,y0,x1,y1> <zoom> <out.png> <lines.json> [both]
lines.json: {"name": {"pts": [[x, y, z], ...], "col": [r, g, b]}}.   Lines are 1 px wide at the output scale (thin on purpose: the photo is the reference, not the line).
"""
import sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cam as C, imgio


def _scale(img, cm):
    return img.shape[1] / cm.w


def stamp(img, a, b, col, r):
    n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2) + 2
    t = np.linspace(0, 1, n)
    xs, ys = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            if dx * dx + dy * dy > r * r + 0.5:
                continue
            xi, yi = np.round(xs).astype(int) + dx, np.round(ys).astype(int) + dy
            ok = (xi >= 0) & (xi < img.shape[1]) & (yi >= 0) & (yi < img.shape[0])
            img[yi[ok], xi[ok]] = col


def zoom_img(img, zoom):
    z = int(round(zoom))
    if z <= 1:
        return img
    return np.repeat(np.repeat(img, z, axis=0), z, axis=1)


def draw(view, img_path, lines, crop=None, zoom=3, out=None, both_sides=False, th=1, dashed=()):
    img = imgio.read(img_path)
    cm = C.Cam(view)
    sc = _scale(img, cm)
    x0, y0, x1, y1 = (int(round(c * sc)) for c in (crop if crop else (0, 0, cm.w, cm.h)))
    img = zoom_img(img[y0:y1, x0:x1].copy(), zoom)
    z = int(round(zoom))
    for name, (pts, col) in lines.items():
        pts = np.asarray(pts, float)
        for sd in ((-1, 1) if both_sides else (-1,)):
            q = (cm.project(pts * [1, sd, 1]) * sc - [x0, y0]) * z
            for i, (a, b) in enumerate(zip(q[:-1], q[1:])):
                if name in dashed and (i // 3) % 2:
                    continue
                stamp(img, a, b, col, th)
    if out:
        imgio.write(out, img)
    return img


def pair(view, photo, render, lines, crop, zoom, out, both_sides=False, dashed=()):
    """photo | render, both with the lines, side by side (vertically stacked when the crop is wide)"""
    a = draw(view, photo, lines, crop, zoom, None, both_sides, dashed=dashed)
    b = draw(view, render, lines, crop, zoom, None, both_sides, dashed=dashed)
    h = min(a.shape[0], b.shape[0]); w = min(a.shape[1], b.shape[1])
    out_img = np.vstack([a[:h, :w], b[:h, :w]]) if w > 1.3 * h else np.hstack([a[:h, :w], b[:h, :w]])
    imgio.write(out, out_img)


if __name__ == '__main__':
    view, img, crop, zoom, out, lj = sys.argv[1:7]
    L = {k: (np.array(v['pts']), tuple(v['col'])) for k, v in json.load(open(lj)).items()}
    draw(view, img, L, tuple(float(c) for c in crop.split(',')), float(zoom), out, len(sys.argv) > 7)
