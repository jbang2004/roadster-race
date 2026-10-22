"""numpy-only: build the shell's panels (shell2.build_panels) from the shell2.py / design2.py in THIS directory and dump them to an .npz (verts + faces per panel),
so two versions (e.g. the R1c backup and the working copy) can be compared by compare_panels.py.      python3 dump_panels.py <out.npz>"""
import sys, os, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell2 as S
panels, R = S.build_panels()
out = {}
for n, pm in panels.items():
    out[n + '__v'] = np.array(pm.verts, float)
    out[n + '__f'] = np.array([list(f) + [-1] * (4 - len(f)) for f in pm.faces], int)
np.savez(sys.argv[1], **out)
print('dumped', len(panels), 'panels ->', sys.argv[1])
