"""Geração de um tailwind.config.js colável a partir dos tokens extraídos."""

from __future__ import annotations

import json
from typing import Any

from ..analysis.color import scale_name
from ..analysis.typography import name_font_sizes
from ..models import DesignSystem
from .tokens import token_name


def _js(value: Any, indent: int = 0) -> str:
    """Serializa em JS legível (aspas simples, chaves sem aspas quando possível)."""
    pad = "  " * indent
    inner = "  " * (indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        parts = []
        for key, val in value.items():
            k = key if _is_ident(key) else _quote(str(key))
            parts.append(f"{inner}{k}: {_js(val, indent + 1)},")
        return "{\n" + "\n".join(parts) + f"\n{pad}}}"
    if isinstance(value, list):
        if not value:
            return "[]"
        if all(isinstance(v, str) for v in value):
            joined = ", ".join(_quote(v) for v in value)
            if len(joined) < 70:
                return f"[{joined}]"
        parts = [f"{inner}{_js(v, indent + 1)}," for v in value]
        return "[\n" + "\n".join(parts) + f"\n{pad}]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return _quote(str(value))


def _quote(text: str) -> str:
    if "'" in text:
        return json.dumps(text)
    return f"'{text}'"


def _is_ident(key: str) -> bool:
    return bool(key) and (key[0].isalpha() or key[0] == "_") and all(
        c.isalnum() or c in "_$" for c in key
    )


def _len(value: Any) -> str:
    if isinstance(value, (int, float)):
        if value == 0:
            return "0px"
        return f"{value / 16:g}rem" if value >= 16 and value % 4 == 0 else f"{value:g}px"
    return str(value)


def build_tailwind_config(ds: DesignSystem) -> str:
    extend: dict[str, Any] = {}

    # ------------------------------------------------------------- colors
    colors: dict[str, Any] = {}
    for role, info in (ds.colors.get("roles") or {}).items():
        colors[token_name(role)] = info["value"]
    named = ds.colors.get("named") or {}
    for name, value in named.items():
        parts = token_name(name).split("-")
        node = colors
        for part in parts[:-1]:
            nxt = node.get(part)
            if not isinstance(nxt, dict):
                nxt = {"DEFAULT": nxt} if isinstance(nxt, str) else {}
                node[part] = nxt
            node = nxt
        leaf = parts[-1]
        if isinstance(node.get(leaf), dict):
            node[leaf]["DEFAULT"] = value
        else:
            node[leaf] = value

    neutrals = ds.colors.get("neutrals") or []
    if neutrals:
        colors["neutral"] = {
            scale_name(i, len(neutrals)): e["value"] for i, e in enumerate(neutrals)
        }
    accents = ds.colors.get("accents") or []
    if accents:
        colors["accent"] = {str(i): e["value"] for i, e in enumerate(accents[:10], start=1)}
    if colors:
        extend["colors"] = colors

    # ------------------------------------------------------------ spacing
    spacing_named = ds.spacing.get("named") or {}
    if spacing_named:
        extend["spacing"] = {token_name(k): _len(v) for k, v in spacing_named.items()}

    radii_named = ds.radii.get("named") or {}
    if radii_named:
        extend["borderRadius"] = {
            token_name(k): ("9999px" if _is_pill(v) else _len(v)) for k, v in radii_named.items()
        }

    if ds.shadows:
        shadow_names = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl", "inner"]
        shadows: dict[str, str] = {}
        for index, entry in enumerate(ds.shadows):
            key = token_name(
                entry.get("name") or (shadow_names[index] if index < len(shadow_names) else f"s{index}")
            )
            while key in shadows:
                key += "-alt"
            shadows[key] = entry["value"]
        extend["boxShadow"] = shadows

    typo = ds.typography or {}
    families = typo.get("families") or []
    if families:
        font_family: dict[str, Any] = {}
        for index, fam in enumerate(families[:5]):
            key = "sans" if index == 0 else token_name(fam["family"])
            stack = [p.strip().strip("\"'") for p in (fam.get("stack") or fam["family"]).split(",")]
            font_family[key] = [p for p in stack if p]
        extend["fontFamily"] = font_family

    named_sizes = (typo.get("named") or {}).get("fontSize") or {}
    sizes = named_sizes or name_font_sizes(typo.get("sizes") or [])
    if sizes:
        extend["fontSize"] = {token_name(k): _len(v) for k, v in sizes.items()}

    if typo.get("weights"):
        extend["fontWeight"] = {str(w): str(w) for w in typo["weights"]}

    if ds.breakpoints:
        names = ["sm", "md", "lg", "xl", "2xl", "3xl", "4xl", "5xl"]
        named_bp = ds.raw.get("named_breakpoints") or {}
        if named_bp:
            extend["screens"] = {token_name(k): str(v) for k, v in named_bp.items()}
        else:
            extend["screens"] = {
                (names[i] if i < len(names) else f"bp{i}"): f"{bp}px"
                for i, bp in enumerate(ds.breakpoints)
            }

    if ds.containers:
        extend["maxWidth"] = {token_name(f"{v:g}"): _len(v) for v in ds.containers}
    if ds.borders.get("widths"):
        extend["borderWidth"] = {token_name(f"{v:g}"): _len(v) for v in ds.borders["widths"]}
    if ds.z_index:
        extend["zIndex"] = {str(z): str(z) for z in ds.z_index}
    if ds.opacity:
        extend["opacity"] = {str(int(v * 100)): f"{v:g}" for v in ds.opacity}
    motion = ds.motion or {}
    if motion.get("durations"):
        extend["transitionDuration"] = {
            token_name(d): d for d in motion["durations"] if d and d != "0s"
        }
    if motion.get("easings"):
        extend["transitionTimingFunction"] = {
            token_name(e): e for e in motion["easings"]
        }

    # Tema escuro: o Tailwind não tem modes, então as cores escuras entram como
    # um grupo próprio, usável com `dark:bg-dark-background`.
    pares = (ds.themes or {}).get("pairs") or {}
    escuras = {
        token_name(papel): valores["dark"]
        for papel, valores in pares.items()
        if valores.get("dark") and valores.get("dark") != valores.get("light")
    }
    if escuras and "colors" in extend:
        extend["colors"]["dark"] = escuras

    config: dict[str, Any] = {
        "content": ds.raw.get("tailwind", {}).get("content")
        or ["./src/**/*.{js,ts,jsx,tsx,html,vue,svelte}"],
        "theme": {"extend": extend},
        "plugins": [],
    }
    dark = ds.raw.get("tailwind", {}).get("darkMode")
    if dark:
        config["darkMode"] = dark
    elif escuras:
        config["darkMode"] = "class"

    header = (
        "/**\n"
        f" * Extraído de {ds.display_target} por designsys em {ds.generated_at}\n"
        " *\n"
        " * Cole no seu projeto Tailwind. Tudo está dentro de `theme.extend`,\n"
        " * então os defaults do Tailwind continuam valendo.\n"
        " * @type {import('tailwindcss').Config}\n"
        " */\n"
    )
    return header + "module.exports = " + _js(config) + "\n"


def _is_pill(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return value >= 999
    text = str(value)
    return "9999" in text or "50%" in text
