"""Gera os cards SVG animados do README do perfil.

Uso:
    python scripts/render_cards.py            # busca contribuições e gera cards/
    STATIC=1 python scripts/render_cards.py   # gera tudo no estado final (sem animação)

Cada card sai em duas versões, sem fundo, para combinar com o tema do GitHub:
    cards/<nome>.svg       -> tema claro
    cards/<nome>-dark.svg  -> tema escuro
O README escolhe a versão certa com <picture> + prefers-color-scheme.

Sem dependências externas: só a biblioteca padrão do Python.
"""
import datetime as dt
import html
import json
import os
import re
import urllib.request
from collections import OrderedDict
from pathlib import Path

USER = "mateto2"
ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "cards"
DATA = ROOT / "data" / "contributions.json"
STATIC = os.environ.get("STATIC") == "1"

# ---------- temas (sem fundo: o card herda o fundo do GitHub) ----------
THEMES = {
    "light": dict(
        ink="#1F2328", muted="#656D76", line="#D0D7DE", panel="#F6F8FA",
        accent="#2F5BEA", bar="#8EA8F5",
        heat=["#EBEDF0", "#C9D6FB", "#8EA8F5", "#5277EE", "#2F5BEA"],
        snake="#1F3FB0", portrait_box=None,
    ),
    "dark": dict(
        ink="#E6EDF3", muted="#8B949E", line="#30363D", panel="#161B22",
        accent="#6F93FF", bar="#2A4C9E",
        heat=["#161B22", "#1B3270", "#2A55C9", "#4F7BF0", "#9DB5FF"],
        snake="#C9D6FB", portrait_box=None,
    ),
}
T = THEMES["light"]  # tema atual (trocado em main)

SERIF = "'Instrument Serif','Iowan Old Style','Palatino Linotype',Georgia,serif"
SANS = "'Geist','Segoe UI',system-ui,-apple-system,Helvetica,Arial,sans-serif"
MONO = "'Geist Mono',ui-monospace,'Cascadia Code',Consolas,monospace"

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


# ---------- dados ----------
def fetch_contributions():
    """Lê o calendário público de contribuições (não precisa de token)."""
    url = f"https://github.com/users/{USER}/contributions"
    req = urllib.request.Request(url, headers={"User-Agent": "profile-readme-cards"})
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    cells = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"\s+id="([^"]+)"', page)
    tips = dict(re.findall(r'for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page))
    days = {}
    for date, cid in cells:
        m = re.match(r"\s*(\d+)\s+contribution", tips.get(cid, ""))
        days[date] = int(m.group(1)) if m else 0
    if not days:
        raise RuntimeError("Calendário de contribuições vazio — o layout do GitHub mudou?")
    return dict(sorted(days.items()))


def load_days():
    try:
        days = fetch_contributions()
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps(days, indent=1), encoding="utf-8")
        return days
    except Exception as exc:  # sem internet: usa o último JSON salvo
        print(f"Aviso: usando data/contributions.json ({exc})")
        return json.loads(DATA.read_text(encoding="utf-8"))


def stats(days):
    dates = [dt.date.fromisoformat(d) for d in days]
    counts = list(days.values())
    total = sum(counts)
    active = sum(1 for c in counts if c)
    best = run = 0
    best_end = dates[-1]
    for d, c in zip(dates, counts):
        run = run + 1 if c else 0
        if run > best:
            best, best_end = run, d
    # sequência atual (hoje ainda pode estar zerado: nesse caso conta até ontem)
    seq = counts[:-1] if counts and counts[-1] == 0 else counts
    cur = 0
    for c in reversed(seq):
        if not c:
            break
        cur += 1
    months = OrderedDict()
    for d, c in zip(dates, counts):
        months[(d.year, d.month)] = months.get((d.year, d.month), 0) + c
    months = OrderedDict(list(months.items())[-12:])
    wd = [0] * 7
    for d, c in zip(dates, counts):
        wd[d.weekday()] += c
    busiest = DIAS[wd.index(max(wd))] if total else "—"
    return dict(
        total=total, active=active, best=best, best_end=best_end, cur=cur, months=months,
        busiest=busiest, first=dates[0], last=dates[-1],
    )


def fmt_date(d):
    return f"{d.day} {MESES[d.month - 1]} {d.year}"


# ---------- helpers SVG ----------
def esc(s):
    return html.escape(str(s), quote=True)


BASE_CSS = """
.serif{font-family:%s} .sans{font-family:%s} .mono{font-family:%s}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pop{0%%{opacity:0;transform:scale(.2)}70%%{opacity:1;transform:scale(1.15)}100%%{opacity:1;transform:scale(1)}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes pulse{0%%{opacity:.7;transform:scale(1)}100%%{opacity:0;transform:scale(2.8)}}
@keyframes nudge{0%%,70%%,100%%{transform:none}80%%{transform:translateX(5px)}}
@keyframes draw{from{stroke-dashoffset:var(--len)}to{stroke-dashoffset:0}}
""" % (SERIF, SANS, MONO)


def svg(w, h, body, css="", label=""):
    reduced = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{esc(label)}">'
        f"<title>{esc(label)}</title>"
        f"<style>{BASE_CSS}{'' if STATIC else css}{reduced}"
        f"{'*{animation:none!important}' if STATIC else ''}</style>{body}</svg>"
    )


def shine_gradient(gid, base, glint, dur=4, delay=1.5):
    """Gradiente cujo brilho atravessa o texto (SMIL — background-clip:text não existe em SVG)."""
    anim = "" if STATIC else (
        f'<animateTransform attributeName="gradientTransform" type="translate" '
        f'values="-1 0;1 0;1 0" keyTimes="0;.35;1" dur="{dur}s" begin="{delay}s" repeatCount="indefinite"/>'
    )
    return (
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0" gradientUnits="objectBoundingBox">'
        f'<stop offset="0" stop-color="{base}"/><stop offset=".42" stop-color="{base}"/>'
        f'<stop offset=".5" stop-color="{glint}"/><stop offset=".58" stop-color="{base}"/>'
        f'<stop offset="1" stop-color="{base}"/>{anim}</linearGradient>'
    )


def counter(x, y, value, attrs, begin=0.6, frames=18, step=0.04):
    """Número que conta de 0 até value usando quadros <set> (CSS não muda texto)."""
    if STATIC or value == 0:
        return f'<text x="{x}" y="{y}" {attrs}>{value}</text>'
    out = []
    for i in range(frames + 1):
        v = round(value * (i / frames) ** 0.6)
        start = begin + i * step
        timing = f'dur="{step:.2f}s"' if i < frames else 'fill="freeze"'
        out.append(
            f'<text x="{x}" y="{y}" {attrs} opacity="0">{v}'
            f'<set attributeName="opacity" to="1" begin="{start:.2f}s" {timing}/></text>'
        )
    return "".join(out)


# ---------- retrato ----------
def portrait_group(x, y, box_w, box_h, start=0.3):
    """Retrato ASCII; cada linha aparece 18 ms depois da anterior."""
    mpath = ROOT / "data" / "portrait_mono.json"
    cpath, path = ROOT / "data" / "portrait.json", ROOT / "data" / "portrait.txt"
    if mpath.exists():  # preto e branco: uma versão por tema
        runs = json.loads(mpath.read_text(encoding="utf-8"))["dark" if T is THEMES["dark"] else "light"]
    elif cpath.exists():  # versão colorida: lista de trechos [texto, cor] por linha
        runs = json.loads(cpath.read_text(encoding="utf-8"))["lines"]
    elif path.exists():
        runs = [[[l, None]] for l in path.read_text(encoding="utf-8").splitlines()]
    else:
        return None
    if not runs:
        return None
    lines = ["".join(t for t, _ in r) for r in runs]
    cols = max(len(l) for l in lines)
    fs = min(box_w / (cols * 0.6), box_h / len(lines))  # mono: largura ≈ 0.6em
    x += (box_w - cols * 0.6 * fs) / 2
    y += (box_h - len(lines) * fs) / 2
    cw = 0.6 * fs
    weight = "" if T is THEMES["dark"] else ' font-weight="700"'  # no branco, traço mais grosso
    out = [f'<g class="mono" font-size="{fs:.2f}" fill="{T["ink"]}"{weight}>']
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        anim = "" if STATIC else f' style="animation:fade .25s ease-out {start + i*0.018:.3f}s both"'
        out.append(f"<g{anim}>")
        col = 0
        for text, color in runs[i]:
            if text.strip():
                lead = len(text) - len(text.lstrip())
                body = text.strip()
                fill = f' fill="{color}"' if color else ""
                out.append(
                    f'<text x="{x + (col+lead)*cw:.1f}" y="{y + (i+1)*fs:.1f}" textLength="{len(body)*cw:.1f}" '
                    f'lengthAdjust="spacingAndGlyphs"{fill}>{esc(body)}</text>'
                )
            col += len(text)
        out.append("</g>")
    out.append("</g>")
    return "".join(out)


# ---------- cards ----------
def hero(s):
    w, h = 880, 400
    css = """
    .l1{animation:rise .8s ease-out .1s both}.l2{animation:rise .8s ease-out .35s both}
    .l3{animation:rise .8s ease-out .6s both}.l4{animation:fade 1s ease-out 1s both}
    .dot{animation:pulse 1.8s ease-out 1.2s infinite;transform-box:fill-box;transform-origin:center}
    .ar{animation:nudge 3s ease-in-out 2s infinite}
    """
    box = (
        f'<rect x="596" y="4" width="276" height="312" rx="14" fill="{T["portrait_box"]}"/>'
        if T["portrait_box"] else ""
    )
    # retrato ocupa a metade direita, na altura toda do card
    portrait = portrait_group(430, 4, 446, 392) or ""
    body = (
        f"<defs>{shine_gradient('nm', T['ink'], T['accent'], 5, 1.6)}</defs>"
        + box + portrait
        + '<g transform="translate(0 40)">'  # centraliza o texto na altura maior
        + f'<text x="8" y="62" class="mono l1" font-size="14" letter-spacing="2" fill="{T["muted"]}">OLÁ, EU SOU</text>'
        + f'<text x="4" y="136" class="serif l2" font-size="76" fill="{T["ink"]}">Matheus</text>'
        + f'<text x="4" y="206" class="serif l2" font-size="76" font-style="italic" fill="url(#nm)">Amaral</text>'
        + f'<text x="8" y="246" class="sans l3" font-size="19" fill="{T["ink"]}">Estudante de Ciência da Computação</text>'
        + f'<text x="8" y="272" class="sans l3" font-size="19" fill="{T["accent"]}" font-weight="600">Web Developer &amp; Automação de IA</text>'
        + '<g class="l4">'
        + f'<circle cx="14" cy="302" r="5" fill="{T["accent"]}"/><circle class="dot" cx="14" cy="302" r="5" fill="{T["accent"]}"/>'
        + f'<text x="30" y="307" class="mono" font-size="13" fill="{T["muted"]}">{s["total"]} contribuições no último ano <tspan class="ar">→</tspan></text>'
        + "</g></g>"
    )
    return svg(w, h, body, css, "Matheus Amaral — Estudante de Ciência da Computação, Web Developer e Automação de IA")


def streak(s):
    """Substitui o card externo de streak: total, sequência atual (anel) e maior sequência."""
    w, h = 880, 200
    cx, cy, r = 440, 92, 48
    circ = 2 * 3.14159 * r
    css = f"""
    .c1{{animation:rise .7s ease-out .2s both}}.c3{{animation:rise .7s ease-out .5s both}}
    .ring{{--len:{circ:.1f};stroke-dasharray:{circ:.1f};animation:draw 1.2s ease-out .3s both}}
    .fire{{animation:pop .6s ease-out 1.3s both;transform-box:fill-box;transform-origin:center}}
    .lb{{animation:fade .8s ease-out .9s both}}
    """
    num = f'class="serif" font-size="40" text-anchor="middle" fill="{T["ink"]}"'
    lbl = lambda x, y, t, c: f'<text x="{x}" y="{y}" class="sans lb" font-size="15" text-anchor="middle" fill="{c}" font-weight="600">{t}</text>'
    sub = lambda x, y, t: f'<text x="{x}" y="{y}" class="mono lb" font-size="12" text-anchor="middle" fill="{T["muted"]}">{t}</text>'
    body = (
        f'<line x1="293" y1="40" x2="293" y2="160" stroke="{T["line"]}"/>'
        f'<line x1="587" y1="40" x2="587" y2="160" stroke="{T["line"]}"/>'
        # total
        + '<g class="c1">' + counter(146, 102, s["total"], num, begin=0.3)
        + lbl(146, 138, "Contribuições totais", T["ink"])
        + sub(146, 160, f"{fmt_date(s['first'])} – hoje") + "</g>"
        # sequência atual
        + f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{T["line"]}" stroke-width="5"/>'
        + f'<circle class="ring" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{T["accent"]}" stroke-width="5" '
        f'stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>'
        + f'<path class="fire" d="M{cx} {cy-r-16}c6 7 10 11 10 17a10 10 0 0 1-20 0c0-4 2-7 4-9 0 4 2 6 4 6-1-5 0-9 2-14z" '
        f'fill="{T["accent"]}"/>'
        + counter(cx, cy + 14, s["cur"], num, begin=0.5)
        + lbl(cx, 172, "Sequência atual", T["accent"])
        + sub(cx, 192, "dias seguidos")
        # maior sequência
        + '<g class="c3">' + counter(734, 102, s["best"], num, begin=0.6)
        + lbl(734, 138, "Maior sequência", T["ink"])
        + sub(734, 160, f"até {fmt_date(s['best_end'])}") + "</g>"
    )
    return svg(w, h, body, css, f"Sequência atual de {s['cur']} dias; maior sequência {s['best']}; {s['total']} contribuições")


def snake(days):
    """Grade de contribuições com uma cobrinha que anda de um lado para o outro e 'come' os quadrados."""
    w = 880
    items = list(days.items())
    first = dt.date.fromisoformat(items[0][0])
    pad = (first.weekday() + 1) % 7  # GitHub começa a semana no domingo
    peak = max([c for _, c in items] + [1])
    cell, gap, x0, y0 = 12, 3.2, 26, 36
    step = cell + gap
    ncols = (len(items) + pad + 6) // 7
    h = int(y0 + 7 * step + 20)
    grid = {}
    for i, (d, c) in enumerate(items):
        col, row = divmod(i + pad, 7)
        grid[(col, row)] = (d, c)

    # caminho em zigue-zague, linha por linha (esquerda→direita, depois direita→esquerda)
    order = []
    for row in range(7):
        cols = range(ncols) if row % 2 == 0 else range(ncols - 1, -1, -1)
        order += [(c, row) for c in cols]
    pos = {p: i for i, p in enumerate(order)}
    tick = 0.045  # segundos por casa
    walk = len(order) * tick
    dur = walk + 2.5  # pausa no fim antes de recomeçar
    heat = T["heat"]

    rects = []
    for (col, row), (d, c) in grid.items():
        x, y = x0 + col * step, y0 + row * step
        lvl = 0 if c == 0 else min(4, 1 + int(3 * c / peak))
        anim = ""
        if c and not STATIC:
            t = pos[(col, row)] * tick / dur
            anim = (
                f'<animate attributeName="fill" values="{heat[lvl]};{heat[lvl]};{heat[0]};{heat[0]}" '
                f'keyTimes="0;{t:.4f};{min(t+0.002, .999):.4f};1" dur="{dur:.2f}s" repeatCount="indefinite"/>'
            )
        rects.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="3" fill="{heat[lvl]}">'
            f"<title>{d}: {c}</title>{anim}</rect>"
        )

    snake_svg = ""
    if not STATIC:
        pts = [(x0 + c * step + cell / 2, y0 + r * step + cell / 2) for c, r in order]
        d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        segs = []
        n = 6
        for k in range(n):
            size = cell - 1 - k * 1.1
            delay = k * tick * 1.0
            op = 1 - k * 0.12
            # cada gomo segue o mesmo caminho, um pouco atrás do anterior
            segs.append(
                f'<rect x="{-size/2:.1f}" y="{-size/2:.1f}" width="{size:.1f}" height="{size:.1f}" rx="{size/3:.1f}" '
                f'fill="{T["snake"]}" opacity="0">'
                f'<animateMotion path="{d}" dur="{dur:.2f}s" begin="{delay:.3f}s" repeatCount="indefinite" '
                f'keyPoints="0;1;1" keyTimes="0;{walk/dur:.4f};1" calcMode="linear"/>'
                f'<animate attributeName="opacity" values="{op:.2f};{op:.2f};0;0" keyTimes="0;{walk/dur:.4f};{min(walk/dur+.01,.999):.4f};1" '
                f'dur="{dur:.2f}s" begin="{delay:.3f}s" repeatCount="indefinite"/></rect>'
            )
        snake_svg = "<g>" + "".join(reversed(segs)) + "</g>"

    body = (
        f'<text x="{x0}" y="22" class="mono" font-size="13" letter-spacing="2" fill="{T["muted"]}">'
        f"CONTRIBUIÇÕES · {sum(days.values())} NO ÚLTIMO ANO</text>"
        + "".join(rects) + snake_svg
    )
    return svg(w, h, body, "", "Gráfico de contribuições do último ano com uma cobrinha animada")


def activity(s):
    w, h = 880, 300
    months = list(s["months"].items())
    peak = max([v for _, v in months] + [1])
    best_i = max(range(len(months)), key=lambda i: months[i][1]) if months else 0
    x0, base, maxh, bw, gap = 40, 220, 140, 48, 19
    css = ".hd{animation:rise .7s ease-out .1s both}.st{animation:fade .8s ease-out 1.6s both}"
    bars = []
    for i, ((y, m), v) in enumerate(months):
        bh = max(3, v / peak * maxh)
        x = x0 + i * (bw + gap)
        color = T["accent"] if i == best_i and v else T["bar"]
        d = 0.3 + i * 0.07
        anim = "" if STATIC else f' style="animation:grow .7s cubic-bezier(.2,.8,.3,1) {d:.2f}s both;transform-box:fill-box;transform-origin:bottom"'
        bars.append(f'<rect x="{x}" y="{base-bh:.1f}" width="{bw}" height="{bh:.1f}" rx="6" fill="{color}" opacity="{1 if v else .35}"{anim}/>')
        bars.append(f'<text x="{x+bw/2}" y="{base+22}" class="mono" font-size="12" text-anchor="middle" fill="{T["muted"]}">{MESES[m-1]}</text>')
        if i == best_i and v:
            pa = "" if STATIC else f' style="animation:pop .5s ease-out {d+0.7:.2f}s both;transform-box:fill-box;transform-origin:center"'
            bars.append(f'<text x="{x+bw/2}" y="{base-bh-10:.1f}" class="sans" font-size="15" font-weight="600" fill="{T["accent"]}" text-anchor="middle"{pa}>{v}</text>')
    stat = lambda x, n, l: (
        f'<text x="{x}" y="282" class="sans" font-size="14" fill="{T["muted"]}">{l} '
        f'<tspan class="serif" font-size="20" fill="{T["ink"]}">{n}</tspan></text>'
    )
    body = (
        f'<text x="40" y="34" class="serif hd" font-size="30" fill="{T["ink"]}">Atividade por mês</text>'
        + f'<text x="840" y="34" class="mono hd" font-size="13" fill="{T["muted"]}" text-anchor="end">ÚLTIMOS 12 MESES</text>'
        + f'<line x1="40" y1="{base}" x2="840" y2="{base}" stroke="{T["line"]}"/>'
        + "".join(bars)
        + '<g class="st">'
        + stat(40, s["total"], "total")
        + stat(210, s["active"], "dias ativos")
        + stat(400, s["best"], "maior sequência")
        + stat(620, s["busiest"], "dia favorito:")
        + "</g>"
    )
    return svg(w, h, body, css, f"{s['total']} contribuições nos últimos 12 meses")


def repo_card(name, desc, lang, color, delay):
    w, h = 433, 150
    css = f".rc{{animation:rise .8s ease-out {delay}s both}}.ar{{animation:nudge 3s ease-in-out {delay+1:.1f}s infinite}}"
    words, lines, cur = desc.split(), [], ""
    for wd in words:
        if len(cur) + len(wd) > 48:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    lines.append(cur)
    body = (
        f'<defs><clipPath id="cp"><rect x="1" y="1" width="{w-2}" height="{h-2}" rx="14"/></clipPath></defs>'
        '<g class="rc">'
        + f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="14" fill="none" stroke="{T["line"]}" stroke-width="1.5"/>'
        + f'<rect x="0" y="0" width="7" height="{h}" fill="{color}" clip-path="url(#cp)"/>'
        + f'<text x="28" y="46" class="serif" font-size="27" fill="{T["ink"]}">{esc(name)} <tspan class="ar sans" font-size="18">↗</tspan></text>'
        + "".join(
            f'<text x="28" y="{80 + i*21}" class="sans" font-size="14.5" fill="{T["muted"]}">{esc(l)}</text>' for i, l in enumerate(lines[:2])
        )
        + f'<circle cx="34" cy="{h-24}" r="5" fill="{color}"/>'
        + f'<text x="46" y="{h-19}" class="mono" font-size="12.5" fill="{T["ink"]}">{esc(lang)}</text>'
        + "</g>"
    )
    return svg(w, h, body, css, f"Repositório {name}")


# ---------- tecnologias ----------
# (slug do ícone em data/icons.json, nome, cor no tema claro, cor no tema escuro)
TECH = [
    ("LANGUAGES", [
        ("typescript", "TypeScript", "#3178C6", "#3178C6"),
        ("javascript", "JavaScript", "#C9A800", "#F7DF1E"),
        ("python", "Python", "#3776AB", "#5A9FD4"),
        ("html5", "HTML", "#E34F26", "#F06529"),
        ("css3", "CSS", "#1572B6", "#3C9CD7"),
    ]),
    ("FRONTEND", [
        ("react", "React", "#0A9CC4", "#61DAFB"),
        ("tailwindcss", "Tailwind CSS", "#06B6D4", "#38BDF8"),
        ("vite", "Vite", "#646CFF", "#8B91FF"),
        ("figma", "Figma", "#F24E1E", "#F24E1E"),
    ]),
    ("BACKEND & CLOUD", [
        ("nodedotjs", "Node.js", "#5FA04E", "#6CC24A"),
        ("docker", "Docker", "#2496ED", "#2496ED"),
        ("git", "Git", "#F05032", "#F05032"),
        ("vercel", "Vercel", "#000000", "#FFFFFF"),
    ]),
    ("DATABASE & TESTING", [
        ("postgresql", "PostgreSQL", "#4169E1", "#6F8FEF"),
        ("supabase", "Supabase", "#3ECF8E", "#3ECF8E"),
        ("vitest", "Vitest", "#6E9F18", "#8CC63F"),
    ]),
    ("DATA & BI", [
        ("pandas", "Pandas", "#150458", "#E70488"),
        ("microsoftexcel", "Excel", "#217346", "#33C481"),
        ("powerquery", "Power Query", "#217346", "#33C481"),
        ("powerbi", "Power BI", "#D4A900", "#F2C811"),
        ("jupyter", "Jupyter", "#F37626", "#F37626"),
    ]),
    ("AUTOMATION", [
        ("n8n", "n8n", "#EA4B71", "#EA4B71"),
        ("githubactions", "GitHub Actions", "#2088FF", "#2088FF"),
    ]),
    ("AI & LLM", [
        ("openai", "OpenAI", "#000000", "#FFFFFF"),
        ("claude", "Claude", "#D97757", "#D97757"),
        ("googlegemini", "Gemini", "#8E75B2", "#A58BD3"),
    ]),
]
# Power Query não tem ícone oficial no Simple Icons: tabela com seta (desenho próprio, 24x24)
POWERQUERY = "M2 3h14v4H2zm0 6h6v4H2zm8 0h6v4h-6zm-8 6h6v4H2zm8 0h6v4h-6zm9.5-5.5L23 13l-3.5 3.5V14H17v-2h2.5z"


def tech():
    """Card 'Tech Stack': uma categoria por linha, com chips de ícone + nome."""
    icons = json.loads((ROOT / "data" / "icons.json").read_text(encoding="utf-8"))
    icons["powerquery"] = POWERQUERY
    w = 880
    top, rowh, label_w = 70, 46, 190
    h = top + len(TECH) * rowh + 4
    dark = T is THEMES["dark"]
    hd = "" if STATIC else ' style="animation:rise .7s ease-out .1s both"'
    out = [
        f'<g{hd}><text x="8" y="34" class="serif" font-size="30" fill="{T["ink"]}">Tech Stack</text>'
        f'<text x="872" y="34" class="mono" font-size="13" fill="{T["muted"]}" text-anchor="end">{sum(len(i) for _, i in TECH)} TOOLS</text>'
        f'<line x1="8" y1="50" x2="872" y2="50" stroke="{T["line"]}"/></g>'
    ]
    for ri, (title, items) in enumerate(TECH):
        y = top + ri * rowh
        d0 = 0.2 + ri * 0.1
        anim = "" if STATIC else f' style="animation:rise .5s ease-out {d0:.2f}s both"'
        out.append(
            f'<g{anim}><rect x="8" y="{y+9}" width="3" height="16" rx="1.5" fill="{T["accent"]}"/>'
            f'<text x="20" y="{y+22}" class="mono" font-size="12.5" letter-spacing="1.5" fill="{T["muted"]}">{esc(title)}</text></g>'
        )
        x = label_w
        for ci, (slug, name, c_light, c_dark) in enumerate(items):
            color = c_dark if dark else c_light
            cw = 44 + len(name) * 7.9
            delay = d0 + 0.15 + ci * 0.06
            anim = "" if STATIC else f' style="animation:pop .45s ease-out {delay:.2f}s both;transform-box:fill-box;transform-origin:center"'
            out.append(
                f"<g{anim}>"
                f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="34" rx="9" fill="{T["panel"]}" stroke="{T["line"]}"/>'
                f'<path d="{icons[slug]}" fill="{color}" transform="translate({x+10:.1f} {y+8}) scale(.75)"/>'
                f'<text x="{x+36:.1f}" y="{y+22}" class="sans" font-size="14" fill="{T["ink"]}">{esc(name)}</text>'
                "</g>"
            )
            x += cw + 8
    return svg(w, h, "".join(out), "", "Tech Stack — " + "; ".join(
        f"{t}: " + ", ".join(n for _, n, _, _ in i) for t, i in TECH))


def main():
    global T
    days = load_days()
    s = stats(days)
    CARDS.mkdir(exist_ok=True)
    for theme, suffix in (("light", ""), ("dark", "-dark")):
        T = THEMES[theme]
        out = {
            "hero": hero(s),
            "streak": streak(s),
            "snake": snake(days),
            "activity": activity(s),
            "tech": tech(),
            "repo-savett": repo_card("SAVETT", "IA de inteligência financeira — app e site para salvar seu dinheiro.", "TypeScript · React", "#0E9F6E", 0.2),
            "repo-bi": repo_card("bi-inflacao-brasil", "BI da inflação no Brasil (2021–2026) com dados do IBGE, BCB e Ipeadata.", "Jupyter · Power BI", "#F2B705", 0.4),
        }
        for name, content in out.items():
            (CARDS / f"{name}{suffix}.svg").write_text(content, encoding="utf-8")
    print(f"cards gerados — total={s['total']} sequência atual={s['cur']} maior={s['best']}")


if __name__ == "__main__":
    main()
