"""Classificação semântica: de uma lista de clusters de cor para papéis de design system.

Heurísticas baseadas em (a) em que propriedade CSS a cor aparece, (b) onde ela
aparece (botão, link, body), (c) posição em OKLCH. Nada aqui é infalível — por
isso cada papel atribuído carrega a razão em `reason`, que vai para o raw.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .color import (
    RGBA,
    ColorCluster,
    contrast_ratio,
    is_neutral,
    to_css,
    to_hex,
)

# Faixas de matiz em OKLCH (graus) para os papéis de estado.
_HUE_ROLES: list[tuple[str, float, float]] = [
    # Vermelhos de erro vivem em ~15–40°; abaixo disso já é rosa/magenta, que
    # quase nunca significa "erro" num design system.
    ("error", 12.0, 45.0),
    ("warning", 45.0, 115.0),
    ("success", 125.0, 190.0),
    ("info", 200.0, 285.0),
]


def _hue_in(hue: float, start: float, end: float) -> bool:
    if start <= end:
        return start <= hue < end
    return hue >= start or hue < end  # faixa que cruza 0°


@dataclass
class SemanticColor:
    role: str
    cluster: ColorCluster
    reason: str = ""

    @property
    def hex(self) -> str:
        return self.cluster.hex

    @property
    def css(self) -> str:
        return self.cluster.css


@dataclass
class ColorClassification:
    roles: dict[str, SemanticColor] = field(default_factory=dict)
    neutrals: list[ColorCluster] = field(default_factory=list)
    accents: list[ColorCluster] = field(default_factory=list)
    all_clusters: list[ColorCluster] = field(default_factory=list)

    def get(self, role: str) -> ColorCluster | None:
        sc = self.roles.get(role)
        return sc.cluster if sc else None

    def hex_of(self, role: str, default: str | None = None) -> str | None:
        c = self.get(role)
        return c.hex if c else default


def _prop_count(cluster: ColorCluster, *props: str) -> int:
    return sum(cluster.properties.get(p, 0) for p in props)


def classify_colors(
    clusters: Sequence[ColorCluster],
    *,
    body_background: RGBA | None = None,
    body_text: RGBA | None = None,
    accent_hints: Sequence[tuple[RGBA, int]] = (),
    link_hints: Sequence[tuple[RGBA, int]] = (),
) -> ColorClassification:
    """Atribui papéis semânticos aos clusters de cor.

    `accent_hints` vem das cores de fundo de botões; `link_hints`, da cor de
    texto de links. São os sinais mais confiáveis para achar a cor primária.
    """
    result = ColorClassification(all_clusters=list(clusters))
    if not clusters:
        return result

    used: set[str] = set()

    def assign(role: str, cluster: ColorCluster | None, reason: str) -> None:
        if cluster is None or role in result.roles:
            return
        result.roles[role] = SemanticColor(role=role, cluster=cluster, reason=reason)
        used.add(cluster.hex)

    def nearest(rgba: RGBA | None) -> ColorCluster | None:
        if rgba is None:
            return None
        target = to_hex(rgba)
        for c in clusters:
            if c.hex == target:
                return c
        from .color import distance

        best, best_d = None, 0.08
        for c in clusters:
            d = distance(c.color, rgba)
            if d < best_d:
                best, best_d = c, d
        return best

    # --- background / surface -------------------------------------------------
    bg_cluster = nearest(body_background)
    if bg_cluster:
        assign("background", bg_cluster, "background-color computado do <body>")
    else:
        by_bg = [
            c
            for c in sorted(
                clusters, key=lambda c: -_prop_count(c, "background-color", "background")
            )
            if c.color[3] >= 0.9 and _prop_count(c, "background-color", "background") > 0
        ]
        if by_bg:
            assign("background", by_bg[0], "cor de fundo mais frequente na página")

    background = result.get("background")
    surfaces = [
        c
        for c in sorted(
            clusters, key=lambda c: -_prop_count(c, "background-color", "background")
        )
        if c.hex not in used
        and _prop_count(c, "background-color", "background") >= 2
        # Um overlay translúcido (rgba(255,255,255,.1)) não é uma superfície do
        # sistema: o valor só faz sentido composto sobre o que está atrás.
        and c.color[3] >= 0.85
        and (background is None or contrast_ratio(c.color, background.color) < 3.0)
        and is_neutral(c.color, max_chroma=0.02)
    ]
    if surfaces:
        assign("surface", surfaces[0], "segundo fundo neutro mais usado (cards/painéis)")
        if len(surfaces) > 1:
            assign("surface-alt", surfaces[1], "terceiro fundo neutro mais usado")

    # --- texto ----------------------------------------------------------------
    text_cluster = nearest(body_text)
    if text_cluster:
        assign("text", text_cluster, "color computado do <body>")
    else:
        by_color = [
            c
            for c in sorted(clusters, key=lambda c: -_prop_count(c, "color"))
            if c.color[3] >= 0.9 and _prop_count(c, "color") > 0
        ]
        if by_color:
            assign("text", by_color[0], "cor de texto mais frequente")

    text = result.get("text")
    if text and background:
        muted = [
            c
            for c in sorted(clusters, key=lambda c: -_prop_count(c, "color"))
            if c.hex not in used
            and _prop_count(c, "color") >= 2
            and is_neutral(c.color, max_chroma=0.05)
            and 2.0 <= contrast_ratio(c.color, background.color) < contrast_ratio(text.color, background.color)
        ]
        if muted:
            assign("text-muted", muted[0], "texto neutro com contraste menor que o principal")

    # --- borda ----------------------------------------------------------------
    # Bordas são quase sempre neutras. Sem esse filtro, um verde de destaque com
    # borda colorida vence a linha divisória cinza que aparece em toda a página.
    borders = [
        c
        for c in sorted(clusters, key=lambda c: -_prop_count(c, "border-color", "outline-color"))
        if _prop_count(c, "border-color", "outline-color") > 0
    ]
    neutral_borders = [c for c in borders if is_neutral(c.color, max_chroma=0.045)]
    pick = next((c for c in neutral_borders if c.hex not in used), None)
    reason = "cor neutra de borda mais frequente"
    if pick is None and neutral_borders:
        # A linha divisória pode ser o mesmo tom já usado como surface: tudo bem.
        pick, reason = neutral_borders[0], "cor neutra de borda mais frequente (compartilhada com outro papel)"
    if pick is None:
        pick = next((c for c in borders if c.hex not in used), None)
        reason = "cor de borda mais frequente"
    if pick is not None:
        result.roles["border"] = SemanticColor(role="border", cluster=pick, reason=reason)
        used.add(pick.hex)

    # --- primária / secundária -----------------------------------------------
    def hint_cluster(hints: Sequence[tuple[RGBA, int]], require_saturated: bool = True):
        scored: dict[str, tuple[ColorCluster, int]] = {}
        for rgba, count in hints:
            cl = nearest(rgba)
            if cl is None:
                continue
            if require_saturated and is_neutral(cl.color):
                continue
            prev = scored.get(cl.hex)
            scored[cl.hex] = (cl, (prev[1] if prev else 0) + count)
        if not scored:
            return None
        return max(scored.values(), key=lambda cc: cc[1])[0]

    primary = hint_cluster(accent_hints) or hint_cluster(link_hints)
    reason = "cor de fundo dominante em botões" if primary else ""
    if primary is None:
        saturated = [c for c in clusters if not is_neutral(c.color) and c.hex not in used]
        if saturated:
            primary = saturated[0]
            reason = "cor saturada mais frequente da página"
    if primary is not None and primary.hex in used:
        # A primária pode coincidir com o texto/fundo (ex.: sites monocromáticos);
        # nesse caso ainda vale registrá-la como primary.
        result.roles.pop("primary", None)
    assign("primary", primary, reason)

    prim = result.get("primary")
    if prim is not None:
        from .color import to_oklch

        ph = to_oklch(prim.color)[2]
        secondary = None
        for c in clusters:
            if c.hex in used or is_neutral(c.color):
                continue
            h = to_oklch(c.color)[2]
            delta = min(abs(h - ph), 360 - abs(h - ph))
            if delta > 25:
                secondary = c
                break
        assign("secondary", secondary, "segunda cor saturada com matiz distinto da primária")

    # --- estados --------------------------------------------------------------
    from .color import to_oklch

    from .color import distance

    state_picks: list[RGBA] = []
    for role, start, end in _HUE_ROLES:
        best = None
        for c in clusters:
            if c.hex in used:
                continue
            if c.color[3] < 0.85:
                continue
            lightness, chroma, hue = to_oklch(c.color)
            if chroma < 0.09 or not _hue_in(hue, start, end):
                continue
            # Fora dessa faixa de luminosidade a cor é um marrom escuro de
            # gradiente ou um pastel de fundo, não um estado do sistema.
            if lightness < 0.35 or lightness > 0.88:
                continue
            # Faixas vizinhas (error/warning) se tocam: sem esta checagem os dois
            # papéis podem receber praticamente a mesma cor.
            if any(distance(c.color, other) < 0.09 for other in state_picks):
                continue
            best = c
            break
        if best is not None:
            assign(role, best, f"matiz {to_oklch(best.color)[2]:.0f}° compatível com '{role}'")
            state_picks.append(best.color)

    # --- famílias -------------------------------------------------------------
    # A escala de cinzas é mais exigente que `is_neutral`: um verde-claro de
    # fundo de alerta passa em 0.035 de croma e não pertence a uma rampa neutra.
    result.neutrals = sorted(
        (
            c
            for c in clusters
            if is_neutral(c.color, max_chroma=0.022) and c.count >= 2 and c.color[3] >= 0.9
        ),
        key=lambda c: -to_oklch(c.color)[0],
    )
    result.accents = [
        c
        for c in clusters
        if not is_neutral(c.color) and c.count >= 2 and c.hex not in used
    ]
    return result


def theme_pair(classification: ColorClassification) -> str:
    """'dark' se o fundo é escuro, 'light' caso contrário."""
    bg = classification.get("background")
    if bg is None:
        return "light"
    from .color import luminance

    return "dark" if luminance(bg.color) < 0.4 else "light"


def role_export(classification: ColorClassification) -> dict[str, str]:
    """Mapa papel -> valor CSS, pronto para virar variável."""
    return {role: to_css(sc.cluster.color) for role, sc in classification.roles.items()}
