"""Detecção e execução de login, com fallback manual.

Estratégia em camadas (a de cima sempre tem prioridade):
  1. sessão persistente já autenticada -> nada a fazer
  2. login automático por heurística de formulário (inclusive 2 etapas)
  3. fallback manual em navegador visível
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Seletores de campo, do mais específico para o mais genérico.
USER_SELECTORS = [
    "input[type=email]:visible",
    "input[autocomplete='username']:visible",
    "input[name*='email' i]:visible",
    "input[id*='email' i]:visible",
    "input[name*='user' i]:visible",
    "input[id*='user' i]:visible",
    "input[name*='login' i]:visible",
    "input[placeholder*='email' i]:visible",
    "input[placeholder*='usuário' i]:visible",
    "input[type=text]:visible",
]

PASSWORD_SELECTORS = [
    "input[type=password]:visible",
    "input[name*='pass' i]:visible",
    "input[autocomplete='current-password']:visible",
]

SUBMIT_SELECTORS = [
    "button[type=submit]:visible",
    "input[type=submit]:visible",
    "button:has-text('Sign in'):visible",
    "button:has-text('Log in'):visible",
    "button:has-text('Login'):visible",
    "button:has-text('Entrar'):visible",
    "button:has-text('Continuar'):visible",
    "button:has-text('Continue'):visible",
    "button:has-text('Next'):visible",
    "button:has-text('Próximo'):visible",
    "[role=button]:has-text('Sign in'):visible",
]

NEXT_SELECTORS = [
    "button:has-text('Next'):visible",
    "button:has-text('Continue'):visible",
    "button:has-text('Continuar'):visible",
    "button:has-text('Próximo'):visible",
    "button:has-text('Avançar'):visible",
    "#identifierNext button",
    "button[type=submit]:visible",
    "input[type=submit]:visible",
]

LOGIN_URL_HINTS = (
    "login",
    "signin",
    "sign-in",
    "sign_in",
    "auth",
    "sessions/new",
    "account/login",
    "entrar",
    "acessar",
)

LOGIN_TEXT_HINTS = (
    "sign in",
    "log in",
    "login",
    "entrar",
    "acessar sua conta",
    "welcome back",
    "bem-vindo de volta",
)

# Códigos de uso único: campo dedicado, campo numérico, ou os 6 quadradinhos
# de um dígito cada.
OTP_SELECTORS = [
    "input[autocomplete='one-time-code']:visible",
    "input[name*='otp' i]:visible",
    "input[id*='otp' i]:visible",
    "input[name*='verification' i]:visible",
    "input[name*='token' i]:visible",
    "input[name*='code' i]:not([name*='country' i]):not([name*='postal' i]):visible",
    "input[id*='code' i]:not([id*='country' i]):visible",
    "input[placeholder*='código' i]:visible",
    "input[placeholder*='code' i]:visible",
    "input[inputmode='numeric']:visible",
    "input[maxlength='1']:visible",
]

# Texto que indica "mandamos algo pro seu e-mail".
OTP_TEXT = re.compile(
    r"(c[óo]digo de (verifica|acesso|confirma)|one[- ]time|verification code|"
    r"security code|c[óo]digo enviado|digite o c[óo]digo|enter the code)",
    re.I,
)
MAGIC_LINK_TEXT = re.compile(
    r"(magic link|link m[áa]gico|link de acesso|check your (e-?mail|inbox)|"
    r"verifique (seu|sua) (e-?mail|caixa)|enviamos um (e-?mail|link)|"
    r"we (sent|emailed) you|sign[- ]in link|clique no link)",
    re.I,
)

CAPTCHA_MARKERS = (
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='challenges.cloudflare.com']",
    ".g-recaptcha",
    "#cf-challenge-running",
    "[data-sitekey]",
)

TWOFA_TEXT = re.compile(
    r"(two[- ]factor|2fa|verification code|authenticator|c[óo]digo de verifica|autentica[çc][ãa]o em duas)",
    re.I,
)

OAUTH_MARKERS = (
    "accounts.google.com",
    "login.microsoftonline.com",
    "github.com/login",
    "okta.com",
    "auth0.com",
    "onelogin.com",
)


@dataclass
class LoginOutcome:
    ok: bool
    method: str  # session | auto | manual | none
    detail: str = ""
    steps: list[str] = field(default_factory=list)


def _first_visible(page: Any, selectors: list[str], timeout: float = 0):
    """Primeiro locator visível dentro da página ou de qualquer iframe."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                return loc
        except Exception:
            continue
    # Formulários de login em iframe (Auth0, Stripe checkout, etc.)
    try:
        for frame in page.frames[1:]:
            for sel in selectors:
                try:
                    loc = frame.locator(sel).first
                    if loc.count() > 0 and loc.is_visible():
                        return loc
                except Exception:
                    continue
    except Exception:
        pass
    return None


def looks_like_login_page(page: Any) -> bool:
    """A página atual pede autenticação?"""
    try:
        url = (page.url or "").lower()
    except Exception:
        return False
    if any(h in url for h in LOGIN_URL_HINTS):
        return True
    if _first_visible(page, PASSWORD_SELECTORS) is not None:
        return True
    try:
        body = (page.inner_text("body", timeout=3000) or "").lower()[:4000]
    except Exception:
        return False
    has_hint = any(h in body for h in LOGIN_TEXT_HINTS)
    return has_hint and _first_visible(page, USER_SELECTORS) is not None


def detect_blockers(page: Any) -> str | None:
    """Retorna a razão pela qual o login automático não deve ser tentado."""
    for sel in CAPTCHA_MARKERS:
        try:
            if page.locator(sel).count() > 0:
                return "captcha detectado"
        except Exception:
            continue
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    for marker in OAUTH_MARKERS:
        if marker in url:
            return f"fluxo OAuth de terceiro ({marker})"
    try:
        body = page.inner_text("body", timeout=2000) or ""
        if TWOFA_TEXT.search(body[:4000]):
            return "2FA / código de verificação"
    except Exception:
        pass
    return None


def detect_passwordless(page: Any) -> str | None:
    """Distingue os fluxos sem senha: 'otp' (tem campo de código) ou 'magic-link'."""
    if _first_visible(page, OTP_SELECTORS) is not None:
        return "otp"
    try:
        body = (page.inner_text("body", timeout=3000) or "")[:5000]
    except Exception:
        return None
    if OTP_TEXT.search(body):
        return "otp"
    if MAGIC_LINK_TEXT.search(body):
        return "magic-link"
    return None


def otp_inputs(page: Any) -> list[Any]:
    """Campos de código visíveis. Vários = OTP segmentado (um dígito por caixa)."""
    for sel in ("input[maxlength='1']:visible", "input[autocomplete='one-time-code']:visible"):
        try:
            loc = page.locator(sel)
            count = loc.count()
            if count > 1:
                return [loc.nth(i) for i in range(min(count, 12))]
        except Exception:
            continue
    single = _first_visible(page, OTP_SELECTORS)
    return [single] if single is not None else []


def fill_otp(page: Any, code: str, *, log=lambda m: None, timeout_ms: int = 15000) -> LoginOutcome:
    """Digita o código de uso único e conclui o login."""
    code = "".join(ch for ch in (code or "").strip() if ch.isalnum())
    if not code:
        return LoginOutcome(False, "otp", "nenhum código informado")

    fields = otp_inputs(page)
    if not fields:
        return LoginOutcome(False, "otp", "campo de código não encontrado")

    steps = ["código informado"]
    try:
        if len(fields) > 1:
            # Campos segmentados: digitar pelo teclado deixa o componente
            # avançar de caixa sozinho, como faria uma pessoa.
            fields[0].click(timeout=5000)
            page.keyboard.type(code, delay=60)
            steps.append(f"código digitado em {len(fields)} campos")
        else:
            fields[0].click(timeout=5000)
            fields[0].fill(code, timeout=5000)
            steps.append("código preenchido")
    except Exception as exc:
        return LoginOutcome(False, "otp", f"falha ao preencher o código: {exc}", steps)

    # Muitos apps submetem sozinhos ao completar o código.
    try:
        page.wait_for_timeout(1200)
    except Exception:
        pass
    if is_authenticated(page):
        return LoginOutcome(True, "otp", "autenticado por código (auto-submit)", steps)

    for sel in SUBMIT_SELECTORS + ["button:has-text('Verificar'):visible", "button:has-text('Verify'):visible"]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=5000)
                steps.append(f"submetido via {sel}")
                break
        except Exception:
            continue
    else:
        try:
            fields[-1].press("Enter")
            steps.append("submetido via Enter")
        except Exception:
            pass

    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
        page.wait_for_timeout(1200)
    except Exception:
        pass

    if is_authenticated(page):
        return LoginOutcome(True, "otp", "autenticado por código", steps)
    return LoginOutcome(False, "otp", _error_message(page) or "o código não foi aceito", steps)


def follow_magic_link(page: Any, url: str, *, timeout_ms: int = 30000) -> LoginOutcome:
    """Abre o link recebido por e-mail dentro da MESMA sessão do navegador."""
    url = (url or "").strip().strip("<>").strip()
    if not url.startswith(("http://", "https://")):
        return LoginOutcome(False, "magic-link", "isso não parece uma URL http(s)")
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception as exc:
        return LoginOutcome(False, "magic-link", f"não consegui abrir o link: {exc}")
    # Link expirado/já usado costuma responder 4xx com uma página qualquer, que
    # nenhuma heurística de conteúdo distinguiria de um app.
    if response is not None and response.status >= 400:
        return LoginOutcome(
            False,
            "magic-link",
            f"o link retornou HTTP {response.status} — provavelmente expirou ou já foi usado",
        )
    try:
        page.wait_for_timeout(1500)
    except Exception:
        pass
    if is_authenticated(page):
        return LoginOutcome(True, "magic-link", "autenticado pelo link de acesso")
    return LoginOutcome(False, "magic-link", "abri o link, mas a sessão continua deslogada")


def has_login_form(page: Any) -> bool:
    return (
        _first_visible(page, PASSWORD_SELECTORS) is not None
        or _first_visible(page, USER_SELECTORS) is not None
    )


def is_authenticated(page: Any, login_url_seen: str | None = None) -> bool:
    """Sucesso = sumiram os campos de autenticação e a página não é de login.

    A tela de código de uso único não tem campo de senha e muitas vezes nem
    "login" na URL — sem checar o campo de código ela passaria por app logado.
    """
    try:
        if _first_visible(page, PASSWORD_SELECTORS) is not None:
            return False
        if otp_inputs(page):
            return False
    except Exception:
        return False
    return not looks_like_login_page(page)


def attempt_login(
    page: Any,
    username: str,
    password: str | None = None,
    *,
    log=lambda msg: None,
    timeout_ms: int = 15000,
    ask_otp=None,
    ask_magic_link=None,
) -> LoginOutcome:
    """Preenche e submete o formulário de login.

    Cobre quatro fluxos: senha na mesma tela, senha em duas etapas, código de
    uso único (OTP, inclusive como segundo fator) e magic link. Nos dois
    últimos a senha é opcional — o que chega pelo e-mail é pedido no terminal
    via `ask_otp` / `ask_magic_link`.
    """
    steps: list[str] = []
    start_url = page.url

    def resolve_passwordless(kind: str) -> LoginOutcome | None:
        """Trata OTP/magic link; None se não houver como seguir por aqui."""
        if kind == "otp":
            if ask_otp is None:
                return LoginOutcome(False, "auto", "o site pediu um código de verificação", steps)
            code = ask_otp("código enviado para o seu e-mail/telefone")
            if not code:
                return LoginOutcome(False, "otp", "código não informado", steps)
            result = fill_otp(page, code, log=log, timeout_ms=timeout_ms)
            result.steps = steps + result.steps
            return result
        if kind == "magic-link":
            if ask_magic_link is None:
                return LoginOutcome(False, "auto", "o site enviou um link de acesso por e-mail", steps)
            link = ask_magic_link()
            if not link:
                return LoginOutcome(False, "magic-link", "link não informado", steps)
            result = follow_magic_link(page, link, timeout_ms=timeout_ms)
            result.steps = steps + result.steps
            return result
        return None

    blocker = detect_blockers(page)
    if blocker:
        return LoginOutcome(False, "auto", f"bloqueio antes de tentar: {blocker}", steps)

    user_field = _first_visible(page, USER_SELECTORS)
    pass_field = _first_visible(page, PASSWORD_SELECTORS)

    if user_field is None and pass_field is None:
        return LoginOutcome(False, "auto", "nenhum campo de login encontrado", steps)

    if user_field is not None:
        try:
            user_field.click(timeout=5000)
            user_field.fill(username, timeout=5000)
            steps.append("usuário preenchido")
            log("campo de usuário preenchido")
        except Exception as exc:  # campo pode sumir em SPAs
            return LoginOutcome(False, "auto", f"falha ao preencher usuário: {exc}", steps)

    # Fluxo em duas etapas: senha só aparece depois de avançar.
    if pass_field is None:
        advanced = False
        for sel in NEXT_SELECTORS:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=5000)
                    advanced = True
                    steps.append(f"avançou via {sel}")
                    break
            except Exception:
                continue
        if not advanced and user_field is not None:
            try:
                user_field.press("Enter")
                advanced = True
                steps.append("avançou via Enter")
            except Exception:
                pass
        if advanced:
            log("segunda etapa: vendo o que o site pede agora")
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            try:
                page.wait_for_selector(
                    "input[type=password]:visible", timeout=6000, state="visible"
                )
            except Exception:
                pass
            pass_field = _first_visible(page, PASSWORD_SELECTORS)

            if pass_field is None:
                # Sem campo de senha: ou o acesso é sem senha, ou já entrou.
                # A ordem importa: a tela de "verifique seu e-mail" não tem
                # nenhum campo e passaria por app autenticado.
                kind = detect_passwordless(page)
                if not kind and is_authenticated(page):
                    return LoginOutcome(True, "auto", "autenticado só com o e-mail", steps)
                if kind:
                    log(f"acesso sem senha detectado: {kind}")
                    steps.append(f"fluxo sem senha: {kind}")
                    resolved = resolve_passwordless(kind)
                    if resolved is not None:
                        return resolved
                blocker = detect_blockers(page)
                detail = "campo de senha não apareceu após avançar"
                if blocker:
                    detail += f" ({blocker})"
                return LoginOutcome(False, "auto", detail, steps)

    if pass_field is None:
        kind = detect_passwordless(page)
        if kind:
            steps.append(f"fluxo sem senha: {kind}")
            resolved = resolve_passwordless(kind)
            if resolved is not None:
                return resolved
        return LoginOutcome(False, "auto", "campo de senha não encontrado", steps)

    if not password:
        return LoginOutcome(
            False, "auto", "o site pede senha, mas nenhuma foi informada", steps
        )

    try:
        pass_field.click(timeout=5000)
        pass_field.fill(password, timeout=5000)
        steps.append("senha preenchida")
        log("senha preenchida")
    except Exception as exc:
        return LoginOutcome(False, "auto", f"falha ao preencher senha: {exc}", steps)

    submitted = False
    for sel in SUBMIT_SELECTORS:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=5000)
                submitted = True
                steps.append(f"submetido via {sel}")
                break
        except Exception:
            continue
    if not submitted:
        try:
            pass_field.press("Enter")
            submitted = True
            steps.append("submetido via Enter")
        except Exception as exc:
            return LoginOutcome(False, "auto", f"não consegui submeter: {exc}", steps)

    log("aguardando resposta do servidor")
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        pass
    try:
        page.wait_for_timeout(1500)
    except Exception:
        pass

    if is_authenticated(page):
        moved = page.url != start_url
        return LoginOutcome(
            True,
            "auto",
            "autenticado" + (" (navegou para nova URL)" if moved else ""),
            steps,
        )

    # Senha aceita, mas o site pede um segundo fator por código: dá para
    # resolver aqui mesmo, sem cair no fallback manual.
    kind = detect_passwordless(page)
    if kind == "otp":
        log("segundo fator por código detectado")
        steps.append("2FA por código")
        resolved = resolve_passwordless(kind)
        if resolved is not None:
            return resolved

    blocker = detect_blockers(page)
    if blocker:
        return LoginOutcome(False, "auto", f"após submeter: {blocker}", steps)

    error = _error_message(page)
    return LoginOutcome(False, "auto", error or "ainda na tela de login após submeter", steps)


def _error_message(page: Any) -> str | None:
    for sel in ("[role=alert]", ".error", ".alert-danger", "[class*='error' i]"):
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                txt = (loc.inner_text(timeout=2000) or "").strip()
                if txt:
                    return txt[:160]
        except Exception:
            continue
    return None
