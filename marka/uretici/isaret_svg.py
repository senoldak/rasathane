import sys, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("c", Path(__file__).with_name("isaret_png.py"))
sys.argv = ["x", str(Path(__file__).parent / "_cikti")]
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
D = Path(sys.argv[1] if False else r"C:/DEPO/KOD DEPOSU/para/rasathane/marka")
def svg(zemin, murekkep, soluk, ad, olcek=0.42):
    W = 1000; R = W * olcek; m = W / 2
    p = lambda x, y: (round(m + R * x, 2), round(m + R * y, 2))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{W}" viewBox="0 0 {W} {W}">']
    if zemin: out.append(f'<rect width="{W}" height="{W}" fill="{zemin}"/>')
    for x, y in c.SOLUK_YILDIZ:
        px, py = p(x, y); out.append(f'<circle cx="{px}" cy="{py}" r="{round(0.045*R,2)}" fill="{soluk}"/>')
    pts = " ".join(f"{a},{b}" for a, b in (p(x, y) for x, y, _ in c.YILDIZ))
    out.append(f'<polyline points="{pts}" fill="none" stroke="{soluk}" stroke-width="{round(0.085*R,2)}" stroke-linejoin="round"/>')
    for i, (x, y, r) in enumerate(c.YILDIZ):
        px, py = p(x, y); out.append(f'<circle cx="{px}" cy="{py}" r="{round(r*R,2)}" fill="{c.VURGU if i == 3 else murekkep}"/>')
    out.append("</svg>")
    (D / f"{ad}.svg").write_text("\n".join(out) + "\n", encoding="utf-8")
svg(None, c.MUREKKEP, c.SOLUK, "rasathane-isaret")
svg("#151515", "#f6f5f0", "#55544f", "rasathane-isaret-koyu-zemin")
svg(c.KAGIT, c.MUREKKEP, c.SOLUK, "rasathane-telegram-profil")
