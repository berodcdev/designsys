"""Escrita de tokens no formato W3C Design Tokens (DTCG)."""

from __future__ import annotations

import re
from typing import Any

from ..analysis.color import scale_name
from ..models import DesignSystem

DTCG_SCHEMA = "https://tr.designtokens.org/format/"

_CUBIC = re.compile(r"cubic-bezier\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)")

# Tokeniza uma box-shadow mantendo funções de cor inteiras (`rgba(0, 0, 0, .1)`
# tem vírgulas e espaços dentro, então não dá para quebrar por espaço).
_SHADOW_TOKEN = re.compile(
    r"[a-zA-Z-]+\([^()]*\)|#[0-9a-fA-F]{3,8}|-?\d*\.?\d+(?:px|rem|em|%)?|[a-zA-Z-]+"
)
_LENGTH_TOKEN = re.compile(r"^-?\d*\.?\d+(px|rem|em)?$")


def split_top_level(text: str, sep: str = ",") -> list[str]:
    """Divide respeitando parênteses — `a, rgba(1, 2, 3), b` vira 3 partes."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in text:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        if char == sep and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


def token_name(raw: str) -> str:
    """Normaliza um nome para kebab-case seguro em JSON/CSS."""
    name = str(raw).strip().strip("-").replace("/", "-").replace(".", "-")
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name or "token"


def _dim(value: float | str) -> str:
    if isinstance(value, (int, float)):
        return f"{value:g}px"
    v = str(value).strip()
    return v or "0"


def _shadow_value(raw: str) -> Any:
    """Converte uma box-shadow CSS para o objeto DTCG; cai para string se não der."""
    shadows = []
    for part in split_top_level(raw, ","):
        inset = False
        lengths: list[str] = []
        color: str | None = None
        for token in _SHADOW_TOKEN.findall(part):
            low = token.lower()
            if low == "inset":
                inset = True
            elif _LENGTH_TOKEN.match(token):
                # `0` sem unidade é comprimento válido em CSS; DTCG quer unidade.
                lengths.append(token if not token.lstrip("-").replace(".", "").isdigit() else f"{token}px")
            elif color is None and _looks_like_color(token):
                color = token
        if len(lengths) < 2:
            return raw
        entry: dict[str, Any] = {
            "offsetX": lengths[0],
            "offsetY": lengths[1],
            "blur": lengths[2] if len(lengths) > 2 else "0px",
            "spread": lengths[3] if len(lengths) > 3 else "0px",
            "color": color or "rgba(0, 0, 0, 0.1)",
        }
        if inset:
            entry["inset"] = True
        shadows.append(entry)
    if not shadows:
        return raw
    return shadows[0] if len(shadows) == 1 else shadows


def _looks_like_color(token: str) -> bool:
    from ..analysis.color import parse_color

    return parse_color(token) is not None


def _typography_value(style: dict[str, Any]) -> dict[str, Any]:
    return {
        "fontFamily": style.get("fontFamily") or "",
        "fontSize": _dim(style.get("fontSize", 16)),
        "fontWeight": _weight(style.get("fontWeight", "400")),
        "lineHeight": str(style.get("lineHeight") or "normal"),
        "letterSpacing": str(style.get("letterSpacing") or "normal"),
    }


def _weight(value: Any) -> Any:
    s = str(value).strip()
    if s.isdigit():
        return int(s)
    return {"normal": 400, "bold": 700}.get(s.lower(), s or 400)


def build_dtcg(ds: DesignSystem) -> dict[str, Any]:
    """Monta a árvore DTCG completa a partir do DesignSystem."""
    out: dict[str, Any] = {
        "$schema": DTCG_SCHEMA,
        "$description": f"Design tokens extraídos de {ds.display_target} por designsys em {ds.generated_at}",
    }

    # ---------------------------------------------------------------- cores
    colors: dict[str, Any] = {}
    for role, info in (ds.colors.get("roles") or {}).items():
        colors[token_name(role)] = {
            "$value": info["value"],
            "$type": "color",
            "$description": info.get("reason", ""),
            "$extensions": {"designsys": {"usageCount": info.get("count", 0)}},
        }

    named = ds.colors.get("named") or {}
    if named:
        group: dict[str, Any] = {}
        for name, value in named.items():
            _nest(group, token_name(name).split("-"), {"$value": value, "$type": "color"})
        colors["palette"] = group

    neutrals = ds.colors.get("neutrals") or []
    if neutrals:
        scale: dict[str, Any] = {}
        for index, entry in enumerate(neutrals):
            scale[scale_name(index, len(neutrals))] = {
                "$value": entry["value"],
                "$type": "color",
                "$extensions": {"designsys": {"usageCount": entry.get("count", 0)}},
            }
        colors["neutral"] = scale

    accents = ds.colors.get("accents") or []
    if accents:
        acc: dict[str, Any] = {}
        for index, entry in enumerate(accents[:10], start=1):
            acc[str(index)] = {
                "$value": entry["value"],
                "$type": "color",
                "$extensions": {"designsys": {"hue": entry.get("hue"), "usageCount": entry.get("count", 0)}},
            }
        colors["accent"] = acc

    if colors:
        out["color"] = colors

    # -------------------------------------------------------------- spacing
    spacing_named = ds.spacing.get("named") or {}
    if spacing_named:
        out["spacing"] = {
            token_name(name): {"$value": _dim(value), "$type": "dimension"}
            for name, value in spacing_named.items()
        }
    elif ds.spacing.get("scale"):
        out["spacing"] = {
            token_name(f"{v:g}"): {"$value": _dim(v), "$type": "dimension"}
            for v in ds.spacing["scale"]
        }

    # ---------------------------------------------------------------- radii
    radii_named = ds.radii.get("named") or {}
    if radii_named:
        out["borderRadius"] = {
            token_name(name): {"$value": _dim(value), "$type": "dimension"}
            for name, value in radii_named.items()
        }

    # -------------------------------------------------------------- sombras
    if ds.shadows:
        shadows: dict[str, Any] = {}
        for index, entry in enumerate(ds.shadows):
            name = token_name(entry.get("name") or _shadow_step_name(index, len(ds.shadows)))
            while name in shadows:
                name += "-alt"
            shadows[name] = {"$value": _shadow_value(entry["value"]), "$type": "shadow"}
        out["shadow"] = shadows

    # ----------------------------------------------------------- tipografia
    typo = ds.typography or {}
    families = typo.get("families") or []
    if families:
        out["fontFamily"] = {}
        for index, fam in enumerate(families[:6]):
            key = "base" if index == 0 else token_name(fam["family"])
            out["fontFamily"][key] = {
                "$value": fam.get("stack") or fam["family"],
                "$type": "fontFamily",
                "$extensions": {"designsys": {"usageCount": fam.get("count", 0)}},
            }

    named_sizes = (typo.get("named") or {}).get("fontSize") or {}
    if named_sizes:
        out["fontSize"] = {
            token_name(name): {"$value": _dim(value), "$type": "dimension"}
            for name, value in named_sizes.items()
        }
    elif typo.get("sizes"):
        from ..analysis.typography import name_font_sizes

        out["fontSize"] = {
            token_name(name): {"$value": _dim(px), "$type": "dimension"}
            for name, px in name_font_sizes(typo["sizes"]).items()
        }

    if typo.get("weights"):
        out["fontWeight"] = {
            str(w): {"$value": int(w), "$type": "fontWeight"} for w in typo["weights"]
        }

    if typo.get("scale"):
        out["typography"] = {
            token_name(style["name"]): {
                "$value": _typography_value(style),
                "$type": "typography",
                "$extensions": {"designsys": {"usageCount": style.get("count", 0)}},
            }
            for style in typo["scale"]
        }

    # ------------------------------------------------------------- restantes
    if ds.breakpoints:
        names = ["sm", "md", "lg", "xl", "2xl", "3xl", "4xl", "5xl"]
        named_bp = ds.raw.get("named_breakpoints") or {}
        if named_bp:
            out["breakpoint"] = {
                token_name(name): {"$value": _dim(value), "$type": "dimension"}
                for name, value in named_bp.items()
            }
        else:
            out["breakpoint"] = {
                (names[i] if i < len(names) else f"bp{i}"): {
                    "$value": _dim(bp),
                    "$type": "dimension",
                }
                for i, bp in enumerate(ds.breakpoints)
            }

    if ds.borders.get("widths"):
        out["borderWidth"] = {
            token_name(f"{v:g}"): {"$value": _dim(v), "$type": "dimension"}
            for v in ds.borders["widths"]
        }

    if ds.containers:
        out["container"] = {
            token_name(f"{v:g}"): {"$value": _dim(v), "$type": "dimension"} for v in ds.containers
        }

    motion = ds.motion or {}
    if motion.get("durations"):
        out["duration"] = {
            token_name(d): {"$value": d, "$type": "duration"} for d in motion["durations"]
        }
    if motion.get("easings"):
        easings: dict[str, Any] = {}
        for easing in motion["easings"]:
            m = _CUBIC.match(easing.strip())
            key = token_name(easing)
            if m:
                easings[key] = {
                    "$value": [float(m.group(i)) for i in range(1, 5)],
                    "$type": "cubicBezier",
                }
            else:
                easings[key] = {"$value": easing, "$type": "other"}
        out["easing"] = easings

    if ds.z_index:
        out["zIndex"] = {str(z): {"$value": z, "$type": "number"} for z in ds.z_index}
    if ds.opacity:
        out["opacity"] = {
            token_name(f"{int(v * 100)}"): {"$value": v, "$type": "number"} for v in ds.opacity
        }

    return out


def _shadow_step_name(index: int, total: int) -> str:
    names = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl", "inner"]
    return names[index] if index < len(names) else f"s{index}"


def _nest(root: dict[str, Any], path: list[str], leaf: dict[str, Any]) -> None:
    """Cria a árvore aninhada para `a-b-c`, sem sobrescrever grupos existentes."""
    node = root
    for part in path[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict) or "$value" in nxt:
            nxt = {}
            node[part] = nxt
        node = nxt
    key = path[-1]
    if isinstance(node.get(key), dict) and "$value" not in node[key]:
        node[key]["DEFAULT"] = leaf
    else:
        node[key] = leaf
