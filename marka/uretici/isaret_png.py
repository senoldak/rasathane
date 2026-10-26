"""Rasathane işareti v2: kalın takımyıldız, yazısız; kare + daire kırpma önizlemesi."""

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(sys.argv[1])
MUREKKEP, KAGIT, SOLUK, VURGU = "#151515", "#f6f5f0", "#bdb9ad", "#2d4fd6"
S = 4
W = 1000

# (x, y, yarıçap) birim karede; çizgi sırası 0→1→2→3→4→5
YILDIZ = [(-0.78, 0.50, 0.075), (-0.36, 0.08, 0.10), (0.02, 0.30, 0.065), (0.24, -0.34, 0.135),
          (0.66, -0.12, 0.08), (0.80, -0.70, 0.06)]
SOLUK_YILDIZ = [(-0.40, -0.62), (-0.82, -0.18), (0.60, 0.48), (0.05, 0.78), (0.92, 0.18)]
# Takımyıldızı kutusuna göre ortala
_x0 = min(x - r for x, _, r in YILDIZ)
_x1 = max(x + r for x, _, r in YILDIZ)
_y0 = min(y - r for _, y, r in YILDIZ)
_y1 = max(y + r for _, y, r in YILDIZ)
_dx, _dy = -(_x0 + _x1) / 2, -(_y0 + _y1) / 2
YILDIZ = [(x + _dx, y + _dy, r * 1.35) for x, y, r in YILDIZ]
SOLUK_YILDIZ = [(x + _dx, y + _dy) for x, y in SOLUK_YILDIZ]


def ciz(zemin: str, murekkep: str, soluk: str, ad: str, olcek: float = 0.42) -> None:
    im = Image.new("RGB", (W * S, W * S), zemin)
    d = ImageDraw.Draw(im)
    R = W * olcek
    c = W / 2

    def p(x: float, y: float) -> tuple[float, float]:
        return (c + R * x) * S, (c + R * y) * S

    for x, y in SOLUK_YILDIZ:
        px, py = p(x, y)
        r = 0.045 * R * S
        d.ellipse((px - r, py - r, px + r, py + r), fill=soluk)
    for (x1, y1, _), (x2, y2, _) in zip(YILDIZ, YILDIZ[1:]):
        d.line((*p(x1, y1), *p(x2, y2)), fill=soluk, width=int(0.085 * R * S))
    for i, (x, y, r) in enumerate(YILDIZ):
        px, py = p(x, y)
        rr = r * R * S
        d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=VURGU if i == 3 else murekkep)
    im = im.resize((W, W), Image.LANCZOS)
    im.save(OUT / f"{ad}.png")
    # Telegram önizlemesi: daire kırpma
    maske = Image.new("L", (W, W), 0)
    ImageDraw.Draw(maske).ellipse((0, 0, W, W), fill=255)
    daire = Image.new("RGB", (W, W), "#ffffff")
    daire.paste(im, (0, 0), maske)
    daire.resize((300, 300), Image.LANCZOS).save(OUT / f"{ad}-daire-onizleme.png")


OUT.mkdir(parents=True, exist_ok=True)
ciz(KAGIT, MUREKKEP, SOLUK, "rasathane-isaret")
ciz("#151515", "#f6f5f0", "#55544f", "rasathane-isaret-koyu-zemin")

a = Image.open(OUT / "rasathane-isaret.png").resize((500, 500), Image.LANCZOS)
b = Image.open(OUT / "rasathane-isaret-koyu-zemin.png").resize((500, 500), Image.LANCZOS)
da = Image.open(OUT / "rasathane-isaret-daire-onizleme.png").resize((160, 160))
db = Image.open(OUT / "rasathane-isaret-koyu-zemin-daire-onizleme.png").resize((160, 160))
k = Image.new("RGB", (1040, 700), "#e2e0d8")
k.paste(a, (0, 0))
k.paste(b, (540, 0))
k.paste(da, (170, 520))
k.paste(db, (710, 520))
k.save(OUT / "karsilastir-v2.png")
