"""Converte uma foto em retrato ASCII (data/portrait.txt). Rode uma vez, localmente.

Uso:
    pip install pillow
    python scripts/make_portrait.py caminho/da/foto.jpg [--cols 72] [--contrast 1.6] [--invert]

Dica: foto de rosto bem iluminada, fundo liso, recortada perto do rosto.
Depois rode `python scripts/render_cards.py` para atualizar o card.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

# do mais "escuro" (mais tinta) ao mais claro
RAMP = "@%#*+=-:. "  # noqa: E501
OUT = Path(__file__).resolve().parent.parent / "data" / "portrait.txt"


def sticker_mask(rgb, white=200):
    """Separa a figura do fundo usando o contorno branco de 'adesivo' em volta dela.

    1) a partir do centro, pinta tudo que não é branco (a figura);
    2) o que sobra e encosta na borda da imagem é fundo; o resto (olhos, brilhos) volta para a figura.
    """
    from collections import deque

    w, h = rgb.size
    px = rgb.load()
    is_white = [[min(px[x, y]) >= white for x in range(w)] for y in range(h)]

    def flood(starts, ok):
        seen = [[False] * w for _ in range(h)]
        q = deque()
        for x, y in starts:
            if ok(x, y):
                seen[y][x] = True
                q.append((x, y))
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and ok(nx, ny):
                    seen[ny][nx] = True
                    q.append((nx, ny))
        return seen

    cx, cy = w // 2, int(h * 0.55)
    starts = [(cx + dx, cy + dy) for dx in range(-20, 21, 5) for dy in range(-20, 21, 5)]
    fig = flood(starts, lambda x, y: not is_white[y][x])
    border = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + \
             [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
    outside = flood(border, lambda x, y: not fig[y][x])
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            if not outside[y][x]:
                mp[x, y] = 255
    return mask


def color_portrait(src, mask, a):
    """Caracteres coloridos para fundo escuro: claro = caractere denso, contorno preto = vazio."""
    import json

    ramp = " .:-=+*#%@"
    rows = max(1, round(src.height / src.width * a.cols * 0.5))
    small = src.resize((a.cols, rows), Image.LANCZOS)
    m = mask.resize((a.cols, rows), Image.LANCZOS).load()
    q = small.quantize(colors=a.colors, method=Image.Quantize.MEDIANCUT).convert("RGB").load()
    # brilho da cor (canal V do HSV): azul vivo e marrom ficam densos, só o contorno preto some
    lum = small.convert("HSV").split()[2].load()
    lines = []
    for y in range(rows):
        runs = []
        for x in range(a.cols):
            if m[x, y] < 128:
                ch, col = " ", None
            else:
                ch = ramp[min(len(ramp) - 1, lum[x, y] * len(ramp) // 256)]
                col = "#%02X%02X%02X" % q[x, y] if ch != " " else None
            if runs and runs[-1][1] == col:
                runs[-1][0] += ch
            else:
                runs.append([ch, col])
        lines.append(runs)
    out = OUT.with_suffix(".json")
    out.write_text(json.dumps({"cols": a.cols, "lines": lines}, ensure_ascii=False), encoding="utf-8")
    print(f"Retrato colorido salvo em {out} ({a.cols}x{rows})")


def mono_portrait(src, mask, a):
    """Preto e branco, sem fundo, com uma versão para cada tema do GitHub (data/portrait_mono.json).

    claro : parte clara do desenho = caractere denso e escuro (efeito xilogravura)
    escuro: parte clara do desenho  = caractere denso e claro
    """
    import json

    ramp = " .:-=+*#%@"
    rows = max(1, round(src.height / src.width * a.cols * 0.5))
    small = src.resize((a.cols, rows), Image.LANCZOS)
    m = mask.resize((a.cols, rows), Image.LANCZOS).load()
    L = ImageOps.autocontrast(small.convert("L"), cutoff=2).load()
    V = small.convert("HSV").split()[2].load()
    themes = {
        # (densidade a partir do pixel, cinza a partir do pixel)
        "light": (lambda x, y: V[x, y],
                  lambda x, y: "#0D1117" if V[x, y] > 200 else "#2D333B" if V[x, y] > 140 else "#57606A"),
        "dark": (lambda x, y: V[x, y],
                 lambda x, y: "#E6EDF3" if V[x, y] > 200 else "#B1BAC4" if V[x, y] > 140 else "#7D8590"),
    }
    out = {"cols": a.cols}
    for name, (dens, gray) in themes.items():
        lines = []
        for y in range(rows):
            runs = []
            for x in range(a.cols):
                ch, col = " ", None
                if m[x, y] >= 128:
                    ch = ramp[min(len(ramp) - 1, dens(x, y) * len(ramp) // 256)]
                    col = gray(x, y) if ch != " " else None
                if runs and runs[-1][1] == col:
                    runs[-1][0] += ch
                else:
                    runs.append([ch, col])
            lines.append(runs)
        out[name] = lines
    path = OUT.parent / "portrait_mono.json"
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"Retrato P&B salvo em {path} ({a.cols}x{rows})")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("foto")
    p.add_argument("--cols", type=int, default=72)
    p.add_argument("--contrast", type=float, default=1.6)
    p.add_argument("--invert", action="store_true", help="inverte claro/escuro")
    p.add_argument("--sticker", action="store_true",
                   help="remove o fundo de desenhos com contorno branco de adesivo")
    p.add_argument("--debug", help="salva a imagem recortada neste caminho")
    p.add_argument("--color", action="store_true",
                   help="retrato colorido para fundo escuro (gera data/portrait.json)")
    p.add_argument("--mono", action="store_true",
                   help="preto e branco, sem fundo, versões clara e escura (data/portrait_mono.json)")
    p.add_argument("--colors", type=int, default=10, help="nº de cores no modo --color")
    a = p.parse_args()

    src = ImageOps.exif_transpose(Image.open(a.foto)).convert("RGB")
    if a.sticker:
        small = src.resize((400, round(400 * src.height / src.width)))
        mask = sticker_mask(small).resize(src.size)
        bg = Image.new("RGB", src.size, (255, 255, 255))
        src = Image.composite(src, bg, mask).crop(mask.getbbox())
    else:
        mask = Image.new("L", src.size, 255)
    if a.debug:
        src.save(a.debug)
    if a.mono:
        return mono_portrait(src, mask.crop(mask.getbbox()) if a.sticker else mask, a)
    if a.color:
        return color_portrait(src, mask.crop(mask.getbbox()) if a.sticker else mask, a)
    img = src.convert("L")
    img = ImageOps.autocontrast(img, cutoff=2)
    img = ImageEnhance.Contrast(img).enhance(a.contrast)
    if a.invert:
        img = ImageOps.invert(img)
    # caracteres monoespaçados são ~2x mais altos que largos
    rows = max(1, round(img.height / img.width * a.cols * 0.5))
    img = img.resize((a.cols, rows), Image.LANCZOS)
    px = img.load()
    lines = [
        "".join(
            " " if px[x, y] >= 225 else RAMP[px[x, y] * (len(RAMP) - 2) // 225]
            for x in range(a.cols)
        ).rstrip()
        for y in range(rows)
    ]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Retrato salvo em {OUT} ({a.cols}x{rows})")


if __name__ == "__main__":
    main()
