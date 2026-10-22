#!/usr/bin/env python3
"""
overlay.py <kind> [args ...]  --  the one entry point for the overlay tools (a model drawn over the press photos through the matched cameras).

It only forwards: everything after <kind> goes unchanged to the engine script, so  `overlay.py views --glb x.glb`  is exactly
`Blender -b --python tools/blender/overlay_views.py -- --glb x.glb`.  Run `overlay.py <kind> --help` for the engine's own options (its docstring is printed).

  kind     what                                                                                     engine (runs in)
  views    Workbench render of a GLB from the matched cameras, 55 % over the photo, ~3 s per view   overlay_views.py (Blender)
  lines    3-D polylines (lines.json) drawn on the photos; --crop/--zoom/--hubs/--unproj; no render lines_overlay.py (Blender)
  proj     3-D polylines on a photo or on a render of the same view (module + script)               proj_overlay.py (python3, numpy)
  outline  silhouette outlines of mask sets (mask_views.py) on a zoomed photo crop                  outline_overlay.py (python3)
  nose     old vs new nose lines (lines.json of `overlay.py dump`) on photo | render pairs          nose_overlay.py (python3)
  rear     the model's own rear curves (arc, crest, glass edge) on photo | render pairs; --arc-table rear_overlay.py (python3)
  reading  my reading of the roof-to-tail lines on the photos (starting values for the rear)        reading_overlay.py (python3)
  fender   the model's L5 / U / L on a photo + the p016 photo lines 1-4 (fender3); --design <dir> for the BEFORE   fender_overlay.py (python3, numpy)
  dump     helper: nose + side lines of a design (<dir>/design2.py) -> lines.json for proj / nose   dump_lines.py (python3)

Blender is taken from $BLENDER or /Applications/Blender.app/Contents/MacOS/Blender.  Examples (from the project root):
  python3 tools/blender/overlay.py views --glb shots/regions/rear/build/car_hi.raw.glb --out shots/regions/rear/r1/ov --views p017,r81,high
  python3 tools/blender/overlay.py rear --out shots/regions/rear/r1/ov --render-dir shots/regions/rear/r1 --views p017,r81 --ear
  python3 tools/blender/overlay.py dump tools/blender lines_new.json && python3 tools/blender/overlay.py nose p016 <photo> <render> lines_old.json lines_new.json 0,380,1000,900 1.5 out.png
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')
KINDS = {                     # kind: (engine script, runner)
    'views': ('overlay_views.py', 'blender'),
    'lines': ('lines_overlay.py', 'blender'),
    'proj': ('proj_overlay.py', 'python'),
    'outline': ('outline_overlay.py', 'python'),
    'nose': ('nose_overlay.py', 'python'),
    'rear': ('rear_overlay.py', 'python'),
    'reading': ('reading_overlay.py', 'python'),
    'dump': ('dump_lines.py', 'python'),
    'fender': ('fender_overlay.py', 'python'),
}


def command(kind, args):
    script, runner = KINDS[kind]
    path = os.path.join(HERE, script)
    if runner == 'blender':
        return [BLENDER, '-b', '--python', path, '--'] + args
    return [sys.executable, path] + args


def engine_doc(script):
    parts = open(os.path.join(HERE, script)).read().split('"""')
    return parts[1] if len(parts) > 2 else script


def main(argv):
    if not argv or argv[0] in ('-h', '--help', 'help', 'list'):
        print(__doc__)
        return 0
    if argv[0] not in KINDS:
        print('overlay.py: unknown kind %r (kinds: %s)' % (argv[0], ', '.join(KINDS)), file=sys.stderr)
        return 2
    kind, args = argv[0], argv[1:]
    if args[:1] in (['--help'], ['-h']):
        print(engine_doc(KINDS[kind][0]))
        return 0
    return subprocess.call(command(kind, args))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
