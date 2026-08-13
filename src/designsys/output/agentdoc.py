"""DESIGN-SYSTEM.md — as regras do sistema em forma acionável.

O destinatário é um agente de código (Claude Code, Cursor) trabalhando dentro de
um projeto: o arquivo precisa caber num contexto sem desperdício, dizer o que
usar e o que não fazer, e trazer valores concretos em vez de descrições. Tudo
que ele afirma sai da extração — nada de conselho genérico de design.
"""

from __future__ import annotations

from typing import Any

from ..models import DesignSystem

MAX_COLORS = 24
MAX_TEXT_STYLES = 10


def build_agent_doc(ds: DesignSystem) -> str:
    linhas: list[str] = []
    a = linhas.append

    a(f"# Design system — {ds.display_target}")
    a("")
    a(
        "Regras extraídas automaticamente por `designsys`. Ao escrever ou alterar "
        "interface neste projeto, **siga os valores abaixo**: eles são o sistema que "
        "já existe, não sugestões."
    )
    a("")

    _colors(ds, a)
    _typography(ds, a)
    _spacing(ds, a)
    _components(ds, a)
    _rules(ds, a)
    _accessibility(ds, a)

    a("---")
    a("")
    a(
        f"Gerado por `designsys` em {ds.generated_at[:10]} a partir de "
        f"{'um site ao vivo' if ds.mode == 'url' else 'um repositório'}. "
        "Os arquivos `tokens.json`, `variables.css` e `tailwind.config.js` ao lado "
        "contêm os mesmos valores em formato consumível."
    )
    a("")
    return "\n".join(linhas)


def _colors(ds: DesignSystem, a) -> None:
    papeis = ds.colors.get("roles") or {}
    if not papeis:
        return
    nomes = (ds.context or {}).get("colorNames") or {}

    a("## Cores")
    a("")
    a("Use **sempre** por papel, nunca por valor literal:")
    a("")
    a("| papel | valor | quando usar |")
    a("| --- | --- | --- |")
    uso = {
        "primary": "ação principal, CTA, links de destaque",
        "secondary": "ação secundária, apoio",
        "background": "fundo da página",
        "surface": "cartões, painéis, áreas elevadas",
        "surface-alt": "faixas alternadas, fundo sutil",
        "text": "texto principal",
        "text-muted": "texto secundário, legendas",
        "border": "divisórias e contornos",
        "success": "confirmação, estado positivo",
        "warning": "atenção, estado que pede cuidado",
        "error": "erro, destruição, estado negativo",
        "info": "informação neutra",
    }
    for papel, info in papeis.items():
        escuro = ((ds.themes.get("pairs") or {}).get(papel) or {}).get("dark")
        valor = f"`{info['value']}`" + (f" / escuro `{escuro}`" if escuro else "")
        a(f"| `{papel}` | {valor} | {uso.get(papel, '—')} |")
    a("")

    neutros = ds.colors.get("neutrals") or []
    if neutros:
        escala = " · ".join(f"`{n['hex']}`" for n in neutros[:MAX_COLORS])
        a(f"**Escala neutra** (clara → escura): {escala}")
        a("")

    if nomes:
        amostra = [f"`{hexv}` ({nome})" for hexv, nome in list(nomes.items())[:10]]
        a(f"Nomes em uso: {', '.join(amostra)}.")
        a("")


def _typography(ds: DesignSystem, a) -> None:
    typo = ds.typography or {}
    familias = typo.get("families") or []
    escala = typo.get("scale") or []
    if not familias and not escala:
        return

    a("## Tipografia")
    a("")
    if familias:
        principal = familias[0]
        a(f"Família principal: `{principal.get('stack') or principal['family']}`")
        reais = [f for f in familias if not f.get("generic")]
        outras = [f["family"] for f in reais[1:3]]
        if outras:
            a("")
            a(
                f"Também em uso: {', '.join(outras)}. "
                f"São {len(reais)} famílias no total — não introduza outra."
            )
        a("")

    if escala:
        a("| papel | tamanho | peso | entrelinha |")
        a("| --- | --- | --- | --- |")
        for estilo in escala[:MAX_TEXT_STYLES]:
            a(
                f"| `{estilo['name']}` | {estilo['fontSize']:g}px | "
                f"{estilo.get('fontWeight', 400)} | {estilo.get('lineHeight', 'normal')} |"
            )
        a("")

    fluidos = (ds.responsive or {}).get("fluid") or {}
    if fluidos:
        a("Tamanhos que mudam por breakpoint:")
        a("")
        for papel, tamanhos in list(fluidos.items())[:5]:
            trilha = " → ".join(
                f"{tela} {valor:g}px" for tela, valor in sorted(tamanhos.items(), key=lambda kv: kv[1])
            )
            a(f"- `{papel}`: {trilha}")
        a("")


def _spacing(ds: DesignSystem, a) -> None:
    escala = ds.spacing.get("scale") or []
    if not escala:
        return
    unidade = ds.spacing.get("base_unit")

    a("## Espaçamento e forma")
    a("")
    a(f"Escala: {' · '.join(f'`{v:g}px`' for v in escala)}")
    if unidade:
        a("")
        a(f"Grade base **{unidade:g}px** — todo espaçamento novo deve ser múltiplo dela.")
    a("")

    raios = ds.radii.get("named") or {}
    if raios:
        itens = " · ".join(
            f"`{nome}` {v:g}px" if isinstance(v, (int, float)) else f"`{nome}` {v}"
            for nome, v in raios.items()
        )
        a(f"Raios: {itens}")
        a("")
    if ds.shadows:
        a(f"Sombras disponíveis: {len(ds.shadows)} — use `--shadow-*` do variables.css, não invente.")
        a("")


def _components(ds: DesignSystem, a) -> None:
    componentes = {c.kind: c for c in ds.components}
    principal = componentes.get("button-primary")
    if principal is None:
        return

    a("## Componentes")
    a("")
    a("Botão primário, como está implementado hoje:")
    a("")
    a("```css")
    interessa = [
        "background-color", "color", "border-radius", "padding-top", "padding-right",
        "padding-bottom", "padding-left", "font-size", "font-weight", "border-top-width",
    ]
    for prop in interessa:
        valor = principal.base.get(prop)
        if valor:
            a(f"{prop}: {valor};")
    for estado, valores in principal.states().items():
        mudancas = {p: v for p, v in valores.items() if principal.base.get(p) not in (None, v)}
        relevantes = {
            p: v for p, v in mudancas.items()
            if p in ("background-color", "color", "box-shadow", "outline-width", "outline-color", "border-top-color")
        }
        if relevantes:
            a("")
            a(f"/* :{estado} */")
            for prop, valor in relevantes.items():
                a(f"{prop}: {valor};")
    a("```")
    a("")

    outros = [k for k in componentes if k != "button-primary"]
    if outros:
        a(f"Também capturados em `components.json`: {', '.join(f'`{k}`' for k in outros[:10])}.")
        a("")


def _rules(ds: DesignSystem, a) -> None:
    a("## Regras")
    a("")
    regras = [
        "Não escreva cor literal em componente novo — use `var(--color-*)` do `variables.css`.",
    ]
    unidade = ds.spacing.get("base_unit")
    if unidade:
        regras.append(
            f"Espaçamento sempre múltiplo de {unidade:g}px (meio degrau, {unidade / 2:g}px, é aceitável)."
        )
    if ds.radii.get("named"):
        regras.append("Raio de borda só entre os valores da escala acima.")
    familias = [f for f in (ds.typography.get("families") or []) if not f.get("generic")]
    if familias:
        regras.append(f"Tipografia limitada a {len(familias)} família(s): não adicione outra.")
    if ds.has_dark:
        regras.append(
            "Este sistema tem tema claro e escuro: toda cor nova precisa do par escuro."
        )
    if ds.breakpoints:
        pontos = ", ".join(f"{b}px" for b in ds.breakpoints[:6])
        regras.append(f"Breakpoints existentes: {pontos}. Não crie um novo.")
    regras.append(
        "Ao precisar de um valor que não existe aqui, adicione-o ao `tokens.json` "
        "antes de usar — e não em linha no componente."
    )
    for regra in regras:
        a(f"- {regra}")
    a("")


def _accessibility(ds: DesignSystem, a) -> None:
    diag = (ds.diagnostics or {}).get("accessibility") or {}
    if not diag:
        return
    falhas = diag.get("contrast") or []
    sem_foco = diag.get("focusMissing") or []
    if not falhas and not sem_foco:
        return

    a("## Acessibilidade — o que já está errado")
    a("")
    if falhas:
        a("Combinações abaixo do mínimo AA que **não devem ser repetidas**:")
        a("")
        for item in falhas[:6]:
            a(
                f"- `{item['fg']}` sobre `{item['bg']}` — {item['ratio']}:1 "
                f"(mínimo {item['required']}), {item['count']}× na página"
            )
        a("")
    if sem_foco:
        a(
            f"Sem indicação visível de foco: {', '.join(f'`{k}`' for k in sem_foco[:6])}. "
            "Todo controle novo precisa de `:focus-visible` perceptível."
        )
        a("")
