"""Identificação do kit de UI a partir das assinaturas deixadas no HTML/CSS.

Cada biblioteca deixa marcas próprias: prefixos de classe (`Mui`, `ant-`,
`chakra-`), custom properties (`--tw-`, `--bs-`, `--mantine-`) e atributos
(`data-radix-*`, `data-headlessui-state`). Um único sinal não decide nada — a
confiança vem do acúmulo, e o resultado sempre diz em que evidência se apoiou.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Pattern


@dataclass
class Signature:
    name: str
    classes: list[Pattern[str]] = field(default_factory=list)
    vars_prefix: tuple[str, ...] = ()
    attrs: tuple[str, ...] = ()
    note: str = ""
    weight: float = 1.0

    def __post_init__(self) -> None:
        # Protege contra `("--x")` — uma string, não uma tupla —, que faria
        # `startswith` casar com qualquer variável.
        if isinstance(self.vars_prefix, str):
            self.vars_prefix = (self.vars_prefix,)
        if isinstance(self.attrs, str):
            self.attrs = (self.attrs,)


def _c(*padroes: str) -> list[Pattern[str]]:
    return [re.compile(p) for p in padroes]


SIGNATURES: list[Signature] = [
    Signature(
        name="Tailwind CSS",
        classes=_c(
            r"^-?[mp][trblxyse]?-(\d+(\.\d+)?|px|auto|\[.+\])$",
            r"^(bg|text|border|ring|shadow|from|to|via|fill|stroke|divide|outline)-[a-z]+(-\d{2,3})?(/\d+)?$",
            r"^(w|h|min-w|min-h|max-w|max-h|size)-(\d+|full|screen|fit|auto|\[.+\])$",
            r"^(sm|md|lg|xl|2xl|dark|hover|focus|group-hover|active|disabled):",
            r"^(flex|grid|hidden|block|inline-flex|inline-block|absolute|relative|sticky|fixed)$",
            r"^(items|justify|self|place|content)-(start|end|center|between|around|evenly|stretch|baseline)$",
            r"^(gap|space-x|space-y)-\d+$",
            r"^rounded(-[a-z0-9]+)?$",
            r"^(font|leading|tracking)-[a-z0-9]+$",
        ),
        vars_prefix=("--tw-",),
        note="classes utilitárias",
    ),
    Signature(
        name="Bootstrap",
        classes=_c(
            r"^(btn|btn-[a-z-]+|container(-fluid)?|row|col(-[a-z0-9]+)*|navbar(-[a-z]+)?)$",
            r"^(form-control|form-label|form-check|input-group|card|card-body|modal|dropdown)$",
            r"^(d|m|p)[a-z]?-(0|1|2|3|4|5|auto)$",
            r"^text-(start|end|center|muted|primary|secondary)$",
        ),
        vars_prefix=("--bs-",),
        note="grid e utilitários do Bootstrap",
    ),
    Signature(
        name="Material UI (MUI)",
        classes=_c(r"^Mui[A-Z]", r"^css-[a-z0-9]{6,8}(-Mui|$)"),
        vars_prefix=("--mui-", "--Mui"),
        note="classes Mui* geradas pelo emotion",
    ),
    # A vírgula final importa: sem ela isto vira uma tupla de caracteres e
    # `startswith` casa com qualquer variável que comece com "-".
    Signature(name="Chakra UI", classes=_c(r"^chakra-"), vars_prefix=("--chakra-",)),
    Signature(name="Ant Design", classes=_c(r"^ant-"), vars_prefix=("--ant-",)),
    Signature(
        name="Radix UI",
        classes=_c(r"^radix-"),
        vars_prefix=("--radix-",),
        attrs=("data-radix-popper-content-wrapper", "data-radix-scroll-area-viewport"),
        note="primitivos Radix",
    ),
    Signature(
        name="shadcn/ui",
        attrs=("data-slot", "data-sidebar"),
        vars_prefix=("--radix-",),
        note="Radix + Tailwind com data-slot",
        weight=0.8,
    ),
    Signature(name="Headless UI", attrs=("data-headlessui-state",)),
    Signature(name="Mantine", classes=_c(r"^mantine-"), vars_prefix=("--mantine-",)),
    Signature(name="Vuetify", classes=_c(r"^v-(btn|card|app|main|container|row|col|icon)$"), vars_prefix=("--v-",)),
    Signature(name="Element Plus", classes=_c(r"^el-"), vars_prefix=("--el-",)),
    Signature(name="Angular Material", classes=_c(r"^mat-", r"^cdk-"), vars_prefix=("--mat-", "--mdc-")),
    Signature(name="Bulma", classes=_c(r"^(is|has)-[a-z-]+$", r"^(hero|columns|column|navbar-item)$")),
    Signature(name="Semantic UI", classes=_c(r"^ui$", r"^(segment|grid|column|menu)$"), weight=0.6),
    Signature(name="Foundation", classes=_c(r"^(grid-x|grid-y|cell|callout)$")),
    Signature(name="styled-components", classes=_c(r"^sc-[A-Za-z0-9]{5,}$"), note="classes geradas"),
    Signature(name="Emotion", classes=_c(r"^css-[a-z0-9]{6,10}$"), note="classes geradas", weight=0.7),
    Signature(name="Bootstrap Icons / Font Awesome", classes=_c(r"^(fa|fas|far|fab|bi)-"), weight=0.5),
]

# Sinais de que o Tailwind é v4 (motor novo, tokens em @theme).
TAILWIND_V4_VARS = ("--color-", "--spacing", "--text-", "--radius-", "--font-", "--breakpoint-")


@dataclass
class Detection:
    name: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence[:6],
            "version": self.version,
        }


def detect(
    class_tokens: dict[str, int] | Counter,
    css_vars: Iterable[str] = (),
    attr_hints: dict[str, int] | Counter | None = None,
) -> list[Detection]:
    """Devolve os kits de UI detectados, do mais provável para o menos."""
    tokens = Counter(class_tokens or {})
    vars_list = list(css_vars or [])
    atributos = Counter(attr_hints or {})
    total_classes = max(1, sum(tokens.values()))

    resultados: list[Detection] = []
    for assinatura in SIGNATURES:
        acertos = 0
        evidencias: list[str] = []

        for token, quantidade in tokens.items():
            if any(padrao.match(token) for padrao in assinatura.classes):
                acertos += quantidade
                if len(evidencias) < 8 and f".{token}" not in evidencias:
                    evidencias.append(f".{token}")

        prefixos = tuple(assinatura.vars_prefix or ())
        vars_encontradas = [v for v in vars_list if v.startswith(prefixos)] if prefixos else []
        for var in vars_encontradas[:3]:
            evidencias.append(var)

        attrs_encontrados = [a for a in assinatura.attrs if atributos.get(a)]
        evidencias.extend(attrs_encontrados[:2])

        if not acertos and not vars_encontradas and not attrs_encontrados:
            continue

        # Classes pesam por proporção; variáveis e atributos são sinais fortes
        # porque ninguém os escreve por acaso.
        proporcao = acertos / total_classes
        pontos = min(1.0, proporcao * 4)
        if vars_encontradas:
            pontos = max(pontos, 0.75)
        if attrs_encontrados:
            pontos = max(pontos, 0.7)
        pontos *= assinatura.weight
        if pontos < 0.12:
            continue

        deteccao = Detection(name=assinatura.name, confidence=min(1.0, pontos), evidence=evidencias)
        if assinatura.name == "Tailwind CSS":
            deteccao.version = _tailwind_version(vars_list)
        resultados.append(deteccao)

    resultados.sort(key=lambda d: -d.confidence)
    return resultados


def _tailwind_version(css_vars: list[str]) -> str:
    """v4 publica a paleta como custom properties; v3 só expõe `--tw-*` internas."""
    tem_v4 = sum(1 for v in css_vars if v.startswith(TAILWIND_V4_VARS))
    tem_v3 = sum(1 for v in css_vars if v.startswith("--tw-"))
    if tem_v4 >= 12:
        return "v4"
    if tem_v3:
        return "v3"
    return ""


def summarize(detections: list[Detection]) -> str:
    """Uma frase para o relatório."""
    if not detections:
        return "nenhum kit de UI conhecido foi identificado — provavelmente CSS próprio"
    principal = detections[0]
    versao = f" {principal.version}" if principal.version else ""
    if principal.confidence < 0.35:
        return f"talvez {principal.name}{versao} (sinais fracos)"
    extras = [d.name for d in detections[1:3] if d.confidence >= 0.4]
    if extras:
        return f"{principal.name}{versao}, junto de {', '.join(extras)}"
    return f"{principal.name}{versao}"
