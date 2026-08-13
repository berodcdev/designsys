"""Extração de design system a partir de um repositório local."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..analysis import classify, color as colormod, report, scales, typography
from ..models import Asset, DesignSystem, FontFace
from ..util.cssparse import CssFacts, parse_css, parse_preprocessor
from ..util.report import Reporter
from .jsobj import JSRaw, find_config_object, find_named_object, flatten

IGNORE_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "out",
    "coverage",
    "vendor",
    ".venv",
    "venv",
    "__pycache__",
    ".cache",
    ".turbo",
    ".parcel-cache",
    "storybook-static",
    ".vercel",
    ".output",
    "target",
    ".idea",
    ".vscode",
    "Pods",
    ".pytest_cache",
    ".mypy_cache",
    "designsys-output",
}

CSS_EXT = {".css", ".scss", ".sass", ".less", ".pcss", ".postcss"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}
FONT_EXT = {".woff2", ".woff", ".ttf", ".otf", ".eot"}
IMG_EXT = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".ico", ".gif"}

TAILWIND_CONFIG_NAMES = {
    "tailwind.config.js",
    "tailwind.config.ts",
    "tailwind.config.cjs",
    "tailwind.config.mjs",
    "tailwind.config.mts",
    "tailwind.config.cts",
}

THEME_FILE_HINT = re.compile(
    r"(^|[/_.-])(theme|themes|tokens|design-tokens|designTokens|palette|colors?)\.(js|jsx|ts|tsx|mjs|cjs)$",
    re.I,
)
THEME_CONTENT_HINT = re.compile(
    r"(createTheme|extendTheme|ThemeProvider|createGlobalTheme|styled-components|@emotion|createMuiTheme|defineTheme)"
)

TOKEN_JSON_HINT = re.compile(
    r"(^tokens\.json$|\.tokens\.json$|^design-tokens\.json$|^theme\.json$|tokens/.*\.json$|^\$?themes\.json$)",
    re.I,
)

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 6000

# Peso dado a um token declarado explicitamente (config/variável) contra um
# valor solto encontrado numa regra qualquer.
DECLARED_WEIGHT = 12


@dataclass
class RepoOptions:
    path: Path
    out: Path | None = None
    no_assets: bool = False
    verbose: bool = False
    max_files: int = MAX_FILES


@dataclass
class NamedToken:
    name: str
    value: str
    source: str
    group: str = ""


class RepoExtractor:
    def __init__(self, options: RepoOptions, reporter: Reporter | None = None) -> None:
        self.opt = options
        self.rep = reporter or Reporter()
        self.root = options.path.resolve()
        self.ds = DesignSystem(mode="repo", target=str(self.root), name=self.root.name)
        self.out_dir = options.out or Path.cwd()

        self.css_facts = CssFacts()
        self.colors_by_prop: defaultdict[str, Counter] = defaultdict(Counter)
        self.spacing: Counter = Counter()
        self.radii: Counter = Counter()
        self.shadows: Counter = Counter()
        self.border_widths: Counter = Counter()
        self.durations: Counter = Counter()
        self.easings: Counter = Counter()
        self.z_index: Counter = Counter()
        self.opacity: Counter = Counter()
        self.containers: Counter = Counter()
        self.font_stacks: Counter = Counter()
        self.font_sizes: Counter = Counter()
        self.font_weights: Counter = Counter()
        self.media_queries: list[str] = []
        self.font_faces: dict[str, FontFace] = {}
        self.css_vars: dict[str, dict[str, Any]] = {}

        self.named: defaultdict[str, dict[str, NamedToken]] = defaultdict(dict)
        self.provenance: defaultdict[str, set[str]] = defaultdict(set)
        self.breakpoint_values: Counter = Counter()
        self.sources: list[str] = []
        # Guardado para achar tokens declarados e nunca referenciados por var().
        self.source_texts: list[str] = []

    # ===================================================================== run
    def run(self) -> DesignSystem:
        if not self.root.exists():
            raise FileNotFoundError(f"caminho não existe: {self.root}")
        files = list(self._walk())
        self.rep.step(f"{len(files)} arquivo(s) relevantes encontrados")

        configs = [f for f in files if f.name in TAILWIND_CONFIG_NAMES]
        css_files = [f for f in files if f.suffix.lower() in CSS_EXT]
        js_files = [f for f in files if f.suffix.lower() in JS_EXT]
        json_files = [f for f in files if f.suffix.lower() == ".json"]
        asset_files = [f for f in files if f.suffix.lower() in FONT_EXT | IMG_EXT]

        for path in configs:
            self._read_tailwind_config(path)
        if css_files:
            self.rep.step(f"lendo {len(css_files)} arquivo(s) de estilo")
        for path in css_files:
            self._read_css(path)
        for path in json_files:
            self._read_json_tokens(path)
        theme_files = [f for f in js_files if self._is_theme_file(f)]
        if theme_files:
            self.rep.step(f"lendo {len(theme_files)} arquivo(s) de tema JS/TS")
        for path in theme_files:
            self._read_theme_js(path)
        if not self.opt.no_assets:
            self._collect_assets(asset_files)

        self._merge_css_facts()
        self._aggregate()
        if not any(
            [
                self.ds.colors.get("clusters"),
                self.ds.css_variables,
                self.ds.typography.get("families"),
            ]
        ):
            self.ds.warnings.append(
                "nenhum token de design encontrado — o repositório tem CSS, Tailwind ou tema JS?"
            )
        return self.ds

    # ================================================================== walk
    def _walk(self) -> Iterable[Path]:
        spec = self._gitignore_spec()
        count = 0
        stack = [self.root]
        while stack:
            current = stack.pop()
            try:
                entries = sorted(current.iterdir())
            except (PermissionError, OSError):
                continue
            for entry in entries:
                if entry.name.startswith(".") and entry.name not in (".storybook",):
                    if entry.is_dir():
                        continue
                rel = entry.relative_to(self.root).as_posix()
                if spec is not None and spec.match_file(rel + ("/" if entry.is_dir() else "")):
                    continue
                if entry.is_dir():
                    if entry.name in IGNORE_DIRS:
                        continue
                    stack.append(entry)
                    continue
                if not entry.is_file():
                    continue
                suffix = entry.suffix.lower()
                if suffix not in CSS_EXT | JS_EXT | FONT_EXT | IMG_EXT | {".json"}:
                    continue
                if suffix in {".json"} and not self._json_is_interesting(entry, rel):
                    continue
                try:
                    if entry.stat().st_size > MAX_FILE_BYTES:
                        continue
                except OSError:
                    continue
                count += 1
                if count > self.opt.max_files:
                    self.ds.warnings.append(
                        f"limite de {self.opt.max_files} arquivos atingido; varredura truncada"
                    )
                    return
                yield entry

    def _gitignore_spec(self):
        gitignore = self.root / ".gitignore"
        if not gitignore.exists():
            return None
        try:
            import pathspec

            lines = gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()
            return pathspec.PathSpec.from_lines("gitwildmatch", lines)
        except Exception:
            return None

    def _json_is_interesting(self, path: Path, rel: str) -> bool:
        return bool(TOKEN_JSON_HINT.search(path.name) or TOKEN_JSON_HINT.search(rel))

    def _is_theme_file(self, path: Path) -> bool:
        rel = path.relative_to(self.root).as_posix()
        if THEME_FILE_HINT.search(rel):
            return True
        try:
            if path.stat().st_size > 400_000:
                return False
            head = path.read_text(encoding="utf-8", errors="ignore")[:6000]
        except OSError:
            return False
        return bool(THEME_CONTENT_HINT.search(head))

    def _rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def _read(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            self.ds.warnings.append(f"não consegui ler {self._rel(path)}: {exc}")
            return None

    # ============================================================== tailwind
    def _read_tailwind_config(self, path: Path) -> None:
        text = self._read(path)
        if text is None:
            return
        rel = self._rel(path)
        self.rep.step(f"lendo {rel}")
        self.sources.append(rel)
        self.ds.files_scanned.append(rel)
        config, unresolved = find_config_object(text)
        if not config:
            self.ds.warnings.append(f"{rel}: não consegui extrair o objeto de configuração")
            return

        theme = config.get("theme")
        if not isinstance(theme, dict):
            self.ds.warnings.append(f"{rel}: sem bloco `theme`")
            theme = {}
        extend = theme.get("extend") if isinstance(theme.get("extend"), dict) else {}

        merged: dict[str, Any] = {}
        for key, value in theme.items():
            if key == "extend":
                continue
            merged[key] = value
        for key, value in (extend or {}).items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value

        self._ingest_tailwind_theme(merged, rel)

        if unresolved:
            uniq = sorted({u for u in unresolved if u and not u.startswith("<")})[:8]
            if uniq:
                self.ds.warnings.append(
                    f"{rel}: valores não literais ignorados ({', '.join(uniq)})"
                )
        if isinstance(config.get("darkMode"), (str, list)):
            self.ds.raw.setdefault("tailwind", {})["darkMode"] = config["darkMode"]
        content = config.get("content") or config.get("purge")
        if isinstance(content, list):
            self.ds.raw.setdefault("tailwind", {})["content"] = [
                c for c in content if isinstance(c, str)
            ]

    def _ingest_tailwind_theme(self, theme: dict[str, Any], source: str) -> None:
        group_map = {
            "colors": "colors",
            "backgroundColor": "colors",
            "textColor": "colors",
            "borderColor": "colors",
            "spacing": "spacing",
            "padding": "spacing",
            "margin": "spacing",
            "gap": "spacing",
            "borderRadius": "radii",
            "boxShadow": "shadows",
            "fontFamily": "fontFamily",
            "fontSize": "fontSize",
            "fontWeight": "fontWeight",
            "lineHeight": "lineHeight",
            "letterSpacing": "letterSpacing",
            "screens": "breakpoints",
            "maxWidth": "containers",
            "container": "containers",
            "borderWidth": "borderWidth",
            "zIndex": "zIndex",
            "opacity": "opacity",
            "transitionDuration": "durations",
            "transitionTimingFunction": "easings",
            "animation": "animation",
            "keyframes": "keyframes",
        }
        for key, value in theme.items():
            group = group_map.get(key)
            if group is None or value is None:
                continue
            if group in ("keyframes", "animation"):
                self.ds.raw.setdefault("tailwind", {})[key] = _jsonable(value)
                continue
            flat = flatten(value) if isinstance(value, (dict, list)) else {key: value}
            for name, raw_value in flat.items():
                self._record_named(group, name or key, raw_value, source)

    def _record_named(self, group: str, name: str, raw_value: Any, source: str) -> None:
        if isinstance(raw_value, JSRaw) or raw_value is None:
            return
        if isinstance(raw_value, list):
            if group == "fontFamily":
                value = ", ".join(str(v) for v in raw_value if isinstance(v, str))
            elif raw_value and isinstance(raw_value[0], (str, int, float)):
                value = str(raw_value[0])
            else:
                return
        elif isinstance(raw_value, bool):
            return
        elif isinstance(raw_value, (int, float)):
            value = str(raw_value)
        else:
            value = str(raw_value).strip()
        if not value:
            return

        name = name.strip("-") or group
        self.named[group][name] = NamedToken(name=name, value=value, source=source, group=group)
        weight = DECLARED_WEIGHT

        if group == "colors":
            rgba = colormod.parse_color(value)
            if rgba is not None:
                hexv = colormod.to_hex(rgba)
                self.colors_by_prop["declared"][value] += weight
                self.provenance[hexv].add(f"{source}:{name}")
        elif group == "spacing":
            self.spacing[value] += weight
        elif group == "radii":
            self.radii[value] += weight
        elif group == "shadows":
            self.shadows[value] += weight
        elif group == "fontFamily":
            self.font_stacks[value] += weight
        elif group == "fontSize":
            self.font_sizes[value] += weight
        elif group == "fontWeight":
            self.font_weights[value] += weight
        elif group == "breakpoints":
            for num, unit in re.findall(r"([0-9.]+)(px|rem|em)", value):
                px = float(num) * (16 if unit in ("rem", "em") else 1)
                self.breakpoint_values[int(px)] += weight
                self.media_queries.append(f"(min-width: {value})")
        elif group == "containers":
            self.containers[value] += weight
        elif group == "borderWidth":
            self.border_widths[value] += weight
        elif group == "durations":
            self.durations[value if value.endswith(("s", "ms")) else f"{value}ms"] += weight
        elif group == "easings":
            self.easings[value] += weight
        elif group == "zIndex":
            if value.lstrip("-").isdigit():
                self.z_index[value] += weight
        elif group == "opacity":
            self.opacity[value] += weight

    # ==================================================================== css
    def _read_css(self, path: Path) -> None:
        text = self._read(path)
        if text is None:
            return
        rel = self._rel(path)
        self.ds.files_scanned.append(rel)
        suffix = path.suffix.lower()
        if len(self.source_texts) < 400:
            self.source_texts.append(text)
        if suffix in (".scss", ".sass", ".less"):
            facts = parse_preprocessor(text, origin=rel)
        else:
            facts = parse_css(text, origin=rel)
        self.css_facts.merge(facts)
        for prop in facts.custom_props:
            name = prop["name"]
            value = prop["value"]
            if name not in self.css_vars:
                self.css_vars[name] = {
                    "value": value,
                    "origin": rel,
                    "scope": prop.get("selector", ""),
                }
            clean = name.lstrip("-$@")
            # Uma variável declarada é um token intencional: classifica pelo
            # nome/valor para que caia no grupo certo (spacing, shadow, radius…).
            group = _token_group(clean, value, None)
            if group:
                self._record_named(group, clean, value, rel)
            rgba = colormod.parse_color(value)
            if rgba is not None:
                self.provenance[colormod.to_hex(rgba)].add(f"{rel}:{name}")
                self.named["cssVars"][clean] = NamedToken(
                    name=clean, value=value, source=rel, group="cssVars"
                )
        for ff in facts.font_faces:
            family = (ff.get("font-family") or "").strip().strip("\"'")
            if not family:
                continue
            urls = re.findall(r"url\(\s*[\"']?([^\"')]+)", ff.get("src", ""))
            key = f"{family}|{ff.get('font-weight', '400')}|{ff.get('font-style', 'normal')}"
            self.font_faces.setdefault(
                key,
                FontFace(
                    family=family,
                    weight=str(ff.get("font-weight", "400")).strip(),
                    style=str(ff.get("font-style", "normal")).strip(),
                    urls=urls,
                    display=ff.get("font-display"),
                    unicode_range=ff.get("unicode-range"),
                ),
            )

    def _merge_css_facts(self) -> None:
        f = self.css_facts
        for prop, counter in f.colors_by_prop.items():
            for value, count in counter.items():
                self.colors_by_prop[prop][value] += count
        self.spacing.update(f.spacing)
        self.radii.update(f.radii)
        self.shadows.update(f.shadows)
        self.border_widths.update(f.border_widths)
        self.durations.update(f.durations)
        self.easings.update(f.easings)
        self.z_index.update(f.z_indexes)
        self.opacity.update(f.opacities)
        self.containers.update(f.max_widths)
        self.font_stacks.update(f.font_families)
        self.font_sizes.update(f.font_sizes)
        self.font_weights.update(f.font_weights)
        self.media_queries.extend(f.media_queries)

    # ============================================================ tokens json
    def _read_json_tokens(self, path: Path) -> None:
        text = self._read(path)
        if text is None:
            return
        rel = self._rel(path)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            self.ds.warnings.append(f"{rel}: JSON inválido ({exc.msg})")
            return
        if not isinstance(data, dict):
            return
        found = list(_walk_token_json(data))
        if not found:
            return
        self.rep.step(f"lendo tokens de {rel} ({len(found)} entradas)")
        self.ds.files_scanned.append(rel)
        self.sources.append(rel)
        for name, value, ttype in found:
            group = _token_group(name, value, ttype)
            if group:
                self._record_named(group, name, value, rel)

    # ================================================================ theme js
    def _read_theme_js(self, path: Path) -> None:
        text = self._read(path)
        if text is None:
            return
        rel = self._rel(path)
        obj, unresolved = find_named_object(
            text, ["theme", "tokens", "designTokens", "palette", "colors", "defaultTheme"]
        )
        if not obj:
            obj, unresolved = find_config_object(text)
        if not obj:
            return
        self.ds.files_scanned.append(rel)
        self.sources.append(rel)
        flat = flatten(obj)
        recorded = 0
        for name, value in flat.items():
            if not isinstance(value, (str, int, float, list)):
                continue
            group = _token_group(name, value, None)
            if group:
                self._record_named(group, name, value, rel)
                recorded += 1
        if recorded:
            self.rep.step(f"tema JS lido de {rel} ({recorded} tokens)")

    # ================================================================= assets
    def _collect_assets(self, files: list[Path]) -> None:
        asset_dirs = ("public", "assets", "static", "src/assets", "app/assets", "resources")
        for path in files:
            rel = self._rel(path)
            suffix = path.suffix.lower()
            in_asset_dir = any(part in rel.split("/") for part in ("public", "assets", "static", "fonts", "img", "images", "icons"))
            name = path.name.lower()
            if suffix in FONT_EXT:
                kind = "font"
            elif "logo" in name or "brand" in name or "wordmark" in name:
                kind = "logo"
            elif "favicon" in name or "apple-touch" in name:
                kind = "favicon"
            elif suffix == ".svg" and (in_asset_dir or "icon" in rel.lower()):
                kind = "icon"
            elif suffix in IMG_EXT and in_asset_dir:
                kind = "image"
            else:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > 4 * 1024 * 1024:
                continue
            self.ds.assets.append(Asset(kind=kind, url=rel, path=None, note=f"{size // 1024} KB"))

        # Copia para a pasta de saída.
        copied = 0
        for asset in self.ds.assets:
            src = self.root / asset.url
            if not src.exists():
                continue
            sub = {"logo": "logo", "icon": "icons", "favicon": "icons", "font": "fonts"}.get(
                asset.kind, "images"
            )
            dest = self.out_dir / "assets" / sub / src.name
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(src.read_bytes())
                asset.path = str(dest.relative_to(self.out_dir))
                if asset.kind in ("logo", "icon") and src.suffix.lower() == ".svg" and dest.stat().st_size < 60_000:
                    asset.inline_svg = src.read_text(encoding="utf-8", errors="ignore")
                copied += 1
            except OSError:
                continue
        if copied:
            self.rep.step(f"{copied} asset(s) copiados")

    # ============================================================== agregação
    def _aggregate(self) -> None:
        ds = self.ds

        totals: Counter = Counter()
        props_by_hex: dict[str, dict[str, int]] = {}
        for prop, counter in self.colors_by_prop.items():
            for value, count in counter.items():
                rgba = colormod.parse_color(value)
                if rgba is None:
                    continue
                hexv = colormod.to_hex(rgba)
                totals[hexv] += count
                props_by_hex.setdefault(hexv, {})
                props_by_hex[hexv][prop] = props_by_hex[hexv].get(prop, 0) + count

        clusters = colormod.cluster_colors(
            [(h, c) for h, c in totals.items()], threshold=0.018, properties=props_by_hex
        )[:80]

        # Sinais para a classificação: nomes de token são o melhor indício aqui.
        accent_hints: list[tuple[Any, int]] = []
        for name, token in {**self.named.get("colors", {}), **self.named.get("cssVars", {})}.items():
            rgba = colormod.parse_color(token.value)
            if rgba is None:
                continue
            lname = name.lower()
            if any(k in lname for k in ("primary", "brand", "accent", "action")):
                accent_hints.append((rgba, 100))
            elif "link" in lname:
                accent_hints.append((rgba, 40))

        body_bg = None
        body_text = None
        for name, token in {**self.named.get("cssVars", {}), **self.named.get("colors", {})}.items():
            lname = name.lower()
            rgba = colormod.parse_color(token.value)
            if rgba is None:
                continue
            if body_bg is None and any(
                k in lname for k in ("background", "-bg", "bg-", "surface-base", "canvas")
            ):
                body_bg = rgba
            if body_text is None and lname.startswith(("text", "foreground", "fg", "color-text")):
                body_text = rgba

        classification = classify.classify_colors(
            clusters,
            body_background=body_bg,
            body_text=body_text,
            accent_hints=accent_hints,
        )
        ds.colors = _repo_colors_payload(clusters, classification, self.provenance)
        ds.colors["named"] = {
            name: token.value for name, token in sorted(self.named.get("colors", {}).items())
        }

        families = typography.rank_families(self.font_stacks.items())
        ds.typography = {
            "families": families,
            "scale": _type_scale_from_named(self.named.get("fontSize", {}), families),
            "font_faces": [f.to_dict() for f in self.font_faces.values()],
            "sizes": scales.infer_scale(
                self.font_sizes, max_items=12, min_value=8, max_value=200, min_share=0.0
            ),
            "weights": sorted(
                {int(v) for v in self.font_weights if str(v).isdigit() and 100 <= int(v) <= 900}
            ),
            "named": {
                group: {n: t.value for n, t in sorted(self.named.get(group, {}).items())}
                for group in ("fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing")
                if self.named.get(group)
            },
        }

        spacing_named = self.named.get("spacing", {})
        spacing_scale = scales.infer_scale(
            self.spacing, max_items=16, max_value=400, min_share=0.0 if spacing_named else 0.004
        )
        ds.spacing = {
            "scale": spacing_scale,
            "base_unit": scales.detect_base_unit(spacing_scale),
            "named": (
                {n: t.value for n, t in sorted(spacing_named.items())}
                if spacing_named
                else scales.name_spacing_steps(spacing_scale)
            ),
        }

        radii_named = self.named.get("radii", {})
        radii_scale = scales.infer_scale(self.radii, max_items=10, max_value=200, min_share=0.0)
        if any("9999" in str(t.value) or "50%" in str(t.value) for t in radii_named.values()):
            radii_scale = sorted(set(radii_scale + [9999.0]))
        ds.radii = {
            "scale": radii_scale,
            "named": (
                {n: t.value for n, t in sorted(radii_named.items())}
                if radii_named
                else scales.name_size_steps(radii_scale)
            ),
        }

        shadow_named = self.named.get("shadows", {})
        if shadow_named:
            ds.shadows = [
                {"name": n, "value": t.value, "count": DECLARED_WEIGHT}
                for n, t in shadow_named.items()
            ]
        else:
            ds.shadows = [
                {"value": v, "count": c}
                for v, c in scales.infer_string_scale(
                    self.shadows, max_items=8, sort_key=scales.shadow_weight
                )
            ]

        ds.borders = {
            "widths": scales.infer_scale(
                self.border_widths, max_items=6, max_value=20, min_share=0.0
            )
        }
        bps = scales.infer_breakpoints(self.media_queries)
        if self.breakpoint_values:
            bps = sorted(set(bps) | set(self.breakpoint_values))
        ds.breakpoints = bps
        if self.named.get("breakpoints"):
            ds.raw["named_breakpoints"] = {
                n: t.value for n, t in self.named["breakpoints"].items()
            }
        ds.containers = scales.infer_scale(
            self.containers, max_items=8, min_value=200, max_value=2400, min_share=0.0
        )
        ds.z_index = sorted({int(v) for v in self.z_index if str(v).lstrip("-").isdigit()})[:12]
        ds.motion = {
            "durations": [
                v for v, _ in scales.infer_string_scale(self.durations, max_items=6, sort_key=scales.duration_ms, normalize=scales.normalize_duration)
            ],
            "easings": [v for v, _ in scales.infer_string_scale(self.easings, max_items=6)],
        }
        ds.opacity = sorted(
            {round(float(v), 2) for v in self.opacity if _is_number(v) and 0 < float(v) <= 1}
        )[:10]
        ds.css_variables = self.css_vars

        ds.raw["named_tokens"] = {
            group: {n: {"value": t.value, "source": t.source} for n, t in sorted(tokens.items())}
            for group, tokens in self.named.items()
        }
        ds.raw["provenance"] = {h: sorted(v) for h, v in sorted(self.provenance.items())}
        ds.raw["frequencies"] = {
            "colors_by_prop": {k: dict(v.most_common(60)) for k, v in self.colors_by_prop.items()},
            "spacing": dict(self.spacing.most_common(60)),
            "radii": dict(self.radii.most_common(30)),
            "shadows": dict(self.shadows.most_common(20)),
            "font_stacks": dict(self.font_stacks.most_common(30)),
        }
        ds.raw["media_queries"] = sorted(set(self.media_queries))[:120]
        ds.raw["sources"] = sorted(set(self.sources))
        ds.raw["css_errors"] = self.css_facts.errors[:20]

        # Mesma leitura do modo url. Sem navegador não há pares de contraste
        # medidos nem componentes, então essas verificações ficam de fora em vez
        # de virarem nota inventada.
        ds.context = report.build_context(
            ds, class_tokens={}, attr_hints={}, site_origin=""
        )
        ds.diagnostics = report.build_diagnostics(
            ds,
            spacing_frequencies=dict(self.spacing),
            source_texts=self.source_texts,
        )


# ------------------------------------------------------------------ helpers
def _repo_colors_payload(clusters, classification, provenance) -> dict[str, Any]:
    return {
        "theme": classify.theme_pair(classification),
        "clusters": [
            {
                "hex": c.hex,
                "value": c.css,
                "count": c.count,
                "properties": c.properties,
                "oklch": [round(x, 4) for x in c.oklch],
                "sources": sorted(provenance.get(c.hex, []))[:6],
            }
            for c in clusters
        ],
        "roles": {
            role: {
                "value": sc.cluster.css,
                "hex": sc.cluster.hex,
                "count": sc.cluster.count,
                "reason": sc.reason,
            }
            for role, sc in classification.roles.items()
        },
        "neutrals": [
            {"hex": c.hex, "value": c.css, "count": c.count, "lightness": round(c.oklch[0], 3)}
            for c in classification.neutrals[:14]
        ],
        "accents": [
            {"hex": c.hex, "value": c.css, "count": c.count, "hue": round(c.oklch[2], 1)}
            for c in classification.accents[:14]
        ],
    }


def _type_scale_from_named(font_sizes: dict[str, NamedToken], families: list[dict]) -> list[dict]:
    family = families[0]["stack"] if families else ""
    out = []
    for name, token in font_sizes.items():
        px = scales.parse_length(token.value)
        if px is None:
            continue
        out.append(
            {
                "name": name,
                "fontSize": px,
                "fontWeight": "400",
                "lineHeight": "normal",
                "letterSpacing": "normal",
                "fontFamily": family,
                "textTransform": "none",
                "count": 1,
                "sample": "",
            }
        )
    out.sort(key=lambda t: -t["fontSize"])
    return out


def _walk_token_json(node: Any, prefix: str = "") -> Iterable[tuple[str, str, str | None]]:
    """Percorre JSON de tokens (DTCG, Style Dictionary, Figma Tokens)."""
    if not isinstance(node, dict):
        return
    if "$value" in node or "value" in node:
        value = node.get("$value", node.get("value"))
        ttype = node.get("$type", node.get("type"))
        if isinstance(value, (str, int, float)):
            yield (prefix, str(value), ttype if isinstance(ttype, str) else None)
        elif isinstance(value, dict):
            for key, sub in value.items():
                if isinstance(sub, (str, int, float)):
                    yield (f"{prefix}-{key}", str(sub), ttype if isinstance(ttype, str) else None)
        return
    for key, sub in node.items():
        if key.startswith("$"):
            continue
        name = f"{prefix}-{key}" if prefix else str(key)
        if isinstance(sub, dict):
            yield from _walk_token_json(sub, name)
        elif isinstance(sub, (str, int, float)):
            yield (name, str(sub), None)


def _token_group(name: str, value: Any, ttype: str | None) -> str | None:
    """Classifica um token solto pelo tipo declarado, pelo nome ou pelo valor."""
    lname = str(name).lower()
    sval = str(value).strip() if not isinstance(value, list) else " ".join(map(str, value))
    t = (ttype or "").lower()

    if t in ("color", "colour") or colormod.parse_color(sval) is not None:
        if not re.match(r"^-?\d+(\.\d+)?$", sval):
            return "colors"
    if t in ("fontfamilies", "fontfamily") or "fontfamily" in lname.replace("-", "") or "font-family" in lname:
        return "fontFamily"
    # `--font-heading: 'Zodiak', Georgia, serif` — stack tipográfica sem tipo declarado.
    if re.search(r"\b(sans-serif|serif|monospace|system-ui|cursive)\s*$", sval) and (
        "font" in lname or "," in sval
    ):
        return "fontFamily"
    if t in ("fontsizes", "fontsize", "dimension") and ("font" in lname or "text" in lname):
        return "fontSize"
    if "fontsize" in lname.replace("-", "") or lname.startswith("text-") and re.search(r"\d", sval):
        return "fontSize"
    if t in ("fontweights", "fontweight") or "fontweight" in lname.replace("-", ""):
        return "fontWeight"
    if "letterspacing" in lname.replace("-", ""):
        return "letterSpacing"
    if "lineheight" in lname.replace("-", ""):
        return "lineHeight"
    if t == "boxshadow" or "shadow" in lname:
        return "shadows"
    if "radius" in lname or "radii" in lname or "rounded" in lname:
        return "radii"
    if "breakpoint" in lname or "screen" in lname or lname.startswith("media"):
        return "breakpoints"
    if "duration" in lname or "transition" in lname and re.search(r"\d+(ms|s)\b", sval):
        return "durations"
    if "easing" in lname or "timing" in lname or "cubic-bezier" in sval:
        return "easings"
    if "zindex" in lname.replace("-", "") or lname.startswith("z-"):
        return "zIndex"
    if "opacity" in lname:
        return "opacity"
    if "border" in lname and "width" in lname:
        return "borderWidth"
    if any(k in lname for k in ("spacing", "space", "gap", "size", "padding", "margin")) and re.search(
        r"^\d*\.?\d+(px|rem|em)?$", sval
    ):
        return "spacing"
    if "container" in lname or "maxwidth" in lname.replace("-", ""):
        return "containers"
    return None


def _jsonable(value: Any) -> Any:
    if isinstance(value, JSRaw):
        return {"__unresolved__": value.text[:120]}
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _is_number(v: Any) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False
