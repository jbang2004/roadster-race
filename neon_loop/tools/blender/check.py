#!/usr/bin/env python3
"""
check.py <metric> [args ...]  --  the one entry point for the measuring tools.

The engine script runs unchanged and its output is printed unchanged; where a metric has a known target, a PASS/FAIL table is appended (and the exit code
is 1 when something fails that is not an accepted known deviation).  Targets: SPEC.md section 0 (outline / line residual <= 1 % of the image width = 18 px of
1800), the numbers in AGENT_GUIDE.md, and the accepted deviations of SPEC.md section 6.   `check.py <metric> --help` prints the engine's own usage.

  metric     what (engine)                                                                                      target
  nose       <maskdir>: nose silhouette vs photos p013 / p016 / p018 (measure_nose.py)                            mean|d| <= 1 % W
  rear       key points of the rear buttress vs photo readings r81 / high (measure_rear.py)                       err <= 1 % W
  roofline   p018 roofline vs the projected crest (measure_roofline.py [--old design2.py] [--render p018.png])    mean <= 18 px
  masks      silhouette <A> <B> | glass_p013 <dir> (measure_masks.py)                                            (comparison; no target)
  plan       curvature of the nose curves L / U (plan_report.py [out.png])                                        0 inflections, 1 curvature peak
  crease     dihedral angle along every panel join (crease_report.py [panelA,panelB])                             (listing; no target)
  fold       the soft arc: path error, G1 gap, roll radius (fold_report.py [out.png])                             <= 6 cm, 0 deg, > 5 cm
  dihedral   dihedral along U, shoulder | door glass (dihedral_u.py [x0 x1])                                      <= 1.2 deg aft of the fold start
  fender     front fender, three faces: U profile / top-face lean / p016 lines 1-4 / p018 crest (fender_report.py)    p018 <= 8 px
  cam        cam_fit.py <verts.npz> [...]: residuals of a photo camera;  no args: cam.py self test             (listing; no target)
  lock       shell lock check without --unlock (build_game_car.py --check-lock)                                  all locked panels match
  budget     <build.log>: REPORT of a build vs the LOD budgets and the quotas in REGIONS.md section 5            lod1 60k/20, lod2 15k/10, hi 450k
  equiv      <dirA> <dirB> | <a.raw.glb> <b.raw.glb>: per object / material triangles + bbox (glb_compare.py)   0 tris, 0.1 mm
  panels     dump <out.npz> | compare <old.npz> <new.npz> [...]: per-panel deviation proof (dump / compare_panels.py)

Exit code: 0 = no unexpected FAIL, 1 = FAIL, 2 = usage / the engine itself failed.
"""
import glob
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PY = sys.executable
BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')
W = 1800.0                      # photo width the residuals are quoted against
TOL_PCT = 1.0                   # SPEC section 0: outline / line residual <= 1 % of the image width
TOL_PX = TOL_PCT / 100.0 * W    # = 18 px

ACCEPTED = {                    # rows that are known and accepted (a FAIL with a reason is shown as "FAIL (accepted)" and does not change the exit code)
    'nose:p013 front edge': 'SPEC 6-1: p013 puts the nose ~10 cm further aft than p016 / p018 (known camera disagreement); the shape-only row decides',
    'nose:p013 nose centre': 'SPEC 6-1: same p013 vs p016 / p018 offset',
    'plan:U one curvature peak': 'AGENT_GUIDE known issue 1: the U plan curvature dip (1.28 -> 0.37 -> 1.23 1/m near x -2.06) was accepted in R1e3',
    'fold:roll radius': 'AGENT_GUIDE known issue 2: roll radius < 5 cm for x 0.874-0.935 accepted (geometric limit)',
}


def run(script, args, python=True):
    """run an engine, print its output unchanged, return (returncode, stdout)"""
    cmd = ([PY, os.path.join(HERE, script)] if python else script) + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    if p.stderr.strip():
        sys.stderr.write('\n'.join(l for l in p.stderr.splitlines() if 'Warning' not in l and not l.lstrip().startswith('print(')) + '\n')
    return p.returncode, p.stdout


class Table:
    def __init__(self, title, target, cols):
        self.title, self.target, self.cols, self.rows = title, target, cols, []
        self.fails = 0          # unexpected FAILs
        self.accepted = 0
        self.passes = 0

    def add(self, key, label, cells, ok, note=''):
        """ok: True / False / None (None = information only)"""
        verdict = 'info' if ok is None else 'PASS' if ok else 'FAIL'
        why = ACCEPTED.get(key) if ok is False else None
        if ok is False and why:
            verdict, note = 'FAIL (accepted)', (note + '  ' if note else '') + why
            self.accepted += 1
        elif ok is False:
            self.fails += 1
        elif ok:
            self.passes += 1
        self.rows.append((label, cells, verdict, note))

    def show(self):
        if not self.rows:
            print('\nCHECK %s: nothing to judge (no matching rows in the engine output)' % self.title)
            return
        lw = max(len(r[0]) for r in self.rows)
        print('\nCHECK %s   target: %s' % (self.title, self.target))
        print('  %-*s  %s  verdict' % (lw, 'measure', '  '.join('%-11s' % c for c in self.cols)))
        for label, cells, verdict, note in self.rows:
            print('  %-*s  %s  %s%s' % (lw, label, '  '.join('%-11s' % c for c in cells), verdict, ('   <- ' + note) if note else ''))
        print('SUMMARY %s: %d PASS, %d FAIL%s' % (self.title, self.passes, self.fails + self.accepted, ' (%d of them accepted known deviations)' % self.accepted if self.accepted else ''))

    def code(self):
        return 1 if self.fails else 0


# ----------------------------------------------------------------------------------------------------------------------------------- metrics
NOSE_RE = re.compile(r'^\s*(?P<name>\S.*?)\s+mean\s+(?P<mean>[+-]\d+\.\d) px \((?P<mp>[+-]\d+\.\d+) %\)\s+mean\|d\|\s+(?P<mabs>\d+\.\d) px\s+max\|d\|\s+(?P<mx>\d+\.\d) px = (?P<mxp>\d+\.\d+) %')


def m_nose(args):
    rc, out = run('measure_nose.py', args)
    t = Table('nose', 'mean|d| <= %.1f %% of the image width (%d px)' % (TOL_PCT, TOL_PX), ['mean|d| %W', 'max|d| %W'])
    for line in out.splitlines():
        m = NOSE_RE.match(line)
        if m:
            name = m['name']
            mabs = 100.0 * float(m['mabs']) / W
            key = next((k for k in ACCEPTED if k.startswith('nose:') and name.startswith(k[5:])), 'nose:' + name)
            t.add(key, name, ['%.2f' % mabs, '%.2f' % float(m['mxp'])], mabs <= TOL_PCT)
    t.show()
    return max(t.code(), 2 if rc else 0)


ROW_RE = re.compile(r'^(?P<view>r81|high|thrust)\s+(?P<pt>\S.*?)\s+(?P<px>\d+\.\d)\s+(?P<py>\d+\.\d)\s+\|\s+(?P<mx>\d+\.\d)\s+(?P<my>\d+\.\d)\s+\|\s+(?P<dx>[+-]\d+\.\d+)\s+(?P<dy>[+-]\d+\.\d+)\s+(?P<err>\d+\.\d+)\s*$')


def m_rear(args):
    rc, out = run('measure_rear.py', args)
    t = Table('rear', 'point error <= %.1f %% of the image width' % TOL_PCT, ['err %W', 'dx %', 'dy %'])
    for line in out.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        label = '%s %s' % (m['view'], m['pt'])
        if float(m['py']) == 0.0:       # a width / spacing row: relative error of the distance, not a point
            t.add('rear:' + label, label, ['(spacing)', m['dx'] + ' rel', ''], None)
        else:
            t.add('rear:' + label, label, [m['err'], m['dx'], m['dy']], float(m['err']) <= TOL_PCT)
    t.show()
    return max(t.code(), 2 if rc else 0)


def m_roofline(args):
    rc, out = run('measure_roofline.py', args)
    t = Table('roofline', 'mean |line - photo edge| <= %.1f %% of the image width (%d px)' % (TOL_PCT, TOL_PX), ['mean px', 'mean %W'])
    m = re.search(r'mean \|new-photo\| (\S+) px', out)
    if m and m.group(1) != 'nan':
        v = float(m.group(1))
        t.add('roofline:crest', 'new crest vs photo edge (x 1.25-2.35)', ['%.2f' % v, '%.2f' % (100 * v / W)], v <= TOL_PX)
    m = re.search(r'render edge vs the new crest: mean (\S+) px', out)
    if m and m.group(1) != 'nan':
        v = abs(float(m.group(1)))
        t.add('roofline:render', 'render silhouette vs crest', ['%.2f' % v, '%.2f' % (100 * v / W)], v <= TOL_PX)
    t.show()
    return max(t.code(), 2 if rc else 0)


def m_masks(args):
    rc, _ = run('measure_masks.py', args)
    print('\n(masks: a comparison of two builds / a photo outline; no PASS/FAIL target)')
    return 2 if rc else 0


MONO_TOL = float(os.environ.get('MONO_TOL', '0.01'))


def m_plan(args):
    rc, out = run('plan_report.py', args)
    t = Table('plan', 'no inflection; ONE curvature peak (largest rise after it <= %.3f 1/m per sample, MONO_TOL)' % MONO_TOL, ['value'])
    curve = None
    for line in out.splitlines():
        h = re.match(r'^--- (\w+) \(', line)
        if h:
            curve = h.group(1)
        m = re.search(r'inflections \(.*?\): (\d+)', line)
        if m and curve:
            t.add('plan:%s inflections' % curve, '%s plan: inflections' % curve, [m.group(1)], int(m.group(1)) == 0)
        m = re.search(r'largest rise after it (-?[\d.]+)', line)
        if m and curve:
            v = float(m.group(1))
            t.add('plan:%s one curvature peak' % curve, '%s plan: rise after the peak' % curve, ['%.4f' % v], v <= MONO_TOL)
    t.show()
    return max(t.code(), 2 if rc else 0)


def m_crease(args):
    rc, out = run('crease_report.py', args)
    rows = [l for l in out.splitlines() if ' edges ' in l]
    fil = sum('FILLET' in l for l in rows)
    sm = sum('smooth pair' in l for l in rows)
    print('\nSUMMARY crease: %d panel joins, %d filleted (> 3 deg), %d smooth pairs, %d below the fillet threshold (a listing: no PASS/FAIL target)' % (len(rows), fil, sm, len(rows) - fil - sm))
    return 2 if rc else 0


def m_fold(args):
    rc, out = run('fold_report.py', args)
    t = Table('fold', 'path error <= 6 cm (SPEC R-6), G1 gap to the glass strip = 0 deg, roll radius < 5 cm only for x <= 0.94', ['value'])
    m = re.search(r'max path error ([\d.]+) cm', out)
    if m:
        t.add('fold:path error', 'max path error of the arc (cm)', [m.group(1)], float(m.group(1)) <= 6.0)
    gaps = [abs(float(g)) for g in re.findall(r'\|\s+[\d.]+\s+/\s+[\d.]+\s+([+-]\d+\.\d+)\s+\|', out)]
    if gaps:
        t.add('fold:G1 gap', 'max |G1 gap| to the glass strip (deg)', ['%.2f' % max(gaps)], max(gaps) <= 0.1)
    m = re.search(r'roll radius < 5 cm at (\d+) stations \(x ([\d.]+) \.\. ([\d.]+)\)', out)
    if m:
        t.add('fold:roll radius', 'roll radius < 5 cm: last station x', [m.group(3)], float(m.group(3)) <= 0.94, 'at %s stations' % m.group(1))
    elif 'roll radius >= 5 cm everywhere' in out:
        t.add('fold:roll radius', 'roll radius >= 5 cm', ['everywhere'], True)
    t.show()
    return max(t.code(), 2 if rc else 0)


def m_dihedral(args):
    rc, out = run('dihedral_u.py', args)
    t = Table('dihedral', 'max dihedral aft of the fold start <= 1.2 deg (R1d2)', ['value'])
    m = re.search(r'aft of x ([\d.]+): max ([\d.]+) deg, mean ([\d.]+) deg', out)
    if m:
        t.add('dihedral:aft', 'dihedral along U aft of x %s: max (deg)' % m.group(1), [m.group(2)], float(m.group(2)) <= 1.2, 'mean %s' % m.group(3))
    t.show()
    return max(t.code(), 2 if rc else 0)


def m_fender(args):
    """fender3: the front fender's three faces on the design curves (fender_report.py): U profile, lean of the top face, p016 photo lines 1-4, p018 crest residual; p018 <= 8 px is the one hard target"""
    rc, out = run('fender_report.py', args)
    t = Table('fender', 'p018 crest residual <= 8 px (fender3 ruling); the rest is a listing', ['value'])
    m = re.search(r'p018 crest U .*max\|d\| +([\d.]+) px', out)
    if m:
        t.add('fender:p018', 'p018 crest U vs the photo top edge: max |d| (px)', [m.group(1)], float(m.group(1)) <= 8.0)
    m = re.search(r'curvature sign changes N\.\.x -1\.3: (\d+)', out)
    if m:
        t.add('fender:p016 curv', 'U in p016: curvature sign changes (target 0; the photo line is one parabola)', [m.group(1)], int(m.group(1)) == 0)
    t.show()
    return max(t.code(), 2 if rc else 0)


def m_cam(args):
    rc, _ = run('cam_fit.py' if args else 'cam.py', args)
    return 2 if rc else 0


def m_lock(args):
    p = subprocess.run([BLENDER, '-b', '--python', os.path.join(HERE, 'build_game_car.py'), '--', '--check-lock'] + list(args), capture_output=True, text=True)
    lines = [l for l in p.stdout.splitlines() if l.startswith('SHELL2')]
    print('\n'.join(lines) if lines else p.stdout[-800:])
    n_lock = len(json.load(open(os.path.join(HERE, 'shell_lock.json')))['panels'])
    m = re.search(r'SHELL2 lock check passed \((\d+) locked panels\)', p.stdout)
    t = Table('lock', 'all %d panels of shell_lock.json match, no --unlock' % n_lock, ['value'])
    t.add('lock:check', 'lock check (--check-lock%s)' % (' ' + ' '.join(args) if args else ''), [m.group(1) + ' locked' if m else 'FAILED'], bool(m) and p.returncode == 0 and int(m.group(1)) == n_lock)
    t.show()
    return t.code()


BUDGET = {'hi': (450000, None), 'lod1': (60000, 20), 'lod2': (15000, 10)}


def quotas():
    """{(region, 'lod1'|'lod2'): int} from the table in REGIONS.md section 5 (empty cells = no quota)"""
    q = {}
    try:
        txt = open(os.path.join(HERE, 'REGIONS.md')).read()
    except OSError:
        return q
    sec = txt[txt.index('## 5.'):txt.index('## 6.')] if '## 5.' in txt and '## 6.' in txt else ''
    head = None
    for line in sec.splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if cells[0].startswith('区域'):
            head = cells
            continue
        if head is None or set(cells[0]) <= set('-: '):
            continue
        reg = cells[0].split()[0].split('（')[0].strip('*').upper()
        for h, c in zip(head, cells):
            m = re.search(r'(\d[\d,]*)', c)
            if '配额' in h and m:
                lod = 'lod1' if 'lod1' in h else 'lod2' if 'lod2' in h else None
                if lod:
                    q[(reg, lod)] = int(m.group(1).replace(',', ''))
    return q


def m_budget(args):
    if not args:
        print('usage: check.py budget <build.log>   (the log of a build_game_car.py run; shots.sh --live writes it as <out>/build.log)')
        return 2
    txt = sys.stdin.read() if args[0] == '-' else open(args[0], errors='replace').read()
    reps = re.findall(r'^REPORT (\{.*\})\s*$', txt, re.M)
    if not reps:
        print('no REPORT line in', args[0])
        return 2
    rep = json.loads(reps[-1])
    t = Table('budget', 'hi <= 450k tris; lod1 <= 60k / 20 calls; lod2 <= 15k / 10 calls; region quotas of REGIONS.md section 5 when set', ['value', 'limit'])
    for lv, (tris, calls) in BUDGET.items():
        if lv + '_tris' in rep:
            t.add('budget:%s tris' % lv, '%s triangles' % lv, ['{:,}'.format(rep[lv + '_tris']), '{:,}'.format(tris)], rep[lv + '_tris'] <= tris)
            if calls:
                t.add('budget:%s calls' % lv, '%s draw calls' % lv, [str(rep[lv + '_calls']), str(calls)], rep[lv + '_calls'] <= calls)
    q = quotas()
    for lv, regs in (rep.get('regions') or {}).items():
        for r in ('front', 'side', 'rear'):
            lim = q.get((r.upper(), lv))
            tr = regs.get(r, {}).get('tris')
            if lim is not None and tr is not None:
                t.add('budget:%s %s quota' % (r, lv), '%s %s triangles (quota)' % (r.upper(), lv), ['{:,}'.format(tr), '{:,}'.format(lim)], tr <= lim)
    t.show()
    print('\nper-region breakdown (triangles; draw calls the region adds; as in the build log):')
    for lv, regs in (rep.get('regions') or {}).items():
        print('  %-5s ' % lv + '  '.join('%s %s' % (k, '{:,}'.format(v['tris']) + ('+%dc' % v['calls'] if 'calls' in v else '')) for k, v in regs.items()))
    return t.code()


def m_equiv(args):
    rc, _ = run('glb_compare.py', args)
    return rc


def m_panels(args):
    if not args or args[0] not in ('dump', 'compare'):
        print('usage: check.py panels dump <out.npz>  |  check.py panels compare <old.npz> <new.npz> [...]')
        return 2
    rc, _ = run('dump_panels.py' if args[0] == 'dump' else 'compare_panels.py', args[1:])
    return 2 if rc else 0


METRICS = {'nose': m_nose, 'rear': m_rear, 'roofline': m_roofline, 'masks': m_masks, 'plan': m_plan, 'crease': m_crease, 'fold': m_fold, 'dihedral': m_dihedral, 'fender': m_fender,
           'cam': m_cam, 'lock': m_lock, 'budget': m_budget, 'equiv': m_equiv, 'panels': m_panels}


def main(argv):
    if not argv or argv[0] in ('-h', '--help', 'help', 'list'):
        print(__doc__)
        return 0
    if argv[0] not in METRICS:
        print('check.py: unknown metric %r (metrics: %s)' % (argv[0], ', '.join(METRICS)), file=sys.stderr)
        return 2
    return METRICS[argv[0]](argv[1:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
