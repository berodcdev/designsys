"""Parser de CSS/SCSS/LESS baseado em tinycss2.

Usado em dois lugares: para folhas de estilo que o CSSOM não deixa ler por CORS
(baixadas via HTTP) e para todos os arquivos de estilo do modo repo.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

import tinycss2

COLOR_PROPS = {
    "color",
    "background-color",
    "background",
    "border-color",
    "border-top-color",
    "border-right-color",
    "border-bottom-color",
    "border-left-color",
    "outline-color",
    "fill",
    "stroke",
    "text-decoration-color",
    "caret-color",
    "accent-color",
    "column-rule-color",
    "box-shadow",
    "text-shadow",
    "border",
    "border-top",
    "border-bottom",
    "border-left",
    "border-right",
    "outline",
}

SPACING_PROPS = {
    "margin",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "padding",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "gap",
    "row-gap",
    "column-gap",
    "grid-gap",
    "inset",
    "top",
    "right",
    "bottom",
    "left",
}

RADIUS_PROPS = {
    "border-radius",
    "border-top-left-radius",
    "border-top-right-radius",
    "border-bottom-left-radius",
    "border-bottom-right-radius",
}

COLOR_RE = re.compile(
    r"(#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)|oklch\([^)]*\)|oklab\([^)]*\)|lab\([^)]*\)|lch\([^)]*\))"
)
LENGTH_RE = re.compile(r"(?<![\w.-])([0-9]*\.?[0-9]+)(px|rem|em)(?![\w-])")
DURATION_RE = re.compile(r"(?<![\w.-])([0-9]*\.?[0-9]+)(ms|s)(?![\w-])")
EASING_RE = re.compile(
    r"(cubic-bezier\([^)]*\)|steps\([^)]*\)|ease-in-out|ease-in|ease-out|linear|ease)\b"
)

# Nomes CSS que aparecem tanto como valor quanto como palavra-chave.
NAMED_COLORS_HINT = re.compile(
    r"\b(white|black|red|green|blue|yellow|orange|purple|pink|gray|grey|transparent|currentColor)\b",
    re.I,
)


@dataclass
class CssFacts:
    custom_props: list[dict[str, str]] = field(default_factory=list)
    font_faces: list[dict[str, Any]] = field(default_factory=list)
    media_queries: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    colors: Counter = field(default_factory=Counter)
    colors_by_prop: dict[str, Counter] = field(default_factory=dict)
    spacing: Counter = field(default_factory=Counter)
    radii: Counter = field(default_factory=Counter)
    shadows: Counter = field(default_factory=Counter)
    border_widths: Counter = field(default_factory=Counter)
    font_families: Counter = field(default_factory=Counter)
    font_sizes: Counter = field(default_factory=Counter)
    font_weights: Counter = field(default_factory=Counter)
    line_heights: Counter = field(default_factory=Counter)
    letter_spacings: Counter = field(default_factory=Counter)
    durations: Counter = field(default_factory=Counter)
    easings: Counter = field(default_factory=Counter)
    z_indexes: Counter = field(default_factory=Counter)
    opacities: Counter = field(default_factory=Counter)
    max_widths: Counter = field(default_factory=Counter)
    theme_blocks: list[dict[str, str]] = field(default_factory=list)  # Tailwind v4 @theme
    rule_count: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: "CssFacts") -> None:
        self.custom_props.extend(other.custom_props)
        self.font_faces.extend(other.font_faces)
        self.media_queries.extend(other.media_queries)
        self.imports.extend(other.imports)
        self.theme_blocks.extend(other.theme_blocks)
        self.errors.extend(other.errors)
        self.rule_count += other.rule_count
        for name in (
            "colors",
            "spacing",
            "radii",
            "shadows",
            "border_widths",
            "font_families",
            "font_sizes",
            "font_weights",
            "line_heights",
            "letter_spacings",
            "durations",
            "easings",
            "z_indexes",
            "opacities",
            "max_widths",
        ):
            getattr(self, name).update(getattr(other, name))
        for prop, counter in other.colors_by_prop.items():
            self.colors_by_prop.setdefault(prop, Counter()).update(counter)


def _serialize(tokens: Iterable[Any]) -> str:
    try:
        return tinycss2.serialize(tokens).strip()
    except Exception:
        return ""


def _add_color(facts: CssFacts, prop: str, value: str, origin: str, count: int = 1) -> None:
    group = _color_group(prop)
    for match in COLOR_RE.findall(value):
        facts.colors[match] += count
        facts.colors_by_prop.setdefault(group, Counter())[match] += count
    # Nomes CSS só contam quando a propriedade é inequivocamente de cor.
    if prop in {"color", "background-color", "fill", "stroke", "border-color"}:
        bare = value.strip()
        if bare and NAMED_COLORS_HINT.fullmatch(bare):
            facts.colors[bare.lower()] += count
            facts.colors_by_prop.setdefault(group, Counter())[bare.lower()] += count


def _color_group(prop: str) -> str:
    if prop in ("color",):
        return "color"
    if prop.startswith("background"):
        return "background-color"
    if "border" in prop and "radius" not in prop:
        return "border-color"
    if prop == "outline" or prop == "outline-color":
        return "outline-color"
    if prop in ("fill", "stroke"):
        return prop
    if "shadow" in prop:
        return "shadow-color"
    return prop


def _handle_declaration(facts: CssFacts, prop: str, value: str, origin: str, selector: str) -> None:
    prop = prop.lower().strip()
    value = value.strip()
    if not prop or not value:
        return

    if prop.startswith("--"):
        facts.custom_props.append(
            {"name": prop, "value": value, "selector": selector, "origin": origin}
        )
        # Uma custom property pode carregar qualquer tipo de valor.
        _add_color(facts, "color" if COLOR_RE.search(value) else prop, value, origin)
        return

    if prop in COLOR_PROPS or COLOR_RE.search(value):
        _add_color(facts, prop, value, origin)

    if prop in SPACING_PROPS:
        for num, unit in LENGTH_RE.findall(value):
            facts.spacing[f"{num}{unit}"] += 1
    if prop in RADIUS_PROPS:
        for num, unit in LENGTH_RE.findall(value):
            facts.radii[f"{num}{unit}"] += 1
        if "9999" in value or "50%" in value:
            facts.radii["9999px"] += 1
    if prop == "box-shadow" and value.lower() != "none":
        facts.shadows[" ".join(value.split())] += 1
    if prop in ("border-width", "border-top-width", "border", "border-bottom-width"):
        for num, unit in LENGTH_RE.findall(value):
            if unit == "px" and float(num) <= 12:
                facts.border_widths[f"{num}{unit}"] += 1
    if prop in ("font-family",):
        facts.font_families[" ".join(value.split())] += 1
    if prop == "font-size":
        facts.font_sizes[value] += 1
    if prop == "font-weight":
        facts.font_weights[value] += 1
    if prop == "line-height":
        facts.line_heights[value] += 1
    if prop == "letter-spacing":
        facts.letter_spacings[value] += 1
    if prop in ("transition", "transition-duration", "animation", "animation-duration"):
        for num, unit in DURATION_RE.findall(value):
            facts.durations[f"{num}{unit}"] += 1
    if prop in ("transition", "transition-timing-function", "animation", "animation-timing-function"):
        for easing in EASING_RE.findall(value):
            facts.easings[easing] += 1
    if prop == "z-index" and value.lstrip("-").isdigit():
        facts.z_indexes[value] += 1
    if prop == "opacity":
        facts.opacities[value] += 1
    if prop in ("max-width", "width") and prop == "max-width":
        for num, unit in LENGTH_RE.findall(value):
            facts.max_widths[f"{num}{unit}"] += 1


def _walk(facts: CssFacts, rules: Iterable[Any], origin: str, depth: int = 0) -> None:
    if depth > 8:
        return
    for rule in rules:
        try:
            if rule.type == "qualified-rule":
                facts.rule_count += 1
                selector = _serialize(rule.prelude)[:200]
                decls = tinycss2.parse_declaration_list(
                    rule.content, skip_comments=True, skip_whitespace=True
                )
                for d in decls:
                    if d.type == "declaration":
                        _handle_declaration(
                            facts, d.lower_name, _serialize(d.value), origin, selector
                        )
                    elif d.type == "qualified-rule":  # aninhamento SCSS
                        _walk(facts, [d], origin, depth + 1)
            elif rule.type == "at-rule":
                name = (rule.lower_at_keyword or "").lower()
                prelude = _serialize(rule.prelude)
                if name == "media" and prelude:
                    facts.media_queries.append(prelude)
                if name == "import":
                    m = re.search(r"""url\(\s*["']?([^"')]+)|["']([^"']+)["']""", prelude)
                    if m:
                        facts.imports.append(m.group(1) or m.group(2))
                if name == "font-face" and rule.content:
                    ff: dict[str, Any] = {"origin": origin}
                    for d in tinycss2.parse_declaration_list(
                        rule.content, skip_comments=True, skip_whitespace=True
                    ):
                        if d.type == "declaration":
                            ff[d.lower_name] = _serialize(d.value)
                    if ff.get("font-family"):
                        facts.font_faces.append(ff)
                    continue
                if name == "theme" and rule.content:  # Tailwind v4
                    block: dict[str, str] = {}
                    for d in tinycss2.parse_declaration_list(
                        rule.content, skip_comments=True, skip_whitespace=True
                    ):
                        if d.type == "declaration" and d.lower_name.startswith("--"):
                            value = _serialize(d.value)
                            block[d.lower_name] = value
                            facts.custom_props.append(
                                {
                                    "name": d.lower_name,
                                    "value": value,
                                    "selector": "@theme",
                                    "origin": origin,
                                }
                            )
                            _handle_declaration(facts, d.lower_name, value, origin, "@theme")
                    if block:
                        facts.theme_blocks.append(block)
                    continue
                if rule.content:
                    inner = tinycss2.parse_rule_list(
                        rule.content, skip_comments=True, skip_whitespace=True
                    )
                    if inner and any(getattr(r, "type", "") in ("qualified-rule", "at-rule") for r in inner):
                        _walk(facts, inner, origin, depth + 1)
                    else:
                        for d in tinycss2.parse_declaration_list(
                            rule.content, skip_comments=True, skip_whitespace=True
                        ):
                            if d.type == "declaration":
                                _handle_declaration(
                                    facts, d.lower_name, _serialize(d.value), origin, f"@{name}"
                                )
        except Exception as exc:  # regra malformada não pode derrubar a extração
            facts.errors.append(f"{origin}: {exc}")
    return


def parse_css(text: str, origin: str = "inline") -> CssFacts:
    """Extrai todos os fatos de uma folha de estilo."""
    facts = CssFacts()
    if not text or not text.strip():
        return facts
    try:
        rules = tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True)
    except Exception as exc:
        facts.errors.append(f"{origin}: não consegui parsear ({exc})")
        return facts
    _walk(facts, rules, origin)
    return facts


def parse_preprocessor(text: str, origin: str = "inline") -> CssFacts:
    """SCSS/LESS: roda o parser CSS e ainda captura variáveis $foo / @foo."""
    # Sintaxes exclusivas de pré-processador confundem o tinycss2; neutraliza.
    cleaned = re.sub(r"^\s*@(use|forward|import)\s+[^;]+;", "", text, flags=re.M)
    cleaned = re.sub(r"^\s*@(mixin|include|extend|if|else|each|for|function|return)\b[^\n{;]*[;{]?", "", cleaned, flags=re.M)
    facts = parse_css(cleaned, origin)
    for m in re.finditer(r"^\s*\$([\w-]+)\s*:\s*([^;{]+);", text, flags=re.M):
        name, value = m.group(1), m.group(2).strip()
        facts.custom_props.append(
            {"name": f"${name}", "value": value, "selector": "$variables", "origin": origin}
        )
        _add_color(facts, "color", value, origin)
        _sort_variable_value(facts, value)
    for m in re.finditer(r"^\s*@([\w-]+)\s*:\s*([^;{]+);", text, flags=re.M):
        name, value = m.group(1), m.group(2).strip()
        if name in ("media", "import", "use", "forward", "font-face", "supports", "charset", "keyframes"):
            continue
        facts.custom_props.append(
            {"name": f"@{name}", "value": value, "selector": "@variables", "origin": origin}
        )
        _add_color(facts, "color", value, origin)
        _sort_variable_value(facts, value)
    return facts


def _sort_variable_value(facts: CssFacts, value: str) -> None:
    """Classifica o valor de uma variável em spacing/radius/duração pelo formato."""
    v = value.strip()
    if COLOR_RE.search(v):
        return
    lengths = LENGTH_RE.findall(v)
    if len(lengths) == 1 and len(v.split()) == 1:
        num, unit = lengths[0]
        px = float(num) * (16 if unit in ("rem", "em") else 1)
        if px <= 24 and "radius" not in v:
            facts.spacing[f"{num}{unit}"] += 1
        else:
            facts.spacing[f"{num}{unit}"] += 1
    for num, unit in DURATION_RE.findall(v):
        facts.durations[f"{num}{unit}"] += 1
