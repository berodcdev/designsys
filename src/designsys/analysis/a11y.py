"""Auditoria de acessibilidade sobre o que foi realmente medido na página.

Nada aqui é simulação: os pares de cor vêm de texto que existe no site, com o
fundo que estava atrás dele, e o foco vem do estado `:focus` capturado no
navegador. Por isso o relatório fala em ocorrências, não em possibilidades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .color import contrast_ratio, parse_color, to_hex
from .scales import parse_length

# WCAG 2.2: texto grande é ≥ 24px, ou ≥ 18.66px quando bold.
LARGE_PX = 24.0
LARGE_BOLD_PX = 18.66
AA_NORMAL = 4.5
AA_LARGE = 3.0
AAA_NORMAL = 7.0
MIN_TARGET = 24.0  # 2.5.8 Target Size (Minimum), nível AA
MIN_FONT_PX = 12.0


@dataclass
class ContrastIssue:
    fg: str
    bg: str
    ratio: float
    required: float
    size: float
    weight: str
    count: int
    sample: str = ""
    tag: str = ""

    @property
    def severity(self) -> str:
        if self.ratio < self.required * 0.6:
            return "grave"
        return "moderado"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fg": self.fg,
            "bg": self.bg,
            "ratio": round(self.ratio, 2),
            "required": self.required,
            "size": self.size,
            "weight": self.weight,
            "count": self.count,
            "sample": self.sample,
            "tag": self.tag,
            "severity": self.severity,
        }


@dataclass
class A11yReport:
    contrast: list[ContrastIssue] = field(default_factory=list)
    contrast_checked: int = 0
    contrast_failing_occurrences: int = 0
    focus_missing: list[str] = field(default_factory=list)
    focus_checked: int = 0
    small_text: list[dict[str, Any]] = field(default_factory=list)
    small_targets: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contrast": [i.to_dict() for i in self.contrast],
            "contrastChecked": self.contrast_checked,
            "contrastFailingOccurrences": self.contrast_failing_occurrences,
            "focusMissing": self.focus_missing,
            "focusChecked": self.focus_checked,
            "smallText": self.small_text,
            "smallTargets": self.small_targets,
            "summary": self.summary(),
        }

    def summary(self) -> str:
        partes: list[str] = []
        if self.contrast_checked:
            reprovados = len(self.contrast)
            if reprovados:
                partes.append(
                    f"{reprovados} combinação(ões) de texto abaixo do mínimo AA "
                    f"({self.contrast_failing_occurrences} ocorrências)"
                )
            else:
                partes.append(f"todos os {self.contrast_checked} pares de texto passam no AA")
        if self.focus_missing:
            partes.append(f"{len(self.focus_missing)} componente(s) sem foco visível")
        if self.small_text:
            partes.append(f"{len(self.small_text)} tamanho(s) de fonte abaixo de {MIN_FONT_PX:g}px")
        if self.small_targets:
            partes.append(f"{len(self.small_targets)} alvo(s) de toque menores que {MIN_TARGET:g}px")
        return "; ".join(partes) or "nada a apontar"


def required_ratio(size_px: float, weight: str) -> float:
    """Mínimo exigido pelo AA para este tamanho e peso."""
    try:
        peso = int(str(weight).strip() or 400)
    except ValueError:
        peso = 700 if str(weight).strip().lower() == "bold" else 400
    if size_px >= LARGE_PX or (size_px >= LARGE_BOLD_PX and peso >= 700):
        return AA_LARGE
    return AA_NORMAL


def audit_pairs(pairs: dict[str, dict[str, Any]] | list[dict[str, Any]], limit: int = 14) -> tuple[list[ContrastIssue], int, int]:
    """Avalia os pares texto/fundo coletados. Devolve (falhas, avaliados, ocorrências)."""
    entradas = list(pairs.values()) if isinstance(pairs, dict) else list(pairs or [])
    falhas: list[ContrastIssue] = []
    avaliados = 0
    ocorrencias = 0

    for par in entradas:
        fg = parse_color(par.get("fg"))
        bg = parse_color(par.get("bg"))
        if fg is None or bg is None:
            continue
        # Texto transparente ou quase é decoração/animação, não conteúdo.
        if fg[3] < 0.5:
            continue
        # Contra fundo translúcido não dá para afirmar o contraste: o resultado
        # depende do que está atrás. Melhor não avaliar do que avaliar errado.
        if bg[3] < 0.9:
            continue
        tamanho = parse_length(par.get("size")) or 16.0
        peso = str(par.get("weight") or "400")
        avaliados += 1
        exigido = required_ratio(tamanho, peso)
        razao = contrast_ratio(fg, bg)
        if razao >= exigido:
            continue
        contagem = int(par.get("count", 1))
        ocorrencias += contagem
        falhas.append(
            ContrastIssue(
                fg=to_hex(fg),
                bg=to_hex(bg),
                ratio=razao,
                required=exigido,
                size=round(tamanho, 1),
                weight=peso,
                count=contagem,
                sample=str(par.get("sample") or "")[:48],
                tag=str(par.get("tag") or ""),
            )
        )

    # Os que mais aparecem doem mais: ordena por ocorrência, depois por gravidade.
    falhas.sort(key=lambda i: (-i.count, i.ratio))
    return falhas[:limit], avaliados, ocorrencias


def audit_focus(components: list[Any]) -> tuple[list[str], int]:
    """Componentes interativos cujo `:focus` não muda nada visualmente."""
    interativos = ("button", "link", "input", "textarea", "select", "checkbox")
    sem_foco: list[str] = []
    avaliados = 0

    for comp in components or []:
        dados = comp.to_dict() if hasattr(comp, "to_dict") else comp
        tipo = str(dados.get("kind", ""))
        if not tipo.startswith(interativos):
            continue
        base = dados.get("base") or {}
        foco = dados.get("focus") or {}
        if not foco:
            continue
        avaliados += 1
        mudancas = {
            prop: valor
            for prop, valor in foco.items()
            if base.get(prop) not in (None, valor)
        }
        # Um foco que só muda a cor do texto não é indicação suficiente de foco.
        visiveis = {
            "outline-width", "outline-color", "outline", "outline-offset",
            "box-shadow", "border-top-width", "border-top-color", "background-color",
        }
        if not (set(mudancas) & visiveis):
            sem_foco.append(tipo)
    return sem_foco, avaliados


def audit_font_sizes(type_scale: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Estilos de texto pequenos demais para leitura confortável."""
    pequenos = []
    for estilo in type_scale or []:
        tamanho = float(estilo.get("fontSize") or 0)
        if 0 < tamanho < MIN_FONT_PX:
            pequenos.append(
                {"name": estilo.get("name"), "size": tamanho, "count": estilo.get("count", 0)}
            )
    return sorted(pequenos, key=lambda e: e["size"])


def audit(
    pairs: Any,
    components: list[Any],
    type_scale: list[dict[str, Any]],
    small_targets: list[dict[str, Any]] | None = None,
) -> A11yReport:
    falhas, avaliados, ocorrencias = audit_pairs(pairs)
    sem_foco, foco_avaliados = audit_focus(components)
    return A11yReport(
        contrast=falhas,
        contrast_checked=avaliados,
        contrast_failing_occurrences=ocorrencias,
        focus_missing=sem_foco,
        focus_checked=foco_avaliados,
        small_text=audit_font_sizes(type_scale),
        small_targets=(small_targets or [])[:12],
    )


def score(report: A11yReport) -> tuple[int, list[str]]:
    """Nota 0–100 com as parcelas que a compõem, para poder ser contestada."""
    nota = 100.0
    partes: list[str] = []

    if report.contrast_checked:
        proporcao = len(report.contrast) / max(1, report.contrast_checked)
        perda = min(45.0, proporcao * 150)
        if perda >= 1:
            nota -= perda
            partes.append(f"−{perda:.0f} por {len(report.contrast)} pares de texto abaixo do AA")
    if report.focus_checked:
        proporcao = len(report.focus_missing) / max(1, report.focus_checked)
        perda = proporcao * 25
        if perda >= 1:
            nota -= perda
            partes.append(f"−{perda:.0f} por foco invisível em {len(report.focus_missing)} componente(s)")
    if report.small_text:
        perda = min(12.0, len(report.small_text) * 4)
        nota -= perda
        partes.append(f"−{perda:.0f} por texto abaixo de {MIN_FONT_PX:g}px")
    if report.small_targets:
        perda = min(10.0, len(report.small_targets) * 2)
        nota -= perda
        partes.append(f"−{perda:.0f} por alvos de toque pequenos")

    if not partes:
        partes.append("nenhum problema encontrado nas verificações feitas")
    return max(0, round(nota)), partes
