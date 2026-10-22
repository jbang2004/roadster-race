"""
R1d: p018 roofline (silhouette) check, numpy only.  For the columns between the window tip and the ear tip it finds the photo's top edge (first row, from above, whose luminance passes the background
by THR), and compares it with the projected crest of the model (new: the straight crest; old: the R1c rail, from a design2.py given with --old).   Positive = the line is BELOW the photo's edge.
   python3 tools/blender/measure_roofline.py [--old <design2.py of the previous round>] [--thr 55]
"""
import sys, os, argparse, importlib.util
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design2 as D, imgio
from cam import Cam
ap = argparse.ArgumentParser(); ap.add_argument('--old', default=''); ap.add_argument('--thr', type=float, default=55)
ap.add_argument('--render', default='', help='render of view p018 (png): its silhouette is measured the same way')
a = ap.parse_args()
REFS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'refs'))
img = imgio.read(os.path.join(REFS, 'press2/tesla-roadster-2026-018.jpg')).astype(float).mean(2)
cm = Cam('p018')


def top_edge(lum, col, thr):
    c = lum[:500, col - 1:col + 2].mean(1)
    bg = np.median(c[:60])
    idx = np.where(c > bg + thr)[0]
    return float(idx[0]) if len(idx) else np.nan


new = D.CURVES['rail']
old = None
if a.old:
    spec = importlib.util.spec_from_file_location('d_old', a.old); old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
    old = old.CURVES['rail']
ren = imgio.read(a.render).astype(float).mean(2) if a.render else None
print('x      col  photo   new   old  | new-photo  old-photo  new-old (px, 1800 px wide; + = the line below the photo edge)   [render edge]')
rows = []
for x in np.arange(1.25, 2.36, 0.05):
    pn = cm.project(new.at(x) * [1, -1, 1])
    col = int(round(pn[0]))
    pe = top_edge(img, col, a.thr)
    po = cm.project(old.at(x) * [1, -1, 1])[1] if old is not None else np.nan
    pr = top_edge(ren, col, 25) if ren is not None else np.nan
    rows.append((x, col, pe, pn[1], po, pr))
    print(f'{x:4.2f} {col:5d} {pe:6.1f} {pn[1]:6.1f} {po:6.1f} | {pn[1]-pe:+6.1f}   {po-pe:+6.1f}   {pn[1]-po:+6.1f}      {pr:6.1f}')
r = np.array(rows)
print('mean |new-photo| %.2f px   mean |old-photo| %.2f px   max |new-old| %.2f px' % (np.nanmean(abs(r[:, 3] - r[:, 2])), np.nanmean(abs(r[:, 4] - r[:, 2])), np.nanmax(abs(r[:, 3] - r[:, 4]))))
if ren is not None:
    print('render edge vs the new crest: mean %.2f px' % np.nanmean(r[:, 5] - r[:, 3]))
