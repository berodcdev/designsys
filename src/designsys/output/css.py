"""Geração de variables.css — todos os tokens como CSS custom properties."""

from __future__ import annotations

from ..analysis.color import scale_name
from ..analysis.typography import name_font_sizes
from ..models import DesignSystem
from .tokens import token_name


def _section(title: str) -> str:
    return f"\n  /* {title} */\n"


def build_variables_css(ds: DesignSystem) -> str:
    lines: list[str] = []
    lines.append("/*")
    lines.append(f" * Design tokens de {ds.display_target}")
    lines.append(f" * Gerado por designsys em {ds.generated_at}")
    lines.append(" *")
    lines.append(" * Cole no seu projeto e use com var(--color-primary), var(--spacing-4)...")
    lines.append(" */\n")

    font_faces = _font_face_rules(ds)
    if font_faces:
        lines.append(font_faces)

    body: list[str] = [":root {"]

    roles = ds.colors.get("roles") or {}
    if roles:
        body.append(_section("cores semânticas").rstrip("\n"))
        for role, info in roles.items():
            comment = f"  /* {info['reason']} */" if info.get("reason") else ""
            body.append(f"  --color-{token_name(role)}: {info['value']};{comment}")

    named = ds.colors.get("named") or {}
    if named:
        body.append(_section("paleta nomeada (do código-fonte)").rstrip("\n"))
        for name, value in named.items():
            body.append(f"  --color-{token_name(name)}: {value};")

    neutrals = ds.colors.get("neutrals") or []
    if neutrals:
        body.append(_section("escala de cinzas (claro → escuro)").rstrip("\n"))
        for index, entry in enumerate(neutrals):
            body.append(f"  --color-neutral-{scale_name(index, len(neutrals))}: {entry['value']};")

    accents = ds.colors.get("accents") or []
    if accents:
        body.append(_section("cores de destaque").rstrip("\n"))
        for index, entry in enumerate(accents[:10], start=1):
            body.append(f"  --color-accent-{index}: {entry['value']};")

    spacing_named = ds.spacing.get("named") or {}
    if spacing_named:
        body.append(_section("espaçamento").rstrip("\n"))
        for name, value in spacing_named.items():
            body.append(f"  --spacing-{token_name(name)}: {_len(value)};")

    radii_named = ds.radii.get("named") or {}
    if radii_named:
        body.append(_section("border-radius").rstrip("\n"))
        for name, value in radii_named.items():
            body.append(f"  --radius-{token_name(name)}: {_len(value)};")

    if ds.shadows:
        body.append(_section("sombras").rstrip("\n"))
        for index, shadow in enumerate(ds.shadows):
            name = token_name(shadow.get("name") or _shadow_name(index))
            body.append(f"  --shadow-{name}: {shadow['value']};")

    typo = ds.typography or {}
    families = typo.get("families") or []
    if families:
        body.append(_section("famílias tipográficas").rstrip("\n"))
        for index, fam in enumerate(families[:5]):
            key = "base" if index == 0 else token_name(fam["family"])
            body.append(f"  --font-{key}: {fam.get('stack') or fam['family']};")

    named_sizes = (typo.get("named") or {}).get("fontSize") or {}
    sizes = named_sizes or name_font_sizes(typo.get("sizes") or [])
    if sizes:
        body.append(_section("tamanhos de fonte").rstrip("\n"))
        for name, value in sizes.items():
            body.append(f"  --text-{token_name(name)}: {_len(value)};")

    if typo.get("weights"):
        body.append(_section("pesos").rstrip("\n"))
        for weight in typo["weights"]:
            body.append(f"  --font-weight-{weight}: {weight};")

    if typo.get("scale"):
        body.append(_section("estilos de texto").rstrip("\n"))
        for style in typo["scale"]:
            name = token_name(style["name"])
            body.append(f"  --text-{name}-size: {_len(style['fontSize'])};")
            body.append(f"  --text-{name}-weight: {style['fontWeight']};")
            if style.get("lineHeight") and style["lineHeight"] != "normal":
                body.append(f"  --text-{name}-leading: {style['lineHeight']};")
            if style.get("letterSpacing") and style["letterSpacing"] != "normal":
                body.append(f"  --text-{name}-tracking: {style['letterSpacing']};")

    if ds.borders.get("widths"):
        body.append(_section("larguras de borda").rstrip("\n"))
        for width in ds.borders["widths"]:
            body.append(f"  --border-{token_name(f'{width:g}')}: {_len(width)};")

    if ds.breakpoints:
        body.append(_section("breakpoints (referência — media query não aceita var())").rstrip("\n"))
        names = ["sm", "md", "lg", "xl", "2xl", "3xl", "4xl", "5xl"]
        for index, bp in enumerate(ds.breakpoints):
            key = names[index] if index < len(names) else f"bp{index}"
            body.append(f"  --breakpoint-{key}: {bp}px;")

    if ds.containers:
        body.append(_section("larguras de container").rstrip("\n"))
        for value in ds.containers:
            body.append(f"  --container-{token_name(f'{value:g}')}: {_len(value)};")

    motion = ds.motion or {}
    if motion.get("durations") or motion.get("easings"):
        body.append(_section("movimento").rstrip("\n"))
        for index, duration in enumerate(motion.get("durations") or []):
            body.append(f"  --duration-{index + 1}: {duration};")
        for index, easing in enumerate(motion.get("easings") or []):
            body.append(f"  --ease-{index + 1}: {easing};")

    if ds.z_index:
        body.append(_section("z-index").rstrip("\n"))
        for z in ds.z_index:
            body.append(f"  --z-{token_name(str(z))}: {z};")

    if ds.opacity:
        body.append(_section("opacidades").rstrip("\n"))
        for value in ds.opacity:
            body.append(f"  --opacity-{int(value * 100)}: {value};")

    body.append("}")
    lines.append("\n".join(body))

    dark = _dark_block(ds)
    if dark:
        lines.append(dark)

    fluid = _fluid_block(ds)
    if fluid:
        lines.append(fluid)

    lines.append("")
    return "\n".join(lines)


def _dark_block(ds: DesignSystem) -> str:
    """Tema escuro por preferência do sistema e por atributo/classe.

    Os dois seletores existem porque os sites usam ambos: `prefers-color-scheme`
    atende quem não tem toggle, e `[data-theme]`/`.dark` atende quem tem.
    """
    pares = (ds.themes or {}).get("pairs") or {}
    escuros = {
        papel: valores["dark"]
        for papel, valores in pares.items()
        if valores.get("dark") and valores.get("dark") != valores.get("light")
    }
    if not escuros:
        return ""

    declaracoes = [f"    --color-{token_name(papel)}: {valor};" for papel, valor in escuros.items()]
    corpo = "\n".join(declaracoes)
    return (
        "\n/* ---------------------------------------------------------------\n"
        " * Tema escuro capturado do site.\n"
        " * --------------------------------------------------------------- */\n"
        "@media (prefers-color-scheme: dark) {\n"
        "  :root {\n" + corpo + "\n  }\n}\n\n"
        '[data-theme="dark"],\n'
        ".dark {\n" + corpo.replace("    --", "  --") + "\n}\n"
    )


def _fluid_block(ds: DesignSystem) -> str:
    """Tamanhos que mudam entre telas viram `clamp()` a partir dos extremos medidos."""
    fluidos = (ds.responsive or {}).get("fluid") or {}
    if not fluidos:
        return ""

    larguras = (ds.responsive or {}).get("widths") or {}
    linhas: list[str] = []
    for papel, tamanhos in fluidos.items():
        if len(tamanhos) < 2:
            continue
        menor_tela = min(tamanhos, key=lambda t: larguras.get(t, 1440))
        maior_tela = max(tamanhos, key=lambda t: larguras.get(t, 1440))
        minimo, maximo = tamanhos[menor_tela], tamanhos[maior_tela]
        if maximo <= minimo:
            continue
        largura_min = larguras.get(menor_tela, 390)
        largura_max = larguras.get(maior_tela, 1440)
        # Reta que passa pelos dois pontos medidos, escrita em vw + rem.
        inclinacao = (maximo - minimo) / max(1, largura_max - largura_min)
        intercepto = minimo - inclinacao * largura_min
        linhas.append(
            f"  --text-{token_name(papel)}-fluid: clamp("
            f"{minimo:g}px, {intercepto / 16:.3f}rem + {inclinacao * 100:.2f}vw, {maximo:g}px);"
        )
    if not linhas:
        return ""
    return (
        "\n/* ---------------------------------------------------------------\n"
        " * Escala fluida, interpolada entre os tamanhos medidos em cada tela.\n"
        " * --------------------------------------------------------------- */\n"
        ":root {\n" + "\n".join(linhas) + "\n}\n"
    )


def _font_face_rules(ds: DesignSystem) -> str:
    faces = (ds.typography or {}).get("font_faces") or []
    rules: list[str] = []
    for face in faces:
        local = face.get("localPath")
        urls = face.get("urls") or []
        src_parts = []
        if local:
            fmt = "woff2" if local.endswith(".woff2") else "woff" if local.endswith(".woff") else None
            src_parts.append(f'url("{local}")' + (f' format("{fmt}")' if fmt else ""))
        for url in urls[:2]:
            fmt = "woff2" if url.endswith(".woff2") else "woff" if url.endswith(".woff") else None
            src_parts.append(f'url("{url}")' + (f' format("{fmt}")' if fmt else ""))
        if not src_parts:
            continue
        rule = [
            "@font-face {",
            f"  font-family: \"{face['family']}\";",
            f"  font-style: {face.get('style') or 'normal'};",
            f"  font-weight: {face.get('weight') or '400'};",
        ]
        if face.get("display"):
            rule.append(f"  font-display: {face['display']};")
        if face.get("unicodeRange"):
            rule.append(f"  unicode-range: {face['unicodeRange']};")
        rule.append("  src: " + ",\n       ".join(src_parts) + ";")
        rule.append("}")
        rules.append("\n".join(rule))
    if not rules:
        return ""
    header = "/* @font-face capturados do site (URLs remotas + cópias em assets/fonts/) */\n"
    return header + "\n\n".join(rules) + "\n"


def _len(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{value:g}px"
    return str(value)


def _shadow_name(index: int) -> str:
    names = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl", "inner"]
    return names[index] if index < len(names) else f"s{index}"
