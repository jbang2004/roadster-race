"""numpy-only: dump the nose / side lines of a design (design2.py in <design_dir>) to a lines.json for proj_overlay.py / nose_overlay.py.
     python3 dump_lines.py <design_dir> <out.json> [x_max=0.0]
names: U, L (every station from the nose to x_max), plus the nose curves that exist (bar_top, bar_bot, E_up, E_low, face_edge_up, face_edge_low, L5, tri_seam, hood_seam_L7, cowl_edge, F_bot)"""
import sys, os, json
import numpy as np
d = os.path.abspath(sys.argv[1])
sys.path.insert(0, d)
import design2 as D
D.build_all()
xm = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
out = {}
for k in ('U', 'L'):
    c = D.CURVES[k]
    xs = np.linspace(c.x0 + 1e-6, xm, 160)
    out[k] = np.asarray(c.at(xs)).tolist()
for k in ('bar_top', 'bar_bot', 'E_up', 'E_low', 'face_edge_up', 'face_edge_low', 'L5', 'tri_seam', 'hood_seam_L7', 'cowl_edge', 'F_bot'):
    v = getattr(D, 'NOSE', {}).get('curves', {}).get(k)
    if v is not None:
        out[k] = np.asarray(v, float).tolist()
json.dump(out, open(sys.argv[2], 'w'))
print('dumped', list(out), '->', sys.argv[2])
