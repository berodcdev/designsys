"""Parsing, métrica perceptual e clustering de cores.

Toda cor circula internamente como uma tupla RGBA de floats 0..1 (`RGBA`).
As distâncias são calculadas em OKLab, que é perceptualmente uniforme e barato
o bastante para rodar par-a-par em alguns milhares de cores únicas.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from coloraide import Color

RGBA = tuple[float, float, float, float]

# Palavras que aparecem em computed styles e não são cor de verdade.
_NON_COLORS = {
    "none",
    "transparent",
    "inherit",
    "initial",
    "unset",
    "currentcolor",
    "auto",
    "revert",
    "",
}

_NUM = r"[-+]?[0-9]*\.?[0-9]+"
_RGB_FUNC = re.compile(
    rf"^rgba?\(\s*({_NUM})%?\s*[,\s]\s*({_NUM})%?\s*[,\s]\s*({_NUM})%?\s*(?:[,/]\s*({_NUM})(%?)\s*)?\)$",
    re.I,
)
_HEX = re.compile(r"^#([0-9a-fA-F]{3,8})$")

# Cache: parsing de cor é chamado dezenas de milhares de vezes por página.
_parse_cache: dict[str, RGBA | None] = {}
_oklab_cache: dict[RGBA, tuple[float, float, float]] = {}


def parse_color(value: str | None) -> RGBA | None:
    """Converte qualquer notação CSS de cor para RGBA 0..1. Retorna None se não for cor."""
    if value is None:
        return None
    key = value.strip()
    if key in _parse_cache:
        return _parse_cache[key]
    result = _parse_uncached(key)
    if len(_parse_cache) < 100_000:
        _parse_cache[key] = result
    return result


def _parse_uncached(value: str) -> RGBA | None:
    v = value.strip().lower()
    if not v or v in _NON_COLORS:
        return None
    # Valores compostos ("1px solid #ccc", gradientes) não são cor única.
    if v.startswith(("url(", "linear-gradient", "radial-gradient", "conic-gradient")):
        return None

    m = _HEX.match(v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        elif len(h) == 4:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            h += "ff"
        if len(h) != 8:
            return None
        try:
            r, g, b, a = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4, 6))
        except ValueError:
            return None
        return (r, g, b, a)

    m = _RGB_FUNC.match(v)
    if m:
        try:
            r, g, b = (float(m.group(i)) for i in (1, 2, 3))
        except (TypeError, ValueError):
            return None
        if "%" in v.split("(")[1].split(",")[0]:
            r, g, b = r * 2.55, g * 2.55, b * 2.55
        a = 1.0
        if m.group(4) is not None:
            a = float(m.group(4))
            if m.group(5) == "%":
                a /= 100
        return (
            _clamp(r / 255),
            _clamp(g / 255),
            _clamp(b / 255),
            _clamp(a),
        )

    # hsl(), oklch(), lab(), color(display-p3 ...), nomes CSS: delega ao coloraide.
    try:
        c = Color(v).convert("srgb")
    except Exception:
        return None
    coords = c.coords()
    alpha = c.alpha()
    if any(math.isnan(x) for x in coords) or math.isnan(alpha):
        return None
    return (_clamp(coords[0]), _clamp(coords[1]), _clamp(coords[2]), _clamp(alpha))


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def to_hex(rgba: RGBA) -> str:
    """#rrggbb, ou #rrggbbaa quando há transparência."""
    r, g, b, a = rgba
    base = "#{:02x}{:02x}{:02x}".format(
        round(_clamp(r) * 255), round(_clamp(g) * 255), round(_clamp(b) * 255)
    )
    if a >= 0.999:
        return base
    return base + "{:02x}".format(round(_clamp(a) * 255))


def to_css(rgba: RGBA) -> str:
    """Notação preferida para exibição: hex quando opaco, rgba() quando não."""
    r, g, b, a = rgba
    if a >= 0.999:
        return to_hex(rgba)
    return "rgba({}, {}, {}, {})".format(
        round(_clamp(r) * 255),
        round(_clamp(g) * 255),
        round(_clamp(b) * 255),
        round(a, 3),
    )


def to_oklab(rgba: RGBA) -> tuple[float, float, float]:
    cached = _oklab_cache.get(rgba)
    if cached is not None:
        return cached
    try:
        c = Color("srgb", list(rgba[:3]), rgba[3]).convert("oklab")
        coords = tuple(0.0 if math.isnan(x) else float(x) for x in c.coords())
    except Exception:
        coords = (0.0, 0.0, 0.0)
    if len(_oklab_cache) < 100_000:
        _oklab_cache[rgba] = coords  # type: ignore[assignment]
    return coords  # type: ignore[return-value]


def to_oklch(rgba: RGBA) -> tuple[float, float, float]:
    """(lightness 0..1, chroma, hue em graus 0..360)."""
    lab_l, lab_a, lab_b = to_oklab(rgba)
    chroma = math.hypot(lab_a, lab_b)
    hue = math.degrees(math.atan2(lab_b, lab_a)) % 360.0
    return (lab_l, chroma, hue)


def distance(a: RGBA, b: RGBA) -> float:
    """Distância perceptual em OKLab, penalizando diferença de alpha.

    ~0.02 separa tons que o olho considera "a mesma cor" de tons distintos.
    """
    al, aa, ab = to_oklab(a)
    bl, ba, bb = to_oklab(b)
    d = math.sqrt((al - bl) ** 2 + (aa - ba) ** 2 + (ab - bb) ** 2)
    return d + abs(a[3] - b[3]) * 0.5


def luminance(rgba: RGBA) -> float:
    """Luminância relativa WCAG."""

    def ch(c: float) -> float:
        c = _clamp(c)
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b, _ = rgba
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a: RGBA, b: RGBA) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def is_neutral(rgba: RGBA, max_chroma: float = 0.035) -> bool:
    """Cinzas, brancos e pretos — inclusive levemente tingidos (slate, zinc...)."""
    return to_oklch(rgba)[1] <= max_chroma


@dataclass
class ColorCluster:
    """Um grupo de cores perceptualmente equivalentes."""

    color: RGBA
    count: int = 0
    members: list[tuple[RGBA, int]] = field(default_factory=list)
    properties: dict[str, int] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)

    @property
    def hex(self) -> str:
        return to_hex(self.color)

    @property
    def css(self) -> str:
        return to_css(self.color)

    @property
    def oklch(self) -> tuple[float, float, float]:
        return to_oklch(self.color)


def cluster_colors(
    entries: Iterable[tuple[RGBA, int]] | Iterable[tuple[str, int]],
    threshold: float = 0.02,
    properties: dict[str, dict[str, int]] | None = None,
) -> list[ColorCluster]:
    """Agrupa cores quase idênticas.

    Guloso por frequência: a cor mais usada vira o representante do cluster, o
    que garante que o token final seja um valor que existe de verdade no site
    (e não uma média que não aparece em lugar nenhum).

    `properties` opcional mapeia hex -> {propriedade CSS: contagem} para que o
    cluster saiba em que contextos a cor aparece (usado na classificação).
    """
    normalized: list[tuple[RGBA, int]] = []
    for value, count in entries:
        rgba = parse_color(value) if isinstance(value, str) else value
        if rgba is None:
            continue
        if rgba[3] <= 0.001:  # totalmente transparente não é token de cor
            continue
        normalized.append((rgba, int(count)))

    # Agrega duplicatas exatas antes de comparar par-a-par.
    exact: dict[RGBA, int] = {}
    for rgba, count in normalized:
        key = tuple(round(c, 4) for c in rgba)  # type: ignore[assignment]
        exact[key] = exact.get(key, 0) + count  # type: ignore[index]

    ordered = sorted(exact.items(), key=lambda kv: (-kv[1], to_hex(kv[0])))

    clusters: list[ColorCluster] = []
    for rgba, count in ordered:
        best: ColorCluster | None = None
        best_dist = threshold
        for cl in clusters:
            d = distance(cl.color, rgba)
            if d <= best_dist:
                best, best_dist = cl, d
        if best is None:
            best = ColorCluster(color=rgba)
            clusters.append(best)
        best.count += count
        best.members.append((rgba, count))
        if properties:
            for prop, pcount in (properties.get(to_hex(rgba)) or {}).items():
                best.properties[prop] = best.properties.get(prop, 0) + pcount

    clusters.sort(key=lambda c: -c.count)
    return clusters


def sort_by_lightness(clusters: Sequence[ColorCluster]) -> list[ColorCluster]:
    return sorted(clusters, key=lambda c: -c.oklch[0])


def scale_name(index: int, total: int) -> str:
    """Nome estilo Tailwind (50..950) para uma posição numa escala clara→escura."""
    steps = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]
    if total <= 1:
        return "500"
    pos = index / (total - 1)
    return str(steps[min(len(steps) - 1, round(pos * (len(steps) - 1)))])
