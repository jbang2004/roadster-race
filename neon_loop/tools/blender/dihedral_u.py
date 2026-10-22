"""numpy-only: the dihedral angle (deg) along U between the last quad of the shoulder and the first quad of the door glass, station by station (R1d2: the inclined leg of the soft arc must leave U
tangent to the glass strip, aft of x = design2.X_FOLD0; forward of it U is the 8 mm creased shoulder / glass line).      python3 dihedral_u.py [x0 x1]"""
import sys, os, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design2 as D, shell2 as S
panels, R = S.build_panels(only=['shoulder', 'door_glass'])
sh, dg = panels['shoulder'], panels['door_glass']
X = S.XS
x0, x1 = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) > 2 else (0.80, 1.2)


def qn(P):
    n = np.cross(P[2] - P[0], P[3] - P[1])
    return n / np.linalg.norm(n)


res = []
for i in range(S.I_A, S.I_TIP):
    if not (x0 <= X[i] <= x1):
        continue
    r0, r1 = sh.rows[i], sh.rows[i + 1]
    ns = qn([np.array(r0[-2]), np.array(r0[-1]), np.array(r1[-1]), np.array(r1[-2])])
    j = i - S.I_A
    d0, d1 = dg.rows[j], dg.rows[j + 1]
    if len(d0) < 2 or len(d1) < 2:
        continue
    ng = qn([np.array(d0[0]), np.array(d0[1]), np.array(d1[1]), np.array(d1[0])])
    res.append((X[i], math.degrees(math.acos(float(np.clip(ns @ ng, -1, 1))))))
for x, a in res:
    print('x %.3f   %6.2f deg' % (x, a))
aft = [a for x, a in res if x > D.X_FOLD0 + 0.03]
print('aft of x %.3f: max %.2f deg, mean %.2f deg' % (D.X_FOLD0 + 0.03, max(aft), sum(aft) / len(aft)))
