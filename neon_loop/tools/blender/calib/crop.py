# crop.py: magnified crops of a press photo with a pixel grid (labels in photo px), for reading landmark coordinates by eye.
#   python3 crop.py OUT.png PHOTO label:x:y[:hw[:mark]] ...      (hw = half window in photo px, default 40)
import sys, os
from PIL import Image, ImageDraw
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'refs') + os.sep      # (refs/ sits next to neon_loop/)
PH = {'r81': 'press/r81.png', 'high': 'press/2026-Tesla-Roadster-official-02.jpg', 'thrust': 'press/2026-Tesla-Roadster-rear-thrusters.jpg',
      'p016': 'press2/telsa-roadster-2026-016.jpg', 'p013': 'press2/tesla-roadster-2026-013-1.jpg'}
for n in ('001', '002', '003', '004', '005', '011', '012', '014', '017', '018', '019'):
    PH['p' + n] = 'press2/tesla-roadster-2026-%s.jpg' % n


def sheet(out, photo, specs, D=360, cols=3):
    im = Image.open(REF + PH[photo]).convert('RGB')
    tiles = []
    for s in specs:
        f = s.split(':')
        lab, x, y = f[0], float(f[1]), float(f[2])
        hw = float(f[3]) if len(f) > 3 and f[3] else 40
        m = D / (2 * hw)
        x0, y0 = x - hw, y - hw
        c = im.crop((int(x0), int(y0), int(x0 + 2 * hw), int(y0 + 2 * hw))).resize((D, D), Image.LANCZOS)
        ov = Image.new('RGBA', (D, D), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        st = 5 if hw <= 25 else (10 if hw <= 60 else (20 if hw <= 120 else 50))
        for ax in (0, 1):
            o = x0 if ax == 0 else y0
            g = int(o // st + 1) * st
            while g < o + 2 * hw:
                P = (g - int(o)) * m
                big = g % (st * 2) == 0
                col = (0, 255, 255, 110) if big else (0, 200, 255, 45)
                d.line([(P, 0), (P, D)] if ax == 0 else [(0, P), (D, P)], fill=col, width=1)
                d.line([(P, 0), (P, 8)] if ax == 0 else [(0, P), (8, P)], fill=(255, 255, 0, 255), width=2)
                if big:
                    d.text((P + 2, 9) if ax == 0 else (9, P + 1), str(g), fill=(255, 255, 0, 255))
                g += st
        c = Image.alpha_composite(c.convert('RGBA'), ov).convert('RGB'); d = ImageDraw.Draw(c)
        if len(f) > 4:      # mark a point
            mx, my = (x - int(x0)) * m, (y - int(y0)) * m
            d.ellipse([mx - 4, my - 4, mx + 4, my + 4], outline=(255, 0, 255))
        lab_im = Image.new('RGB', (D, 16), (30, 30, 30)); ImageDraw.Draw(lab_im).text((3, 2), '%s %s @(%g,%g) hw %g' % (photo, lab, x, y, hw), fill=(255, 255, 255))
        t = Image.new('RGB', (D, D + 16)); t.paste(lab_im, (0, 0)); t.paste(c, (0, 16)); tiles.append(t)
    rows = (len(tiles) + cols - 1) // cols
    W = min(cols, len(tiles)) * (D + 4)
    sh = Image.new('RGB', (W, rows * (D + 20)), (60, 60, 60))
    for i, t in enumerate(tiles):
        sh.paste(t, ((i % cols) * (D + 4), (i // cols) * (D + 20)))
    sh.save(out)


if __name__ == '__main__':
    sheet(sys.argv[1], sys.argv[2], sys.argv[3:])
