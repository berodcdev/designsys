"""Consistência do design system: o quanto a implementação segue o próprio sistema.

Todo número aqui vem acompanhado dos casos que o produziram. Um índice sem os
ofensores ao lado não serve para agir — e um índice que não se sustenta é pior
que nenhum.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from .color import distance, parse_color
from .scales import parse_length, round_px


@dataclass
class ConsistencyReport:
    base_unit: float | None = None
    spacing_off_grid: list[dict[str, Any]] = field(default_factory=list)
    spacing_on_grid_ratio: float = 1.0
    orphan_colors: list[dict[str, Any]] = field(default_factory=list)
    palette_size: int = 0
    ghost_tokens: list[str] = field(default_factory=list)
    declared_tokens: int = 0
    font_families: int = 0
    radius_values: int = 0
    page_divergences: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseUnit": self.base_unit,
            "spacingOffGrid": self.spacing_off_grid,
            "spacingOnGridRatio": round(self.spacing_on_grid_ratio, 3),
            "orphanColors": self.orphan_colors,
            "paletteSize": self.palette_size,
            "ghostTokens": self.ghost_tokens,
            "declaredTokens": self.declared_tokens,
            "fontFamilies": self.font_families,
            "radiusValues": self.radius_values,
            "pageDivergences": self.page_divergences,
            "summary": self.summary(),
        }

    def summary(self) -> str:
        partes: list[str] = []
        if self.base_unit:
            pct = self.spacing_on_grid_ratio * 100
            partes.append(f"{pct:.0f}% do espaçamento cai na grade de {self.base_unit:g}px")
        if self.orphan_colors:
            partes.append(f"{len(self.orphan_colors)} cor(es) usada(s) uma única vez")
        if self.palette_size:
            partes.append(f"{self.palette_size} cores cobrem 90% do uso")
        if self.ghost_tokens:
            partes.append(f"{len(self.ghost_tokens)} token(s) declarado(s) e nunca usado(s)")
        if self.font_families > 3:
            partes.append(f"{self.font_families} famílias tipográficas em uso")
        if self.page_divergences:
            partes.append(f"{len(self.page_divergences)} divergência(s) entre páginas")
        return "; ".join(partes) or "nada a apontar"


# Abaixo disso não é uma grade: com passo de 2px quase todo valor "cai na
# grade", e a métrica deixa de dizer qualquer coisa.
MIN_GRID = 4.0


def spacing_grid(
    frequencies: dict[str, int] | Counter, base_unit: float | None, limit: int = 10
) -> tuple[list[dict[str, Any]], float]:
    """Valores de espaçamento fora da grade, ordenados por quanto aparecem."""
    if not base_unit or base_unit < MIN_GRID:
        return [], 1.0

    dentro = 0
    fora: Counter = Counter()
    for valor, contagem in (frequencies or {}).items():
        px = parse_length(valor)
        if px is None or px <= 0 or px > 400:
            continue
        px = round_px(px)
        # Meio degrau (4px numa grade de 8) é intencional em quase todo sistema.
        if px % base_unit == 0 or px % (base_unit / 2) == 0:
            dentro += contagem
        else:
            fora[px] += contagem

    total = dentro + sum(fora.values())
    if not total:
        return [], 1.0
    piores = [
        {"value": f"{px:g}px", "count": contagem, "nearest": f"{round(px / base_unit) * base_unit:g}px"}
        for px, contagem in fora.most_common(limit)
    ]
    return piores, dentro / total


def core_palette_size(clusters: list[dict[str, Any]], coverage: float = 0.9) -> int:
    """Quantas cores respondem pela maior parte do uso.

    O total de clusters não serve como métrica: ele bate no teto que a própria
    extração impõe. Já a concentração é real — uma paleta disciplinada cobre
    90% das ocorrências com poucas cores.
    """
    contagens = sorted((c.get("count", 0) for c in clusters or []), reverse=True)
    total = sum(contagens)
    if not total:
        return 0
    acumulado = 0
    for indice, contagem in enumerate(contagens, start=1):
        acumulado += contagem
        if acumulado >= total * coverage:
            return indice
    return len(contagens)


def orphan_colors(clusters: list[dict[str, Any]], threshold: int = 2, limit: int = 12) -> list[dict[str, Any]]:
    """Cores que aparecem pouquíssimo e não pertencem a nenhum grupo grande.

    São o sintoma clássico de cor escrita à mão no lugar de token: um `#3a3a3c`
    solitário no meio de uma paleta que já tem `#3a3a3b`.
    """
    if not clusters:
        return []
    principais = [c for c in clusters if c.get("count", 0) > threshold * 4]
    orfas: list[dict[str, Any]] = []

    for cluster in clusters:
        if cluster.get("count", 0) > threshold:
            continue
        rgba = parse_color(cluster.get("value") or cluster.get("hex"))
        if rgba is None:
            continue
        vizinha = None
        menor = 0.12
        for principal in principais:
            outra = parse_color(principal.get("value") or principal.get("hex"))
            if outra is None:
                continue
            d = distance(rgba, outra)
            if d < menor:
                menor, vizinha = d, principal.get("hex")
        orfas.append(
            {
                "hex": cluster.get("hex"),
                "count": cluster.get("count", 0),
                "near": vizinha,
                "distance": round(menor, 3) if vizinha else None,
            }
        )
    # As que têm vizinha próxima são as mais gritantes: dava para reusar.
    orfas.sort(key=lambda o: (o["near"] is None, o["distance"] or 1))
    return orfas[:limit]


_VAR_USE = re.compile(r"var\(\s*(--[\w-]+)")


def ghost_tokens(
    declared: Iterable[str], source_texts: Iterable[str], limit: int = 20
) -> list[str]:
    """Custom properties declaradas que ninguém referencia com `var()`."""
    usados: set[str] = set()
    for texto in source_texts or []:
        usados.update(_VAR_USE.findall(texto or ""))
    fantasmas = [nome for nome in declared or [] if nome.startswith("--") and nome not in usados]
    return sorted(fantasmas)[:limit]


def page_divergences(fingerprints: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    """Sinais de que a mesma coisa aparece diferente em páginas diferentes."""
    if len(fingerprints or []) < 2:
        return []

    achados: list[dict[str, Any]] = []

    botoes_por_pagina = {
        f["url"]: set((f.get("buttons") or {}).keys()) for f in fingerprints if f.get("buttons")
    }
    if len(botoes_por_pagina) >= 2:
        todos = set().union(*botoes_por_pagina.values())
        comuns = set.intersection(*botoes_por_pagina.values())
        exclusivos = todos - comuns
        if exclusivos and len(exclusivos) >= 2:
            achados.append(
                {
                    "kind": "cor de botão",
                    "detail": f"{len(exclusivos)} cor(es) de fundo de botão aparecem em algumas páginas e não em outras",
                    "values": sorted(exclusivos)[:5],
                }
            )

    familias_por_pagina = {
        f["url"]: set(f.get("families") or []) for f in fingerprints if f.get("families")
    }
    if len(familias_por_pagina) >= 2:
        todas = set().union(*familias_por_pagina.values())
        comuns = set.intersection(*familias_por_pagina.values())
        if todas - comuns:
            achados.append(
                {
                    "kind": "tipografia",
                    "detail": "nem todas as páginas usam as mesmas famílias tipográficas",
                    "values": sorted(todas - comuns)[:4],
                }
            )
    return achados[:limit]


def analyze(
    *,
    spacing_frequencies: dict[str, int] | Counter,
    base_unit: float | None,
    clusters: list[dict[str, Any]],
    css_variables: dict[str, Any] | None = None,
    source_texts: Iterable[str] = (),
    families: list[dict[str, Any]] | None = None,
    radii: list[float] | None = None,
    fingerprints: list[dict[str, Any]] | None = None,
) -> ConsistencyReport:
    grade = base_unit if (base_unit or 0) >= MIN_GRID else None
    fora, proporcao = spacing_grid(spacing_frequencies, grade)
    fantasmas = (
        ghost_tokens(list((css_variables or {}).keys()), source_texts) if source_texts else []
    )
    return ConsistencyReport(
        base_unit=grade,
        spacing_off_grid=fora,
        spacing_on_grid_ratio=proporcao,
        orphan_colors=orphan_colors(clusters),
        palette_size=core_palette_size(clusters),
        ghost_tokens=fantasmas,
        declared_tokens=len(css_variables or {}),
        font_families=len([f for f in (families or []) if not f.get("generic")]),
        radius_values=len(radii or []),
        page_divergences=page_divergences(fingerprints or []),
    )


def score(report: ConsistencyReport) -> tuple[int, list[str]]:
    """Nota 0–100, sempre acompanhada das parcelas."""
    nota = 100.0
    partes: list[str] = []

    if report.base_unit:
        perda = (1 - report.spacing_on_grid_ratio) * 60
        if perda >= 1:
            nota -= perda
            partes.append(
                f"−{perda:.0f} por {(1 - report.spacing_on_grid_ratio) * 100:.0f}% do espaçamento fora da grade"
            )
    else:
        nota -= 10
        partes.append("−10 por não haver uma grade de espaçamento reconhecível")

    if report.palette_size > 20:
        perda = min(20.0, (report.palette_size - 20) * 0.8)
        nota -= perda
        partes.append(
            f"−{perda:.0f} por paleta larga: {report.palette_size} cores para cobrir 90% do uso"
        )

    if report.orphan_colors:
        perda = min(15.0, len(report.orphan_colors) * 1.5)
        nota -= perda
        partes.append(f"−{perda:.0f} por {len(report.orphan_colors)} cor(es) usada(s) uma vez só")

    if report.ghost_tokens:
        perda = min(10.0, len(report.ghost_tokens) * 0.8)
        nota -= perda
        partes.append(f"−{perda:.0f} por {len(report.ghost_tokens)} token(s) nunca usado(s)")

    if report.font_families > 3:
        perda = min(10.0, (report.font_families - 3) * 3)
        nota -= perda
        partes.append(f"−{perda:.0f} por {report.font_families} famílias tipográficas")

    if report.page_divergences:
        perda = len(report.page_divergences) * 4
        nota -= perda
        partes.append(f"−{perda:.0f} por divergências entre páginas")

    if not partes:
        partes.append("nenhuma inconsistência relevante encontrada")
    return max(0, round(nota)), partes
