"""Escreve a pasta de resultado completa."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import DesignSystem
from .agentdoc import build_agent_doc
from .css import build_variables_css
from .sprite import build_sprite, usage_snippet
from .tokensstudio import build_tokens_studio
from .styleguide import build_style_guide
from .tailwind import build_tailwind_config
from .tokens import build_dtcg


def write_pdf(ds: DesignSystem, out_dir: Path, name: str = "design-system.pdf") -> Path:
    """Gera o documento em PDF. Levanta PdfError se o Chromium não colaborar."""
    from .pdfdoc import build_print_html
    from .pdfrender import render_pdf

    html_text = build_print_html(ds)
    return render_pdf(
        html_text,
        out_dir / name,
        base_dir=out_dir,
        title=f"Design system — {ds.name}",
    )


def write_all(ds: DesignSystem, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    def write(name: str, content: str) -> None:
        path = out_dir / name
        path.write_text(content, encoding="utf-8")
        written[name] = path

    write("tokens.json", json.dumps(build_dtcg(ds), indent=2, ensure_ascii=False) + "\n")
    write("variables.css", build_variables_css(ds))
    write("tailwind.config.js", build_tailwind_config(ds))
    write("style-guide.html", build_style_guide(ds))
    write(
        "components.json",
        json.dumps(
            {
                "source": ds.display_target,
                "mode": ds.mode,
                "generatedAt": ds.generated_at,
                "components": [c.to_dict() for c in ds.components],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
    )
    write(
        "raw.json",
        json.dumps(
            {**ds.to_dict(), "raw": _jsonable(ds.raw)},
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
    )
    write("DESIGN-SYSTEM.md", build_agent_doc(ds))
    write(
        "tokens.studio.json",
        json.dumps(build_tokens_studio(ds), indent=2, ensure_ascii=False) + "\n",
    )

    sprite, simbolos = build_sprite(ds.assets)
    if sprite:
        destino = out_dir / "assets" / "icons" / "sprite.svg"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(sprite, encoding="utf-8")
        written["assets/icons/sprite.svg"] = destino
        ds.raw["sprite"] = {"path": "assets/icons/sprite.svg", "symbols": simbolos}

    write("README.md", build_readme(ds))
    return written


def build_readme(ds: DesignSystem) -> str:
    counts = ds.counts()
    roles = ds.colors.get("roles") or {}
    families = (ds.typography or {}).get("families") or []

    lines: list[str] = []
    lines.append(f"# Design system — {ds.name}")
    lines.append("")
    origin = "site ao vivo" if ds.mode == "url" else "repositório local"
    lines.append(f"Extraído de **{ds.display_target}** ({origin}) em {ds.generated_at[:19].replace('T', ' ')}.")
    lines.append("")

    lines.append("## O que foi extraído")
    lines.append("")
    lines.append("| item | quantidade |")
    lines.append("| --- | ---: |")
    for key, value in counts.items():
        if value:
            lines.append(f"| {key} | {value} |")
    lines.append("")

    if roles:
        lines.append("## Cores semânticas")
        lines.append("")
        lines.append("| papel | valor | por quê |")
        lines.append("| --- | --- | --- |")
        for role, info in roles.items():
            lines.append(f"| `{role}` | `{info['value']}` | {info.get('reason', '')} |")
        lines.append("")

    if families:
        lines.append("## Tipografia")
        lines.append("")
        for fam in families[:5]:
            lines.append(f"- **{fam['family']}** — {fam['count']} usos · `{fam.get('stack', '')}`")
        lines.append("")

    if ds.spacing.get("scale"):
        unit = ds.spacing.get("base_unit")
        scale = ", ".join(f"{v:g}px" for v in ds.spacing["scale"])
        lines.append("## Espaçamento")
        lines.append("")
        lines.append(f"Escala: {scale}")
        if unit:
            lines.append("")
            lines.append(f"Grade base detectada: **{unit:g}px**.")
        lines.append("")

    if ds.breakpoints:
        lines.append("## Breakpoints")
        lines.append("")
        lines.append(", ".join(f"{bp}px" for bp in ds.breakpoints))
        lines.append("")

    lines.append("## Arquivos")
    lines.append("")
    lines.append("| arquivo | para que serve |")
    lines.append("| --- | --- |")
    lines.append("| `design-system.pdf` | **O documento completo em PDF**, formatado para leitura e circulação: capa, sumário, paleta, tipografia, escalas, componentes, assets e apêndice. Abra com `designsys open .`. |")
    lines.append("| `style-guide.html` | A mesma coisa em versão navegável — clique numa cor para copiar o hex. |")
    lines.append("| `tokens.json` | Design tokens no formato [W3C DTCG](https://tr.designtokens.org/format/) (`$value`/`$type`). Entrada para Style Dictionary, Tokens Studio etc. |")
    lines.append("| `variables.css` | Os mesmos tokens como CSS custom properties. Importe e use `var(--color-primary)`. |")
    lines.append("| `tailwind.config.js` | `theme.extend` pronto para colar num projeto Tailwind. |")
    lines.append("| `components.json` | Estilos computados completos dos componentes detectados, incluindo `:hover` e `:focus`. |")
    lines.append("| `DESIGN-SYSTEM.md` | As regras do sistema em forma acionável, escritas para um agente de código (Claude Code, Cursor) seguir dentro do seu projeto. |")
    lines.append("| `tokens.studio.json` | Mesmos tokens no formato do plugin Tokens Studio, para levar ao Figma (claro e escuro como *modes*). |")
    lines.append("| `raw.json` | Dump bruto com frequências e procedência de cada valor — para auditar qualquer decisão desta extração. |")
    if ds.mode == "url":
        lines.append("| `assets/` | Logo, ícones, fontes e imagens baixados. |")
        lines.append("| `screenshots/` | Screenshot full-page de cada página visitada. |")
    else:
        lines.append("| `assets/` | Logos, ícones e fontes copiados do repositório. |")
    lines.append("")

    lines.append("## Como usar")
    lines.append("")
    lines.append("```bash")
    lines.append("# guia visual")
    lines.append("open style-guide.html")
    lines.append("")
    lines.append("# CSS vars num projeto qualquer")
    lines.append('cp variables.css seu-projeto/src/styles/ && echo "@import \'./styles/variables.css\';"')
    lines.append("")
    lines.append("# Tailwind")
    lines.append("cp tailwind.config.js seu-projeto/  # ou copie só o bloco theme.extend")
    lines.append("```")
    lines.append("")

    if ds.pages:
        lines.append("## Páginas visitadas")
        lines.append("")
        for page in ds.pages:
            lines.append(f"- {page['url']} — {page.get('elements', 0)} elementos, {page.get('rules', 0)} regras CSS")
        lines.append("")

    if ds.files_scanned:
        lines.append("## Arquivos lidos")
        lines.append("")
        for path in ds.files_scanned[:40]:
            lines.append(f"- `{path}`")
        if len(ds.files_scanned) > 40:
            lines.append(f"- … e mais {len(ds.files_scanned) - 40}")
        lines.append("")

    login = (ds.raw or {}).get("login")
    if login:
        metodos = {
            "session": "sessão salva de uma execução anterior",
            "auto": "usuário e senha",
            "otp": "código de uso único (OTP)",
            "magic-link": "link de acesso enviado por e-mail",
            "manual": "login manual no navegador",
            "none": "sem autenticação",
        }
        metodo = metodos.get(login.get("method", ""), login.get("method", ""))
        status = "sucesso" if login.get("ok") else "falhou"
        lines.append("## Autenticação")
        lines.append("")
        lines.append(f"Login via **{metodo}** — {status}: {login.get('detail', '')}")
        lines.append("")
        lines.append(
            "> Nenhuma senha foi gravada em disco. O que persiste é apenas o perfil do Chromium "
            "em `~/.designsys/profiles/<domínio>/`, que guarda os **cookies de sessão** — trate essa "
            "pasta como material sensível e apague-a quando não precisar mais "
            "(`rm -rf ~/.designsys/profiles/<domínio>`)."
        )
        lines.append("")

    if ds.warnings:
        lines.append("## Avisos")
        lines.append("")
        for warning in ds.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Gerado por `designsys`.")
    lines.append("")
    return "\n".join(lines)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
