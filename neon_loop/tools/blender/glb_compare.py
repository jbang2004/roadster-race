#!/usr/bin/env python3
"""Compare two uncompressed GLBs (the *.raw.glb files): per object and per material, triangle count and world-space bounding box.

    python3 tools/blender/glb_compare.py before.raw.glb after.raw.glb [--tol-mm 0.1] [--verbose]
    python3 tools/blender/glb_compare.py dirA dirB            # compares car_hi / car_lod1 / car_lod2 (.raw.glb) in both dirs

Objects are the glTF nodes that carry a mesh (key = node path of names, so a renamed object shows up as missing + extra);
materials are keyed by material name, all primitives in the file that use it.  Also printed: the centroid shift of each object's
vertices (catches a part that moved without changing its box).  Exit code 0 = equal within the tolerance, 1 = not.
numpy only; meshopt-compressed files are not supported (use --raw builds).
"""
import json, struct, sys, os
import numpy as np

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def load_glb(path):
    b = open(path, 'rb').read()
    magic, ver, _ = struct.unpack('<4sII', b[:12])
    assert magic == b'glTF', path
    off, js, binc = 12, None, None
    while off < len(b):
        n, t = struct.unpack('<I4s', b[off:off + 8])
        d = b[off + 8: off + 8 + n]
        if t == b'JSON':
            js = json.loads(d)
        elif t == b'BIN\x00':
            binc = d
        off += 8 + n + (-n % 4)
    return js, binc


def accessor(js, binc, i):
    a = js['accessors'][i]
    bv = js['bufferViews'][a['bufferView']] if 'bufferView' in a else None
    nc = NC[a['type']]
    dt = np.dtype(CT[a['componentType']])
    if bv is None:
        return np.zeros((a['count'], nc), dt)
    base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    stride = bv.get('byteStride', 0)
    if stride and stride != nc * dt.itemsize:
        raw = np.frombuffer(binc, np.uint8, count=stride * a['count'], offset=base).reshape(a['count'], stride)
        arr = np.ascontiguousarray(raw[:, :nc * dt.itemsize]).view(dt).reshape(a['count'], nc)
    else:
        arr = np.frombuffer(binc, dt, count=a['count'] * nc, offset=base).reshape(a['count'], nc)
    if a.get('normalized'):
        arr = arr.astype(np.float64) / np.iinfo(dt).max
    return arr


def node_matrix(n):
    if 'matrix' in n:
        return np.array(n['matrix'], float).reshape(4, 4).T
    T = np.eye(4)
    t = n.get('translation', [0, 0, 0])
    q = n.get('rotation', [0, 0, 0, 1])
    s = n.get('scale', [1, 1, 1])
    x, y, z, w = q
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    T[:3, :3] = R * np.array(s)[None, :]
    T[:3, 3] = t
    return T


def summarize(path):
    """-> (objects, materials): {key: dict(tris, lo, hi, cen)}"""
    js, binc = load_glb(path)
    nodes = js.get('nodes', [])
    objs, mats = {}, {}
    seen = {}

    def acc(d, key, tris, P):
        e = d.setdefault(key, dict(tris=0, lo=np.full(3, np.inf), hi=np.full(3, -np.inf), sum=np.zeros(3), n=0))
        e['tris'] += tris
        if len(P):
            e['lo'] = np.minimum(e['lo'], P.min(0))
            e['hi'] = np.maximum(e['hi'], P.max(0))
            e['sum'] += P.sum(0)
            e['n'] += len(P)

    def walk(i, M, path):
        n = nodes[i]
        M2 = M @ node_matrix(n)
        p = path + '/' + n.get('name', 'node%d' % i)
        if 'mesh' in n:
            k = seen.get(p, 0)
            seen[p] = k + 1
            key = p if k == 0 else '%s#%d' % (p, k)
            for prim in js['meshes'][n['mesh']]['primitives']:
                if prim.get('mode', 4) != 4:
                    continue
                P = accessor(js, binc, prim['attributes']['POSITION']).astype(np.float64)
                P = P @ M2[:3, :3].T + M2[:3, 3]
                tris = (accessor(js, binc, prim['indices']).size if 'indices' in prim else len(P)) // 3
                mname = js['materials'][prim['material']]['name'] if 'material' in prim else '(none)'
                acc(objs, key, tris, P)
                acc(mats, mname, tris, P)
        for c in n.get('children', []):
            walk(c, M2, p)

    sc = js['scenes'][js.get('scene', 0)]
    for r in sc['nodes']:
        walk(r, np.eye(4), '')
    return objs, mats


def compare(a, b, tol, label, verbose):
    keys = sorted(set(a) | set(b))
    miss = [k for k in keys if k not in a or k not in b]
    both = [k for k in keys if k in a and k in b]
    dtri = dbox = dcen = 0.0
    worst = ''
    bad = []
    for k in both:
        x, y = a[k], b[k]
        dt = abs(x['tris'] - y['tris'])
        if len(x['lo']) and x['n'] and y['n']:
            db = max(np.abs(x['lo'] - y['lo']).max(), np.abs(x['hi'] - y['hi']).max())
            dc = np.abs(x['sum'] / max(x['n'], 1) - y['sum'] / max(y['n'], 1)).max() if x['n'] == y['n'] else float('inf')
        else:
            db = dc = 0.0
        if dt > dtri:
            dtri = dt
        if db > dbox:
            dbox, worst = db, k
        dcen = max(dcen, dc)
        if dt or db > tol or dc > tol:
            bad.append((k, x['tris'], y['tris'], db, dc))
        elif verbose:
            print('   ok   %-48s tris %7d  box %.4f mm' % (k[-48:], x['tris'], db * 1000))
    ok = not miss and not bad
    print('%-10s %-9s compared %3d  | max tri diff %d | max bbox diff %.4f mm | max centroid diff %.4f mm | %s'
          % (label, 'PASS' if ok else 'FAIL', len(both), dtri, dbox * 1000, (dcen if np.isfinite(dcen) else float('nan')) * 1000,
             'worst bbox: ' + worst if dbox > 0 else ''))
    for k in miss:
        print('   MISSING in %s: %s' % ('after' if k in a else 'before', k))
    for k, ta, tb, db, dc in bad:
        print('   DIFF %-48s tris %d -> %d  bbox %.4f mm  centroid %s' % (k[-48:], ta, tb, db * 1000,
                                                                      '%.4f mm' % (dc * 1000) if np.isfinite(dc) else 'n/a (vertex count differs)'))
    return ok, len(both), dtri, dbox, dcen


def compare_files(pa, pb, tol, verbose=False, name=''):
    oa, ma = summarize(pa)
    ob, mb = summarize(pb)
    r1 = compare(oa, ob, tol, name + ' objects', verbose)
    r2 = compare(ma, mb, tol, name + ' materials', verbose)
    return r1, r2


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    tol = 0.1e-3
    if '--tol-mm' in sys.argv:
        tol = float(sys.argv[sys.argv.index('--tol-mm') + 1]) * 1e-3
        args = [a for a in args if a != sys.argv[sys.argv.index('--tol-mm') + 1]]
    verbose = '--verbose' in sys.argv
    if len(args) != 2:
        print(__doc__)
        return 2
    A, B = args
    allok = True
    if os.path.isdir(A) and os.path.isdir(B):
        for lv in ('hi', 'lod1', 'lod2'):
            pa, pb = os.path.join(A, 'car_%s.raw.glb' % lv), os.path.join(B, 'car_%s.raw.glb' % lv)
            r1, r2 = compare_files(pa, pb, tol, verbose, lv)
            allok &= r1[0] and r2[0]
    else:
        r1, r2 = compare_files(A, B, tol, verbose, os.path.basename(A).split('.')[0])
        allok &= r1[0] and r2[0]
    print('EQUIVALENT' if allok else 'NOT EQUIVALENT', '(tolerance %.3f mm)' % (tol * 1000))
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
