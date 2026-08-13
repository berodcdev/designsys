"""Sprite SVG com os ícones capturados.

Os ícones saem da página com tamanho e cor fixos, que servem ao site de origem e
atrapalham em qualquer outro lugar. Aqui eles viram `<symbol>` sem dimensão e
com `currentColor`, que é o que torna um sprite reutilizável.
"""

from __future__ import annotations

import re
from typing import Any

from ..models import Asset

_VIEWBOX = re.compile(r'viewBox\s*=\s*"([^"]+)"', re.I)
_SVG_OPEN = re.compile(r"<svg\b[^>]*>", re.I)
_SVG_CLOSE = re.compile(r"</svg\s*>", re.I)
# Atributos que amarram o ícone ao contexto original.
_STRIP_ATTRS = re.compile(
    r'\s(width|height|class|style|id|xmlns|xmlns:xlink|aria-hidden|aria-label|focusable|role|data-[\w-]+)\s*=\s*"[^"]*"',
    re.I,
)
_FIXED_FILL = re.compile(r'\s(fill|stroke)\s*=\s*"(?!none)(?!currentColor)[^"]*"', re.I)


def _inner(svg: str) -> str:
    abertura = _SVG_OPEN.search(svg)
    if not abertura:
        return ""
    fim = _SVG_CLOSE.search(svg, abertura.end())
    return svg[abertura.end() : fim.start()] if fim else svg[abertura.end() :]


def _viewbox(svg: str) -> str:
    m = _VIEWBOX.search(svg)
    if m:
        return m.group(1).strip()
    # Sem viewBox, usa width/height para não deformar o ícone.
    largura = re.search(r'\swidth\s*=\s*"([\d.]+)', svg)
    altura = re.search(r'\sheight\s*=\s*"([\d.]+)', svg)
    if largura and altura:
        return f"0 0 {largura.group(1)} {altura.group(1)}"
    return "0 0 24 24"


def _clean(markup: str) -> str:
    limpo = re.sub(r"<script[\s\S]*?</script>", "", markup, flags=re.I)
    limpo = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", limpo, flags=re.I)
    # Cor fixa vira currentColor: é o que permite recolorir por CSS.
    limpo = _FIXED_FILL.sub(lambda m: f' {m.group(1).lower()}="currentColor"', limpo)
    return limpo.strip()


def build_sprite(assets: list[Asset], prefix: str = "icon") -> tuple[str, list[dict[str, Any]]]:
    """Monta o sprite e a lista de símbolos (id + viewBox)."""
    simbolos: list[str] = []
    indice: list[dict[str, Any]] = []
    vistos: set[str] = set()

    for asset in assets:
        if asset.kind not in ("icon", "logo") or not asset.inline_svg:
            continue
        conteudo = _inner(asset.inline_svg)
        if not conteudo.strip():
            continue
        assinatura = re.sub(r"\s+", "", conteudo)[:400]
        if assinatura in vistos:
            continue
        vistos.add(assinatura)

        nome = f"{prefix}-{len(indice) + 1}"
        viewbox = _viewbox(asset.inline_svg)
        corpo = _clean(_STRIP_ATTRS.sub("", conteudo))
        simbolos.append(f'<symbol id="{nome}" viewBox="{viewbox}">{corpo}</symbol>')
        indice.append({"id": nome, "viewBox": viewbox, "kind": asset.kind})

    if not simbolos:
        return "", []

    sprite = (
        '<svg xmlns="http://www.w3.org/2000/svg" style="display:none">\n  '
        + "\n  ".join(simbolos)
        + "\n</svg>\n"
    )
    return sprite, indice


def usage_snippet(path: str, first_id: str = "icon-1") -> str:
    """Como usar o sprite, para entrar no README gerado."""
    return (
        f'<svg width="24" height="24" aria-hidden="true">\n'
        f'  <use href="{path}#{first_id}" />\n'
        f"</svg>"
    )
