"""Monta `ds.diagnostics` e `ds.context` — o mesmo relatório para os dois modos.

O extrator web e o de repositório coletam coisas diferentes, mas o diagnóstico
é o mesmo: o que estiver ausente simplesmente não é avaliado, em vez de virar
um número inventado.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..models import DesignSystem
from . import a11y, consistency, frameworks, known, signature


def build_diagnostics(
    ds: DesignSystem,
    *,
    contrast_pairs: Any = None,
    small_targets: list[dict[str, Any]] | None = None,
    spacing_frequencies: dict[str, int] | None = None,
    source_texts: Iterable[str] = (),
    fingerprints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    relatorio_a11y = a11y.audit(
        contrast_pairs or {},
        ds.components,
        ds.typography.get("scale") or [],
        small_targets,
    )
    nota_a11y, parcelas_a11y = a11y.score(relatorio_a11y)

    relatorio_cons = consistency.analyze(
        spacing_frequencies=spacing_frequencies or {},
        base_unit=ds.spacing.get("base_unit"),
        clusters=ds.colors.get("clusters") or [],
        css_variables=ds.css_variables,
        source_texts=source_texts,
        families=ds.typography.get("families") or [],
        radii=ds.radii.get("scale") or [],
        fingerprints=fingerprints,
    )
    nota_cons, parcelas_cons = consistency.score(relatorio_cons)

    assinatura = signature.compute(
        spacing_scale=ds.spacing.get("scale") or [],
        radii_scale=ds.radii.get("scale") or [],
        weights=ds.typography.get("weights") or [],
        accents=(ds.colors.get("accents") or []) + _role_colors(ds),
        type_scale=ds.typography.get("scale") or [],
    )

    # A nota geral pesa acessibilidade um pouco mais: um sistema bonito e
    # inacessível é um problema maior que um sistema irregular e legível.
    tem_a11y = relatorio_a11y.contrast_checked > 0 or relatorio_a11y.focus_checked > 0
    geral = round(nota_a11y * 0.55 + nota_cons * 0.45) if tem_a11y else nota_cons

    return {
        "score": geral,
        "accessibility": {**relatorio_a11y.to_dict(), "score": nota_a11y, "breakdown": parcelas_a11y},
        "consistency": {**relatorio_cons.to_dict(), "score": nota_cons, "breakdown": parcelas_cons},
        "signature": assinatura.to_dict(),
        "evaluated": {
            "contrastPairs": relatorio_a11y.contrast_checked,
            "components": relatorio_a11y.focus_checked,
            "colors": len(ds.colors.get("clusters") or []),
        },
    }


def _role_colors(ds: DesignSystem) -> list[dict[str, Any]]:
    """Papéis semânticos entram na assinatura junto com os destaques."""
    saida = []
    for papel in ("primary", "secondary", "success", "warning", "error", "info"):
        info = (ds.colors.get("roles") or {}).get(papel)
        if info:
            saida.append({"hex": info.get("hex"), "value": info.get("value")})
    return saida


def build_context(
    ds: DesignSystem,
    *,
    class_tokens: dict[str, int] | None = None,
    attr_hints: dict[str, int] | None = None,
    site_origin: str = "",
) -> dict[str, Any]:
    deteccoes = frameworks.detect(
        class_tokens or {}, list(ds.css_variables.keys()), attr_hints or {}
    )
    clusters = ds.colors.get("clusters") or []
    nomes = known.name_palette(clusters, ds.css_variables)

    from .color import parse_color

    cores = [parse_color(c.get("value") or c.get("hex")) for c in clusters]
    tailwind = known.match_tailwind([c for c in cores if c])

    return {
        "frameworks": [d.to_dict() for d in deteccoes[:4]],
        "frameworkSummary": frameworks.summarize(deteccoes),
        "colorNames": nomes,
        "knownPalette": tailwind if tailwind["count"] >= 3 else {"matches": {}, "count": 0, "confidence": 0.0},
        "fonts": fonts_description(ds, site_origin),
    }


def fonts_description(ds: DesignSystem, site_origin: str = "") -> list[dict[str, Any]]:
    from . import fonts

    return fonts.describe(
        ds.typography.get("families") or [],
        ds.typography.get("font_faces") or [],
        site_origin,
    )
