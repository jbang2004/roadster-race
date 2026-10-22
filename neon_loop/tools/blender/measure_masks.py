"""
numpy-only measurements on the flat-colour masks of mask_views.py (+ the press photos):

  python3 tools/blender/measure_masks.py silhouette <maskdir_A> <maskdir_B> [--view p018] [--x0 1000 --x1 1700]    topmost-pixel (roofline) diff of two sets, px
  python3 tools/blender/measure_masks.py glass_p013 <maskdir>                                                      rear glass outline (half widths vs x) of the model mask vs the p013 photo
  python3 tools/blender/measure_masks.py apex <maskdir> <view>                                                     top of the white buttresses (ear tips) in the model mask
"""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import imgio
from cam import Cam
REFS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'refs'))


def load(d, v):
    return imgio.read(os.path.join(d, f'{v}_mask.png')) if False else _rgba(os.path.join(d, f'{v}_mask.png'))


def _rgba(path):
    import subprocess
    w, h = imgio.size(path)
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 4)


def silhouette(a, b, view='p018', x0=1000, x1=1700):
    A, B = _rgba(os.path.join(a, f'{view}_mask.png')), _rgba(os.path.join(b, f'{view}_mask.png'))
    ma, mb = A[..., 3] > 127, B[..., 3] > 127
    top = lambda m, x: int(np.argmax(m[:, x])) if m[:, x].any() else -1
    d = [top(mb, x) - top(ma, x) for x in range(x0, x1) if top(ma, x) >= 0 and top(mb, x) >= 0]
    xs = [x for x in range(x0, x1) if top(ma, x) >= 0 and top(mb, x) >= 0]
    d = np.array(d)
    print(f'{view} roofline x {x0}-{x1}: topmost-pixel diff B-A  max |d| = {np.abs(d).max()} px at x={xs[int(np.argmax(np.abs(d)))]}   mean |d| = {np.abs(d).mean():.2f}   columns with |d|>2: {(np.abs(d) > 2).sum()}')
    xo = (ma ^ mb)
    print(f'{view} silhouette XOR pixels in the roofline band: {int(xo[:, x0:x1].sum())}   whole image: {int(xo.sum())}')
    return d


def glass_p013(mdir):
    cam = Cam('p013')
    M = _rgba(os.path.join(mdir, 'p013_mask.png'))
    red = (M[..., 0] > 200) & (M[..., 1] < 60) & (M[..., 2] < 60) & (M[..., 3] > 127)
    ph = imgio.read(os.path.join(REFS, 'press2', 'tesla-roadster-2026-013-1.jpg')).astype(float)
    R, G, B = ph[..., 0], ph[..., 1], ph[..., 2]
    lum = (R + G + B) / 3
    pm = ((R - B) > 22) | (lum < 55)
    print('x_px  x_m   |  photo: top bot width(px)  | model: top bot width(px) | d width %')
    for px in range(1110, 1566, 24):
        def run(mask, c=593):
            s = set(np.where(mask[380:820, px])[0] + 380)
            if c not in s:
                return None
            t = b = c
            while t - 1 in s: t -= 1
            while b + 1 in s: b += 1
            return t, b
        rp, rm = run(pm), run(red)
        x = cam.unproject(px, 600, 'z', 1.2)[0]
        if rp and rm:
            print(f'{px}  {x:5.2f} |  {rp[0]:4d} {rp[1]:4d} {rp[1]-rp[0]:4d}        |  {rm[0]:4d} {rm[1]:4d} {rm[1]-rm[0]:4d}       | {100*((rm[1]-rm[0])-(rp[1]-rp[0]))/(rp[1]-rp[0]):+6.1f}')
        else:
            print(px, x, rp, rm)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'silhouette':
        g = lambda k, d: a[a.index(k) + 1] if k in a else d
        silhouette(a[1], a[2], g('--view', 'p018'), int(g('--x0', 1000)), int(g('--x1', 1700)))
    elif a[0] == 'glass_p013':
        glass_p013(a[1])
