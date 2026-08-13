"""Estruturas de dados compartilhadas entre extratores e writers.

`DesignSystem` é o formato canônico: os dois modos de extração (web e repo)
produzem esse objeto, e todos os writers consomem só ele.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FontFace:
    family: str
    weight: str = "400"
    style: str = "normal"
    urls: list[str] = field(default_factory=list)
    display: str | None = None
    unicode_range: str | None = None
    local_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "weight": self.weight,
            "style": self.style,
            "urls": self.urls,
            "display": self.display,
            "unicodeRange": self.unicode_range,
            "localPath": self.local_path,
        }


@dataclass
class TypeStyle:
    """Um degrau da escala tipográfica, ancorado num tipo de elemento."""

    name: str
    font_size: float
    font_weight: str = "400"
    line_height: str = "normal"
    letter_spacing: str = "normal"
    font_family: str = ""
    text_transform: str = "none"
    count: int = 1
    sample: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "fontSize": self.font_size,
            "fontWeight": self.font_weight,
            "lineHeight": self.line_height,
            "letterSpacing": self.letter_spacing,
            "fontFamily": self.font_family,
            "textTransform": self.text_transform,
            "count": self.count,
            "sample": self.sample,
        }


@dataclass
class Asset:
    kind: str  # logo | icon | font | image | favicon | screenshot
    url: str
    path: str | None = None  # relativo à pasta de saída
    width: int | None = None
    height: int | None = None
    inline_svg: str | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "url": self.url,
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "note": self.note,
        }


@dataclass
class ComponentSnapshot:
    """Estilos computados de um componente, incluindo estados."""

    kind: str  # button-primary, input, card...
    selector: str = ""
    label: str = ""
    html: str = ""
    base: dict[str, str] = field(default_factory=dict)
    hover: dict[str, str] = field(default_factory=dict)
    focus: dict[str, str] = field(default_factory=dict)
    active: dict[str, str] = field(default_factory=dict)
    page: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "selector": self.selector,
            "label": self.label,
            "html": self.html,
            "base": self.base,
            "hover": self.hover,
            "focus": self.focus,
            "active": self.active,
            "page": self.page,
        }

    def states(self) -> dict[str, dict[str, str]]:
        """Estados não vazios, na ordem em que interessam ao leitor."""
        return {
            nome: valores
            for nome, valores in (
                ("hover", self.hover),
                ("focus", self.focus),
                ("active", self.active),
            )
            if valores
        }


@dataclass
class DesignSystem:
    mode: str = "url"  # url | repo
    target: str = ""
    name: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat())

    pages: list[dict[str, Any]] = field(default_factory=list)
    files_scanned: list[str] = field(default_factory=list)

    colors: dict[str, Any] = field(default_factory=dict)
    typography: dict[str, Any] = field(default_factory=dict)
    spacing: dict[str, Any] = field(default_factory=dict)
    radii: dict[str, Any] = field(default_factory=dict)
    shadows: list[dict[str, Any]] = field(default_factory=list)
    borders: dict[str, Any] = field(default_factory=dict)
    breakpoints: list[int] = field(default_factory=list)
    containers: list[float] = field(default_factory=list)
    z_index: list[int] = field(default_factory=list)
    motion: dict[str, Any] = field(default_factory=dict)
    opacity: list[float] = field(default_factory=list)

    css_variables: dict[str, dict[str, Any]] = field(default_factory=dict)
    components: list[ComponentSnapshot] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    # v0.2: contextos extras e leitura sobre os dados
    themes: dict[str, Any] = field(default_factory=dict)
    responsive: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ helpers
    def assets_of(self, kind: str) -> list[Asset]:
        return [a for a in self.assets if a.kind == kind]

    def role(self, name: str, default: str | None = None) -> str | None:
        return (self.colors.get("roles") or {}).get(name, {}).get("value", default)

    @property
    def theme(self) -> str:
        return self.colors.get("theme", "light")

    @property
    def display_target(self) -> str:
        """Como a origem aparece nos documentos.

        No modo repo, `target` é um caminho absoluto da máquina de quem rodou —
        isso não interessa a quem lê o design system (e expõe a estrutura de
        pastas), então nos documentos mostramos só o nome do repositório. O
        caminho completo continua no raw.json, para auditoria.
        """
        if self.mode == "repo":
            from pathlib import Path

            return self.name or Path(self.target).name or self.target
        return self.target

    @property
    def has_dark(self) -> bool:
        return bool((self.themes or {}).get("dark"))

    def counts(self) -> dict[str, int]:
        base = {
            "cores": len(self.colors.get("clusters", [])),
            "papéis": len(self.colors.get("roles", {})),
            "fontes": len(self.typography.get("families", [])),
            "estilos de texto": len(self.typography.get("scale", [])),
            "@font-face": len(self.typography.get("font_faces", [])),
            "spacing": len(self.spacing.get("scale", [])),
            "radii": len(self.radii.get("scale", [])),
            "sombras": len(self.shadows),
            "breakpoints": len(self.breakpoints),
            "vars CSS": len(self.css_variables),
            "componentes": len(self.components),
            "assets": len([a for a in self.assets if a.kind != "screenshot"]),
        }
        if self.has_dark:
            base["temas"] = 2
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DesignSystem":
        """Reconstrói a partir de um raw.json — usado para regerar saídas."""
        ds = cls(
            mode=data.get("mode", "url"),
            target=data.get("target", ""),
            name=data.get("name", ""),
        )
        if data.get("generatedAt"):
            ds.generated_at = data["generatedAt"]
        ds.pages = data.get("pages") or []
        ds.files_scanned = data.get("filesScanned") or []
        ds.colors = data.get("colors") or {}
        ds.typography = data.get("typography") or {}
        ds.spacing = data.get("spacing") or {}
        ds.radii = data.get("radii") or {}
        ds.shadows = data.get("shadows") or []
        ds.borders = data.get("borders") or {}
        ds.breakpoints = data.get("breakpoints") or []
        ds.containers = data.get("containers") or []
        ds.z_index = data.get("zIndex") or []
        ds.motion = data.get("motion") or {}
        ds.opacity = data.get("opacity") or []
        ds.css_variables = data.get("cssVariables") or {}
        ds.raw = data.get("raw") or {}
        ds.warnings = data.get("warnings") or []
        # Ausentes nas extrações da v0.1 — o documento simplesmente omite as seções.
        ds.themes = data.get("themes") or {}
        ds.responsive = data.get("responsive") or {}
        ds.diagnostics = data.get("diagnostics") or {}
        ds.context = data.get("context") or {}
        ds.components = [
            ComponentSnapshot(
                kind=c.get("kind", ""),
                selector=c.get("selector", ""),
                label=c.get("label", ""),
                html=c.get("html", ""),
                base=c.get("base") or {},
                hover=c.get("hover") or {},
                focus=c.get("focus") or {},
                active=c.get("active") or {},
                page=c.get("page", ""),
            )
            for c in (data.get("components") or [])
        ]
        ds.assets = [
            Asset(
                kind=a.get("kind", ""),
                url=a.get("url", ""),
                path=a.get("path"),
                width=a.get("width"),
                height=a.get("height"),
                note=a.get("note", ""),
            )
            for a in (data.get("assets") or [])
        ]
        return ds

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "target": self.target,
            "name": self.name,
            "generatedAt": self.generated_at,
            "pages": self.pages,
            "filesScanned": self.files_scanned,
            "colors": self.colors,
            "typography": self.typography,
            "spacing": self.spacing,
            "radii": self.radii,
            "shadows": self.shadows,
            "borders": self.borders,
            "breakpoints": self.breakpoints,
            "containers": self.containers,
            "zIndex": self.z_index,
            "motion": self.motion,
            "opacity": self.opacity,
            "cssVariables": self.css_variables,
            "components": [c.to_dict() for c in self.components],
            "assets": [a.to_dict() for a in self.assets],
            "warnings": self.warnings,
            "themes": self.themes,
            "responsive": self.responsive,
            "diagnostics": self.diagnostics,
            "context": self.context,
        }
