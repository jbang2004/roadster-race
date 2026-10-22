"""numpy-only: the nose lines of two designs (lines.json of dump_lines.py: OLD = the R1e state, NEW = this round) projected through the matched press cameras (cam.py) on the photo and on the render of the same view:
the user's explicit corrections U (crest) and L (lower edge) on p016 / p018 must look unchanged aft of the nose (old = cyan, new = red), the new nose edges in yellow / green.
     python3 nose_overlay.py <view> <photo> <render> <old.json> <new.json> <crop x0,y0,x1,y1> <zoom> <out.png> [both]"""
import sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proj_overlay as P
view, photo, render, oj, nj, crop, zoom, out = sys.argv[1:9]
both = len(sys.argv) > 9
O, N = json.load(open(oj)), json.load(open(nj))
lines = {}
for k in ('U', 'L'):
    lines['old_' + k] = (np.array(O[k]), (60, 220, 255))
for k in ('U', 'L'):
    lines['new_' + k] = (np.array(N[k]), (255, 50, 50))
for k, col in (('bar_top', (255, 230, 0)), ('E_up', (60, 255, 80)), ('E_low', (60, 255, 80)), ('L5', (255, 160, 0)), ('face_edge_up', (255, 230, 0)), ('face_edge_low', (255, 230, 0)), ('tri_seam', (255, 0, 255))):
    if k in N:
        lines['new_' + k] = (np.array(N[k]), col)
P.pair(view, photo, render, lines, tuple(float(c) for c in crop.split(',')), float(zoom), out, both_sides=both, dashed=('old_U', 'old_L'))
