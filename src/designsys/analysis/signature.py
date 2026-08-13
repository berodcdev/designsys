"""Assinatura visual: descrever o caráter de um design system em poucos eixos.

Cinco medidas simples, todas derivadas de valores já coletados, que juntas
distinguem sistemas que a lista de tokens não distingue: dois sites podem ter a
mesma paleta e parecer completamente diferentes por causa de densidade, forma e
peso.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Sequence

from .color import parse_color, to_oklch
from .scales import parse_length


@dataclass
class Axis:
    """Um eixo de 0 a 1, com o rótulo que descreve a posição."""

    key: str
    label: str
    value: float
    left: str
    right: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": round(self.value, 3),
            "left": self.left,
            "right": self.right,
            "detail": self.detail,
        }


@dataclass
class Signature:
    axes: list[Axis] = field(default_factory=list)
    sentence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"axes": [a.to_dict() for a in self.axes], "sentence": self.sentence}

    def get(self, key: str) -> Axis | None:
        return next((a for a in self.axes if a.key == key), None)


def _mediana_px(valores: Sequence[Any]) -> float:
    numeros = [px for px in (parse_length(v) for v in valores) if px is not None and px > 0]
    return statistics.median(numeros) if numeros else 0.0


def _normalizar(valor: float, minimo: float, maximo: float) -> float:
    if maximo <= minimo:
        return 0.5
    return max(0.0, min(1.0, (valor - minimo) / (maximo - minimo)))


def _rotulo(valor: float, baixo: str, meio: str, alto: str) -> str:
    if valor < 0.34:
        return baixo
    if valor < 0.67:
        return meio
    return alto


def compute(
    *,
    spacing_scale: Sequence[float],
    radii_scale: Sequence[float],
    weights: Sequence[int],
    accents: Sequence[dict[str, Any]],
    type_scale: Sequence[dict[str, Any]] = (),
) -> Signature:
    eixos: list[Axis] = []

    # Densidade — o espaçamento mediano do sistema.
    espaco = statistics.median(spacing_scale) if spacing_scale else 0.0
    densidade = _normalizar(espaco, 8, 40)
    eixos.append(
        Axis(
            key="density",
            label=_rotulo(densidade, "compacto", "equilibrado", "arejado"),
            value=densidade,
            left="compacto",
            right="arejado",
            detail=f"espaçamento mediano de {espaco:g}px",
        )
    )

    # Forma — o raio mediano, ignorando o pill (que é sempre um extremo).
    raios = [r for r in radii_scale if r < 100]
    raio = statistics.median(raios) if raios else 0.0
    forma = _normalizar(raio, 0, 20)
    eixos.append(
        Axis(
            key="shape",
            label=_rotulo(forma, "anguloso", "suave", "arredondado"),
            value=forma,
            left="anguloso",
            right="arredondado",
            detail=f"raio mediano de {raio:g}px",
        )
    )

    # Peso tipográfico — o peso mais alto que o sistema usa de fato.
    pesos = [int(w) for w in weights if str(w).isdigit()]
    peso_max = max(pesos) if pesos else 400
    peso = _normalizar(peso_max, 400, 900)
    eixos.append(
        Axis(
            key="weight",
            label=_rotulo(peso, "leve", "regular", "encorpado"),
            value=peso,
            left="leve",
            right="encorpado",
            detail=f"peso máximo em uso: {peso_max}",
        )
    )

    # Saturação — o quanto as cores de destaque são vivas.
    chromas: list[float] = []
    for entrada in accents or []:
        rgba = parse_color(entrada.get("value") or entrada.get("hex"))
        if rgba is not None:
            chromas.append(to_oklch(rgba)[1])
    croma = statistics.median(chromas) if chromas else 0.0
    saturacao = _normalizar(croma, 0.02, 0.22)
    eixos.append(
        Axis(
            key="saturation",
            label=_rotulo(saturacao, "sóbrio", "moderado", "vibrante"),
            value=saturacao,
            left="sóbrio",
            right="vibrante",
            detail=f"croma mediano de {croma:.3f}",
        )
    )

    # Temperatura — o matiz predominante dos destaques.
    quentes = frios = 0
    for entrada in accents or []:
        rgba = parse_color(entrada.get("value") or entrada.get("hex"))
        if rgba is None:
            continue
        _, chroma, hue = to_oklch(rgba)
        if chroma < 0.04:
            continue
        if hue < 110 or hue >= 330:
            quentes += 1
        elif 180 <= hue < 300:
            frios += 1
    total = quentes + frios
    temperatura = 0.5 if not total else frios / total
    eixos.append(
        Axis(
            key="temperature",
            label=_rotulo(temperatura, "quente", "neutro", "frio"),
            value=temperatura,
            left="quente",
            right="frio",
            detail=f"{quentes} matiz(es) quente(s) contra {frios} frio(s)",
        )
    )

    return Signature(axes=eixos, sentence=_frase(eixos))


def _frase(eixos: list[Axis]) -> str:
    """Uma frase que descreve o sistema — a leitura que os números permitem."""
    por_chave = {a.key: a for a in eixos}
    densidade = por_chave["density"].label
    forma = por_chave["shape"].label
    peso = por_chave["weight"].label
    saturacao = por_chave["saturation"].label
    temperatura = por_chave["temperature"].label

    # "paleta moderado e frio" não é português: os eixos viram feminino aqui.
    feminino = {
        "sóbrio": "sóbria", "moderado": "moderada", "vibrante": "vibrante",
        "quente": "quente", "neutro": "neutra", "frio": "fria",
    }
    frase = f"Sistema {densidade} e {forma}, de tipografia {peso}"
    if temperatura == "neutro":
        frase += f" e paleta {feminino[saturacao]}."
    else:
        frase += f", com paleta {feminino[saturacao]} e {feminino[temperatura]}."
    return frase
