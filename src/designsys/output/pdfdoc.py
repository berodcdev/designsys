"""Documento de impressão: o design system inteiro em A4.

Não é o style-guide.html "impresso" — é um layout próprio para papel: capa,
sumário, quebras de página controladas, sem nada interativo, e com a cor
primária extraída do site usada como cor de destaque do próprio documento.
"""

from __future__ import annotations

import html
from typing import Any

from ..analysis.color import contrast_ratio, is_neutral, luminance, parse_color, to_hex, to_oklch
from ..analysis.typography import name_font_sizes
from ..models import DesignSystem
from .styleguide import _font_faces_css, _sanitize_html

PRINT_CSS = r"""
/* Só o tamanho: as margens vêm da API do Chromium (prefer_css_page_size faria
   um `margin: 0` daqui vencer e colar tudo na borda do papel). */
@page { size: A4; }

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: var(--doc-sans);
  color: var(--ink);
  background: #fff;
  font-size: 9.6pt;
  line-height: 1.5;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
  -webkit-font-smoothing: antialiased;
}
:root {
  --ink: #14161a;
  --ink-soft: #5f6773;
  --ink-faint: #8c95a1;
  --line: #e3e6ea;
  --line-soft: #f0f2f5;
  --panel: #fafbfc;
  --doc-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Helvetica, Arial, sans-serif;
  --doc-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}

/* ---------------------------------------------------------------- páginas
   As margens vêm da página impressa (API do Chromium), não de padding: assim
   uma seção que transborda continua respeitando a margem na folha seguinte,
   em vez de colar no topo. */
.page {
  position: relative;
  page-break-after: always;
  break-after: page;
  display: flow-root;
}
.page:last-child { page-break-after: auto; break-after: auto; }

.page-head {
  display: flex; align-items: baseline; justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: 3mm; margin-bottom: 7mm;
}
.page-head .kicker {
  font-size: 7.4pt; letter-spacing: .16em; text-transform: uppercase;
  color: var(--accent); font-weight: 700;
}
.page-head .src { font-size: 7.2pt; color: var(--ink-faint); font-family: var(--doc-mono); }

h1.section { font-size: 20pt; letter-spacing: -.02em; margin: 0 0 1.5mm; font-weight: 650;
  break-after: avoid; }
p.section-lede { color: var(--ink-soft); font-size: 9pt; margin: 0 0 7mm; max-width: 150mm;
  break-after: avoid; }
h2.block {
  font-size: 8pt; text-transform: uppercase; letter-spacing: .12em; color: var(--ink-soft);
  margin: 8mm 0 3mm; font-weight: 700; border-bottom: 1px solid var(--line-soft); padding-bottom: 1.5mm;
  break-after: avoid;  /* nunca deixa o título sozinho no pé da página */
  break-inside: avoid;
}
h2.block:first-of-type { margin-top: 0; }

/* ------------------------------------------------------------------- capa
   Sem sangrar: o que sai da área imprimível é cortado pelo Chromium, então a
   faixa vive dentro das margens. */
.cover { display: flex; flex-direction: column; min-height: 258mm; }
/* A borda do container é o que faz um #ffffff da paleta aparecer como bloco,
   em vez de virar um buraco na faixa. */
.cover-band {
  height: 11mm; display: flex; border-radius: 1.2mm; overflow: hidden;
  border: 1px solid rgba(0,0,0,.10);
}
.cover-band span { flex: 1; box-shadow: inset -0.2mm 0 0 rgba(0,0,0,.10); }
.cover-band span:last-child { box-shadow: none; }
.cover-type { margin-top: 10mm; border-top: 1px solid var(--line); padding-top: 6mm; }
.cover-type .row {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 6mm; padding: 2.5mm 0;
}
.cover-type .big { font-size: 19pt; letter-spacing: -.02em; }
.cover-type .meta { font-family: var(--doc-mono); font-size: 7.2pt; color: var(--ink-faint); white-space: nowrap; }
.cover-body { padding: 18mm 0 0; flex: 1; display: flex; flex-direction: column; }
.cover .eyebrow {
  font-size: 8pt; letter-spacing: .22em; text-transform: uppercase;
  color: var(--accent); font-weight: 700; margin-bottom: 7mm;
}
.cover h1 {
  font-size: 40pt; line-height: 1.04; letter-spacing: -.035em;
  margin: 0 0 4mm; font-weight: 680; max-width: 160mm;
}
.cover .target {
  font-family: var(--doc-mono); font-size: 10pt; color: var(--ink-soft);
  word-break: break-all; margin-bottom: 10mm;
}
.cover-logo { margin-bottom: 9mm; max-height: 20mm; }
.cover-logo svg, .cover-logo img { max-height: 20mm; max-width: 85mm; height: auto; width: auto; }
.cover-roles { display: grid; grid-template-columns: repeat(6, 1fr); gap: 3mm; margin-bottom: 10mm; }
.cover-roles div .box { height: 16mm; border-radius: 1.5mm; border: 1px solid rgba(0,0,0,.08); }
.cover-roles div b { display: block; font-size: 7.4pt; margin-top: 1.5mm; font-weight: 600; }
.cover-roles div code { font-family: var(--doc-mono); font-size: 6.6pt; color: var(--ink-soft); }
.cover-stats {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 5mm 4mm; margin-top: auto;
  border-top: 1px solid var(--line); padding-top: 7mm;
}
.cover-stats div b { display: block; font-size: 17pt; letter-spacing: -.02em; line-height: 1.15; }
.cover-stats div span { font-size: 7.6pt; color: var(--ink-soft); }
.cover-foot {
  padding: 6mm 0 0; display: flex; justify-content: space-between;
  font-size: 7.8pt; color: var(--ink-faint);
}

/* ------------------------------------------------------------------ sumário */
.toc { column-count: 2; column-gap: 12mm; }
.toc-item {
  display: flex; align-items: baseline; gap: 2mm; padding: 2.2mm 0;
  border-bottom: 1px dotted var(--line); break-inside: avoid;
}
.toc-item .n {
  font-family: var(--doc-mono); font-size: 7.6pt; color: var(--accent);
  width: 7mm; flex: none; font-weight: 700;
}
.toc-item .t { flex: 1; font-size: 9.4pt; }
.toc-item .c { font-size: 7.8pt; color: var(--ink-faint); font-family: var(--doc-mono); }
.toc-item .pg {
  font-family: var(--doc-mono); font-size: 8pt; color: var(--ink-soft);
  min-width: 6mm; text-align: right; font-weight: 600;
}

/* --------------------------------------------------------------- resumo */
.exec { display: grid; grid-template-columns: 1fr 1fr; gap: 6mm; }
.exec-card {
  border: 1px solid var(--line); border-radius: 2mm; padding: 5mm; break-inside: avoid;
}
.exec-card h3 {
  font-size: 7.4pt; text-transform: uppercase; letter-spacing: .12em;
  color: var(--ink-soft); margin: 0 0 3mm; font-weight: 700;
}
.exec-card .big { font-size: 15pt; letter-spacing: -.02em; line-height: 1.25; }
.exec-card .sub { font-size: 8pt; color: var(--ink-soft); margin-top: 2mm; line-height: 1.45; }
.exec-swatches { display: flex; gap: 2mm; margin-bottom: 3mm; }
.exec-swatches span {
  flex: 1; height: 12mm; border-radius: 1.5mm; border: 1px solid rgba(0,0,0,.08);
}
.exec-list { list-style: none; padding: 0; margin: 0; font-size: 8.2pt; }
.exec-list li { padding: 1.6mm 0; border-bottom: 1px solid var(--line-soft); }
.exec-list li:last-child { border-bottom: 0; }
.exec-list b { color: var(--accent); }

/* -------------------------------------------------- amostra de UI por tema */
.ui-demo { display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; }
.ui-frame { border: 1px solid var(--line); border-radius: 2mm; overflow: hidden; break-inside: avoid; }
.ui-frame .cap {
  font-size: 7pt; text-transform: uppercase; letter-spacing: .1em; padding: 2mm 3mm;
  border-bottom: 1px solid var(--line); color: var(--ink-soft); background: var(--panel);
}
.ui-frame .stage { padding: 6mm; }
.ui-card { border-radius: 3mm; padding: 5mm; }
.ui-card .t { font-size: 11pt; font-weight: 650; margin-bottom: 2mm; }
.ui-card .p { font-size: 8.4pt; margin-bottom: 4mm; }
.ui-btn { display: inline-block; padding: 2.5mm 5mm; border-radius: 2mm; font-size: 8.4pt; font-weight: 600; }

/* ------------------------------------------------------------------- cores */
.roles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4mm; }
.role {
  border: 1px solid var(--line); border-radius: 2mm; overflow: hidden; break-inside: avoid;
}
.role .chip { height: 22mm; display: flex; align-items: flex-end; padding: 2.5mm; }
.role .chip .ratio {
  font-size: 6.6pt; padding: .6mm 1.6mm; border-radius: 4mm;
  background: rgba(0,0,0,.28); color: #fff; font-family: var(--doc-mono);
}
.role .meta { padding: 2.5mm 3mm 3mm; }
.role .name { font-size: 9pt; font-weight: 650; letter-spacing: -.01em; }
.role .hex { font-family: var(--doc-mono); font-size: 8pt; color: var(--ink-soft); }
.role .why { font-size: 6.8pt; color: var(--ink-faint); margin-top: 1.2mm; line-height: 1.35; }

.ramp { display: flex; border: 1px solid var(--line); border-radius: 2mm; overflow: hidden; break-inside: avoid; }
.ramp div { flex: 1; height: 17mm; position: relative; }
.ramp div span {
  position: absolute; left: 0; right: 0; bottom: 1.4mm; text-align: center;
  font-family: var(--doc-mono); font-size: 5.9pt;
}
.ramp div small {
  position: absolute; left: 0; right: 0; top: 1.4mm; text-align: center;
  font-family: var(--doc-mono); font-size: 5.6pt; opacity: .75;
}
.swatches { display: grid; grid-template-columns: repeat(6, 1fr); gap: 3mm; }
.sw { break-inside: avoid; }
.sw .box { height: 13mm; border-radius: 1.5mm; border: 1px solid rgba(0,0,0,.08); }
.sw .lbl { font-size: 7pt; margin-top: 1.2mm; line-height: 1.3; }
.sw .lbl b { display: block; font-weight: 600; }
.sw .lbl code { font-family: var(--doc-mono); font-size: 6.6pt; color: var(--ink-soft); }

/* ------------------------------------------------------------- tipografia */
.family { display: flex; justify-content: space-between; align-items: baseline;
  gap: 6mm; padding: 3.5mm 0; border-bottom: 1px solid var(--line-soft); break-inside: avoid; }
.family .sample { font-size: 17pt; letter-spacing: -.015em; }
.family .info { text-align: right; font-family: var(--doc-mono); font-size: 7pt; color: var(--ink-soft); white-space: nowrap; }
.typerow {
  display: grid; grid-template-columns: 26mm 1fr; gap: 5mm; align-items: baseline;
  padding: 3.2mm 0; border-bottom: 1px solid var(--line-soft); break-inside: avoid;
}
.typerow .meta { font-family: var(--doc-mono); font-size: 6.6pt; color: var(--ink-soft); line-height: 1.55; }
.typerow .meta b { font-family: var(--doc-sans); font-size: 7.4pt; color: var(--ink);
  display: block; text-transform: uppercase; letter-spacing: .08em; margin-bottom: .8mm; }
.typerow .sample { overflow: hidden; }

/* --------------------------------------------------------------- escalas */
.spacerow { display: flex; align-items: center; gap: 4mm; padding: 1.5mm 0; break-inside: avoid; }
.spacerow .lbl { width: 30mm; flex: none; font-family: var(--doc-mono); font-size: 7.4pt; color: var(--ink-soft); }
.spacerow .bar { height: 3.4mm; background: var(--accent); border-radius: .8mm; }
.tiles { display: grid; grid-template-columns: repeat(5, 1fr); gap: 4mm; }
.tile { border: 1px solid var(--line); border-radius: 2mm; padding: 3mm; text-align: center; break-inside: avoid; }
.tile .demo { height: 14mm; background: var(--accent-soft); border: 1px solid var(--accent-line); margin-bottom: 2mm; }
.tile .demo.sh { background: #fff; border: 1px solid var(--line-soft); border-radius: 1.5mm; }
.tile b { font-size: 8pt; display: block; }
.tile code { font-family: var(--doc-mono); font-size: 6.4pt; color: var(--ink-soft); word-break: break-all; }

/* --------------------------------------------------------------- tabelas */
table.data { width: 100%; border-collapse: collapse; font-size: 7.6pt; }
table.data th {
  text-align: left; font-size: 6.6pt; text-transform: uppercase; letter-spacing: .1em;
  color: var(--ink-soft); border-bottom: 1px solid var(--line); padding: 1.8mm 2mm; font-weight: 700;
}
table.data td { padding: 1.5mm 2mm; border-bottom: 1px solid var(--line-soft); vertical-align: top; }
table.data tr { break-inside: avoid; }
table.data td.mono, table.data th.mono { font-family: var(--doc-mono); font-size: 7pt; }
table.data td.num { text-align: right; font-family: var(--doc-mono); color: var(--ink-soft); }
.dot { display: inline-block; width: 3.2mm; height: 3.2mm; border-radius: .8mm;
  border: 1px solid rgba(0,0,0,.12); vertical-align: -.6mm; margin-right: 1.5mm; }
.pill {
  display: inline-block; padding: .8mm 2.2mm; border-radius: 4mm; background: var(--panel);
  border: 1px solid var(--line); font-family: var(--doc-mono); font-size: 7pt; margin: 0 1.5mm 1.5mm 0;
}

/* ----------------------------------------------------------- componentes */
/* O card pode quebrar entre páginas (a tabela de estilos é longa), mas o
   cabeçalho e a amostra visual nunca se separam. */
.cmp { border: 1px solid var(--line); border-radius: 2mm; margin-bottom: 5mm; break-inside: auto; }
.cmp-head { display: flex; justify-content: space-between; align-items: baseline; gap: 4mm;
  padding: 2mm 3mm; border-bottom: 1px solid var(--line); background: var(--panel);
  break-after: avoid; break-inside: avoid; }
.cmp-head b { font-size: 8.4pt; }
.cmp-head span { font-family: var(--doc-mono); font-size: 6.4pt; color: var(--ink-faint);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 90mm; }
.cmp-stage { padding: 6mm; display: flex; gap: 4mm; flex-wrap: wrap; align-items: center;
  background: #fff; min-height: 18mm; overflow: hidden; break-inside: avoid; }
.cmp-props { padding: 0 3mm 3mm; }
.cmp-props table { width: 100%; border-collapse: collapse; font-family: var(--doc-mono); font-size: 6.4pt; }
.cmp-props td { padding: .8mm 2mm .8mm 0; border-bottom: 1px solid var(--line-soft); }
.cmp-props td:first-child { color: var(--ink-soft); width: 34mm; }
.cmp-props td.changed { color: var(--accent); font-weight: 600; }
.cmp-props .cap { font-size: 6.6pt; color: var(--ink-faint); padding: 2mm 0 1mm; font-family: var(--doc-sans); }

/* --------------------------------------------------------------- assets */
.icons { display: grid; grid-template-columns: repeat(10, 1fr); gap: 2.5mm; }
.icon {
  aspect-ratio: 1; border: 1px solid var(--line); border-radius: 1.5mm;
  display: flex; align-items: center; justify-content: center; padding: 2mm; overflow: hidden;
}
.icon svg, .icon img { max-width: 100%; max-height: 100%; width: auto; height: auto; }
.logos { display: flex; flex-wrap: wrap; gap: 4mm; }
.logo-box { border: 1px solid var(--line); border-radius: 2mm; padding: 4mm 6mm;
  display: flex; align-items: center; justify-content: center; min-width: 40mm; min-height: 18mm; }
.logo-box svg, .logo-box img { max-width: 55mm; max-height: 14mm; height: auto; width: auto; }
.shots { display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; }
.shot { border: 1px solid var(--line); border-radius: 2mm; overflow: hidden; break-inside: avoid; }
.shot img { width: 100%; display: block; max-height: 105mm; object-fit: cover; object-position: top; }
.shot .cap { padding: 2mm 2.5mm; font-family: var(--doc-mono); font-size: 6.4pt;
  color: var(--ink-soft); word-break: break-all; border-top: 1px solid var(--line); }

/* ------------------------------------------------------------- diagnóstico */
.score-row { display: flex; gap: 5mm; margin-bottom: 6mm; }
.score {
  flex: 1; border: 1px solid var(--line); border-radius: 2mm; padding: 4mm;
  text-align: center; break-inside: avoid;
}
.score b { display: block; font-size: 26pt; line-height: 1; letter-spacing: -.03em; }
.score span { font-size: 7.6pt; color: var(--ink-soft); display: block; margin-top: 1.5mm; }
.score.main b { color: var(--accent); }
.breakdown { list-style: none; padding: 0; margin: 0 0 5mm; font-size: 8pt; }
.breakdown li { padding: 1.2mm 0; border-bottom: 1px solid var(--line-soft); color: var(--ink-soft); }
.pair { display: inline-flex; border: 1px solid var(--line); border-radius: 1mm; overflow: hidden;
  vertical-align: -1mm; margin-right: 1.5mm; }
.pair span { width: 6mm; height: 4.5mm; display: block; }
.axis { display: grid; grid-template-columns: 26mm 1fr 26mm; gap: 3mm; align-items: center;
  padding: 2.4mm 0; break-inside: avoid; }
.axis .left, .axis .right { font-size: 7.4pt; color: var(--ink-faint); }
.axis .right { text-align: right; }
.axis .track { height: 4mm; background: var(--panel); border: 1px solid var(--line);
  border-radius: 2mm; position: relative; }
.axis .dot { position: absolute; top: -1px; width: 4mm; height: 4mm; border-radius: 2mm;
  background: var(--accent); transform: translateX(-2mm); }
.axis .cap { font-size: 7.2pt; color: var(--ink); font-weight: 600; }
.theme-pair { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4mm; }
.theme-pair .row { border: 1px solid var(--line); border-radius: 2mm; overflow: hidden; break-inside: avoid; }
.theme-pair .chips { display: flex; height: 18mm; }
.theme-pair .chips span { flex: 1; }
.theme-pair .meta { padding: 2mm 2.5mm 2.5mm; }
.theme-pair .name { font-size: 8.4pt; font-weight: 650; }
.theme-pair .vals { font-family: var(--doc-mono); font-size: 6.8pt; color: var(--ink-soft); }
.resp { display: grid; grid-template-columns: 22mm repeat(3, 1fr); gap: 2mm 4mm; align-items: baseline;
  font-size: 8pt; padding: 2mm 0; border-bottom: 1px solid var(--line-soft); break-inside: avoid; }
.resp .k { font-weight: 600; }
.resp .v { font-family: var(--doc-mono); font-size: 7.4pt; color: var(--ink-soft); }

.note { border-left: 2px solid var(--accent); background: var(--panel);
  padding: 3mm 4mm; font-size: 8pt; margin: 4mm 0; break-inside: avoid; }
.warn { border-left: 2px solid #d97706; background: #fffbf3; padding: 3mm 4mm;
  font-size: 8pt; margin-bottom: 3mm; break-inside: avoid; }
.two-col { column-count: 2; column-gap: 10mm; }
.avoid { break-inside: avoid; }
code.inline { font-family: var(--doc-mono); font-size: 7.4pt; background: var(--panel);
  border: 1px solid var(--line); border-radius: 1mm; padding: .3mm 1.2mm; }
"""


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _ink_on(color: str) -> str:
    rgba = parse_color(color)
    if rgba is None:
        return "#111"
    return "#fff" if contrast_ratio(rgba, (1, 1, 1, 1)) >= contrast_ratio(rgba, (0, 0, 0, 1)) else "#111"


def _ratio_label(color: str) -> str:
    rgba = parse_color(color)
    if rgba is None:
        return ""
    branco = contrast_ratio(rgba, (1, 1, 1, 1))
    preto = contrast_ratio(rgba, (0, 0, 0, 1))
    if branco >= preto:
        return f"branco {branco:.1f}:1"
    return f"preto {preto:.1f}:1"


def _len(value: Any) -> str:
    if isinstance(value, (int, float)):
        return "9999px" if value >= 9999 else f"{value:g}px"
    return str(value)


class _Doc:
    """Acumula páginas e numera as seções para o sumário."""

    def __init__(self, ds: DesignSystem, accent: str) -> None:
        self.ds = ds
        self.accent = accent
        self.pages: list[str] = []
        self.toc: list[tuple[str, str]] = []
        self._numero = 0

    def page(
        self, kicker: str, title: str, lede: str, body: str, *, count: str = "", in_toc: bool = True
    ) -> None:
        if not body.strip():
            return
        # Continuações de uma seção longa não viram entradas no sumário — quatro
        # linhas "Componentes (cont.)" seguidas não ajudam ninguém.
        if in_toc:
            self.toc.append((title, count))
            self._numero = len(self.toc)
        numero = self._numero
        head = (
            '<div class="page-head">'
            f'<span class="kicker">{_esc(kicker)}</span>'
            f'<span class="src">{_esc(self.ds.name)} · {numero:02d}</span>'
            "</div>"
        )
        lede_html = f'<p class="section-lede">{_esc(lede)}</p>' if lede else ""
        marca = f' data-section="{len(self.toc)}"' if in_toc else ""
        self.pages.append(
            f'<section class="page"{marca}>{head}<h1 class="section">{_esc(title)}</h1>'
            f"{lede_html}{body}</section>"
        )


def build_print_html(ds: DesignSystem) -> str:
    colors = ds.colors or {}
    typo = ds.typography or {}
    roles = colors.get("roles") or {}

    accent = (roles.get("primary") or {}).get("hex") or "#4f46e5"
    if parse_color(accent) is None or luminance(parse_color(accent)) > 0.75:
        accent = "#4f46e5"  # accent claro demais não funciona como cor de texto
    accent_rgba = parse_color(accent) or (0.3, 0.3, 0.9, 1)
    accent_soft = "rgba({}, {}, {}, 0.10)".format(*(round(c * 255) for c in accent_rgba[:3]))
    accent_line = "rgba({}, {}, {}, 0.28)".format(*(round(c * 255) for c in accent_rgba[:3]))

    doc = _Doc(ds, accent)

    # ============================================================ 1. cores
    body = ""
    if roles:
        body += '<div class="roles">'
        for role, info in roles.items():
            body += (
                '<div class="role">'
                f'<div class="chip" style="background:{_esc(info["value"])};color:{_ink_on(info["value"])}">'
                f'<span class="ratio">{_esc(_ratio_label(info["value"]))}</span></div>'
                f'<div class="meta"><div class="name">{_esc(role)}</div>'
                f'<div class="hex">{_esc(info.get("hex") or info["value"])}</div>'
                f'<div class="why">{_esc(info.get("reason", ""))}</div></div></div>'
            )
        body += "</div>"

    neutrals = colors.get("neutrals") or []
    if neutrals:
        from ..analysis.color import scale_name

        body += '<h2 class="block">Escala neutra — claro para escuro</h2><div class="ramp">'
        for index, entry in enumerate(neutrals[:12]):
            ink = _ink_on(entry["value"])
            body += (
                f'<div style="background:{_esc(entry["value"])};color:{ink}">'
                f'<small>{scale_name(index, len(neutrals[:12]))}</small>'
                f'<span>{_esc(entry["hex"])}</span></div>'
            )
        body += "</div>"

    accents = colors.get("accents") or []
    if accents:
        body += '<h2 class="block">Outras cores de destaque</h2><div class="swatches">'
        for index, entry in enumerate(accents[:12], start=1):
            body += (
                f'<div class="sw"><div class="box" style="background:{_esc(entry["value"])}"></div>'
                f'<div class="lbl"><b>accent {index}</b><code>{_esc(entry["hex"])}</code></div></div>'
            )
        body += "</div>"

    doc.page(
        "paleta",
        "Cores",
        "Papéis atribuídos por heurística a partir de onde cada cor aparece na página. "
        "O contraste indicado é o do texto sobre a cor.",
        body,
        count=f'{len(colors.get("clusters") or [])} cores',
    )

    # paleta nomeada + tabela de frequências
    body = ""
    named = colors.get("named") or {}
    if named:
        body += '<h2 class="block">Paleta nomeada (do código-fonte)</h2><div class="swatches">'
        for name, value in list(named.items())[:48]:
            body += (
                f'<div class="sw"><div class="box" style="background:{_esc(value)}"></div>'
                f'<div class="lbl"><b>{_esc(name)}</b><code>{_esc(value)}</code></div></div>'
            )
        body += "</div>"

    clusters = colors.get("clusters") or []
    if clusters:
        body += '<h2 class="block">Todas as cores, por frequência de uso</h2>'
        body += '<table class="data"><tr><th>cor</th><th class="mono">hex</th><th class="num">usos</th>'
        body += "<th>onde aparece</th><th>origem</th></tr>"
        for c in clusters[:46]:
            onde = ", ".join(f"{k} {v}" for k, v in list((c.get("properties") or {}).items())[:3])
            origem = ", ".join(c.get("sources", [])[:1]) or ""
            body += (
                f'<tr><td><span class="dot" style="background:{_esc(c["value"])}"></span></td>'
                f'<td class="mono">{_esc(c["hex"])}</td><td class="num">{c["count"]}</td>'
                f'<td>{_esc(onde or "—")}</td><td class="mono">{_esc(origem[:34])}</td></tr>'
            )
        body += "</table>"
        if len(clusters) > 46:
            body += f'<p class="section-lede" style="margin-top:3mm">… e mais {len(clusters) - 46} cores em raw.json.</p>'
    doc.page("paleta", "Cores em detalhe", "", body)

    # ======================================================= 2. tipografia
    body = ""
    families = typo.get("families") or []
    if families:
        for fam in families[:6]:
            stack = fam.get("stack") or fam["family"]
            body += (
                '<div class="family">'
                f'<div class="sample" style="font-family:{_esc(stack)}">{_esc(fam["family"])} — Aa Bb Cc 0123</div>'
                f'<div class="info">{fam["count"]}× usos</div></div>'
            )

    scale = typo.get("scale") or []
    if scale:
        body += '<h2 class="block">Escala tipográfica</h2>'
        for style in scale:
            css = (
                f"font-family:{style.get('fontFamily') or 'inherit'};"
                f"font-size:{min(float(style['fontSize']), 46)}px;"
                f"font-weight:{style.get('fontWeight', 400)};"
                f"line-height:{style.get('lineHeight', 'normal')};"
                f"letter-spacing:{style.get('letterSpacing', 'normal')};"
                f"text-transform:{style.get('textTransform', 'none')};"
            )
            amostra = style.get("sample") or "The quick brown fox jumps over the lazy dog"
            body += (
                '<div class="typerow">'
                f'<div class="meta"><b>{_esc(style["name"])}</b>'
                f'{style["fontSize"]:g}px · {_esc(style.get("fontWeight", 400))}<br>'
                f'lh {_esc(style.get("lineHeight", "normal"))}<br>'
                f'ls {_esc(style.get("letterSpacing", "normal"))}<br>'
                f'{style.get("count", 0)}× no site</div>'
                f'<div class="sample" style="{_esc(css)}">{_esc(amostra[:70])}</div></div>'
            )
    doc.page(
        "tipografia",
        "Tipografia",
        "Renderizado com as fontes reais do site quando elas puderam ser carregadas.",
        body,
        count=f'{len(families)} famílias',
    )

    body = ""
    sizes = (typo.get("named") or {}).get("fontSize") or name_font_sizes(typo.get("sizes") or [])
    if sizes:
        body += '<h2 class="block">Tamanhos</h2><div class="tiles">'
        for name, value in sizes.items():
            body += f'<div class="tile"><b>{_esc(name)}</b><code>{_esc(_len(value))}</code></div>'
        body += "</div>"
    if typo.get("weights"):
        body += '<h2 class="block">Pesos</h2><div>'
        for weight in typo["weights"]:
            body += f'<span class="pill">{weight}</span>'
        body += "</div>"
    faces = typo.get("font_faces") or []
    if faces:
        body += '<h2 class="block">Regras @font-face</h2><table class="data">'
        body += "<tr><th>família</th><th>peso</th><th>estilo</th><th>arquivo</th></tr>"
        for face in faces[:26]:
            arquivo = face.get("localPath") or (face.get("urls") or [""])[0] or ""
            body += (
                f'<tr><td>{_esc(face["family"])}</td><td class="mono">{_esc(face.get("weight"))}</td>'
                f'<td class="mono">{_esc(face.get("style"))}</td>'
                f'<td class="mono">{_esc(arquivo[-52:])}</td></tr>'
            )
        body += "</table>"
    doc.page("tipografia", "Tokens tipográficos", "", body)

    # ====================================================== 3. espaçamento
    body = ""
    spacing_named = ds.spacing.get("named") or {}
    escala = ds.spacing.get("scale") or []
    itens = list(spacing_named.items()) if spacing_named else [(f"{v:g}", v) for v in escala]
    if itens:
        for name, value in itens:
            from ..analysis.scales import parse_length

            px = value if isinstance(value, (int, float)) else (parse_length(value) or 0)
            largura = min(px, 150)
            body += (
                '<div class="spacerow">'
                f'<div class="lbl">{_esc(name)} · {_esc(_len(value))}</div>'
                f'<div class="bar" style="width:{largura:g}mm"></div></div>'
            )
        if ds.spacing.get("base_unit"):
            body += (
                f'<div class="note">Grade base detectada: <b>{ds.spacing["base_unit"]:g}px</b>. '
                "Os degraus acima são os valores de <code class='inline'>margin</code>, "
                "<code class='inline'>padding</code> e <code class='inline'>gap</code> mais frequentes.</div>"
            )

    radii_named = ds.radii.get("named") or {}
    if radii_named:
        body += '<h2 class="block">Border radius</h2><div class="tiles">'
        for name, value in radii_named.items():
            body += (
                f'<div class="tile"><div class="demo" style="border-radius:{_esc(_len(value))}"></div>'
                f'<b>{_esc(name)}</b><code>{_esc(_len(value))}</code></div>'
            )
        body += "</div>"
    doc.page("layout", "Espaçamento e raios", "", body, count=f"{len(itens)} degraus")

    # ========================================================== 4. sombras
    body = ""
    if ds.shadows:
        body += '<div class="tiles">'
        for index, shadow in enumerate(ds.shadows):
            nome = shadow.get("name") or f"sombra {index + 1}"
            body += (
                f'<div class="tile"><div class="demo sh" style="box-shadow:{_esc(shadow["value"])}"></div>'
                f'<b>{_esc(nome)}</b><code>{_esc(shadow["value"][:52])}</code></div>'
            )
        body += "</div>"

    outros = ""
    if ds.breakpoints:
        outros += "<h2 class='block'>Breakpoints</h2><div>" + "".join(
            f'<span class="pill">{bp}px</span>' for bp in ds.breakpoints
        ) + "</div>"
    if ds.containers:
        outros += "<h2 class='block'>Larguras de container</h2><div>" + "".join(
            f'<span class="pill">{c:g}px</span>' for c in ds.containers
        ) + "</div>"
    if ds.borders.get("widths"):
        outros += "<h2 class='block'>Larguras de borda</h2><div>" + "".join(
            f'<span class="pill">{w:g}px</span>' for w in ds.borders["widths"]
        ) + "</div>"
    motion = ds.motion or {}
    if motion.get("durations") or motion.get("easings"):
        outros += "<h2 class='block'>Movimento</h2><div>"
        outros += "".join(f'<span class="pill">{_esc(d)}</span>' for d in motion.get("durations", []))
        outros += "".join(f'<span class="pill">{_esc(e)}</span>' for e in motion.get("easings", []))
        outros += "</div>"
    if ds.z_index:
        outros += "<h2 class='block'>z-index</h2><div>" + "".join(
            f'<span class="pill">{z}</span>' for z in ds.z_index
        ) + "</div>"
    if ds.opacity:
        outros += "<h2 class='block'>Opacidades</h2><div>" + "".join(
            f'<span class="pill">{o:g}</span>' for o in ds.opacity
        ) + "</div>"
    if outros:
        body += outros
    doc.page("estilo", "Sombras e demais tokens", "", body, count=f"{len(ds.shadows)} sombras")

    # ====================================================== 5. componentes
    comps = [c.to_dict() if hasattr(c, "to_dict") else c for c in ds.components]
    if comps:
        pedaco: list[str] = []
        for comp in comps:
            pedaco.append(_component_block(comp))
        # 3 componentes por página para não estourar a altura
        for i in range(0, len(pedaco), 3):
            doc.page(
                "componentes",
                "Componentes" if i == 0 else "Componentes (cont.)",
                "Amostras reconstruídas a partir dos estilos computados capturados no site, "
                "com as diferenças de :hover e :focus destacadas."
                if i == 0
                else "",
                "".join(pedaco[i : i + 3]),
                count=f"{len(comps)} detectados" if i == 0 else "",
                in_toc=(i == 0),
            )

    # =========================================================== 6. assets
    body = ""
    logos = [a for a in ds.assets if a.kind == "logo"]
    if logos:
        body += '<h2 class="block">Logo</h2><div class="logos">'
        for logo in logos[:6]:
            if logo.inline_svg:
                body += f'<div class="logo-box">{_sanitize_html(logo.inline_svg)}</div>'
            elif logo.path:
                body += f'<div class="logo-box"><img src="{_esc(logo.path)}" alt=""></div>'
        body += "</div>"
    icones = [a for a in ds.assets if a.kind in ("icon", "favicon")]
    if icones:
        body += f'<h2 class="block">Ícones ({len(icones)})</h2><div class="icons">'
        for icone in icones[:80]:
            if icone.inline_svg:
                body += f'<div class="icon">{_sanitize_html(icone.inline_svg)}</div>'
            elif icone.path:
                body += f'<div class="icon"><img src="{_esc(icone.path)}" alt=""></div>'
        body += "</div>"
    fontes = [a for a in ds.assets if a.kind == "font"]
    if fontes:
        body += '<h2 class="block">Arquivos de fonte</h2><table class="data">'
        body += "<tr><th>família</th><th>arquivo</th></tr>"
        for asset in fontes[:22]:
            body += (
                f'<tr><td>{_esc(asset.note)}</td>'
                f'<td class="mono">{_esc((asset.path or asset.url)[-58:])}</td></tr>'
            )
        body += "</table>"
    doc.page("assets", "Assets", "Arquivos baixados para a pasta assets/.", body,
             count=f'{len([a for a in ds.assets if a.kind != "screenshot"])} arquivos')

    # ==================================================== 7. variáveis CSS
    if ds.css_variables:
        body = '<table class="data"><tr><th>variável</th><th>valor</th><th>origem</th></tr>'
        for name, info in list(ds.css_variables.items())[:120]:
            valor = str(info.get("value", ""))
            cor = parse_color(valor)
            ponto = f'<span class="dot" style="background:{_esc(valor)}"></span>' if cor else ""
            body += (
                f'<tr><td class="mono">{_esc(name[:44])}</td>'
                f'<td class="mono">{ponto}{_esc(valor[:44])}</td>'
                f'<td class="mono">{_esc(str(info.get("origin", ""))[-34:])}</td></tr>'
            )
        body += "</table>"
        if len(ds.css_variables) > 120:
            body += (
                f'<p class="section-lede" style="margin-top:3mm">Mostrando 120 de '
                f"{len(ds.css_variables)} variáveis. A lista completa está em variables.css e raw.json.</p>"
            )
        doc.page("tokens", "Variáveis CSS", "", body, count=f"{len(ds.css_variables)} vars")

    # ======================================================= 8. screenshots
    shots = [a for a in ds.assets if a.kind == "screenshot"]
    if shots:
        body = '<div class="shots">'
        for shot in shots[:8]:
            body += (
                f'<div class="shot"><img src="{_esc(shot.path)}" alt="">'
                f'<div class="cap">{_esc(shot.url)}</div></div>'
            )
        body += "</div>"
        doc.page("captura", "Páginas capturadas", "Screenshot full-page de cada página visitada (topo).", body,
                 count=f"{len(shots)} páginas")

    # ============================================================ 9. temas
    doc.page(
        "temas",
        "Tema claro e escuro",
        "Cada papel com o valor nos dois temas. O escuro foi capturado do próprio "
        "site, não derivado por cálculo.",
        _temas(ds),
        count="2 temas",
    )

    # ==================================================== 10. responsividade
    doc.page(
        "responsivo",
        "Escala responsiva",
        "Como a tipografia muda entre telas — medido em cada largura, não inferido "
        "das media queries.",
        _responsivo(ds),
        count=f"{len((ds.responsive or {}).get('fluid') or {})} papéis",
    )

    # ====================================================== 11. diagnóstico
    doc.page(
        "diagnóstico",
        "Diagnóstico",
        "Notas calculadas sobre o que foi medido. Cada desconto vem com a razão — "
        "e o que não pôde ser verificado não entra na conta.",
        _diagnostico(ds),
        count=f"nota {(ds.diagnostics or {}).get('score', '—')}",
    )

    # ================================================== 12. assinatura visual
    doc.page(
        "assinatura",
        "Assinatura visual",
        "O caráter do sistema em cinco eixos, derivados dos tokens.",
        _assinatura(ds),
    )

    # =========================================================== 13. contexto
    doc.page(
        "contexto",
        "Contexto técnico",
        "De onde vem o que está sendo usado.",
        _contexto(ds),
    )

    # ========================================================= 14. apêndice
    body = _apendice(ds)
    doc.page("referência", "Como usar", "", body)

    # ------------------------------------------------------------- montagem
    capa = _cover(ds, accent, doc)
    resumo = _resumo(ds)
    sumario = _toc_page(ds, doc)
    corpo = "".join(doc.pages)

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Design system — {_esc(ds.name)}</title>
<style>
{PRINT_CSS}
:root {{
  --accent: {accent};
  --accent-soft: {accent_soft};
  --accent-line: {accent_line};
}}
{_font_faces_css(ds)}
</style></head>
<body>{capa}{resumo}{sumario}{corpo}</body></html>
"""


def _cover(ds: DesignSystem, accent: str, doc: _Doc) -> str:
    colors = ds.colors or {}
    faixa: list[str] = []
    for cluster in (colors.get("clusters") or []):
        if len(faixa) >= 16:
            break
        faixa.append(cluster["value"])
    faixa = faixa or [accent]
    band = "".join(f'<span style="background:{_esc(c)}"></span>' for c in faixa)

    logo_html = ""
    for asset in ds.assets:
        if asset.kind == "logo":
            if asset.inline_svg:
                logo_html = f'<div class="cover-logo">{_sanitize_html(asset.inline_svg)}</div>'
            elif asset.path:
                logo_html = f'<div class="cover-logo"><img src="{_esc(asset.path)}" alt=""></div>'
            break

    # No modo repo o alvo é o próprio nome do repositório, que já está no
    # título — repetir logo abaixo não acrescenta nada.
    alvo = ""
    if ds.display_target and ds.display_target != ds.name:
        alvo = f'<div class="target">{_esc(ds.display_target)}</div>'

    # Papéis principais já na capa: é o resumo que a maioria vai querer ver.
    principais = ""
    roles = colors.get("roles") or {}
    destaque = [r for r in ("primary", "secondary", "background", "surface", "text", "border") if r in roles]
    if len(destaque) >= 3:
        principais = '<div class="cover-roles">' + "".join(
            f'<div><div class="box" style="background:{_esc(roles[r]["value"])}"></div>'
            f'<b>{_esc(r)}</b><code>{_esc(roles[r].get("hex") or roles[r]["value"])}</code></div>'
            for r in destaque[:6]
        ) + "</div>"

    # Amostra tipográfica na capa: mostra as fontes reais logo de cara.
    tipografia = ""
    familias = (ds.typography or {}).get("families") or []
    reais = [f for f in familias if not f.get("generic")][:3] or familias[:2]
    if reais:
        linhas = ""
        for familia in reais:
            stack = familia.get("stack") or familia["family"]
            linhas += (
                '<div class="row">'
                f'<span class="big" style="font-family:{_esc(stack)}">'
                f'{_esc(familia["family"])} — Aa Bb Cc 0123</span>'
                f'<span class="meta">{familia.get("count", 0)}× usos</span></div>'
            )
        tipografia = f'<div class="cover-type">{linhas}</div>'

    contagens = [(k, v) for k, v in ds.counts().items() if v][:8]
    stats = "".join(
        f"<div><b>{v}</b><span>{_esc(k)}</span></div>" for k, v in contagens
    )
    origem = "site ao vivo" if ds.mode == "url" else "repositório local"
    quando = ds.generated_at[:19].replace("T", " ")

    return f"""<section class="page cover">
  <div class="cover-band">{band}</div>
  <div class="cover-body">
    <div class="eyebrow">design system extraído</div>
    {logo_html}
    <h1>{_esc(ds.name)}</h1>
    {alvo}
    {principais}
    {tipografia}
    <div class="cover-stats">{stats}</div>
  </div>
  <div class="cover-foot"><span>{_esc(origem)} · {_esc(quando)}</span><span>gerado por designsys</span></div>
</section>"""


def _resumo(ds: DesignSystem) -> str:
    """Uma página que responde sozinha: se a pessoa ler só isto, já sabe o essencial."""
    papeis = ds.colors.get("roles") or {}
    diag = ds.diagnostics or {}
    assinatura = (diag.get("signature") or {}).get("sentence", "")
    contexto = ds.context or {}
    typo = ds.typography or {}
    familias = [f for f in (typo.get("families") or []) if not f.get("generic")]

    destaque = [p for p in ("primary", "secondary", "background", "surface", "text", "border") if p in papeis]
    swatches = "".join(
        f'<span style="background:{_esc(papeis[p]["value"])}"></span>' for p in destaque[:6]
    )

    cartoes: list[str] = []

    if swatches:
        principal = papeis.get("primary") or papeis.get("secondary") or {}
        nome_cor = (contexto.get("colorNames") or {}).get(principal.get("hex", ""), "")
        cartoes.append(
            '<div class="exec-card"><h3>paleta</h3>'
            f'<div class="exec-swatches">{swatches}</div>'
            f'<div class="big">{_esc(principal.get("hex", "—"))}</div>'
            f'<div class="sub">cor primária{f" · {_esc(nome_cor)}" if nome_cor else ""}. '
            f'{len(ds.colors.get("clusters") or [])} cores agrupadas no total.</div></div>'
        )

    if familias:
        stack = familias[0].get("stack") or familias[0]["family"]
        fontes_ctx = {f["family"]: f for f in (contexto.get("fonts") or [])}
        info = fontes_ctx.get(familias[0]["family"], {})
        alternativa = info.get("alternative")
        cartoes.append(
            '<div class="exec-card"><h3>tipografia</h3>'
            f'<div class="big" style="font-family:{_esc(stack)}">{_esc(familias[0]["family"])}</div>'
            f'<div class="sub">{len(familias)} família(s) em uso · {_esc(info.get("source", "origem não identificada"))}'
            + (f" · alternativa livre: {_esc(alternativa)}" if alternativa else "")
            + "</div></div>"
        )

    if diag.get("score") is not None:
        a11y = diag.get("accessibility") or {}
        cons = diag.get("consistency") or {}
        cartoes.append(
            '<div class="exec-card"><h3>diagnóstico</h3>'
            f'<div class="big">{diag.get("score")}<span style="font-size:9pt;color:var(--ink-faint)"> / 100</span></div>'
            f'<div class="sub">acessibilidade {a11y.get("score", "—")} · consistência {cons.get("score", "—")}<br>'
            f'{_esc(a11y.get("summary", ""))}</div></div>'
        )

    if assinatura:
        cartoes.append(
            '<div class="exec-card"><h3>caráter</h3>'
            f'<div class="big" style="font-size:12pt;line-height:1.4">{_esc(assinatura)}</div>'
            f'<div class="sub">{_esc(contexto.get("frameworkSummary", ""))}</div></div>'
        )

    if not cartoes:
        return ""

    destaques: list[str] = []
    if ds.has_dark:
        destaques.append("Tem tema claro <b>e</b> escuro — os dois estão documentados aqui.")
    fluidos = (ds.responsive or {}).get("fluid") or {}
    if fluidos:
        destaques.append(f"<b>{len(fluidos)}</b> papéis tipográficos mudam de tamanho entre telas.")
    unidade = ds.spacing.get("base_unit")
    if unidade:
        destaques.append(f"Espaçamento em grade de <b>{unidade:g}px</b>.")
    a11y = diag.get("accessibility") or {}
    if a11y.get("contrast"):
        destaques.append(
            f"<b>{len(a11y['contrast'])}</b> combinações de texto abaixo do mínimo de contraste AA."
        )
    if a11y.get("focusMissing"):
        destaques.append(
            f"<b>{len(a11y['focusMissing'])}</b> componentes sem indicação visível de foco."
        )
    if ds.breakpoints:
        destaques.append(f"<b>{len(ds.breakpoints)}</b> breakpoints declarados.")

    lista = ""
    if destaques:
        lista = (
            '<h2 class="block">Em uma olhada</h2><ul class="exec-list">'
            + "".join(f"<li>{d}</li>" for d in destaques[:6])
            + "</ul>"
        )

    return (
        '<section class="page">'
        '<div class="page-head"><span class="kicker">resumo</span>'
        f'<span class="src">{_esc(ds.name)}</span></div>'
        '<h1 class="section">O essencial</h1>'
        '<p class="section-lede">O documento inteiro em uma página.</p>'
        f'<div class="exec">{"".join(cartoes)}</div>'
        f"{lista}</section>"
    )


def _toc_page(ds: DesignSystem, doc: _Doc) -> str:
    itens = ""
    for index, (titulo, contagem) in enumerate(doc.toc, start=1):
        # `data-toc` é preenchido com o número de página depois da medição do
        # layout de impressão — ver `pdfrender.paginate`.
        itens += (
            f'<div class="toc-item"><span class="n">{index:02d}</span>'
            f'<span class="t">{_esc(titulo)}</span>'
            f'<span class="c">{_esc(contagem)}</span>'
            f'<span class="pg" data-toc="{index}">·</span></div>'
        )
    avisos = ""
    if ds.warnings:
        avisos = "".join(f'<div class="warn">{_esc(w)}</div>' for w in ds.warnings[:5])

    login = (ds.raw or {}).get("login")
    login_html = ""
    if login:
        metodos = {
            "session": "sessão salva de execução anterior",
            "auto": "usuário e senha",
            "otp": "código de uso único (OTP)",
            "magic-link": "link de acesso por e-mail",
            "manual": "login manual no navegador",
        }
        metodo = metodos.get(login.get("method", ""), login.get("method", ""))
        login_html = (
            f'<div class="note"><b>Autenticação:</b> {_esc(metodo)} — '
            f'{_esc(login.get("detail", ""))}. Nenhuma senha foi gravada em disco.</div>'
        )

    paginas = ""
    if ds.pages:
        paginas = '<h2 class="block">Páginas visitadas</h2><table class="data">'
        paginas += '<tr><th>URL</th><th class="num">elementos</th><th class="num">regras CSS</th></tr>'
        for page in ds.pages[:12]:
            paginas += (
                f'<tr><td class="mono">{_esc(page["url"][:64])}</td>'
                f'<td class="num">{page.get("elements", 0)}</td>'
                f'<td class="num">{page.get("rules", 0)}</td></tr>'
            )
        paginas += "</table>"
    elif ds.files_scanned:
        paginas = '<h2 class="block">Arquivos lidos</h2><table class="data">'
        for arquivo in ds.files_scanned[:16]:
            paginas += f'<tr><td class="mono">{_esc(arquivo)}</td></tr>'
        paginas += "</table>"

    return f"""<section class="page">
  <div class="page-head"><span class="kicker">sumário</span>
  <span class="src">{_esc(ds.name)}</span></div>
  <h1 class="section">Neste documento</h1>
  <div class="toc">{itens}</div>
  {login_html}{avisos}{paginas}
</section>"""


def _component_block(comp: dict[str, Any]) -> str:
    from .styleguide import _component_sample

    base = comp.get("base") or {}
    hover = comp.get("hover") or {}
    focus = comp.get("focus") or {}

    destaques = [
        "background-color",
        "color",
        "border-radius",
        "border-top-width",
        "border-top-color",
        "box-shadow",
        "padding-top",
        "padding-left",
        "font-size",
        "font-weight",
        "line-height",
        "letter-spacing",
        "outline-width",
        "outline-color",
        "transition-duration",
    ]
    linhas = ""
    for prop in destaques:
        valor = base.get(prop)
        h = hover.get(prop)
        f = focus.get(prop)
        # O anel de foco costuma existir só no :focus — sem esta condição, a
        # propriedade mais importante do estado sumiria da tabela.
        if not valor and not h and not f:
            continue
        if not valor:
            valor = "—"
        estados = []
        if h and h != valor:
            estados.append(f'<span class="changed">hover: {_esc(h)}</span>')
        if f and f != valor:
            estados.append(f'<span class="changed">focus: {_esc(f)}</span>')
        linhas += (
            f"<tr><td>{_esc(prop)}</td><td>{_esc(valor)}</td>"
            f'<td class="changed">{" · ".join(estados)}</td></tr>'
        )

    tabela = ""
    if linhas:
        tabela = (
            '<div class="cmp-props"><div class="cap">estilos computados — mudanças de estado à direita</div>'
            f"<table>{linhas}</table></div>"
        )

    return (
        '<div class="cmp">'
        f'<div class="cmp-head"><b>{_esc(comp.get("kind"))}</b>'
        f'<span>{_esc((comp.get("selector") or "")[:110])}</span></div>'
        f'<div class="cmp-stage">{_component_sample(comp)}</div>'
        f"{tabela}</div>"
    )


def _temas(ds: DesignSystem) -> str:
    pares = (ds.themes or {}).get("pairs") or {}
    completos = {p: v for p, v in pares.items() if v.get("light") and v.get("dark")}
    if not completos:
        return ""

    deteccao = (ds.themes or {}).get("detection") or {}
    corpo = ""
    if deteccao.get("strategy") and deteccao.get("strategy") != "none":
        modo = {
            "prefers-color-scheme": "preferência do sistema (prefers-color-scheme)",
            "class": "classe/atributo na raiz do documento",
            "toggle": "o próprio botão de tema do site",
        }.get(deteccao["strategy"], deteccao["strategy"])
        corpo += f'<div class="note">Tema escuro obtido via <b>{_esc(modo)}</b>.</div>'

    corpo += '<div class="theme-pair">'
    for papel, valores in completos.items():
        corpo += (
            '<div class="row"><div class="chips">'
            f'<span style="background:{_esc(valores["light"])}"></span>'
            f'<span style="background:{_esc(valores["dark"])}"></span>'
            "</div>"
            f'<div class="meta"><div class="name">{_esc(papel)}</div>'
            f'<div class="vals">claro {_esc(valores["light"])}<br>escuro {_esc(valores["dark"])}</div>'
            "</div></div>"
        )
    corpo += "</div>"

    corpo += _ui_nos_dois_temas(ds, pares)

    so_escuro = {p: v for p, v in pares.items() if v.get("dark") and not v.get("light")}
    if so_escuro:
        corpo += '<h2 class="block">Só no tema escuro</h2><div>'
        corpo += "".join(
            f'<span class="pill">{_esc(p)} {_esc(v["dark"])}</span>' for p, v in so_escuro.items()
        )
        corpo += "</div>"
    return corpo


def _ui_nos_dois_temas(ds: DesignSystem, pares: dict[str, Any]) -> str:
    """Um cartão e um botão montados com os tokens de cada tema, lado a lado.

    Ver a paleta em swatches não é o mesmo que ver a paleta funcionando: é aqui
    que um contraste ruim no tema escuro fica evidente.
    """

    def valor(papel: str, tema: str, alternativa: str = "") -> str:
        return (pares.get(papel) or {}).get(tema) or alternativa

    if not valor("background", "dark") and not valor("surface", "dark"):
        return ""

    raio = 8.0
    escala = ds.radii.get("scale") or []
    if escala:
        raio = min((r for r in escala if r >= 4), default=escala[0])
    sombra = ds.shadows[0]["value"] if ds.shadows else "none"
    familias = (ds.typography or {}).get("families") or []
    stack = familias[0].get("stack") if familias else "inherit"

    def moldura(tema: str, rotulo: str) -> str:
        fundo = valor("background", tema, "#ffffff" if tema == "light" else "#0b0f14")
        superficie = valor("surface", tema, fundo)
        texto = valor("text", tema, "#111111" if tema == "light" else "#f5f5f5")
        suave = valor("text-muted", tema, texto)
        borda = valor("border", tema, "rgba(128,128,128,.25)")
        primaria = valor("primary", tema, "#4f46e5")
        rgba_primaria = parse_color(primaria)
        sobre_primaria = _ink_on(primaria) if rgba_primaria else "#fff"
        return (
            f'<div class="ui-frame"><div class="cap">{_esc(rotulo)}</div>'
            f'<div class="stage" style="background:{_esc(fundo)};font-family:{_esc(stack)}">'
            f'<div class="ui-card" style="background:{_esc(superficie)};border:1px solid {_esc(borda)};'
            f'box-shadow:{_esc(sombra)};border-radius:{raio:g}px">'
            f'<div class="t" style="color:{_esc(texto)}">Título do cartão</div>'
            f'<div class="p" style="color:{_esc(suave)}">Texto de apoio com a cor secundária do tema.</div>'
            f'<span class="ui-btn" style="background:{_esc(primaria)};color:{sobre_primaria};'
            f'border-radius:{raio:g}px">Ação principal</span>'
            "</div></div></div>"
        )

    return (
        '<h2 class="block">A mesma interface nos dois temas</h2>'
        f'<div class="ui-demo">{moldura("light", "tema claro")}{moldura("dark", "tema escuro")}</div>'
    )


def _responsivo(ds: DesignSystem) -> str:
    resp = ds.responsive or {}
    fluidos = resp.get("fluid") or {}
    if not fluidos:
        return ""
    larguras = resp.get("widths") or {}
    ordem = sorted(larguras, key=lambda t: larguras[t])

    corpo = '<div class="resp"><div class="k">papel</div>'
    for tela in ordem:
        corpo += f'<div class="v">{_esc(tela)} · {larguras[tela]}px</div>'
    corpo += "</div>"

    for papel, tamanhos in fluidos.items():
        corpo += f'<div class="resp"><div class="k">{_esc(papel)}</div>'
        for tela in ordem:
            valor = tamanhos.get(tela)
            corpo += f'<div class="v">{f"{valor:g}px" if valor else "—"}</div>'
        corpo += "</div>"

    corpo += (
        '<div class="note">O <code class="inline">variables.css</code> traz esses papéis '
        "também como <code class='inline'>clamp()</code>, interpolando entre as larguras medidas.</div>"
    )

    containers = resp.get("containers") or {}
    if any(containers.values()):
        corpo += '<h2 class="block">Largura de container por tela</h2><div>'
        for tela, valores in containers.items():
            if valores:
                lista = ", ".join(f"{v:g}px" for v in valores[:3])
                corpo += f'<span class="pill">{_esc(tela)}: {lista}</span>'
        corpo += "</div>"
    return corpo


def _diagnostico(ds: DesignSystem) -> str:
    diag = ds.diagnostics or {}
    if not diag:
        return ""
    a11y = diag.get("accessibility") or {}
    cons = diag.get("consistency") or {}

    corpo = (
        '<div class="score-row">'
        f'<div class="score main"><b>{diag.get("score", "—")}</b><span>nota geral</span></div>'
        f'<div class="score"><b>{a11y.get("score", "—")}</b><span>acessibilidade</span></div>'
        f'<div class="score"><b>{cons.get("score", "—")}</b><span>consistência</span></div>'
        "</div>"
    )

    avaliado = diag.get("evaluated") or {}
    corpo += (
        f'<div class="note">Base da avaliação: {avaliado.get("contrastPairs", 0)} combinações de '
        f'texto/fundo medidas na página, {avaliado.get("components", 0)} componentes com estado de '
        f'foco capturado e {avaliado.get("colors", 0)} cores. O que não foi medido não foi pontuado.</div>'
    )

    corpo += '<h2 class="block">Acessibilidade</h2>'
    corpo += '<ul class="breakdown">' + "".join(
        f"<li>{_esc(p)}</li>" for p in a11y.get("breakdown") or []
    ) + "</ul>"

    falhas = a11y.get("contrast") or []
    if falhas:
        corpo += '<table class="data"><tr><th>par</th><th class="mono">contraste</th>'
        corpo += '<th class="mono">mínimo</th><th class="num">ocorrências</th><th>exemplo</th></tr>'
        for item in falhas[:10]:
            corpo += (
                "<tr><td>"
                f'<span class="pair"><span style="background:{_esc(item["bg"])}"></span>'
                f'<span style="background:{_esc(item["fg"])}"></span></span>'
                f'<span class="mono" style="font-size:6.8pt">{_esc(item["fg"])} / {_esc(item["bg"])}</span></td>'
                f'<td class="mono">{item["ratio"]}:1</td>'
                f'<td class="mono">{item["required"]}:1</td>'
                f'<td class="num">{item["count"]}</td>'
                f'<td>{_esc(item.get("sample", ""))[:34]}</td></tr>'
            )
        corpo += "</table>"

    sem_foco = a11y.get("focusMissing") or []
    if sem_foco:
        corpo += (
            '<div class="warn"><b>Foco invisível:</b> '
            + ", ".join(_esc(k) for k in sem_foco[:8])
            + " — o estado <code class='inline'>:focus</code> não muda nada perceptível."
            "</div>"
        )

    corpo += '<h2 class="block">Consistência</h2>'
    corpo += '<ul class="breakdown">' + "".join(
        f"<li>{_esc(p)}</li>" for p in cons.get("breakdown") or []
    ) + "</ul>"

    fora = cons.get("spacingOffGrid") or []
    if fora:
        corpo += '<table class="data"><tr><th class="mono">valor</th><th class="num">usos</th>'
        corpo += '<th class="mono">degrau mais próximo</th></tr>'
        for item in fora[:8]:
            corpo += (
                f'<tr><td class="mono">{_esc(item["value"])}</td>'
                f'<td class="num">{item["count"]}</td>'
                f'<td class="mono">{_esc(item["nearest"])}</td></tr>'
            )
        corpo += "</table>"

    orfas = cons.get("orphanColors") or []
    if orfas:
        corpo += '<h2 class="block">Cores usadas uma vez só</h2><div>'
        for item in orfas[:10]:
            perto = f" ≈ {item['near']}" if item.get("near") else ""
            corpo += (
                f'<span class="pill"><span class="dot" style="background:{_esc(item["hex"])}"></span>'
                f'{_esc(item["hex"])}{_esc(perto)}</span>'
            )
        corpo += "</div>"

    fantasmas = cons.get("ghostTokens") or []
    if fantasmas:
        corpo += (
            '<h2 class="block">Tokens declarados e nunca usados</h2><div>'
            + "".join(f'<span class="pill">{_esc(t)}</span>' for t in fantasmas[:16])
            + "</div>"
        )
    return corpo


def _assinatura(ds: DesignSystem) -> str:
    assinatura = (ds.diagnostics or {}).get("signature") or {}
    eixos = assinatura.get("axes") or []
    if not eixos:
        return ""

    corpo = f'<div class="note" style="font-size:10pt">{_esc(assinatura.get("sentence", ""))}</div>'
    for eixo in eixos:
        posicao = max(0.0, min(1.0, float(eixo.get("value", 0.5)))) * 100
        corpo += (
            '<div class="axis">'
            f'<div class="left">{_esc(eixo["left"])}</div>'
            f'<div class="track"><div class="dot" style="left:{posicao:.1f}%"></div></div>'
            f'<div class="right">{_esc(eixo["right"])}</div>'
            "</div>"
            f'<div style="margin:-1.5mm 0 2mm 29mm;font-size:7.2pt;color:var(--ink-faint)">'
            f'<b style="color:var(--ink)">{_esc(eixo["label"])}</b> — {_esc(eixo.get("detail", ""))}</div>'
        )
    return corpo


def _contexto(ds: DesignSystem) -> str:
    ctx = ds.context or {}
    corpo = ""

    frameworks = ctx.get("frameworks") or []
    corpo += '<h2 class="block">Base de UI</h2>'
    corpo += f'<div class="note">{_esc(ctx.get("frameworkSummary", "—"))}</div>'
    if frameworks:
        corpo += '<table class="data"><tr><th>biblioteca</th><th class="mono">confiança</th><th>evidência</th></tr>'
        for item in frameworks:
            versao = f' {item["version"]}' if item.get("version") else ""
            corpo += (
                f'<tr><td>{_esc(item["name"])}{_esc(versao)}</td>'
                f'<td class="mono">{item["confidence"]:.0%}</td>'
                f'<td class="mono">{_esc(", ".join(item.get("evidence", [])[:3]))}</td></tr>'
            )
        corpo += "</table>"

    conhecida = ctx.get("knownPalette") or {}
    if conhecida.get("count"):
        familias = ", ".join(sorted(conhecida.get("matches", {}))[:10])
        corpo += (
            f'<div class="note">A paleta coincide com a padrão do Tailwind em '
            f'<b>{conhecida["count"]}</b> família(s): {_esc(familias)}.</div>'
        )

    fontes = ctx.get("fonts") or []
    if fontes:
        corpo += '<h2 class="block">Fontes</h2><table class="data">'
        corpo += "<tr><th>família</th><th>origem</th><th>licença</th><th>alternativa livre</th></tr>"
        for fonte in fontes[:8]:
            alternativa = fonte.get("alternative")
            texto_alt = (
                f'{alternativa} <span style="color:var(--ink-faint)">({fonte.get("alternative_reason", "")})</span>'
                if alternativa
                else "—"
            )
            corpo += (
                f'<tr><td>{_esc(fonte["family"])}</td>'
                f'<td>{_esc(fonte.get("source", "—"))}</td>'
                f'<td>{"livre" if fonte.get("libre") else "proprietária"}</td>'
                f"<td>{texto_alt}</td></tr>"
            )
        corpo += "</table>"

    nomes = ctx.get("colorNames") or {}
    if nomes:
        corpo += '<h2 class="block">Nomes das cores</h2><div>'
        for hexv, nome in list(nomes.items())[:24]:
            corpo += (
                f'<span class="pill"><span class="dot" style="background:{_esc(hexv)}"></span>'
                f"{_esc(nome)}</span>"
            )
        corpo += "</div>"
        corpo += (
            '<div class="note">Nomes declarados pelo site quando existem (variáveis CSS); '
            "nos demais, derivados da posição da cor em OKLCH.</div>"
        )
    return corpo


def _apendice(ds: DesignSystem) -> str:
    arquivos = [
        ("tokens.json", "Design tokens no formato W3C DTCG ($value/$type). Entrada para Style Dictionary, Tokens Studio e afins."),
        ("variables.css", "Os mesmos tokens como CSS custom properties — importe e use var(--color-primary)."),
        ("tailwind.config.js", "Bloco theme.extend pronto para colar num projeto Tailwind."),
        ("components.json", "Estilos computados completos dos componentes, incluindo :hover e :focus."),
        ("style-guide.html", "Versão navegável deste documento, com swatches clicáveis."),
        ("raw.json", "Dump bruto com frequências e procedência — para auditar qualquer decisão desta extração."),
        ("assets/", "Logo, ícones, fontes e imagens."),
    ]
    if ds.mode == "url":
        arquivos.append(("screenshots/", "Screenshot full-page de cada página visitada."))

    linhas = "".join(
        f'<tr><td class="mono">{_esc(nome)}</td><td>{_esc(desc)}</td></tr>' for nome, desc in arquivos
    )
    body = (
        '<h2 class="block">Arquivos gerados nesta pasta</h2>'
        f'<table class="data"><tr><th>arquivo</th><th>para que serve</th></tr>{linhas}</table>'
    )

    body += (
        '<h2 class="block">Como este documento foi montado</h2>'
        '<div class="two-col" style="font-size:8.4pt;color:var(--ink-soft)">'
    )
    if ds.mode == "url":
        body += (
            "<p>O Chromium carregou cada página com JavaScript renderizado e percorreu todos os "
            "elementos visíveis lendo <code class='inline'>getComputedStyle</code>. Cores, espaçamento, "
            "raios, sombras, tipografia e transições vêm daí, com a frequência de cada valor.</p>"
            "<p>As custom properties foram lidas via CSSOM; folhas de estilo bloqueadas por CORS "
            "foram baixadas por HTTP e analisadas separadamente.</p>"
            "<p>Cores quase idênticas foram agrupadas por distância perceptual em OKLab, e o "
            "representante de cada grupo é sempre um valor que existe de verdade no site — nunca uma média.</p>"
            "<p>Os papéis semânticos são heurísticos: cada um traz o motivo da escolha ao lado. "
            "Quando discordar, o raw.json tem as frequências completas para conferir.</p>"
        )
    else:
        body += (
            "<p>Os arquivos do repositório foram lidos sem executar nenhum código: o "
            "<code class='inline'>tailwind.config</code> passa por um parser tolerante de objetos "
            "JavaScript, e o CSS/SCSS/LESS por um parser de CSS.</p>"
            "<p>Valores que dependem de execução (imports, spreads, funções) não são inventados — "
            "aparecem como avisos.</p>"
            "<p>Cada token carrega a procedência: de qual arquivo veio. A listagem completa está no raw.json.</p>"
        )
    body += "</div>"

    if ds.warnings:
        body += '<h2 class="block">Avisos desta extração</h2>'
        body += "".join(f'<div class="warn">{_esc(w)}</div>' for w in ds.warnings[:10])

    return body
