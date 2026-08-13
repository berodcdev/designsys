"""Acumuladores de tokens por contexto de coleta.

Um "contexto" é uma combinação de tema e viewport: `light`, `dark`, `mobile`,
`tablet`. Cada um acumula os mesmos tipos de valor de forma independente, para
que o mesmo site possa ser descrito nos dois temas e nos três tamanhos de tela
sem que as coletas se misturem.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

# Contextos principais. `light` é o retrato canônico — é dele que saem
# `ds.colors`, `ds.spacing` e companhia.
MAIN = "light"
DARK = "dark"
VIEWPORTS = {
    "mobile": {"width": 390, "height": 844},
    "tablet": {"width": 820, "height": 1180},
}


@dataclass
class TokenBucket:
    """Tudo que uma coleta de página produz, para um contexto."""

    name: str = MAIN

    colors_by_prop: defaultdict[str, Counter] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    spacing: Counter = field(default_factory=Counter)
    radii: Counter = field(default_factory=Counter)
    shadows: Counter = field(default_factory=Counter)
    border_widths: Counter = field(default_factory=Counter)
    z_index: Counter = field(default_factory=Counter)
    durations: Counter = field(default_factory=Counter)
    easings: Counter = field(default_factory=Counter)
    opacity: Counter = field(default_factory=Counter)
    containers: Counter = field(default_factory=Counter)

    type_samples: list[dict[str, Any]] = field(default_factory=list)
    font_stacks: Counter = field(default_factory=Counter)

    button_bgs: Counter = field(default_factory=Counter)
    link_colors: Counter = field(default_factory=Counter)
    body_info: dict[str, Any] = field(default_factory=dict)
    css_vars: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Diagnóstico (frente B): pares texto/fundo e alvos de toque reais.
    contrast_pairs: dict[str, dict[str, Any]] = field(default_factory=dict)
    small_targets: list[dict[str, Any]] = field(default_factory=list)

    # --------------------------------------------------------------- ingestão
    def merge_page(self, data: dict[str, Any], *, page_url: str = "", light: bool = False) -> None:
        """Incorpora o resultado de uma coleta.

        `light=True` é o modo usado nos viewports secundários: só tipografia,
        espaçamento e containers, que é o que muda com a largura da tela.
        Recoletar a paleta inteira em cada viewport triplicaria o custo sem
        acrescentar nada — cor não muda com media query na prática.
        """
        spacing = data.get("spacing") or {}
        for grupo in ("margin", "padding", "gap"):
            for value, count in (spacing.get(grupo) or {}).items():
                self.spacing[value] += count

        for value, count in (data.get("containers") or {}).items():
            self.containers[value] += count

        for sample in data.get("typography") or []:
            self.type_samples.append(sample)
            stack = sample.get("fontFamily")
            if stack:
                self.font_stacks[stack] += int(sample.get("count", 1))

        if light:
            return

        for group, values in (data.get("colors") or {}).items():
            for value, count in values.items():
                self.colors_by_prop[group][value] += count

        for target, key in (
            (self.radii, "radii"),
            (self.shadows, "shadows"),
            (self.border_widths, "borderWidths"),
            (self.z_index, "zIndex"),
            (self.durations, "durations"),
            (self.easings, "easings"),
            (self.opacity, "opacity"),
        ):
            for value, count in (data.get(key) or {}).items():
                target[value] += count

        for value, count in (data.get("buttonBackgrounds") or {}).items():
            self.button_bgs[value] += count
        for value, count in (data.get("linkColors") or {}).items():
            self.link_colors[value] += count

        for name, value in (data.get("cssVars") or {}).items():
            if name not in self.css_vars:
                self.css_vars[name] = {"value": value, "origin": page_url, "scope": ":root"}
        for entry in data.get("varsFromRules") or []:
            name = entry.get("name")
            if name and name not in self.css_vars:
                self.css_vars[name] = {
                    "value": entry.get("value", ""),
                    "origin": entry.get("href") or page_url,
                    "scope": entry.get("selector", ""),
                }

        for par in data.get("contrastPairs") or []:
            chave = f"{par.get('fg')}|{par.get('bg')}|{par.get('size')}|{par.get('weight')}"
            existente = self.contrast_pairs.get(chave)
            if existente:
                existente["count"] += int(par.get("count", 1))
            else:
                self.contrast_pairs[chave] = {**par, "count": int(par.get("count", 1))}

        for alvo in data.get("smallTargets") or []:
            if len(self.small_targets) < 60:
                self.small_targets.append(alvo)

        if not self.body_info:
            self.body_info = data.get("body") or {}

    # -------------------------------------------------------------- saturação
    def token_signature(self) -> set[str]:
        """Conjunto do que já foi visto — a base da parada por saturação.

        Duas páginas que produzem a mesma assinatura não acrescentaram nada ao
        design system, por mais diferentes que sejam visualmente.
        """
        vistos: set[str] = set()
        for grupo, counter in self.colors_by_prop.items():
            vistos.update(f"c:{v}" for v in counter)
        vistos.update(f"s:{v}" for v in self.spacing)
        vistos.update(f"r:{v}" for v in self.radii)
        vistos.update(f"sh:{v}" for v in self.shadows)
        vistos.update(f"f:{v}" for v in self.font_stacks)
        vistos.update(f"v:{v}" for v in self.css_vars)
        for sample in self.type_samples:
            vistos.add(f"t:{sample.get('tag')}|{sample.get('fontSize')}|{sample.get('fontWeight')}")
        return vistos

    def is_empty(self) -> bool:
        return not self.colors_by_prop and not self.type_samples and not self.spacing


def color_fingerprint(bucket: TokenBucket, limite: int = 40) -> tuple[str, ...]:
    """Assinatura das cores dominantes — usada para saber se o tema mudou."""
    totais: Counter = Counter()
    for counter in bucket.colors_by_prop.values():
        totais.update(counter)
    return tuple(sorted(v for v, _ in totais.most_common(limite)))
