"""Inferência de escalas numéricas (espaçamento, raio, borda, z-index...).

O problema real: uma página produz milhares de valores de padding/margin, a
maioria ruído (valores calculados, 13.328px, etc.). O que queremos é a escala
*intencional* do design system — tipicamente 8 a 12 valores que aparecem com
frequência muito acima do resto.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, Mapping

_LENGTH = re.compile(r"^([-+]?[0-9]*\.?[0-9]+)\s*(px|rem|em|pt|%|vh|vw|ch|ex)?$", re.I)

ROOT_FONT_SIZE = 16.0


def parse_length(value: str | float | None, root_px: float = ROOT_FONT_SIZE) -> float | None:
    """Converte um comprimento CSS para px. Retorna None quando não é comprimento fixo."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    v = str(value).strip().lower()
    if not v or v in {"auto", "normal", "none", "inherit", "initial", "unset"}:
        return None
    m = _LENGTH.match(v)
    if not m:
        return None
    num = float(m.group(1))
    unit = (m.group(2) or "px").lower()
    if unit == "px":
        return num
    if unit in ("rem", "em"):
        return num * root_px
    if unit == "pt":
        return num * 4 / 3
    if unit == "ch":
        return num * root_px * 0.5
    if unit == "ex":
        return num * root_px * 0.5
    # %, vh, vw são relativos ao contexto: não entram numa escala absoluta.
    return None


def round_px(value: float) -> float:
    """Normaliza para no máximo 2 casas, colapsando 15.999998 -> 16."""
    r = round(value, 2)
    if abs(r - round(r)) < 0.03:
        return float(round(r))
    return r


def infer_scale(
    values: Iterable[str | float] | Mapping[str | float, int],
    *,
    max_items: int = 14,
    min_value: float = 0.0,
    max_value: float = 400.0,
    min_share: float = 0.005,
    include_zero: bool = False,
    root_px: float = ROOT_FONT_SIZE,
) -> list[float]:
    """Extrai os degraus significativos de uma escala.

    `values` pode ser uma sequência de valores brutos ou um mapa valor->frequência.
    Um degrau entra na escala se responder por ao menos `min_share` das
    ocorrências, e no máximo `max_items` degraus são devolvidos — ordenados por
    valor, não por frequência, porque é assim que uma escala se lê.
    """
    counter: Counter[float] = Counter()
    items = values.items() if isinstance(values, Mapping) else ((v, 1) for v in values)
    for raw, count in items:
        px = parse_length(raw, root_px)
        if px is None:
            continue
        px = round_px(px)
        if px < 0:
            continue
        if px == 0 and not include_zero:
            continue
        if px < min_value or px > max_value:
            continue
        counter[px] += int(count)

    if not counter:
        return []

    total = sum(counter.values())
    threshold = max(1, math.ceil(total * min_share))
    candidates = [(v, c) for v, c in counter.items() if c >= threshold]
    if not candidates:
        candidates = list(counter.items())

    # Prioriza frequência para escolher quem fica, depois reordena por valor.
    candidates.sort(key=lambda vc: (-vc[1], vc[0]))
    chosen = [v for v, _ in candidates[:max_items]]

    # Valores "redondos" (múltiplos da unidade base) são quase sempre
    # intencionais; se sobrar espaço, garante que não fiquem de fora.
    base = detect_base_unit(chosen) or 4.0
    if len(chosen) < max_items:
        extras = sorted(
            (v for v, c in counter.items() if v not in chosen and v % base == 0 and c >= 2),
            key=lambda v: -counter[v],
        )
        chosen.extend(extras[: max_items - len(chosen)])

    return sorted(set(chosen))


def detect_base_unit(values: Iterable[float]) -> float | None:
    """Descobre se a escala é de 4px, 8px, 5px... Retorna None se não houver grade.

    Passos menores que 4px ficam de fora de propósito: com grade de 2px quase
    todo valor "cai na grade", e afirmar que existe uma grade dessas é pior que
    dizer que não há nenhuma.
    """
    ints = [v for v in values if v > 0 and float(v).is_integer()]
    if len(ints) < 3:
        return None
    for unit in (8.0, 4.0, 5.0, 6.0, 10.0):
        hits = sum(1 for v in ints if v % unit == 0)
        if hits / len(ints) >= 0.7:
            return unit
    return None


def infer_string_scale(
    values: Mapping[str, int] | Iterable[str],
    *,
    max_items: int = 12,
    min_count: int = 1,
    sort_key=None,
    normalize=None,
) -> list[tuple[str, int]]:
    """Escala de valores não-numéricos (sombras, transições) ordenada por frequência."""
    counter: Counter[str] = Counter()
    items = values.items() if isinstance(values, Mapping) else ((v, 1) for v in values)
    for raw, count in items:
        v = " ".join(str(raw).split())
        if normalize:
            v = normalize(v)
        if not v or v.lower() in {"none", "normal", "auto", "0s", "0s ease 0s", "initial"}:
            continue
        counter[v] += int(count)
    picked = [(v, c) for v, c in counter.most_common() if c >= min_count][:max_items]
    if sort_key:
        picked.sort(key=lambda vc: sort_key(vc[0]))
    return picked


def shadow_weight(shadow: str) -> float:
    """Ordena sombras da mais sutil para a mais pronunciada (soma dos offsets/blur)."""
    nums = [abs(float(n)) for n in re.findall(r"([-+]?[0-9]*\.?[0-9]+)px", shadow)]
    return sum(nums) if nums else 0.0


def normalize_duration(value: str) -> str:
    """`.3s` e `300ms` são a mesma duração — colapsa para uma grafia só."""
    ms = duration_ms(value)
    if ms <= 0:
        return value.strip()
    if ms >= 1000 and ms % 1000 == 0:
        return f"{ms / 1000:g}s"
    if ms < 1000:
        return f"{ms:g}ms"
    return f"{ms / 1000:g}s"


def duration_ms(value: str) -> float:
    v = value.strip().lower()
    try:
        if v.endswith("ms"):
            return float(v[:-2])
        if v.endswith("s"):
            return float(v[:-1]) * 1000
    except ValueError:
        pass
    return 0.0


def infer_breakpoints(queries: Iterable[str]) -> list[int]:
    """Extrai larguras de media queries (min-width/max-width) e devolve as usuais."""
    widths: Counter[int] = Counter()
    from_min: Counter[int] = Counter()
    for q in queries:
        for m in re.finditer(r"(min|max)-width\s*:\s*([0-9.]+)\s*(px|rem|em)", q, re.I):
            kind = m.group(1).lower()
            num = float(m.group(2))
            unit = m.group(3).lower()
            px = num if unit == "px" else num * ROOT_FONT_SIZE
            px = int(round(px))
            if 240 <= px <= 2560:
                widths[px] += 1
                if kind == "min":
                    from_min[px] += 1
    if not widths:
        return []

    # Media queries vêm em pares (max-width: 639px) / (min-width: 640px). O
    # degrau publicado do design system é sempre o do min-width, então em caso
    # de empate de frequência é ele que sobrevive à fusão.
    def rank(px: int) -> tuple[int, int]:
        return (widths[px], from_min[px])

    merged: list[int] = []
    for px in sorted(widths):
        if merged and px - merged[-1] <= 1:
            if rank(px) > rank(merged[-1]):
                merged[-1] = px
            continue
        merged.append(px)
    ranked = sorted(merged, key=lambda p: -widths[p])[:8]
    return sorted(ranked)


def name_spacing_steps(values: list[float]) -> dict[str, float]:
    """Nomeia degraus de espaçamento no estilo Tailwind (0.5, 1, 2, 4 = valor/4)."""
    out: dict[str, float] = {}
    for v in values:
        step = v / 4
        if float(step).is_integer():
            key = str(int(step))
        elif abs(step * 2 - round(step * 2)) < 0.01:
            key = f"{step:.1f}".rstrip("0").rstrip(".")
        else:
            key = f"px-{v:g}"
        while key in out:
            key += "_"
        out[key] = v
    return out


def name_size_steps(values: list[float], names: list[str] | None = None) -> dict[str, float]:
    """Nomeia uma escala pequena (radii, etc.) com nomes de camiseta."""
    default = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl", "4xl", "5xl", "6xl"]
    ordered = sorted(values)
    if names is None:
        names = list(default)
        # "none" só faz sentido quando o degrau é realmente 0.
        if ordered and ordered[0] == 0:
            names.insert(0, "none")
        # Um raio gigante é o pill/círculo, não "6xl".
        if ordered and ordered[-1] >= 999:
            names = names[: max(0, len(ordered) - 1)] + ["full"]
    out: dict[str, float] = {}
    if not ordered:
        return out
    if len(ordered) <= len(names):
        pool = names[: len(ordered)]
    else:
        pool = names + [f"{i}" for i in range(len(names), len(ordered))]
    for name, value in zip(pool, ordered):
        out[name] = value
    return out
