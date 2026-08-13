"""Geração do style-guide.html — um arquivo único, navegável e interativo."""

from __future__ import annotations

import html
import json
from typing import Any

from ..analysis.color import contrast_ratio, parse_color, to_hex
from ..analysis.typography import name_font_sizes
from ..models import DesignSystem

PAGE_CSS = r"""
*, *::before, *::after { box-sizing: border-box; }
:root {
  --bg: #ffffff;
  --bg-soft: #f6f7f9;
  --panel: #ffffff;
  --ink: #10131a;
  --ink-soft: #5b6472;
  --line: #e4e7ec;
  --brand: #4f46e5;
  --radius: 12px;
  --shadow: 0 1px 2px rgba(16,19,26,.06), 0 8px 24px rgba(16,19,26,.06);
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif;
  color-scheme: light;
}
html[data-theme="dark"] {
  --bg: #0c0e13;
  --bg-soft: #12151c;
  --panel: #161a22;
  --ink: #eef1f6;
  --ink-soft: #98a2b3;
  --line: #262c38;
  --shadow: 0 1px 2px rgba(0,0,0,.4), 0 12px 32px rgba(0,0,0,.35);
  color-scheme: dark;
}
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--brand); }
header.top {
  position: sticky; top: 0; z-index: 50;
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: saturate(180%) blur(12px);
  border-bottom: 1px solid var(--line);
}
.top-inner {
  max-width: 1180px; margin: 0 auto; padding: 14px 24px;
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
}
.brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
.brand h1 { font-size: 17px; margin: 0; letter-spacing: -.01em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.brand .sub { color: var(--ink-soft); font-size: 12.5px; }
nav.toc { display: flex; gap: 4px; flex-wrap: wrap; margin-left: auto; }
nav.toc a {
  font-size: 12.5px; color: var(--ink-soft); text-decoration: none;
  padding: 5px 10px; border-radius: 999px; border: 1px solid transparent;
}
nav.toc a:hover { color: var(--ink); background: var(--bg-soft); border-color: var(--line); }
.theme-toggle {
  border: 1px solid var(--line); background: var(--panel); color: var(--ink);
  border-radius: 999px; padding: 6px 12px; font-size: 12.5px; cursor: pointer; font-family: inherit;
}
.theme-toggle:hover { border-color: var(--ink-soft); }
main { max-width: 1180px; margin: 0 auto; padding: 8px 24px 96px; }
section { padding: 40px 0 8px; scroll-margin-top: 76px; }
section > h2 {
  font-size: 13px; text-transform: uppercase; letter-spacing: .09em;
  color: var(--ink-soft); margin: 0 0 4px; font-weight: 600;
}
section > .lede { color: var(--ink-soft); font-size: 13.5px; margin: 0 0 20px; }
.stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(132px, 1fr)); gap: 10px; margin: 24px 0 8px; }
.stat { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 12px 14px; }
.stat b { display: block; font-size: 22px; letter-spacing: -.02em; }
.stat span { color: var(--ink-soft); font-size: 12px; }
.grid { display: grid; gap: 12px; }
.cols-roles { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); }
.cols-swatch { grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); }
.swatch {
  border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden;
  background: var(--panel); cursor: pointer; text-align: left; padding: 0; font: inherit; color: inherit;
  transition: transform .12s ease, box-shadow .12s ease;
}
.swatch:hover { transform: translateY(-2px); box-shadow: var(--shadow); }
.swatch .chip { height: 74px; display: block; position: relative; }
.swatch.role .chip { height: 92px; display: flex; align-items: flex-end; padding: 10px; }
.swatch .chip .aa { font-size: 10.5px; padding: 2px 6px; border-radius: 999px; background: rgba(0,0,0,.35); color: #fff; }
.swatch .meta { padding: 9px 11px 11px; }
.swatch .name { font-size: 12.5px; font-weight: 600; letter-spacing: -.01em; }
.swatch .hex { font-family: var(--mono); font-size: 11.5px; color: var(--ink-soft); }
.swatch .why { font-size: 10.5px; color: var(--ink-soft); margin-top: 4px; line-height: 1.35; }
.ramp { display: flex; border-radius: var(--radius); overflow: hidden; border: 1px solid var(--line); }
.ramp button { flex: 1; height: 62px; border: 0; cursor: pointer; padding: 0; position: relative; }
.ramp button span {
  position: absolute; inset: auto 0 4px; text-align: center; font-family: var(--mono);
  font-size: 9.5px; opacity: 0; transition: opacity .12s;
}
.ramp button:hover span { opacity: 1; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 18px 20px; }
.type-row { border-bottom: 1px solid var(--line); padding: 18px 0; display: grid; grid-template-columns: 132px 1fr; gap: 20px; align-items: baseline; }
.type-row:last-child { border-bottom: 0; }
.type-meta { font-family: var(--mono); font-size: 11px; color: var(--ink-soft); line-height: 1.7; }
.type-meta b { color: var(--ink); font-family: var(--sans); font-size: 12px; display: block; text-transform: uppercase; letter-spacing: .06em; }
.type-sample { overflow: hidden; }
.family-card { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 14px 0; border-bottom: 1px solid var(--line); }
.family-card:last-child { border-bottom: 0; }
.family-card .preview { font-size: 26px; letter-spacing: -.01em; }
.family-card .info { text-align: right; font-size: 12px; color: var(--ink-soft); font-family: var(--mono); white-space: nowrap; }
.space-row { display: flex; align-items: center; gap: 14px; padding: 7px 0; }
.space-row .label { font-family: var(--mono); font-size: 11.5px; color: var(--ink-soft); width: 96px; flex: none; }
.space-row .bar { height: 15px; background: linear-gradient(90deg, var(--brand), color-mix(in srgb, var(--brand) 45%, transparent)); border-radius: 4px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(128px, 1fr)); gap: 14px; }
.tile { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 14px; text-align: center; }
.tile .demo { height: 66px; background: color-mix(in srgb, var(--brand) 14%, var(--panel)); border: 1px solid color-mix(in srgb, var(--brand) 30%, transparent); margin-bottom: 10px; }
.tile .demo.shadow { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }
.tile code { font-family: var(--mono); font-size: 11px; color: var(--ink-soft); word-break: break-all; }
.tile b { font-size: 12.5px; display: block; }
.icons { display: grid; grid-template-columns: repeat(auto-fill, minmax(76px, 1fr)); gap: 10px; }
.icon-box {
  aspect-ratio: 1; display: grid; place-items: center; background: var(--panel);
  border: 1px solid var(--line); border-radius: 10px; padding: 12px; overflow: hidden; color: var(--ink);
}
.icon-box svg { max-width: 100%; max-height: 100%; width: auto; height: auto; }
.icon-box img { max-width: 100%; max-height: 100%; object-fit: contain; }
.logo-strip { display: flex; flex-wrap: wrap; gap: 14px; }
.logo-box { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 18px 22px; display: grid; place-items: center; min-width: 150px; min-height: 78px; }
.logo-box svg, .logo-box img { max-width: 220px; max-height: 52px; height: auto; }
.cmp { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; }
.cmp-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 11px 14px; border-bottom: 1px solid var(--line); }
.cmp-head b { font-size: 12.5px; }
.cmp-head span { font-family: var(--mono); font-size: 11px; color: var(--ink-soft); }
.cmp-stage { padding: 26px; display: flex; gap: 14px; flex-wrap: wrap; align-items: center; background: var(--bg-soft); min-height: 96px; }
.cmp-props { padding: 0 14px 14px; }
.cmp-props summary { cursor: pointer; font-size: 12px; color: var(--ink-soft); padding: 10px 0 0; }
.cmp-props table { width: 100%; border-collapse: collapse; font-family: var(--mono); font-size: 11px; margin-top: 8px; }
.cmp-props td { padding: 3px 8px 3px 0; border-bottom: 1px solid var(--line); vertical-align: top; }
.cmp-props td:first-child { color: var(--ink-soft); white-space: nowrap; width: 170px; }
.cmp-props td.changed { color: var(--brand); }
.table { width: 100%; border-collapse: collapse; font-size: 13px; }
.table th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .07em; color: var(--ink-soft); padding: 8px 10px; border-bottom: 1px solid var(--line); font-weight: 600; }
.table td { padding: 8px 10px; border-bottom: 1px solid var(--line); }
.table td.mono, .table th.mono { font-family: var(--mono); font-size: 11.5px; }
.pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: var(--bg-soft); border: 1px solid var(--line); font-family: var(--mono); font-size: 11px; }
.shots { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 14px; }
.shot { border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; background: var(--panel); }
.shot img { width: 100%; display: block; border-bottom: 1px solid var(--line); }
.shot .cap { padding: 9px 11px; font-size: 11.5px; color: var(--ink-soft); word-break: break-all; }
.warn { border-left: 3px solid #d97706; background: color-mix(in srgb, #d97706 8%, var(--panel)); padding: 12px 16px; border-radius: 0 var(--radius) var(--radius) 0; font-size: 13px; margin-bottom: 10px; }
footer { color: var(--ink-soft); font-size: 12px; border-top: 1px solid var(--line); padding: 22px 0 0; margin-top: 48px; }
#toast {
  position: fixed; left: 50%; bottom: 28px; transform: translate(-50%, 24px);
  background: var(--ink); color: var(--bg); padding: 9px 18px; border-radius: 999px;
  font-size: 13px; opacity: 0; pointer-events: none; transition: all .2s ease; z-index: 100;
}
#toast.on { opacity: 1; transform: translate(-50%, 0); }
@media (max-width: 720px) {
  .type-row { grid-template-columns: 1fr; gap: 6px; }
  nav.toc { display: none; }
}
"""

PAGE_JS = r"""
const root = document.documentElement;
const saved = localStorage.getItem('designsys-theme');
if (saved) root.setAttribute('data-theme', saved);
else if (window.matchMedia('(prefers-color-scheme: dark)').matches) root.setAttribute('data-theme', 'dark');
document.getElementById('theme-toggle').addEventListener('click', () => {
  const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('designsys-theme', next);
});
const toast = document.getElementById('toast');
let toastTimer;
function flash(msg) {
  toast.textContent = msg;
  toast.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('on'), 1400);
}
// navigator.clipboard não existe em file:// (contexto não seguro), que é
// justamente como este guia costuma ser aberto — daí o fallback.
function copyText(text) {
  // A Clipboard API existe em file:// (é contexto seguro no Chromium) mas pode
  // ser negada por permissão — por isso o fallback vai no catch, não no if.
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text).catch(() => legacyCopy(text));
  }
  return legacyCopy(text);
}
function legacyCopy(text) {
  return new Promise((resolve, reject) => {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:-1000px;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, text.length);
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    ok ? resolve() : reject(new Error('copy failed'));
  });
}
document.addEventListener('click', (ev) => {
  const el = ev.target.closest('[data-copy]');
  if (!el) return;
  const text = el.getAttribute('data-copy');
  copyText(text).then(
    () => flash(text + ' copiado'),
    () => flash('não consegui copiar')
  );
});
"""


def _esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def _contrast_badge(hex_value: str) -> str:
    rgba = parse_color(hex_value)
    if rgba is None:
        return ""
    white = contrast_ratio(rgba, (1, 1, 1, 1))
    black = contrast_ratio(rgba, (0, 0, 0, 1))
    best = "branco" if white >= black else "preto"
    ratio = max(white, black)
    return f"{best} {ratio:.1f}:1"


def _readable_on(hex_value: str) -> str:
    rgba = parse_color(hex_value)
    if rgba is None:
        return "#000"
    return "#fff" if contrast_ratio(rgba, (1, 1, 1, 1)) >= contrast_ratio(rgba, (0, 0, 0, 1)) else "#111"


def _swatch(name: str, value: str, note: str = "", role: bool = False) -> str:
    hexv = value
    rgba = parse_color(value)
    if rgba is not None:
        hexv = to_hex(rgba)
    ink = _readable_on(value)
    badge = f'<span class="aa" style="background:rgba(0,0,0,.32)">{_esc(_contrast_badge(value))}</span>' if role else ""
    return (
        f'<button class="swatch{" role" if role else ""}" data-copy="{_esc(hexv)}" title="clique para copiar {_esc(hexv)}">'
        f'<span class="chip" style="background:{_esc(value)};color:{ink}">{badge}</span>'
        f'<span class="meta"><span class="name">{_esc(name)}</span><br>'
        f'<span class="hex">{_esc(hexv)}</span>'
        + (f'<div class="why">{_esc(note)}</div>' if note else "")
        + "</span></button>"
    )


def _section(id_: str, title: str, lede: str, body: str) -> str:
    if not body.strip():
        return ""
    return (
        f'<section id="{id_}"><h2>{_esc(title)}</h2>'
        + (f'<p class="lede">{_esc(lede)}</p>' if lede else "")
        + body
        + "</section>"
    )


def _font_faces_css(ds: DesignSystem) -> str:
    """Reaproveita os @font-face para o guia renderizar com as fontes reais."""
    rules = []
    for face in (ds.typography or {}).get("font_faces", [])[:24]:
        srcs = []
        if face.get("localPath"):
            srcs.append(f'url("{face["localPath"]}")')
        for url in (face.get("urls") or [])[:1]:
            if url.startswith("http"):
                srcs.append(f'url("{url}")')
        if not srcs:
            continue
        rules.append(
            "@font-face{font-family:%s;font-style:%s;font-weight:%s;font-display:swap;src:%s;}"
            % (
                json.dumps(face["family"]),
                face.get("style") or "normal",
                face.get("weight") or "400",
                ",".join(srcs),
            )
        )
    return "\n".join(rules)


def _component_sample(comp: dict[str, Any]) -> str:
    """Reconstrói o componente aplicando os estilos computados capturados."""
    base = comp.get("base") or {}
    hover = comp.get("hover") or {}
    kind = comp.get("kind", "")
    ignore = {"width", "height", "z-index", "position", "overflow", "backdrop-filter"}
    if kind in ("card", "nav", "header", "footer", "table", "alert"):
        ignore -= {"width"}
    decls = []
    for prop, value in base.items():
        if prop in ignore or not value or value in ("auto", "normal none"):
            continue
        if prop in ("width", "height") and kind not in ("card", "nav", "header", "footer"):
            continue
        if prop == "background-image" and "none" in value:
            continue
        decls.append(f"{prop}:{value}")
    if kind.startswith("button") or kind == "link":
        decls.append("cursor:pointer")
    style = ";".join(decls)

    label = comp.get("label") or _default_label(kind)
    hover_css = ""
    changed = {p: v for p, v in hover.items() if base.get(p) not in (None, v)}
    if changed:
        hover_css = ";".join(f"{p}:{v}" for p, v in changed.items() if p not in ignore)

    uid = f"cmp-{abs(hash(comp.get('selector', '') + kind)) % 10**8}"
    extra_css = f"#{uid}:hover{{{hover_css}}}" if hover_css else ""

    if kind in ("input", "textarea", "select"):
        tag = "input" if kind == "input" else kind
        if tag == "input":
            el = f'<input id="{uid}" style="{_esc(style)}" placeholder="{_esc(label or "Digite algo")}">'
        elif tag == "textarea":
            el = f'<textarea id="{uid}" style="{_esc(style)}" placeholder="{_esc(label or "Digite algo")}"></textarea>'
        else:
            el = f'<select id="{uid}" style="{_esc(style)}"><option>Opção</option></select>'
    elif kind == "checkbox":
        el = f'<input type="checkbox" id="{uid}" style="{_esc(style)}" checked>'
    elif kind in ("card", "nav", "header", "footer", "table", "alert"):
        inner = _sanitize_html(comp.get("html") or "", comp.get("page") or "")
        if not inner.strip():
            # Markup grande demais para reproduzir: mostra só a caixa, que é o
            # que interessa (fundo, borda, raio, sombra, espaçamento).
            inner = (
                "<div style='font:12px/1.5 system-ui;opacity:.55'>"
                f"{_esc(kind)} — caixa reconstruída a partir dos estilos computados</div>"
            )
        el = f'<div id="{uid}" style="{_esc(style)};max-width:100%">{inner}</div>'
    else:
        el = f'<span id="{uid}" style="{_esc(style)};display:inline-flex">{_esc(label)}</span>'

    css = f"<style>{extra_css}</style>" if extra_css else ""
    return css + el


def _sanitize_html(markup: str, base_url: str = "") -> str:
    """Remove scripts/handlers do HTML capturado e resolve URLs relativas.

    Sem resolver as URLs, um `src="/_next/img.png"` do site vira caminho local
    inexistente ao lado do style guide e quebra na renderização.
    """
    import re
    from urllib.parse import urljoin

    cleaned = re.sub(r"<script[\s\S]*?</script>", "", markup, flags=re.I)
    cleaned = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", cleaned, flags=re.I)
    cleaned = re.sub(r"javascript:", "", cleaned, flags=re.I)
    cleaned = re.sub(r"<(iframe|object|embed|link|meta)\b[\s\S]*?>", "", cleaned, flags=re.I)

    if base_url:

        def absolutize(match: "re.Match[str]") -> str:
            attr, quote, value = match.group(1), match.group(2), match.group(3)
            if not value or value.startswith(("http://", "https://", "data:", "#", "mailto:", "//")):
                return match.group(0)
            return f"{attr}={quote}{urljoin(base_url, value)}{quote}"

        cleaned = re.sub(
            r"\s(src|href)=([\"'])([^\"']*)\2", lambda m: " " + absolutize(m), cleaned, flags=re.I
        )
        cleaned = re.sub(r"\ssrcset=([\"'])[^\"']*\1", "", cleaned, flags=re.I)
    return cleaned


def _default_label(kind: str) -> str:
    return {
        "button-primary": "Ação primária",
        "button-secondary": "Ação secundária",
        "button": "Botão",
        "link": "Um link",
        "badge": "Badge",
        "label": "Rótulo",
    }.get(kind, kind.replace("-", " ").title() or "Componente")


def _diff_table(comp: dict[str, Any]) -> str:
    base = comp.get("base") or {}
    hover = comp.get("hover") or {}
    focus = comp.get("focus") or {}
    rows = []
    for prop, value in sorted(base.items()):
        h = hover.get(prop)
        f = focus.get(prop)
        cells = [f"<td>{_esc(prop)}</td>", f"<td>{_esc(value)}</td>"]
        cells.append(
            f'<td class="{"changed" if h and h != value else ""}">{_esc(h if h and h != value else "—")}</td>'
        )
        cells.append(
            f'<td class="{"changed" if f and f != value else ""}">{_esc(f if f and f != value else "—")}</td>'
        )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    if not rows:
        return ""
    return (
        "<details class='cmp-props'><summary>estilos computados "
        f"({len(rows)} propriedades · hover e focus destacados)</summary>"
        "<table><tr><td><b>propriedade</b></td><td><b>base</b></td><td><b>:hover</b></td><td><b>:focus</b></td></tr>"
        + "".join(rows)
        + "</table></details>"
    )


def build_style_guide(ds: DesignSystem) -> str:
    colors = ds.colors or {}
    typo = ds.typography or {}
    roles = colors.get("roles") or {}
    parts: list[str] = []

    # ------------------------------------------------------------ estatísticas
    counts = ds.counts()
    stats = "".join(
        f'<div class="stat"><b>{v}</b><span>{_esc(k)}</span></div>'
        for k, v in counts.items()
        if v
    )
    parts.append(f'<section id="resumo"><div class="stats">{stats}</div>')
    if ds.warnings:
        for w in ds.warnings[:6]:
            parts.append(f'<div class="warn">{_esc(w)}</div>')
    parts.append("</section>")

    # ----------------------------------------------------------------- cores
    body = ""
    if roles:
        body += '<div class="grid cols-roles">' + "".join(
            _swatch(role, info["value"], info.get("reason", ""), role=True)
            for role, info in roles.items()
        ) + "</div>"

    named = colors.get("named") or {}
    if named:
        body += "<h3 style='font-size:13px;margin:26px 0 10px'>Paleta nomeada (do código-fonte)</h3>"
        body += '<div class="grid cols-swatch">' + "".join(
            _swatch(name, value) for name, value in list(named.items())[:60]
        ) + "</div>"

    neutrals = colors.get("neutrals") or []
    if neutrals:
        body += "<h3 style='font-size:13px;margin:26px 0 10px'>Escala neutra (claro → escuro)</h3><div class='ramp'>"
        for entry in neutrals[:14]:
            ink = _readable_on(entry["value"])
            body += (
                f'<button data-copy="{_esc(entry["hex"])}" style="background:{_esc(entry["value"])};color:{ink}" '
                f'title="{_esc(entry["hex"])}"><span>{_esc(entry["hex"])}</span></button>'
            )
        body += "</div>"

    accents = colors.get("accents") or []
    if accents:
        body += "<h3 style='font-size:13px;margin:26px 0 10px'>Outras cores de destaque</h3>"
        body += '<div class="grid cols-swatch">' + "".join(
            _swatch(f"accent {i}", entry["value"], f'{entry["count"]}× · hue {entry.get("hue", 0):.0f}°')
            for i, entry in enumerate(accents[:12], start=1)
        ) + "</div>"

    clusters = colors.get("clusters") or []
    if clusters:
        rows = "".join(
            "<tr>"
            f'<td><button class="swatch" style="width:26px;height:26px;border-radius:6px;background:{_esc(c["value"])}" data-copy="{_esc(c["hex"])}"></button></td>'
            f'<td class="mono">{_esc(c["hex"])}</td>'
            f'<td class="mono">{c["count"]}</td>'
            f'<td class="mono">{_esc(", ".join(f"{k}:{v}" for k, v in list((c.get("properties") or {}).items())[:4]) or "—")}</td>'
            f'<td class="mono">{_esc(", ".join(c.get("sources", [])[:2]) or "")}</td>'
            "</tr>"
            for c in clusters[:60]
        )
        body += (
            "<details style='margin-top:26px'><summary style='cursor:pointer;color:var(--ink-soft);font-size:12.5px'>"
            f"todas as {len(clusters)} cores agrupadas, com frequência</summary>"
            "<table class='table' style='margin-top:12px'><tr><th></th><th>hex</th><th>usos</th><th>onde</th><th>origem</th></tr>"
            + rows
            + "</table></details>"
        )
    parts.append(
        _section(
            "cores",
            "Cores",
            "Clique em qualquer amostra para copiar o hex. Cores quase idênticas foram agrupadas em OKLCH.",
            body,
        )
    )

    # ------------------------------------------------------------ tipografia
    body = ""
    families = typo.get("families") or []
    if families:
        body += "<div class='panel'>"
        for fam in families[:6]:
            stack = fam.get("stack") or fam["family"]
            body += (
                "<div class='family-card'>"
                f"<div class='preview' style=\"font-family:{_esc(stack)}\">{_esc(fam['family'])} — Aa Bb Cc 123</div>"
                f"<div class='info'>{fam['count']}× usos<br>{_esc(stack[:60])}</div>"
                "</div>"
            )
        body += "</div>"

    scale = typo.get("scale") or []
    if scale:
        body += "<div class='panel' style='margin-top:14px'>"
        for style in scale:
            css = (
                f"font-family:{style.get('fontFamily') or 'inherit'};"
                f"font-size:{style['fontSize']}px;"
                f"font-weight:{style.get('fontWeight', 400)};"
                f"line-height:{style.get('lineHeight', 'normal')};"
                f"letter-spacing:{style.get('letterSpacing', 'normal')};"
                f"text-transform:{style.get('textTransform', 'none')};"
            )
            sample = style.get("sample") or "The quick brown fox jumps over the lazy dog"
            body += (
                "<div class='type-row'>"
                f"<div class='type-meta'><b>{_esc(style['name'])}</b>"
                f"{style['fontSize']:g}px / {_esc(style.get('fontWeight', 400))}<br>"
                f"lh {_esc(style.get('lineHeight', 'normal'))}<br>"
                f"ls {_esc(style.get('letterSpacing', 'normal'))}<br>"
                f"{style.get('count', 0)}× na página</div>"
                f"<div class='type-sample' style=\"{_esc(css)}\">{_esc(sample)}</div>"
                "</div>"
            )
        body += "</div>"

    sizes = (typo.get("named") or {}).get("fontSize") or name_font_sizes(typo.get("sizes") or [])
    if sizes:
        body += "<div class='tiles' style='margin-top:14px'>" + "".join(
            f"<div class='tile'><b>{_esc(name)}</b><code>{_esc(value if isinstance(value, str) else f'{value:g}px')}</code></div>"
            for name, value in sizes.items()
        ) + "</div>"

    faces = typo.get("font_faces") or []
    if faces:
        rows = "".join(
            "<tr>"
            f"<td>{_esc(f['family'])}</td><td class='mono'>{_esc(f.get('weight'))}</td>"
            f"<td class='mono'>{_esc(f.get('style'))}</td>"
            f"<td class='mono'>{_esc((f.get('localPath') or (f.get('urls') or [''])[0] or '')[:80])}</td>"
            "</tr>"
            for f in faces[:30]
        )
        body += (
            "<details style='margin-top:20px'><summary style='cursor:pointer;color:var(--ink-soft);font-size:12.5px'>"
            f"{len(faces)} regras @font-face</summary><table class='table' style='margin-top:10px'>"
            "<tr><th>família</th><th>peso</th><th>estilo</th><th>arquivo</th></tr>" + rows + "</table></details>"
        )
    parts.append(_section("tipografia", "Tipografia", "Renderizado com as fontes reais do site.", body))

    # ------------------------------------------------------------ espaçamento
    body = ""
    spacing_named = ds.spacing.get("named") or {}
    scale_values = ds.spacing.get("scale") or []
    if spacing_named or scale_values:
        body += "<div class='panel'>"
        items = (
            list(spacing_named.items())
            if spacing_named
            else [(f"{v:g}", v) for v in scale_values]
        )
        for name, value in items:
            px = value if isinstance(value, (int, float)) else _to_px(value)
            body += (
                "<div class='space-row'>"
                f"<div class='label'>{_esc(name)} · {_esc(value if isinstance(value, str) else f'{value:g}px')}</div>"
                f"<div class='bar' style='width:{min(px or 0, 520):g}px'></div>"
                "</div>"
            )
        body += "</div>"
        if ds.spacing.get("base_unit"):
            body += f"<p class='lede' style='margin-top:10px'>Grade base detectada: {ds.spacing['base_unit']:g}px.</p>"
    parts.append(_section("espacamento", "Espaçamento", "Escala inferida pelos valores mais frequentes de margin/padding/gap.", body))

    # ------------------------------------------------------------------ raios
    body = ""
    radii_named = ds.radii.get("named") or {}
    if radii_named:
        body += "<div class='tiles'>" + "".join(
            f"<div class='tile'><div class='demo' style='border-radius:{_esc(_radius_css(value))}'></div>"
            f"<b>{_esc(name)}</b><code>{_esc(_radius_css(value))}</code></div>"
            for name, value in radii_named.items()
        ) + "</div>"
    parts.append(_section("raios", "Border radius", "", body))

    # --------------------------------------------------------------- sombras
    body = ""
    if ds.shadows:
        body += "<div class='tiles'>" + "".join(
            f"<div class='tile'><div class='demo shadow' style='box-shadow:{_esc(s['value'])}'></div>"
            f"<b>{_esc(s.get('name') or f'sombra {i + 1}')}</b><code>{_esc(s['value'][:70])}</code></div>"
            for i, s in enumerate(ds.shadows)
        ) + "</div>"
    parts.append(_section("sombras", "Sombras", "", body))

    # ----------------------------------------------------------- componentes
    body = ""
    comps = [c.to_dict() if hasattr(c, "to_dict") else c for c in ds.components]
    if comps:
        body += "<div class='grid' style='grid-template-columns:1fr'>"
        for comp in comps:
            body += (
                "<div class='cmp'>"
                f"<div class='cmp-head'><b>{_esc(comp.get('kind'))}</b>"
                f"<span>{_esc((comp.get('selector') or '')[:90])}</span></div>"
                f"<div class='cmp-stage'>{_component_sample(comp)}</div>"
                f"{_diff_table(comp)}"
                "</div>"
            )
        body += "</div>"
    parts.append(
        _section(
            "componentes",
            "Componentes",
            "Amostras reconstruídas a partir dos estilos computados capturados no site (incluindo :hover e :focus).",
            body,
        )
    )

    # --------------------------------------------------------------- assets
    body = ""
    logos = [a for a in ds.assets if a.kind == "logo"]
    if logos:
        body += "<div class='logo-strip'>"
        for logo in logos[:6]:
            if logo.inline_svg:
                body += f"<div class='logo-box'>{_sanitize_html(logo.inline_svg)}</div>"
            elif logo.path:
                body += f"<div class='logo-box'><img src='{_esc(logo.path)}' alt='logo'></div>"
        body += "</div>"
    icons = [a for a in ds.assets if a.kind in ("icon", "favicon")]
    if icons:
        body += "<h3 style='font-size:13px;margin:24px 0 10px'>Ícones (%d)</h3><div class='icons'>" % len(icons)
        for icon in icons[:80]:
            if icon.inline_svg:
                body += f"<div class='icon-box'>{_sanitize_html(icon.inline_svg)}</div>"
            elif icon.path:
                body += f"<div class='icon-box'><img src='{_esc(icon.path)}' alt=''></div>"
        body += "</div>"
    fonts = [a for a in ds.assets if a.kind == "font"]
    images = [a for a in ds.assets if a.kind == "image"]
    if fonts or images:
        rows = "".join(
            f"<tr><td>{_esc(a.kind)}</td><td class='mono'>{_esc((a.path or a.url)[:90])}</td><td>{_esc(a.note)}</td></tr>"
            for a in (fonts + images)[:40]
        )
        body += f"<table class='table' style='margin-top:20px'><tr><th>tipo</th><th>arquivo</th><th>obs</th></tr>{rows}</table>"
    parts.append(_section("assets", "Assets", "Baixados para a pasta assets/.", body))

    # ------------------------------------------------------------- restantes
    body = ""
    if ds.breakpoints:
        body += "<p><b>Breakpoints:</b> " + " ".join(
            f"<span class='pill'>{bp}px</span>" for bp in ds.breakpoints
        ) + "</p>"
    if ds.containers:
        body += "<p><b>Containers:</b> " + " ".join(
            f"<span class='pill'>{c:g}px</span>" for c in ds.containers
        ) + "</p>"
    if ds.borders.get("widths"):
        body += "<p><b>Bordas:</b> " + " ".join(
            f"<span class='pill'>{w:g}px</span>" for w in ds.borders["widths"]
        ) + "</p>"
    if (ds.motion or {}).get("durations"):
        body += "<p><b>Durações:</b> " + " ".join(
            f"<span class='pill'>{_esc(d)}</span>" for d in ds.motion["durations"]
        ) + "</p>"
    if (ds.motion or {}).get("easings"):
        body += "<p><b>Easings:</b> " + " ".join(
            f"<span class='pill'>{_esc(e)}</span>" for e in ds.motion["easings"]
        ) + "</p>"
    if ds.z_index:
        body += "<p><b>z-index:</b> " + " ".join(
            f"<span class='pill'>{z}</span>" for z in ds.z_index
        ) + "</p>"
    if ds.opacity:
        body += "<p><b>Opacidades:</b> " + " ".join(
            f"<span class='pill'>{o:g}</span>" for o in ds.opacity
        ) + "</p>"
    if ds.css_variables:
        rows = "".join(
            f"<tr><td class='mono'>{_esc(name)}</td><td class='mono'>{_esc(str(info.get('value'))[:70])}</td>"
            f"<td class='mono'>{_esc(str(info.get('origin', ''))[:60])}</td></tr>"
            for name, info in list(ds.css_variables.items())[:200]
        )
        body += (
            "<details style='margin-top:18px'><summary style='cursor:pointer;color:var(--ink-soft);font-size:12.5px'>"
            f"{len(ds.css_variables)} variáveis CSS encontradas</summary>"
            "<table class='table' style='margin-top:10px'><tr><th>variável</th><th>valor</th><th>origem</th></tr>"
            + rows
            + "</table></details>"
        )
    parts.append(_section("outros", "Outros tokens", "", body))

    # ----------------------------------------------------------- screenshots
    body = ""
    shots = [a for a in ds.assets if a.kind == "screenshot"]
    if shots:
        body += "<div class='shots'>" + "".join(
            f"<div class='shot'><img src='{_esc(a.path)}' alt='' loading='lazy'>"
            f"<div class='cap'>{_esc(a.url)}</div></div>"
            for a in shots
        ) + "</div>"
    parts.append(_section("paginas", "Páginas capturadas", "", body))

    # --------------------------------------------------------------- montagem
    toc = [
        ("cores", "Cores"),
        ("tipografia", "Tipografia"),
        ("espacamento", "Espaçamento"),
        ("raios", "Raios"),
        ("sombras", "Sombras"),
        ("componentes", "Componentes"),
        ("assets", "Assets"),
        ("outros", "Outros"),
        ("paginas", "Páginas"),
    ]
    body_html = "".join(parts)
    nav = "".join(
        f'<a href="#{id_}">{label}</a>' for id_, label in toc if f'id="{id_}"' in body_html
    )
    # No modo repo o alvo é o nome do repositório, que já é o título.
    subtitle = ds.mode if ds.display_target == ds.name else f"{ds.mode} · {ds.display_target}"
    generated = ds.generated_at[:19].replace("T", " ")

    return f"""<!doctype html>
<html lang="pt-BR" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Design system — {_esc(ds.name)}</title>
<style>{PAGE_CSS}
{_font_faces_css(ds)}
</style>
</head>
<body>
<header class="top"><div class="top-inner">
  <div class="brand">
    <h1>{_esc(ds.name)}</h1>
    <span class="sub">{_esc(subtitle)}</span>
  </div>
  <nav class="toc">{nav}</nav>
  <button class="theme-toggle" id="theme-toggle">tema</button>
</div></header>
<main>
{body_html}
<footer>
  Extraído de <b>{_esc(ds.display_target)}</b> em {_esc(generated)} · gerado por
  <b>designsys</b> · {len(ds.pages)} página(s) visitada(s)
</footer>
</main>
<div id="toast"></div>
<script>{PAGE_JS}</script>
</body>
</html>
"""


def _to_px(value: Any) -> float:
    from ..analysis.scales import parse_length

    return parse_length(value) or 0.0


def _radius_css(value: Any) -> str:
    if isinstance(value, (int, float)):
        return "9999px" if value >= 999 else f"{value:g}px"
    return str(value)
