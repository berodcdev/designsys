"""Nomes humanos para cores e reconhecimento de paletas conhecidas.

Duas fontes de nome, nesta ordem de confiança:

1. **O próprio site.** Quando existe `--color-blue-500` entre as variáveis CSS,
   o nome real veio da fonte — não há o que adivinhar. Tailwind v4 expõe a
   paleta inteira assim, e muitos design systems próprios também.
2. **Derivação por matiz.** Na falta do nome declarado, a posição em OKLCH dá
   um nome descritivo (`indigo-600`) que é sempre verdadeiro sobre a cor, ainda
   que não seja o nome que o time usa internamente.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .color import RGBA, is_neutral, parse_color, to_hex, to_oklch

# Faixas de matiz em OKLCH, calibradas contra a paleta do Tailwind.
_HUE_NAMES: list[tuple[float, float, str]] = [
    (0.0, 12.0, "rosa"),
    (12.0, 22.0, "carmim"),
    (22.0, 38.0, "vermelho"),
    (38.0, 60.0, "laranja"),
    (60.0, 82.0, "âmbar"),
    (82.0, 105.0, "amarelo"),
    (105.0, 140.0, "lima"),
    (140.0, 158.0, "verde"),
    (158.0, 172.0, "esmeralda"),
    (172.0, 195.0, "turquesa"),
    (195.0, 225.0, "ciano"),
    (225.0, 250.0, "azul-céu"),
    (250.0, 270.0, "azul"),
    (270.0, 288.0, "índigo"),
    (288.0, 300.0, "violeta"),
    (300.0, 315.0, "roxo"),
    (315.0, 340.0, "fúcsia"),
    (340.0, 360.0, "rosa"),
]

# Nome em inglês, para tokens (o CSS do usuário não deveria ter acento).
_HUE_SLUGS = {
    "rosa": "pink",
    "carmim": "rose",
    "vermelho": "red",
    "laranja": "orange",
    "âmbar": "amber",
    "amarelo": "yellow",
    "lima": "lime",
    "verde": "green",
    "esmeralda": "emerald",
    "turquesa": "teal",
    "ciano": "cyan",
    "azul-céu": "sky",
    "azul": "blue",
    "índigo": "indigo",
    "violeta": "violet",
    "roxo": "purple",
    "fúcsia": "fuchsia",
    "cinza": "gray",
    "branco": "white",
    "preto": "black",
}

# Luminosidade OKLCH aproximada de cada degrau, no padrão 50–950.
_TONE_STEPS: list[tuple[float, str]] = [
    (0.985, "50"),
    (0.955, "100"),
    (0.905, "200"),
    (0.835, "300"),
    (0.755, "400"),
    (0.660, "500"),
    (0.575, "600"),
    (0.500, "700"),
    (0.425, "800"),
    (0.340, "900"),
    (0.240, "950"),
]

# Âncoras da paleta padrão do Tailwind (tom 500). Servem só para responder
# "esta paleta parece a do Tailwind?" — a nomeação individual não depende delas.
TAILWIND_ANCHORS: dict[str, str] = {
    "red": "#ef4444",
    "orange": "#f97316",
    "amber": "#f59e0b",
    "yellow": "#eab308",
    "lime": "#84cc16",
    "green": "#22c55e",
    "emerald": "#10b981",
    "teal": "#14b8a6",
    "cyan": "#06b6d4",
    "sky": "#0ea5e9",
    "blue": "#3b82f6",
    "indigo": "#6366f1",
    "violet": "#8b5cf6",
    "purple": "#a855f7",
    "fuchsia": "#d946ef",
    "pink": "#ec4899",
    "rose": "#f43f5e",
    "slate": "#64748b",
    "gray": "#6b7280",
    "zinc": "#71717a",
}

# `--color-blue-500`, `--blue-500`, `--brand-primary`…
_VAR_COLOR_NAME = re.compile(r"^--(?:color|colour|c|palette|theme)?-?(.+)$")

# Variáveis internas de framework não são nomes de paleta: `--tw-mask-bottom-from-color`
# descreve um mecanismo, não a cor.
_INTERNAL_VAR = re.compile(
    r"^--(tw|bs|mui|chakra|mantine|radix|el|mat|mdc)-|"
    r"(mask|gradient|ring-offset|shadow-color|from-color|to-color|via-color|inset)",
    re.I,
)


# Cinzas quase nunca são neutros puros: o vocabulário do mercado distingue o
# cinza azulado (slate) do quente (stone) do neutro (gray), e chamar um slate de
# "azul" é pior que impreciso — é errado.
_NEUTRAL_CHROMA = 0.048


def hue_name(rgba: RGBA, *, slug: bool = False) -> str:
    """Nome do matiz. Neutros viram branco/preto/gray/slate/stone."""
    lightness, chroma, hue = to_oklch(rgba)
    if chroma <= _NEUTRAL_CHROMA:
        if lightness >= 0.985 and chroma <= 0.02:
            return "white" if slug else "branco"
        if lightness <= 0.12:
            return "black" if slug else "preto"
        # Limiares medidos na própria paleta do Tailwind: slate tem chroma
        # ~0.041, gray ~0.023, zinc ~0.014, stone ~0.012 (mas em matiz quente).
        if chroma <= 0.008:
            return "gray" if slug else "cinza"
        if 20.0 <= hue < 110.0:
            return "stone" if slug else "cinza-quente"
        if chroma > 0.030 and 190.0 <= hue < 300.0:
            return "slate" if slug else "cinza-azulado"
        return "gray" if slug else "cinza"
    for inicio, fim, nome in _HUE_NAMES:
        if inicio <= hue < fim:
            return _HUE_SLUGS[nome] if slug else nome
    return "gray" if slug else "cinza"


def tone_step(rgba: RGBA) -> str:
    """Degrau 50–950 mais próximo, pela luminosidade."""
    lightness = to_oklch(rgba)[0]
    return min(_TONE_STEPS, key=lambda passo: abs(passo[0] - lightness))[1]


def color_name(rgba: RGBA, *, slug: bool = True) -> str:
    """Nome derivado: `indigo-600`, `gray-100`, `white`."""
    base = hue_name(rgba, slug=slug)
    if base in ("white", "black", "branco", "preto"):
        return base
    return f"{base}-{tone_step(rgba)}"


def names_from_css_vars(css_vars: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Nomes declarados pelo próprio site: {hex: nome}.

    Uma variável só entra se o valor for cor e o nome não for uma indireção
    (`--x: var(--y)` não diz nada sobre a cor).
    """
    achados: dict[str, str] = {}
    for nome, info in (css_vars or {}).items():
        valor = str(info.get("value", "")).strip()
        if not valor or valor.startswith("var("):
            continue
        rgba = parse_color(valor)
        if rgba is None or rgba[3] < 0.9:
            continue
        if _INTERNAL_VAR.search(nome):
            continue
        m = _VAR_COLOR_NAME.match(nome)
        limpo = (m.group(1) if m else nome.lstrip("-")).strip("-")
        if not limpo or len(limpo) > 38:
            continue
        hexv = to_hex(rgba)
        # O primeiro nome vence: as variáveis vêm em ordem de declaração, e a
        # primeira costuma ser a definição canônica.
        achados.setdefault(hexv, limpo)
    return achados


def match_tailwind(colors: Iterable[RGBA], tolerance: float = 0.05) -> dict[str, Any]:
    """Quanto da paleta padrão do Tailwind aparece nesta lista de cores."""
    from .color import distance

    ancoras = {nome: parse_color(hexv) for nome, hexv in TAILWIND_ANCHORS.items()}
    encontrados: dict[str, str] = {}
    for rgba in colors:
        if rgba is None or is_neutral(rgba):
            continue
        for nome, ancora in ancoras.items():
            if ancora is None or nome in encontrados:
                continue
            if distance(rgba, ancora) <= tolerance:
                encontrados[nome] = to_hex(rgba)
    return {
        "matches": encontrados,
        "count": len(encontrados),
        "confidence": min(1.0, len(encontrados) / 6),
    }


def name_palette(
    clusters: list[dict[str, Any]], css_vars: dict[str, dict[str, Any]] | None = None
) -> dict[str, str]:
    """Nome para cada cor da paleta: declarado quando existe, derivado quando não.

    Devolve {hex: nome}, com os nomes já desambiguados (dois tons diferentes
    nunca recebem o mesmo nome).
    """
    declarados = names_from_css_vars(css_vars or {})
    nomes: dict[str, str] = {}
    usados: set[str] = set()

    for cluster in clusters:
        hexv = cluster.get("hex") or ""
        rgba = parse_color(cluster.get("value") or hexv)
        if rgba is None:
            continue
        nome = declarados.get(hexv) or color_name(rgba)
        base = nome
        sufixo = 2
        while nome in usados:
            nome = f"{base}-{sufixo}"
            sufixo += 1
        usados.add(nome)
        nomes[hexv] = nome
    return nomes
