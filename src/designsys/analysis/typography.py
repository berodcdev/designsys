"""Normalização de famílias e construção da escala tipográfica."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Iterable, Sequence

from ..models import TypeStyle
from .scales import parse_length

GENERIC_FAMILIES = {
    "sans-serif",
    "serif",
    "monospace",
    "cursive",
    "fantasy",
    "system-ui",
    "ui-sans-serif",
    "ui-serif",
    "ui-monospace",
    "ui-rounded",
    "-apple-system",
    "blinkmacsystemfont",
    "inherit",
    "initial",
    "emoji",
    "math",
    "fangsong",
}

# Ordem em que os papéis aparecem no style guide.
ROLE_ORDER = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "body",
    "lead",
    "small",
    "button",
    "input",
    "label",
    "link",
    "code",
    "blockquote",
]

_TAG_TO_ROLE = {
    "h1": "h1",
    "h2": "h2",
    "h3": "h3",
    "h4": "h4",
    "h5": "h5",
    "h6": "h6",
    "p": "body",
    "li": "body",
    "span": "body",
    "div": "body",
    "button": "button",
    "input": "input",
    "textarea": "input",
    "select": "input",
    "label": "label",
    "a": "link",
    "small": "small",
    "code": "code",
    "pre": "code",
    "blockquote": "blockquote",
}


def split_stack(stack: str) -> list[str]:
    """Divide uma font-family CSS respeitando aspas."""
    if not stack:
        return []
    parts = re.split(r",(?=(?:[^\"']*[\"'][^\"']*[\"'])*[^\"']*$)", stack)
    out = []
    for p in parts:
        name = p.strip().strip("\"'").strip()
        if name:
            out.append(name)
    return out


def primary_family(stack: str) -> str | None:
    """Primeira família não-genérica de uma stack. None se for só genérica."""
    for name in split_stack(stack):
        if name.lower() not in GENERIC_FAMILIES and not name.startswith("--"):
            return name
    return None


def normalize_family(name: str) -> str:
    return " ".join(name.strip().strip("\"'").split())


def rank_families(stacks: Iterable[tuple[str, int]]) -> list[dict[str, Any]]:
    """Ordena famílias reais por uso, guardando a stack completa mais comum."""
    counts: Counter[str] = Counter()
    stacks_for: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for stack, count in stacks:
        # `var(--x)` e `inherit` são indireções, não famílias — o valor real já
        # foi coletado onde a variável está definida.
        if not stack or "var(" in stack or stack.strip().lower() in ("inherit", "initial", "unset", "revert"):
            continue
        fam = primary_family(stack)
        if not fam:
            # Só genéricas: ainda vale registrar a primeira (system-ui etc.)
            generic = split_stack(stack)
            if not generic:
                continue
            fam = generic[0]
        fam = normalize_family(fam)
        counts[fam] += count
        stacks_for[fam][" ".join(stack.split())] += count

    out = []
    for fam, count in counts.most_common():
        stack = stacks_for[fam].most_common(1)[0][0]
        out.append(
            {
                "family": fam,
                "count": count,
                "stack": stack,
                "generic": fam.lower() in GENERIC_FAMILIES,
            }
        )
    return out


def role_for(tag: str, sample: dict[str, Any]) -> str:
    tag = (tag or "").lower()
    role = _TAG_TO_ROLE.get(tag)
    if role:
        return role
    if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
        return tag
    return "body"


def build_type_scale(samples: Sequence[dict[str, Any]]) -> list[TypeStyle]:
    """Agrupa amostras de elementos em degraus tipográficos por papel.

    Para cada papel (h1, body, button...) escolhe a combinação
    tamanho/peso/entrelinha mais frequente — a variante "canônica" do site.
    """
    buckets: defaultdict[tuple[str, float, str], dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "samples": []}
    )

    for s in samples:
        size = parse_length(s.get("fontSize"))
        if size is None or size <= 0:
            continue
        role = role_for(s.get("tag", ""), s)
        weight = str(s.get("fontWeight") or "400")
        key = (role, round(size, 1), weight)
        b = buckets[key]
        b["count"] += int(s.get("count", 1))
        if len(b["samples"]) < 6:
            b["samples"].append(s)

    # Mantém no máximo duas variantes por papel (ex.: h2 normal e h2 em card).
    by_role: defaultdict[str, list[tuple[tuple[str, float, str], dict[str, Any]]]] = defaultdict(list)
    for key, data in buckets.items():
        by_role[key[0]].append((key, data))

    styles: list[TypeStyle] = []
    for role, entries in by_role.items():
        is_heading = len(role) == 2 and role[0] == "h" and role[1].isdigit()
        if is_heading:
            # Um <h1> de 15px usado como eyebrow aparece mais vezes que o
            # título de 48px da página — mas quem representa o papel é o maior.
            recorrentes = [e for e in entries if e[1]["count"] >= 2] or entries
            recorrentes.sort(key=lambda kd: (-kd[0][1], -kd[1]["count"]))
            resto = [e for e in entries if e not in recorrentes]
            resto.sort(key=lambda kd: -kd[1]["count"])
            entries = recorrentes + resto
        else:
            entries.sort(key=lambda kd: -kd[1]["count"])
        limit = 2 if role in ("body", "h2", "h3") else 1
        for idx, (key, data) in enumerate(entries[:limit]):
            rep = data["samples"][0]
            name = role if idx == 0 else f"{role}-alt"
            styles.append(
                TypeStyle(
                    name=name,
                    font_size=key[1],
                    font_weight=key[2],
                    line_height=str(rep.get("lineHeight") or "normal"),
                    letter_spacing=str(rep.get("letterSpacing") or "normal"),
                    font_family=" ".join(str(rep.get("fontFamily") or "").split()),
                    text_transform=str(rep.get("textTransform") or "none"),
                    count=data["count"],
                    sample=(rep.get("text") or "")[:80],
                )
            )

    def sort_key(st: TypeStyle) -> tuple[int, float]:
        base = st.name.replace("-alt", "")
        order = ROLE_ORDER.index(base) if base in ROLE_ORDER else len(ROLE_ORDER)
        return (order, -st.font_size)

    styles.sort(key=sort_key)
    return styles


def font_size_scale(samples: Sequence[dict[str, Any]], max_items: int = 12) -> list[float]:
    """Escala de tamanhos de fonte independente de papel."""
    counter: Counter[float] = Counter()
    for s in samples:
        size = parse_length(s.get("fontSize"))
        if size is None or size < 8 or size > 160:
            continue
        counter[round(size, 1)] += int(s.get("count", 1))
    if not counter:
        return []
    total = sum(counter.values())
    picked = [v for v, c in counter.most_common() if c / total >= 0.01][:max_items]
    if not picked:
        picked = [v for v, _ in counter.most_common(max_items)]
    return sorted(picked)


def weight_scale(samples: Sequence[dict[str, Any]]) -> list[int]:
    counter: Counter[int] = Counter()
    for s in samples:
        raw = str(s.get("fontWeight") or "").strip()
        if raw in ("normal", ""):
            raw = "400"
        if raw == "bold":
            raw = "700"
        if not raw.isdigit():
            continue
        counter[int(raw)] += int(s.get("count", 1))
    return sorted(v for v, c in counter.most_common(9))


def size_name(px: float) -> str:
    """Nome de camiseta para um tamanho de fonte em px."""
    table = [
        (12, "xs"),
        (14, "sm"),
        (16, "base"),
        (18, "lg"),
        (20, "xl"),
        (24, "2xl"),
        (30, "3xl"),
        (36, "4xl"),
        (48, "5xl"),
        (60, "6xl"),
        (72, "7xl"),
        (96, "8xl"),
    ]
    best = min(table, key=lambda t: abs(t[0] - px))
    return best[1]


def ladder_name(offset: int) -> str:
    """Nome de camiseta a `offset` degraus do `base` — sem teto para os lados.

    -2 -> xs, -1 -> sm, 0 -> base, 1 -> lg, 2 -> xl, 3 -> 2xl, -3 -> 2xs, …
    """
    if offset == 0:
        return "base"
    if offset < 0:
        return {-1: "sm", -2: "xs"}.get(offset, f"{abs(offset) - 1}xs")
    return {1: "lg", 2: "xl"}.get(offset, f"{offset - 1}xl")


def name_font_sizes(sizes: Sequence[float]) -> dict[str, float]:
    """Nomeia a escala de tamanhos.

    Primeiro tenta o nome "natural" de cada tamanho (16px -> base). Quando dois
    tamanhos disputam o mesmo nome — comum em escalas densas, com 13/14/15px —
    todos passam a ser nomeados por posição, o que dá `sm/base/lg` em vez de
    `xs`, `xs+`, `xs++`.
    """
    ordenados = sorted(set(sizes))
    if not ordenados:
        return {}

    naturais = [size_name(px) for px in ordenados]
    if len(set(naturais)) == len(naturais):
        return dict(zip(naturais, ordenados))

    # Ancora a escada no tamanho mais próximo de 16px, que vira o "base".
    base_index = min(range(len(ordenados)), key=lambda i: abs(ordenados[i] - 16))
    nomes = [ladder_name(i - base_index) for i in range(len(ordenados))]
    return dict(zip(nomes, ordenados))
