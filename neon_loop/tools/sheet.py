# Contact sheet: python3 tools/sheet.py out.png cols cellW img1 img2 ...  (labels each cell with its file name)
import sys
from PIL import Image, ImageDraw
out, cols, cw = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
ims = [Image.open(p).convert('RGB') for p in sys.argv[4:]]
ch = round(cw * ims[0].height / ims[0].width)
rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (cols * cw, rows * ch), (0, 0, 0))
d = ImageDraw.Draw(sheet)
for k, (im, p) in enumerate(zip(ims, sys.argv[4:])):
    x, y = (k % cols) * cw, (k // cols) * ch
    sheet.paste(im.resize((cw, ch), Image.LANCZOS), (x, y))
    d.rectangle([x, y, x + 70, y + 16], fill=(0, 0, 0)); d.text((x + 3, y + 2), p.split('/')[-1][:-4], fill=(255, 255, 0))
sheet.save(out)
