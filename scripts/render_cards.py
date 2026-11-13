"""Gera os cards SVG animados do README do perfil.

Uso:
    python scripts/render_cards.py            # busca contribuições e gera cards/
    STATIC=1 python scripts/render_cards.py   # gera tudo no estado final (sem animação)

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

# ---------- paleta "papel e tinta" ----------
PAPER = "#F6F1E7"
PAPER_2 = "#EFE8DA"
INK = "#1C1B19"
MUTED = "#6B665C"
LINE = "#D9D0BE"
GREEN = "#0E9F6E"
BLUE = "#2F5BEA"
YELLOW = "#F2B705"
RED = "#E4572E"

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
    # sequências
    best = cur = run = 0
    for c in counts:
        run = run + 1 if c else 0
        best = max(best, run)
    # sequência atual (hoje ainda pode estar zerado: ignora o último dia nesse caso)
    seq = counts[:-1] if counts and counts[-1] == 0 else counts
    for c in reversed(seq):
        if not c:
            break
        cur += 1
    # meses (últimos 12)
    months = OrderedDict()
    for d, c in zip(dates, counts):
        key = (d.year, d.month)
        months[key] = months.get(key, 0) + c
    months = OrderedDict(list(months.items())[-12:])
    # dia da semana mais ativo
    wd = [0] * 7
    for d, c in zip(dates, counts):
        wd[d.weekday()] += c
    busiest = DIAS[wd.index(max(wd))] if total else "—"
    return dict(total=total, active=active, best=best, cur=cur, months=months, busiest=busiest)


# ---------- helpers SVG ----------
def esc(s):
    return html.escape(str(s), quote=True)


def svg(w, h, body, css="", label=""):
    reduced = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{esc(label)}">'
        f"<title>{esc(label)}</title>"
        f"<style>{BASE_CSS}{'' if STATIC else css}{reduced}"
        f"{'*{animation:none!important}' if STATIC else ''}</style>{body}</svg>"
    )


BASE_CSS = f"""
.serif{{font-family:{SERIF}}} .sans{{font-family:{SANS}}} .mono{{font-family:{MONO}}}
.ink{{fill:{INK}}} .muted{{fill:{MUTED}}}
@keyframes rise{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:none}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes pop{{0%{{opacity:0;transform:scale(.2)}}70%{{opacity:1;transform:scale(1.15)}}100%{{opacity:1;transform:scale(1)}}}}
@keyframes grow{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
@keyframes pulse{{0%{{opacity:.7;transform:scale(1)}}100%{{opacity:0;transform:scale(2.8)}}}}
@keyframes nudge{{0%,70%,100%{{transform:none}}80%{{transform:translateX(5px)}}}}
@keyframes swing{{0%{{opacity:0;transform:translateY(60px) rotate(-6deg)}}65%{{opacity:1;transform:translateY(-6px) rotate(1.5deg)}}100%{{opacity:1;transform:none}}}}
"""


def frame(w, h, r=18):
    return (
        f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="{r}" fill="{PAPER}" stroke="{LINE}" stroke-width="1.5"/>'
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


def counter(x, y, value, cls, style, begin=0.6, frames=18, step=0.04):
    """Número que conta de 0 até value usando quadros <set> (CSS não muda texto)."""
    if STATIC or value == 0:
        return f'<text x="{x}" y="{y}" class="{cls}" style="{style}">{value}</text>'
    out = []
    for i in range(frames + 1):
        v = round(value * (i / frames) ** 0.6)
        start = begin + i * step
        if i < frames:
            out.append(
                f'<text x="{x}" y="{y}" class="{cls}" style="{style}" opacity="0">{v}'
                f'<set attributeName="opacity" to="1" begin="{start:.2f}s" dur="{step:.2f}s"/></text>'
            )
        else:
            out.append(
                f'<text x="{x}" y="{y}" class="{cls}" style="{style}" opacity="0">{v}'
                f'<set attributeName="opacity" to="1" begin="{start:.2f}s" fill="freeze"/></text>'
            )
    return "".join(out)


# ---------- cards ----------
def hero(s):
    w, h = 880, 300
    css = """
    .l1{animation:rise .8s ease-out .1s both}.l2{animation:rise .8s ease-out .35s both}
    .l3{animation:rise .8s ease-out .6s both}.l4{animation:fade 1s ease-out 1s both}
    .dot{animation:pulse 1.8s ease-out 1.2s infinite;transform-box:fill-box;transform-origin:center}
    .ar{animation:nudge 3s ease-in-out 2s infinite}
    """
    body = (
        frame(w, h)
        + f"<defs>{shine_gradient('nm', INK, GREEN, 5, 1.6)}</defs>"
        + f'<text x="56" y="70" class="mono muted l1" font-size="14" letter-spacing="2">OLÁ, EU SOU</text>'
        + f'<text x="52" y="150" class="serif l2" font-size="84" fill="{INK}">Matheus '
        + f'<tspan font-style="italic" fill="url(#nm)">Amaral</tspan></text>'
        + f'<text x="56" y="196" class="sans l3" font-size="21" fill="{INK}">Estudante de Ciência da Computação — desenvolvimento web &amp; análise de dados.</text>'
        + '<g class="l4">'
        + f'<circle cx="62" cy="244" r="5" fill="{GREEN}"/><circle class="dot" cx="62" cy="244" r="5" fill="{GREEN}"/>'
        + f'<text x="78" y="249" class="sans" font-size="15" fill="{MUTED}">Aprendendo na prática, um projeto por vez</text>'
        + f'<text x="824" y="249" class="mono" font-size="14" fill="{INK}" text-anchor="end">'
        + f'{s["total"]} contribuições no último ano <tspan class="ar">→</tspan></text>'
        + "</g>"
        # detalhe decorativo: três "carimbos" coloridos
        + f'<g class="l3"><circle cx="760" cy="80" r="26" fill="{BLUE}" opacity=".9"/>'
        + f'<circle cx="800" cy="80" r="26" fill="{YELLOW}" opacity=".9"/>'
        + f'<circle cx="780" cy="112" r="26" fill="{RED}" opacity=".85"/></g>'
    )
    return svg(w, h, body, css, "Matheus Amaral — estudante de Ciência da Computação")


def tile(kind, color, title, big, unit, sub, delay):
    w, h = 286, 220
    dark = kind != "dados"
    fg = PAPER if dark else INK
    css = f"""
    .card{{animation:swing 1s cubic-bezier(.2,.8,.3,1.2) {delay}s both;transform-box:fill-box;transform-origin:50% 100%}}
    .ring{{animation:pulse 2.4s ease-out {delay+1:.1f}s infinite;transform-box:fill-box;transform-origin:center}}
    .ar{{animation:nudge 3s ease-in-out {delay+1.5:.1f}s infinite}}
    """
    body = (
        f"<defs>{shine_gradient('sh'+kind, 'rgba(255,255,255,0)', 'rgba(255,255,255,.35)', 5, delay+1.2)}</defs>"
        + '<g class="card">'
        + f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="20" fill="{color}"/>'
        + f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="20" fill="url(#sh{kind})"/>'
        + f'<circle cx="{w-34}" cy="34" r="9" fill="none" stroke="{fg}" stroke-width="2"/>'
        + f'<circle class="ring" cx="{w-34}" cy="34" r="9" fill="none" stroke="{fg}" stroke-width="2"/>'
        + f'<text x="26" y="44" class="mono" font-size="13" letter-spacing="2" fill="{fg}" opacity=".85">{esc(title)}</text>'
        + counter(24, 132, big, "serif", f"font-size:78px;fill:{fg}", begin=delay + 0.5)
        + f'<text x="{26 + 40*len(str(big))}" y="132" class="sans" font-size="18" fill="{fg}" opacity=".85">{esc(unit)}</text>'
        + f'<text x="26" y="186" class="sans" font-size="16" fill="{fg}">{esc(sub)} <tspan class="ar">→</tspan></text>'
        + "</g>"
    )
    return svg(w, h, body, css, f"{title}: {big} {unit}")


def activity(s):
    w, h = 880, 330
    months = list(s["months"].items())
    peak = max([v for _, v in months] + [1])
    best_i = max(range(len(months)), key=lambda i: months[i][1]) if months else 0
    x0, base, maxh, bw, gap = 56, 250, 140, 46, 18
    css = ".hd{animation:rise .7s ease-out .1s both}.st{animation:fade .8s ease-out 1.6s both}"
    bars = []
    for i, ((y, m), v) in enumerate(months):
        bh = max(3, v / peak * maxh)
        x = x0 + i * (bw + gap)
        color = BLUE if i == best_i and v else INK
        d = 0.3 + i * 0.07
        anim = "" if STATIC else f' style="animation:grow .7s cubic-bezier(.2,.8,.3,1) {d:.2f}s both;transform-box:fill-box;transform-origin:bottom"'
        bars.append(f'<rect x="{x}" y="{base-bh:.1f}" width="{bw}" height="{bh:.1f}" rx="6" fill="{color}" opacity="{1 if v else .25}"{anim}/>')
        bars.append(f'<text x="{x+bw/2}" y="{base+24}" class="mono muted" font-size="12" text-anchor="middle">{MESES[m-1]}</text>')
        if i == best_i and v:
            pa = "" if STATIC else f' style="animation:pop .5s ease-out {d+0.7:.2f}s both;transform-box:fill-box;transform-origin:center"'
            bars.append(f'<text x="{x+bw/2}" y="{base-bh-10:.1f}" class="sans" font-size="15" font-weight="600" fill="{BLUE}" text-anchor="middle"{pa}>{v}</text>')
    stat = lambda x, n, l: (
        f'<text x="{x}" y="306" class="sans" font-size="14" fill="{MUTED}">{l} '
        f'<tspan class="serif" font-size="20" fill="{INK}">{n}</tspan></text>'
    )
    body = (
        frame(w, h)
        + f'<text x="56" y="56" class="serif hd" font-size="32" fill="{INK}">Atividade por mês</text>'
        + f'<text x="824" y="56" class="mono hd" font-size="13" fill="{MUTED}" text-anchor="end">ÚLTIMOS 12 MESES</text>'
        + f'<line x1="56" y1="{base}" x2="824" y2="{base}" stroke="{LINE}"/>'
        + "".join(bars)
        + '<g class="st">'
        + stat(56, s["total"], "total")
        + stat(220, s["active"], "dias ativos")
        + stat(410, s["best"], "maior sequência")
        + stat(630, s["busiest"], "dia favorito:")
        + "</g>"
    )
    return svg(w, h, body, css, f"{s['total']} contribuições nos últimos 12 meses")


def heatmap(days):
    w, h = 880, 190
    items = list(days.items())
    first = dt.date.fromisoformat(items[0][0])
    pad = (first.weekday() + 1) % 7  # GitHub começa a semana no domingo
    levels = [PAPER_2, "#C9D6FB", "#8EA8F5", "#5277EE", BLUE]
    peak = max([c for _, c in items] + [1])
    cell, gap, x0, y0 = 12, 3, 52, 50
    rects = []
    for i, (d, c) in enumerate(items):
        k = i + pad
        col, row = divmod(k, 7)
        lvl = 0 if c == 0 else min(4, 1 + int(3 * c / peak))
        anim = "" if STATIC else f' style="animation:pop .35s ease-out {0.2 + col*0.025:.3f}s both;transform-box:fill-box;transform-origin:center"'
        rects.append(
            f'<rect x="{x0 + col*(cell+gap)}" y="{y0 + row*(cell+gap)}" width="{cell}" height="{cell}" rx="3" fill="{levels[lvl]}"{anim}>'
            f"<title>{d}: {c}</title></rect>"
        )
    body = (
        frame(w, h)
        + f'<text x="52" y="34" class="mono" font-size="13" letter-spacing="2" fill="{MUTED}">CONTRIBUIÇÕES · {sum(days.values())} NO ÚLTIMO ANO</text>'
        + "".join(rects)
    )
    return svg(w, h, body, "", "Gráfico de contribuições do último ano")


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
    lines = lines[:2]
    body = (
        f'<defs><clipPath id="cp"><rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16"/></clipPath></defs>'
        '<g class="rc">'
        + frame(w, h, 16)
        + f'<rect x="0" y="0" width="9" height="{h}" fill="{color}" clip-path="url(#cp)"/>'
        + f'<text x="30" y="46" class="serif" font-size="27" fill="{INK}">{esc(name)} <tspan class="ar sans" font-size="18">↗</tspan></text>'
        + "".join(
            f'<text x="30" y="{80 + i*21}" class="sans" font-size="14.5" fill="{MUTED}">{esc(l)}</text>' for i, l in enumerate(lines)
        )
        + f'<circle cx="36" cy="{h-24}" r="5" fill="{color}"/>'
        + f'<text x="48" y="{h-19}" class="mono" font-size="12.5" fill="{INK}">{esc(lang)}</text>'
        + "</g>"
    )
    return svg(w, h, body, css, f"Repositório {name}")


def main():
    days = load_days()
    s = stats(days)
    CARDS.mkdir(exist_ok=True)
    out = {
        "hero.svg": hero(s),
        "projetos.svg": tile("projetos", BLUE, "PROJETOS", 7, "repos públicos", "Ver todos os projetos", 0.2),
        "dados.svg": tile("dados", YELLOW, "DADOS & BI", s["active"], "dias ativos", "Python · Pandas · Power BI", 0.4),
        "contato.svg": tile("contato", RED, "CONTATO", s["best"], "dias seguidos", "LinkedIn · Gmail", 0.6),
        "activity.svg": activity(s),
        "heatmap.svg": heatmap(days),
        "repo-savett.svg": repo_card("SAVETT", "IA de inteligência financeira — app e site para salvar seu dinheiro.", "TypeScript · React", GREEN, 0.2),
        "repo-bi.svg": repo_card("bi-inflacao-brasil", "BI da inflação no Brasil (2021–2026) com dados do IBGE, BCB e Ipeadata.", "Jupyter · Power BI", YELLOW, 0.4),
    }
    for name, content in out.items():
        (CARDS / name).write_text(content, encoding="utf-8")
    print(f"{len(out)} cards gerados em {CARDS} — total={s['total']} ativos={s['active']} sequência={s['best']}")


if __name__ == "__main__":
    main()
