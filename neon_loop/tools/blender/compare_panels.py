"""numpy-only: compare two panel dumps (dump_panels.py): per panel, identical topology -> max vertex deviation (mm); the nose panels are compared by region.
   python3 compare_panels.py old.npz new.npz"""
import sys, numpy as np
A, B = np.load(sys.argv[1]), np.load(sys.argv[2])
names = sorted({k.split('__')[0] for k in A.files})
print('%-14s %8s %8s %12s' % ('panel', 'verts', 'verts2', 'max dev mm'))
for n in names:
    va, vb = A[n + '__v'], B[n + '__v'] if n + '__v' in B.files else None
    if vb is None:
        print('%-14s %8d %8s %12s' % (n, len(va), '-', 'gone')); continue
    if len(va) == len(vb) and A[n + '__f'].shape == B[n + '__f'].shape and (A[n + '__f'] == B[n + '__f']).all():
        d = np.linalg.norm(va - vb, axis=1) * 1000
        print('%-14s %8d %8d %12.4f   (identical topology; vertices moved: %d, x range of the movers [%.3f, %.3f])' % (n, len(va), len(vb), d.max(), int((d > 1e-6).sum()),
              *(((va[d > 1e-6][:, 0].min(), va[d > 1e-6][:, 0].max())) if (d > 1e-6).any() else (0, 0))))
    else:
        print('%-14s %8d %8d %12s' % (n, len(va), len(vb), 'topology changed'))
# fender top: the new panel's vertices are rows TRI_K.. of the old one: compare per row
if 'fender_top__v' in A.files:
    fa, fb = A['fender_top__v'], B['fender_top__v']
    ks = (len(fa) - 1 - 19) // 76          # not needed: compute from sizes
    off = len(fa) - len(fb)
    d = np.linalg.norm(fa[off:] - fb, axis=1) * 1000
    rows = np.arange(len(fb)) // 19
    print('fender_top (new rows from the flap seam on vs the same R1c vertices): max dev %.3f mm' % d.max())
    for r in range(0, len(fb) // 19, 4):
        sel = rows == r
        print('   row +%2d  x %.3f  max dev %.4f mm' % (r, fb[sel][:, 0].mean(), d[sel].max()))
    x_axle = -1.487
    sel = fb[:, 0] > x_axle
    print('   aft of the front axle (x > %.3f): %d vertices, max dev %.5f mm' % (x_axle, sel.sum(), d[sel].max() if sel.any() else 0))
    sel2 = fb[:, 0] > -1.9
    print('   x > -1.9: max dev %.5f mm' % d[sel2].max())

# --xcut X: for every panel, the old vertices forward of X that have no vertex within 0.5 mm in the new panel (the partial-unlock proof: nothing moved forward of the cut)
if '--xcut' in sys.argv:
    xc = float(sys.argv[sys.argv.index('--xcut') + 1])
    print('--- vertex comparison forward of x = %.3f (an old vertex with no new vertex within 0.5 mm counts as moved; max = the largest nearest-vertex distance, mm)' % xc)
    for n in names:
        if n + '__v' not in B.files:
            continue
        va, vb = A[n + '__v'], B[n + '__v']
        sel = va[va[:, 0] < xc]
        if len(sel) == 0:
            continue
        dmax, moved = 0.0, 0
        for i in range(0, len(sel), 500):
            d = np.sqrt(((sel[i:i + 500, None, :] - vb[None, :, :]) ** 2).sum(-1)).min(1) * 1000
            dmax = max(dmax, d.max()); moved += int((d > 0.5).sum())
        print('%-14s %6d old vertices forward of the cut: moved (> 0.5 mm) %d, max nearest distance %.4f mm' % (n, len(sel), moved, dmax))

# --xaft X: the mirror proof (R1e2): old vertices AFT of X (x > X) that have no new vertex within 0.5 mm; and the reverse (new vertices aft of X with no old vertex within 0.5 mm: nothing was added there)
if '--xaft' in sys.argv:
    xa = float(sys.argv[sys.argv.index('--xaft') + 1])
    xm = float(sys.argv[sys.argv.index('--xmax') + 1]) if '--xmax' in sys.argv else 1e9           # --xmax X: only vertices with x < X (leave out a later round's region)
    print('--- vertex comparison AFT of x = %.3f (and forward of --xmax if given) (vertices with no counterpart within 0.5 mm count as moved; max = the largest nearest-vertex distance, mm)' % xa)
    for n in names:
        if n + '__v' not in B.files:
            continue
        va, vb = A[n + '__v'], B[n + '__v']
        out = []
        for lab, P, Q in (('old->new', va, vb), ('new->old', vb, va)):
            sel = P[(P[:, 0] > xa) & (P[:, 0] < xm)]
            dmax, moved = 0.0, 0
            for i in range(0, len(sel), 500):
                d = np.sqrt(((sel[i:i + 500, None, :] - Q[None, :, :]) ** 2).sum(-1)).min(1) * 1000
                dmax = max(dmax, d.max()); moved += int((d > 0.5).sum())
            out.append('%s: %d vertices, moved(>0.5 mm) %d, max %.4f mm' % (lab, len(sel), moved, dmax))
        print('%-14s %s' % (n, '   '.join(out)))
