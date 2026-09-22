"""CLI do designsys."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import traceback
import webbrowser
from datetime import date
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import typer
from typer.core import TyperGroup
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from . import __version__
from .models import DesignSystem
from .util.report import Reporter

console = Console()
err_console = Console(stderr=True)

# Paleta do próprio menu — as mesmas famílias que a ferramenta extrai.
BANNER_COLORS = ["#533afd", "#0a2540", "#15be53", "#ffbb00", "#ff6118", "#425466"]

COMANDOS: list[tuple[str, str, str]] = [
    ("url", "<URL>", "Extrai de um site ao vivo — com JS renderizado e, se precisar, login."),
    ("repo", "[caminho]", "Extrai de um repositório local: Tailwind, CSS, temas JS, tokens."),
    ("open", "<pasta>", "Abre o PDF do resultado (ou o guia navegável com --html)."),
    ("pdf", "<pasta>", "Regera o design-system.pdf de uma pasta já extraída."),
    ("audit", "<pasta>", "Mostra o diagnóstico: acessibilidade, consistência, assinatura."),
    ("doctor", "", "Diagnostica e conserta o ambiente (Playwright, Chromium, rede)."),
]

ENTREGAVEIS: list[tuple[str, str]] = [
    ("design-system.pdf", "documento completo, com capa e sumário"),
    ("tokens.json", "design tokens no padrão W3C DTCG"),
    ("variables.css", "os mesmos tokens como CSS custom properties"),
    ("tailwind.config.js", "bloco theme.extend pronto para colar"),
    ("style-guide.html", "guia navegável, clique numa cor para copiar"),
    ("components.json", "estilos computados, com :hover, :focus e :active"),
    ("DESIGN-SYSTEM.md", "regras acionáveis para agentes de código seguirem"),
    ("tokens.studio.json", "para o plugin Tokens Studio, no Figma"),
    ("assets/ · screenshots/", "logo, ícones, fontes e capturas de tela"),
    ("raw.json", "frequências e procedência, para auditoria"),
]

# Exemplos agrupados pelo momento em que você usa cada um.
EXEMPLOS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "extrair",
        [
            ("designsys url stripe.com --pages 5", "site público, 5 páginas"),
            ("designsys url app.empresa.com --login", "SaaS atrás de login"),
            ("designsys url app.empresa.com --login --path /painel", "direto numa rota interna"),
            ("designsys repo ~/dev/meu-projeto", "um repositório local"),
        ],
    ),
    (
        "ajustar a extração",
        [
            ("designsys url x.com --pages 20 --exhaustive", "varre tudo, sem parar"),
            ("designsys url x.com --no-dark --no-viewports", "o essencial, mais rápido"),
            ("designsys url x.com --headed --no-assets", "navegador visível"),
        ],
    ),
    (
        "depois da extração",
        [
            ("designsys audit designsys-stripe.com-2026-08-12", "nota e ofensores"),
            ("designsys open designsys-stripe.com-2026-08-12", "abre o PDF gerado"),
            ("designsys pdf . --open", "regera o PDF, sem extrair"),
            ("designsys doctor --fix", "conserta o ambiente"),
        ],
    ),
]

# O que a ferramenta lê nos dados, além de listar tokens.
ALEM_DOS_TOKENS: list[tuple[str, str]] = [
    ("tema claro e escuro", "captura os dois quando existem e pareia papel a papel"),
    ("escala responsiva", "remede em mobile e tablet, e gera o clamp() correspondente"),
    ("diagnóstico", "contraste real, foco invisível, grade, tokens nunca usados"),
    ("assinatura visual", "densidade, forma, peso, saturação e temperatura"),
    ("contexto", "qual kit de UI, nome de cada cor, origem das fontes"),
]


CAMADAS_LOGIN: list[tuple[str, str]] = [
    ("sessão salva", "cookies e localStorage do domínio, reaproveitados"),
    ("usuário e senha", "inclusive fluxos em duas etapas"),
    ("código (OTP)", "pedido no terminal; a senha fica em branco"),
    ("magic link", "você cola o link do e-mail, ele abre nesta sessão"),
    ("manual", "captcha ou SSO: o navegador abre e espera você"),
]

ACCENT = "#7c6cff"

AUTOR = "dev@bernardorodc.com"
REPOSITORIO = "github.com/berodcdev/designsys"


def _gradiente(largura: int, char: str = "█") -> Text:
    """Barra em gradiente, interpolada em OKLab — a mesma engine dos tokens."""
    from coloraide import Color

    largura = max(largura, len(BANNER_COLORS))
    faixa = Text()
    trechos = len(BANNER_COLORS) - 1
    for i in range(largura):
        pos = i / max(1, largura - 1) * trechos
        indice = min(int(pos), trechos - 1)
        try:
            # `mix` devolve a cor NO espaço da interpolação: sem converter para
            # sRGB o to_string sai como "oklab(...)", que o Rich ignora calado.
            cor = (
                Color(BANNER_COLORS[indice])
                .mix(BANNER_COLORS[indice + 1], pos - indice, space="oklab")
                .convert("srgb")
                .fit("srgb")
            )
            faixa.append(char, style=cor.to_string(hex=True))
        except Exception:  # coloraide ausente ou cor fora do gamut
            faixa.append(char, style=BANNER_COLORS[indice])
    return faixa


def _secao(titulo: str, corpo: Any, *, nota: str = "", largura: int | None = None) -> None:
    from rich import box

    rotulo = Text()
    rotulo.append(titulo, style=f"bold {ACCENT}")
    if nota:
        rotulo.append(f" · {nota}", style="dim")
    console.print(
        Panel(
            corpo,
            title=rotulo,
            title_align="left",
            border_style="grey37",
            box=box.ROUNDED,
            padding=(1, 2),
            width=largura,
        )
    )
    console.print()


def render_main_help() -> None:
    """Menu principal — desenhado à mão, no lugar do help padrão do Typer."""
    from rich import box

    largura = min(console.width, 96)
    interno = largura - 6

    console.print()

    # ------------------------------------------------------------- banner
    cabecalho = Table.grid(expand=True)
    cabecalho.add_column(justify="left")
    cabecalho.add_column(justify="right")

    marca = Text()
    marca.append("designsys", style=f"bold {ACCENT}")
    nome_linha = Text()
    nome_linha.append_text(marca)
    cabecalho.add_row(nome_linha, Text(f"v{__version__}", style="dim"))

    creditos = Table.grid(expand=True)
    creditos.add_column(justify="left")
    creditos.add_column(justify="right")
    creditos.add_row(
        Text("desenvolvido por ", style="grey42").append(AUTOR, style=ACCENT),
        Text(REPOSITORIO, style="grey42"),
    )

    corpo = Table.grid()
    corpo.add_column()
    corpo.add_row(_gradiente(interno))
    corpo.add_row("")
    corpo.add_row(cabecalho)
    corpo.add_row(
        Text(
            "o design system completo de um site ao vivo — inclusive atrás de\n"
            "login — ou de um repositório de código local.",
            style="dim",
        )
    )
    corpo.add_row("")
    corpo.add_row(creditos)
    console.print(
        Panel(corpo, border_style="grey37", box=box.ROUNDED, padding=(1, 2), width=largura)
    )
    console.print()

    # ----------------------------------------------------------- comandos
    tabela = Table.grid(padding=(0, 2))
    tabela.add_column(style=f"bold {ACCENT}", no_wrap=True)
    tabela.add_column(style="grey58", no_wrap=True)
    tabela.add_column(overflow="fold")
    for nome, arg, desc in COMANDOS:
        # Text() literal: "[caminho]" seria lido como markup do Rich e sumiria.
        tabela.add_row(nome, Text(arg), desc)
    _secao("COMANDOS", tabela, largura=largura)

    # ------------------------------------------------------------- saídas
    saidas = Table.grid(padding=(0, 2))
    saidas.add_column(style="green", no_wrap=True)
    saidas.add_column(style="dim", overflow="fold")
    for arquivo, desc in ENTREGAVEIS:
        saidas.add_row(arquivo, desc)
    _secao("O QUE VOCÊ RECEBE", saidas, nota="uma pasta por extração", largura=largura)

    # ----------------------------------------------------------- exemplos
    exemplos = Table.grid(padding=(0, 2))
    exemplos.add_column(no_wrap=True)
    # Em terminal estreito o comentário some em vez de quebrar em quatro linhas.
    mais_longo = max(len(c) for _, itens in EXEMPLOS for c, _ in itens)
    sobra = largura - 6 - 2 - mais_longo - 2
    if sobra >= 20:
        exemplos.add_column(style="grey50", no_wrap=True, overflow="ellipsis", max_width=sobra)

    for indice, (grupo, itens) in enumerate(EXEMPLOS):
        if indice:
            exemplos.add_row("")
        exemplos.add_row(Text(grupo, style=f"bold {ACCENT}"))
        for comando, desc in itens:
            linha = Text("  $ ", style="grey42")
            linha.append(comando, style="white")
            if sobra >= 20:
                exemplos.add_row(linha, f"# {desc}")
            else:
                exemplos.add_row(linha)
    _secao("EXEMPLOS", exemplos, largura=largura)

    # ------------------------------------------------------ além dos tokens
    leitura = Table.grid(padding=(0, 2))
    leitura.add_column(style="green", no_wrap=True)
    leitura.add_column(style="dim", overflow="fold")
    for assunto, desc in ALEM_DOS_TOKENS:
        leitura.add_row(assunto, desc)
    _secao("ALÉM DOS TOKENS", leitura, nota="o que ele lê nos dados", largura=largura)

    # -------------------------------------------------------------- login
    camadas = Table.grid(padding=(0, 2))
    camadas.add_column(style=ACCENT, no_wrap=True)
    camadas.add_column(style="dim", overflow="fold")
    for camada, desc in CAMADAS_LOGIN:
        camadas.add_row(camada, desc)
    _secao("LOGIN", camadas, nota="da mais automática para a manual", largura=largura)

    # ------------------------------------------------------------- rodapé
    rodape = Table.grid(padding=(0, 2))
    rodape.add_column(style=ACCENT, no_wrap=True)
    rodape.add_column(style="dim")
    rodape.add_row("  designsys <comando> --help", "opções detalhadas de cada comando")
    rodape.add_row("  designsys doctor", "checa se está tudo pronto para rodar")
    console.print(rodape)
    console.print()


class DesignsysGroup(TyperGroup):
    """Grupo que troca o help padrão do Typer pelo menu acima."""

    def format_help(self, ctx: Any, formatter: Any) -> None:
        render_main_help()

    def get_help(self, ctx: Any) -> str:
        render_main_help()
        return ""


app = typer.Typer(
    name="designsys",
    cls=DesignsysGroup,
    rich_markup_mode="rich",
    no_args_is_help=False,  # sem argumentos cai no callback, que chama o menu
    add_completion=False,
    help="""[bold]designsys[/bold] — extrai o design system completo de um site ao vivo ou de um repositório.

Gera um [cyan]design-system.pdf[/cyan] completo, [cyan]tokens.json[/cyan] (W3C DTCG),
[cyan]variables.css[/cyan], [cyan]tailwind.config.js[/cyan], um [cyan]style-guide.html[/cyan]
navegável, os assets e screenshots.

[bold]Exemplos[/bold]
  [dim]$[/dim] designsys url https://stripe.com --pages 5
  [dim]$[/dim] designsys url https://app.suaempresa.com --login --pages 12
  [dim]$[/dim] designsys repo ~/dev/meu-projeto
  [dim]$[/dim] designsys open designsys-stripe.com-2026-08-12
  [dim]$[/dim] designsys pdf designsys-stripe.com-2026-08-12 --open
  [dim]$[/dim] designsys doctor --fix
""",
)


# ============================================================== Rich reporter
class RichReporter(Reporter):
    """Reporter com spinners, barra de progresso e prompts seguros."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self._progress: Progress | None = None
        self._task: Any = None

    # ---------------------------------------------------------------- saída
    def step(self, message: str) -> None:
        console.print(f"  [dim]›[/dim] {message}")

    def detail(self, message: str) -> None:
        if self.verbose:
            console.print(f"    [dim]{message}[/dim]")

    def warn(self, message: str) -> None:
        console.print(f"  [yellow]![/yellow] {message}")

    def success(self, message: str) -> None:
        console.print(f"  [green]✓[/green] {message}")

    # ------------------------------------------------------------ progresso
    def _ensure_progress(self, total: int) -> None:
        if self._progress is None:
            self._progress = Progress(
                SpinnerColumn(style="cyan"),
                TextColumn("[bold]{task.description}"),
                BarColumn(bar_width=28, complete_style="cyan", finished_style="green"),
                TaskProgressColumn(),
                TextColumn("[dim]{task.fields[url]}"),
                console=console,
                transient=False,
            )
            self._progress.start()
            self._task = self._progress.add_task("páginas", total=total, url="")
        else:
            self._progress.update(self._task, total=total)

    def page_start(self, index: int, total: int, url: str) -> None:
        self._ensure_progress(total)
        self._progress.update(self._task, url=_short_url(url), completed=index - 1)

    def page_done(self, url: str, stats: dict[str, Any]) -> None:
        if self._progress is not None:
            self._progress.advance(self._task)
        summary = " · ".join(f"{v} {k}" for k, v in stats.items())
        console.print(f"  [green]✓[/green] [dim]{_short_url(url)}[/dim] — {summary}")

    def stop_progress(self) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
            self._task = None

    # --------------------------------------------------------------- prompts
    def ask_credentials(self, url: str) -> tuple[str, str] | None:
        self.stop_progress()
        console.print()
        console.print(
            Panel(
                "Suas credenciais são usadas [bold]apenas nesta execução[/bold] e nunca gravadas em disco.\n"
                "Só os cookies do navegador ficam no perfil "
                "[dim]~/.designsys/profiles/<domínio>[/dim].",
                title="[bold]login[/bold]",
                border_style="cyan",
                expand=False,
            )
        )
        try:
            user = Prompt.ask("  usuário / e-mail")
            password = Prompt.ask(
                "  senha [dim](Enter para pular — acesso por código/link)[/dim]",
                password=True,
                default="",
                show_default=False,
            )
        except (EOFError, KeyboardInterrupt):
            return None
        if not user:
            return None
        return user, password

    def ask_otp(self, hint: str) -> str | None:
        self.stop_progress()
        console.print()
        console.print(
            Panel(
                f"O site pediu um código de verificação ({hint}).\n"
                "Abra seu e-mail/SMS, pegue o código e cole aqui.",
                title="[bold]código de acesso[/bold]",
                border_style="cyan",
                expand=False,
            )
        )
        try:
            code = Prompt.ask("  código")
        except (EOFError, KeyboardInterrupt):
            return None
        return code.strip() or None

    def ask_magic_link(self) -> str | None:
        self.stop_progress()
        console.print()
        console.print(
            Panel(
                "O site enviou um [bold]link de acesso[/bold] por e-mail.\n\n"
                "Abra o e-mail, [bold]copie o link[/bold] (botão direito → copiar endereço,\n"
                "sem abrir no navegador) e cole aqui. Eu abro o link nesta sessão,\n"
                "para que a autenticação fique com o designsys.",
                title="[bold]link de acesso[/bold]",
                border_style="cyan",
                expand=False,
            )
        )
        try:
            link = Prompt.ask("  cole o link (ou Enter para fazer login manual)", default="", show_default=False)
        except (EOFError, KeyboardInterrupt):
            return None
        return link.strip() or None

    def ask_manual_login(self, url: str) -> bool:
        self.stop_progress()
        console.print()
        console.print(
            Panel(
                "Abri o navegador [bold]visível[/bold]. Faça o login por lá (2FA, captcha, SSO — o que for).\n\n"
                "Quando o app estiver aberto e logado, volte aqui e aperte [bold]Enter[/bold].\n"
                f"[dim]página atual: {url}[/dim]",
                title="[bold yellow]login manual[/bold yellow]",
                border_style="yellow",
                expand=False,
            )
        )
        try:
            answer = Prompt.ask(
                "  [bold]Enter[/bold] para continuar (ou 'q' para abortar)", default="", show_default=False
            )
        except (EOFError, KeyboardInterrupt):
            return False
        return answer.strip().lower() not in ("q", "quit", "n", "no", "abortar")


def _short_url(url: str, limit: int = 52) -> str:
    parsed = urlparse(url)
    text = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


# ================================================================== comandos
@app.command(
    "url",
    help="""Extrai o design system de um [bold]site ao vivo[/bold], com JS renderizado.

Percorre a página inicial, rastreia páginas internas, coleta cores, tipografia,
espaçamento, componentes (com [cyan]:hover[/cyan] e [cyan]:focus[/cyan]), assets e screenshots.

Para SaaS atrás de login use [cyan]--login[/cyan]. Ele cobre, nesta ordem:
sessão salva de execuções anteriores · usuário e senha (inclusive em 2 etapas) ·
[bold]acesso sem senha[/bold] — código por e-mail/SMS (OTP, também como 2FA) e magic link,
que a ferramenta pede no terminal · e, se nada disso servir (captcha, SSO),
abre o navegador visível para você logar à mão.

A senha é opcional: deixe em branco no prompt se o site só manda código ou link.
A sessão fica salva no perfil do domínio, então o login acontece uma vez só.""",
    epilog="""[bold]Exemplos[/bold]

  [dim]$[/dim] designsys url stripe.com
  [dim]$[/dim] designsys url https://tailwindcss.com --pages 5
  [dim]$[/dim] designsys url https://app.exemplo.com --login --path /dashboard --path /settings
  [dim]$[/dim] designsys url https://app.exemplo.com --login --headed --pages 12
  [dim]$[/dim] designsys url https://app.exemplo.com --login --user voce@empresa.com  [dim]# OTP/magic link: sem senha[/dim]
  [dim]$[/dim] designsys url https://exemplo.com --no-assets --out ./tokens-exemplo
""",
)
def url_command(
    target: str = typer.Argument(..., metavar="URL", help="URL do site (https:// é opcional)"),
    login: bool = typer.Option(False, "--login", help="Autentica antes de extrair (prompt seguro)."),
    user: Optional[str] = typer.Option(None, "--user", help="Usuário/e-mail para o login."),
    password: Optional[str] = typer.Option(
        None,
        "--pass",
        help="Senha. [yellow]Fica no histórico do shell[/yellow] — prefira o prompt.",
    ),
    pages: int = typer.Option(8, "--pages", "-p", min=0, max=60, help="Páginas internas além da inicial."),
    path: list[str] = typer.Option([], "--path", help="Rota específica a visitar (repetível)."),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Pasta de saída."),
    no_assets: bool = typer.Option(False, "--no-assets", help="Pula o download de assets."),
    no_pdf: bool = typer.Option(False, "--no-pdf", help="Não gera o design-system.pdf."),
    no_dark: bool = typer.Option(False, "--no-dark", help="Não tenta capturar o tema escuro."),
    no_viewports: bool = typer.Option(
        False, "--no-viewports", help="Não recoleta em mobile/tablet (extração mais rápida)."
    ),
    exhaustive: bool = typer.Option(
        False, "--exhaustive", help="Visita todas as páginas, mesmo sem token novo."
    ),
    headed: bool = typer.Option(False, "--headed", help="Abre o navegador visível."),
    insecure: bool = typer.Option(
        False,
        "--insecure",
        help="Aceita certificado TLS inválido. Só em ambiente interno de confiança.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mostra detalhes e tracebacks."),
    timeout: int = typer.Option(30, "--timeout", help="Timeout de navegação em segundos."),
) -> None:
    from .extractors.web import WebExtractor, WebOptions

    normalized = _normalize_url(target)
    domain = urlparse(normalized).netloc or "site"
    out_dir = (out or Path.cwd() / f"designsys-{domain}-{date.today().isoformat()}").resolve()

    if password and not user:
        _fail("--pass exige --user (ou use só --login e responda o prompt).")
    if password:
        console.print(
            "  [yellow]![/yellow] senha passada por argumento fica no histórico do shell — "
            "considere usar apenas [cyan]--login[/cyan]."
        )
    if insecure:
        console.print(
            "  [yellow]![/yellow] [bold]--insecure[/bold]: a validação do certificado TLS "
            "está desligada — a conexão fica sujeita a interceptação."
        )

    console.print()
    console.print(f"[bold cyan]designsys[/bold cyan] [dim]url[/dim] {normalized}")
    console.print(f"  [dim]saída:[/dim] {out_dir}")
    console.print()

    reporter = RichReporter(verbose=verbose)
    out_dir.mkdir(parents=True, exist_ok=True)
    options = WebOptions(
        url=normalized,
        pages=pages,
        paths=list(path),
        out=out_dir,
        no_assets=no_assets,
        headed=headed,
        insecure=insecure,
        login=login or bool(user and password),
        username=user,
        password=password,
        verbose=verbose,
        timeout_ms=timeout * 1000,
        no_dark=no_dark,
        viewports=not no_viewports,
        exhaustive=exhaustive,
    )

    try:
        ds = WebExtractor(options, reporter).run()
    except KeyboardInterrupt:
        reporter.stop_progress()
        _fail("interrompido.", code=130)
    except Exception as exc:  # noqa: BLE001 - fronteira da CLI
        reporter.stop_progress()
        _handle_error(exc, verbose)
    finally:
        reporter.stop_progress()

    _finish(ds, out_dir, verbose, pdf=not no_pdf)


@app.command(
    "repo",
    help="""Extrai o design system de um [bold]repositório local[/bold].

Lê [cyan]tailwind.config.*[/cyan] (inclusive [cyan]extend[/cyan] e [cyan]@theme[/cyan] do Tailwind v4),
CSS/SCSS/LESS (custom properties, [cyan]$vars[/cyan], [cyan]@font-face[/cyan], media queries),
temas de styled-components/emotion e arquivos de tokens (DTCG, Style Dictionary, Figma Tokens).
Respeita o [cyan].gitignore[/cyan] e ignora node_modules, dist e build.""",
    epilog="""[bold]Exemplos[/bold]

  [dim]$[/dim] designsys repo
  [dim]$[/dim] designsys repo ~/dev/meu-app
  [dim]$[/dim] designsys repo . --out ./ds --no-assets
""",
)
def repo_command(
    target: Path = typer.Argument(Path("."), metavar="[CAMINHO]", help="Raiz do repositório (default: diretório atual)."),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Pasta de saída."),
    no_assets: bool = typer.Option(False, "--no-assets", help="Não copia assets para a saída."),
    no_pdf: bool = typer.Option(False, "--no-pdf", help="Não gera o design-system.pdf."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mostra detalhes e tracebacks."),
) -> None:
    from .extractors.repo import RepoExtractor, RepoOptions

    root = target.expanduser().resolve()
    if not root.exists():
        _fail(f"caminho não encontrado: {root}")
    if not root.is_dir():
        _fail(f"não é um diretório: {root}")

    out_dir = (out or Path.cwd() / f"designsys-{root.name}-{date.today().isoformat()}").resolve()
    console.print()
    console.print(f"[bold cyan]designsys[/bold cyan] [dim]repo[/dim] {root}")
    console.print(f"  [dim]saída:[/dim] {out_dir}")
    console.print()

    reporter = RichReporter(verbose=verbose)
    out_dir.mkdir(parents=True, exist_ok=True)
    options = RepoOptions(path=root, out=out_dir, no_assets=no_assets, verbose=verbose)

    try:
        with console.status("[cyan]varrendo o repositório…", spinner="dots"):
            ds = RepoExtractor(options, reporter).run()
    except KeyboardInterrupt:
        _fail("interrompido.", code=130)
    except Exception as exc:  # noqa: BLE001
        _handle_error(exc, verbose)

    _finish(ds, out_dir, verbose, pdf=not no_pdf)


@app.command(
    "open",
    help="""Abre o resultado de uma pasta de saída.

Por padrão abre o [cyan]design-system.pdf[/cyan]; use [cyan]--html[/cyan] para
abrir a versão navegável no navegador.""",
    epilog="""[bold]Exemplos[/bold]

  [dim]$[/dim] designsys open designsys-stripe.com-2026-08-12
  [dim]$[/dim] designsys open .
  [dim]$[/dim] designsys open . --html
""",
)
def open_command(
    folder: Path = typer.Argument(Path("."), metavar="PASTA", help="Pasta gerada por designsys."),
    html: bool = typer.Option(False, "--html", help="Abre o style-guide.html em vez do PDF."),
) -> None:
    target = folder.expanduser().resolve()
    if target.is_file():
        _launch(target)
        return

    preferidos = ["style-guide.html"] if html else ["design-system.pdf", "style-guide.html"]
    for nome in preferidos:
        candidato = target / nome
        if candidato.exists():
            _launch(candidato)
            return

    # Aponta para uma pasta que contém extrações? Pega a mais recente.
    for nome in preferidos:
        candidatos = sorted(target.glob(f"designsys-*/{nome}"))
        if candidatos:
            _launch(candidatos[-1])
            return

    _fail(
        f"não achei {' nem '.join(preferidos)} em {target}.\n"
        "  Rode primeiro: designsys url <URL>  ou  designsys repo <caminho>"
    )


def _launch(path: Path) -> None:
    console.print(f"[green]✓[/green] abrindo {path}")
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        webbrowser.open(path.as_uri())


@app.command(
    "pdf",
    help="""Gera (ou regera) o [cyan]design-system.pdf[/cyan] de uma pasta já extraída.

Lê o [cyan]raw.json[/cyan] da pasta — não refaz a extração, então é instantâneo.""",
    epilog="""[bold]Exemplos[/bold]

  [dim]$[/dim] designsys pdf designsys-stripe.com-2026-08-12
  [dim]$[/dim] designsys pdf . --open
""",
)
def pdf_command(
    folder: Path = typer.Argument(Path("."), metavar="PASTA", help="Pasta gerada por designsys."),
    open_after: bool = typer.Option(False, "--open", help="Abre o PDF ao terminar."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mostra detalhes e tracebacks."),
) -> None:
    import json

    from .output.pdfrender import PdfError
    from .output.writer import write_pdf

    target = folder.expanduser().resolve()
    raw = target / "raw.json"
    if not raw.exists():
        candidatos = sorted(target.glob("designsys-*/raw.json"))
        if not candidatos:
            _fail(
                f"não achei raw.json em {target}.\n"
                "  O PDF é montado a partir dele — rode uma extração primeiro."
            )
        raw = candidatos[-1]
        target = raw.parent

    try:
        data = json.loads(raw.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _fail(f"não consegui ler {raw}: {exc}")

    ds = DesignSystem.from_dict(data)
    console.print()
    console.print(f"[bold cyan]designsys[/bold cyan] [dim]pdf[/dim] {ds.name}")
    try:
        with console.status("[cyan]montando o PDF…", spinner="dots"):
            path = write_pdf(ds, target)
    except PdfError as exc:
        _fail(str(exc))
    except Exception as exc:  # noqa: BLE001
        _handle_error(exc, verbose)

    kb = path.stat().st_size // 1024
    console.print(f"  [green]✓[/green] {path} [dim]({kb} KB)[/dim]")
    console.print()
    if open_after:
        _launch(path)


@app.command(
    "audit",
    help="""Mostra o [bold]diagnóstico[/bold] de uma pasta já extraída.

Acessibilidade (contraste dos pares reais, foco visível, tamanhos), consistência
(grade de espaçamento, cores órfãs, tokens nunca usados) e a assinatura visual.
Grava também um [cyan]audit.md[/cyan] na pasta.""",
    epilog="""[bold]Exemplos[/bold]

  [dim]$[/dim] designsys audit designsys-stripe.com-2026-08-12
  [dim]$[/dim] designsys audit .
""",
)
def audit_command(
    folder: Path = typer.Argument(Path("."), metavar="PASTA", help="Pasta gerada por designsys."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mostra todos os ofensores."),
) -> None:
    import json

    from rich import box

    target = folder.expanduser().resolve()
    raw = target / "raw.json"
    if not raw.exists():
        candidatos = sorted(target.glob("designsys-*/raw.json"))
        if not candidatos:
            _fail(f"não achei raw.json em {target}. Rode uma extração primeiro.")
        raw = candidatos[-1]
        target = raw.parent

    try:
        ds = DesignSystem.from_dict(json.loads(raw.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        _fail(f"não consegui ler {raw}: {exc}")

    diag = ds.diagnostics or {}
    if not diag:
        _fail(
            "esta pasta foi gerada por uma versão anterior e não tem diagnóstico.\n"
            "  Rode a extração de novo para obtê-lo."
        )

    console.print()
    console.print(f"[bold cyan]designsys[/bold cyan] [dim]audit[/dim] {ds.display_target}")
    console.print()

    a11y = diag.get("accessibility") or {}
    cons = diag.get("consistency") or {}
    notas = Table.grid(padding=(0, 3))
    notas.add_column(justify="right", style="bold")
    notas.add_column()
    notas.add_row(str(diag.get("score", "—")), "[bold]nota geral[/bold]")
    notas.add_row(str(a11y.get("score", "—")), f"acessibilidade — [dim]{a11y.get('summary', '')}[/dim]")
    notas.add_row(str(cons.get("score", "—")), f"consistência — [dim]{cons.get('summary', '')}[/dim]")
    console.print(Panel(notas, border_style="cyan", box=box.ROUNDED, padding=(1, 2), expand=False))

    for titulo, dados in (("acessibilidade", a11y), ("consistência", cons)):
        parcelas = dados.get("breakdown") or []
        if parcelas:
            console.print(f"  [bold]{titulo}[/bold]")
            for parcela in parcelas:
                console.print(f"    [dim]{parcela}[/dim]")
            console.print()

    falhas = a11y.get("contrast") or []
    if falhas:
        tabela = Table(box=box.SIMPLE, header_style="dim", show_edge=False)
        tabela.add_column("texto / fundo")
        tabela.add_column("contraste", justify="right")
        tabela.add_column("mínimo", justify="right")
        tabela.add_column("×", justify="right")
        tabela.add_column("exemplo", overflow="ellipsis", max_width=28)
        for item in falhas[: (30 if verbose else 8)]:
            tabela.add_row(
                f"[{item['fg']}]■[/] {item['fg']} sobre {item['bg']}",
                f"{item['ratio']}:1",
                f"{item['required']}:1",
                str(item["count"]),
                item.get("sample", ""),
            )
        console.print("  [bold]contraste abaixo do mínimo AA[/bold]")
        console.print(tabela)
        console.print()

    sem_foco = a11y.get("focusMissing") or []
    if sem_foco:
        console.print(f"  [yellow]![/yellow] sem foco visível: {', '.join(sem_foco)}")
        console.print()

    assinatura = diag.get("signature") or {}
    if assinatura.get("sentence"):
        console.print(f"  [bold]assinatura visual[/bold] {assinatura['sentence']}")
        console.print()

    caminho = target / "audit.md"
    try:
        caminho.write_text(_audit_markdown(ds), encoding="utf-8")
        console.print(f"  [green]✓[/green] {caminho}")
    except OSError as exc:
        console.print(f"  [yellow]![/yellow] não consegui escrever audit.md: {exc}")
    console.print()


def _audit_markdown(ds: DesignSystem) -> str:
    diag = ds.diagnostics or {}
    a11y = diag.get("accessibility") or {}
    cons = diag.get("consistency") or {}
    linhas = [
        f"# Diagnóstico — {ds.display_target}",
        "",
        f"| | nota |",
        f"| --- | ---: |",
        f"| geral | **{diag.get('score', '—')}** |",
        f"| acessibilidade | {a11y.get('score', '—')} |",
        f"| consistência | {cons.get('score', '—')} |",
        "",
    ]
    for titulo, dados in (("Acessibilidade", a11y), ("Consistência", cons)):
        linhas.append(f"## {titulo}")
        linhas.append("")
        linhas.append(dados.get("summary", ""))
        linhas.append("")
        for parcela in dados.get("breakdown") or []:
            linhas.append(f"- {parcela}")
        linhas.append("")

    falhas = a11y.get("contrast") or []
    if falhas:
        linhas += ["### Pares abaixo do AA", "", "| texto | fundo | contraste | mínimo | ocorrências |", "| --- | --- | ---: | ---: | ---: |"]
        for item in falhas:
            linhas.append(
                f"| `{item['fg']}` | `{item['bg']}` | {item['ratio']}:1 | {item['required']}:1 | {item['count']} |"
            )
        linhas.append("")

    assinatura = diag.get("signature") or {}
    if assinatura.get("axes"):
        linhas += ["## Assinatura visual", "", assinatura.get("sentence", ""), ""]
        for eixo in assinatura["axes"]:
            linhas.append(f"- **{eixo['label']}** ({eixo['left']} ↔ {eixo['right']}) — {eixo.get('detail', '')}")
        linhas.append("")
    return "\n".join(linhas)


@app.command(
    "doctor",
    help="""Diagnostica o ambiente: Python, dependências, Playwright, Chromium, rede e PATH.

Com [cyan]--fix[/cyan] instala o que estiver faltando (browser do Playwright).""",
    epilog="""[bold]Exemplos[/bold]

  [dim]$[/dim] designsys doctor
  [dim]$[/dim] designsys doctor --fix
""",
)
def doctor_command(
    fix: bool = typer.Option(False, "--fix", help="Tenta corrigir o que estiver faltando."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mostra detalhes."),
) -> None:
    console.print()
    console.print("[bold cyan]designsys doctor[/bold cyan]")
    console.print()

    table = Table(show_header=True, header_style="dim", box=None, padding=(0, 2, 0, 0))
    table.add_column("")
    table.add_column("verificação")
    table.add_column("resultado", overflow="fold")

    problems: list[str] = []

    def row(ok: bool | None, name: str, detail: str) -> None:
        icon = "[green]✓[/green]" if ok else ("[yellow]•[/yellow]" if ok is None else "[red]✗[/red]")
        table.add_row(icon, name, detail)

    # Python
    py_ok = sys.version_info >= (3, 11)
    row(py_ok, "Python ≥ 3.11", f"{sys.version.split()[0]} ({sys.executable})")
    if not py_ok:
        problems.append("Python 3.11+ é obrigatório.")

    # Dependências
    for module, label in [
        ("typer", "typer"),
        ("rich", "rich"),
        ("requests", "requests"),
        ("tinycss2", "tinycss2"),
        ("coloraide", "coloraide"),
        ("pathspec", "pathspec"),
        ("playwright", "playwright"),
    ]:
        try:
            mod = __import__(module)
            version = getattr(mod, "__version__", "ok")
            row(True, label, str(version))
        except ImportError:
            row(False, label, "não instalado")
            problems.append(f"dependência ausente: {module}")

    # Chromium: um único sync_playwright para caminho + lançamento, senão o
    # driver reclama de tasks pendentes ao abrir/fechar duas vezes seguidas.
    chromium_path, launch_ok, launch_detail = _check_browser()
    if chromium_path:
        row(True, "Chromium (Playwright)", str(chromium_path))
    else:
        row(False, "Chromium (Playwright)", "não instalado")
        if fix:
            console.print(table)
            console.print()
            console.print("  [cyan]›[/cyan] instalando Chromium do Playwright…")
            code = subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"])
            if code == 0:
                console.print("  [green]✓[/green] Chromium instalado. Rode o doctor de novo.")
                raise typer.Exit(0)
            problems.append("falhou ao instalar o Chromium (`playwright install chromium`).")
        else:
            problems.append("Chromium ausente — rode: designsys doctor --fix")

    # Navegador funcional
    if chromium_path:
        row(launch_ok, "lançar navegador", launch_detail)
        if not launch_ok:
            problems.append(f"não consegui lançar o Chromium: {launch_detail}")

    # Rede
    ok, detail = _check_network()
    row(ok, "rede (https)", detail)
    if not ok:
        problems.append("sem acesso à rede — o modo url não vai funcionar.")

    # PATH
    binary = shutil.which("designsys")
    if binary:
        row(True, "designsys no PATH", binary)
    else:
        row(None, "designsys no PATH", "não encontrado (rode via python -m designsys ou pipx ensurepath)")

    # Perfis salvos
    from .browser.session import PROFILE_ROOT

    if PROFILE_ROOT.exists():
        profiles = [p.name for p in PROFILE_ROOT.iterdir() if p.is_dir()]
        row(True, "perfis de sessão", ", ".join(profiles[:6]) if profiles else "nenhum")
    else:
        row(True, "perfis de sessão", "nenhum ainda")

    console.print(table)
    console.print()
    if problems:
        console.print(
            Panel(
                "\n".join(f"• {p}" for p in problems),
                title="[bold red]problemas[/bold red]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(1)
    console.print("  [bold green]tudo verde.[/bold green] designsys pronto para uso.\n")


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", help="Mostra a versão e sai.", is_eager=True
    ),
) -> None:
    if version:
        console.print(f"designsys {__version__}")
        console.print(f"[dim]desenvolvido por {AUTOR} · {REPOSITORIO}[/dim]")
        raise typer.Exit()
    # `invoke_without_command` é necessário para que --version funcione sem
    # subcomando; sem ele o Click reclamaria de "Missing command".
    if ctx.invoked_subcommand is None:
        render_main_help()
        raise typer.Exit()


# ================================================================== helpers
def _finish(ds: DesignSystem, out_dir: Path, verbose: bool, pdf: bool = True) -> None:
    from .output.writer import write_all, write_pdf

    try:
        written = write_all(ds, out_dir)
    except OSError as exc:
        _fail(f"não consegui escrever em {out_dir}: {exc}")

    if pdf:
        from .output.pdfrender import PdfError

        try:
            with console.status("[cyan]montando o PDF…", spinner="dots"):
                written["design-system.pdf"] = write_pdf(ds, out_dir)
        except PdfError as exc:
            console.print(f"  [yellow]![/yellow] PDF não gerado: {exc}")
            ds.warnings.append(f"PDF não gerado: {exc}")
        except Exception as exc:  # noqa: BLE001 - o PDF nunca derruba a extração
            if verbose:
                err_console.print(traceback.format_exc())
            console.print(f"  [yellow]![/yellow] PDF não gerado: {type(exc).__name__}: {exc}")

    console.print()
    table = Table(
        title=None, show_header=True, header_style="dim", box=None, padding=(0, 3, 0, 0)
    )
    table.add_column("token", style="bold")
    table.add_column("qtd", justify="right")
    for key, value in ds.counts().items():
        table.add_row(key, str(value))
    console.print(
        Panel(
            table,
            title=f"[bold]{ds.name}[/bold]",
            subtitle=f"[dim]{ds.mode} · {len(ds.pages) or len(ds.files_scanned)} fonte(s)[/dim]",
            border_style="cyan",
            expand=False,
        )
    )

    if ds.warnings:
        console.print()
        for warning in ds.warnings[:8]:
            console.print(f"  [yellow]![/yellow] {warning}")

    console.print()
    console.print("  [bold]arquivos gerados[/bold]")
    for name in (
        "design-system.pdf", "style-guide.html", "DESIGN-SYSTEM.md", "tokens.json",
        "tokens.studio.json", "variables.css", "tailwind.config.js", "components.json",
        "README.md", "raw.json", "assets/icons/sprite.svg",
    ):
        if name in written:
            destaque = "[bold]" if name == "design-system.pdf" else ""
            fecha = "[/bold]" if destaque else ""
            tamanho = ""
            if name.endswith(".pdf"):
                kb = written[name].stat().st_size // 1024
                tamanho = f" [dim]({kb} KB)[/dim]"
            console.print(f"    [green]✓[/green] {destaque}{name}{fecha}{tamanho}")
    assets = list((out_dir / "assets").rglob("*")) if (out_dir / "assets").exists() else []
    asset_files = [a for a in assets if a.is_file()]
    if asset_files:
        console.print(f"    [green]✓[/green] assets/ [dim]({len(asset_files)} arquivos)[/dim]")
    shots = list((out_dir / "screenshots").glob("*.png")) if (out_dir / "screenshots").exists() else []
    if shots:
        console.print(f"    [green]✓[/green] screenshots/ [dim]({len(shots)} imagens)[/dim]")

    console.print()
    console.print(Text(str(out_dir), style="bold cyan"))
    console.print(f"  [dim]abra o documento:[/dim] designsys open {_display_path(out_dir)}")
    console.print()


def _display_path(path: Path) -> str:
    try:
        rel = path.relative_to(Path.cwd())
        return str(rel)
    except ValueError:
        return str(path)


def _normalize_url(target: str) -> str:
    url = target.strip()
    if not url:
        _fail("informe uma URL.")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    parsed = urlparse(url)
    if not parsed.netloc or "." not in parsed.netloc:
        if parsed.netloc not in ("localhost",) and not parsed.netloc.startswith("localhost:"):
            _fail(f"URL inválida: {target}")
    return url


def _fail(message: str, code: int = 1) -> None:
    err_console.print(f"\n[bold red]erro[/bold red] {message}\n")
    raise typer.Exit(code)


def _handle_error(exc: Exception, verbose: bool) -> None:
    from .browser.session import BrowserError

    if verbose:
        err_console.print()
        err_console.print(traceback.format_exc())
    if isinstance(exc, BrowserError):
        _fail(str(exc))
    if isinstance(exc, FileNotFoundError):
        _fail(str(exc))
    hint = "" if verbose else "\n  [dim]rode de novo com --verbose para ver os detalhes.[/dim]"
    _fail(f"{type(exc).__name__}: {exc}{hint}")


def _check_browser() -> tuple[Path | None, bool, str]:
    """Caminho do Chromium + teste de lançamento, numa única sessão do driver."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, False, "playwright não instalado"
    try:
        with sync_playwright() as pw:
            try:
                path = Path(pw.chromium.executable_path)
            except Exception:
                return None, False, "browser não instalado"
            if not path.exists():
                return None, False, "browser não instalado"
            try:
                browser = pw.chromium.launch(headless=True)
                version = browser.version
                browser.close()
                return path, True, f"Chromium {version}"
            except Exception as exc:
                return path, False, str(exc).splitlines()[0][:120]
    except Exception as exc:
        return None, False, str(exc).splitlines()[0][:120]


def _check_network() -> tuple[bool, str]:
    import requests

    for url in ("https://example.com", "https://www.google.com"):
        try:
            r = requests.get(url, timeout=6)
            if r.status_code < 500:
                return True, f"{url} → HTTP {r.status_code}"
        except requests.RequestException as exc:
            last = str(exc).splitlines()[0][:90]
            continue
    return False, "sem resposta de example.com nem google.com"


def main() -> None:
    # Silencia o aviso de fork do macOS ao lançar o Chromium.
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
    app()


if __name__ == "__main__":
    main()
