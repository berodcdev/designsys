"""Fluxo de login contra um app de mentira servido em localhost.

Cobre as três camadas: detecção de formulário, login automático (inclusive em
duas etapas), persistência da sessão no profile dir e acionamento do fallback
manual quando a detecção falha.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from designsys.browser import login as loginmod
from designsys.browser.session import BrowserSession, profile_dir_for
from designsys.util.report import Reporter

SESSION_COOKIE = "designsys_test_session=ok"
GOOD_USER = "pessoa@exemplo.com"
GOOD_PASS = "s3nh4-secreta"

PAGE_STYLE = """
<style>
  :root { --color-primary: #7c3aed; --space-4: 16px; }
  body { background: #fbfaff; color: #1c1917; font-family: Inter, sans-serif; margin: 0; }
  .btn { background: #7c3aed; color: #fff; border: 0; border-radius: 8px;
         padding: 12px 20px; font-size: 15px; font-weight: 600; }
  .card { background: #fff; border: 1px solid #e7e5e4; border-radius: 12px;
          padding: 16px; box-shadow: 0 1px 3px rgba(28, 25, 23, 0.08); }
  input { border: 1px solid #d6d3d1; border-radius: 6px; padding: 10px 12px; font-size: 14px; }
</style>
"""

LOGIN_FORM = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Acesso</title>{PAGE_STYLE}</head><body>
<h1>Bem-vindo de volta</h1>
<form method="POST" action="/acesso">
  <input type="email" name="email" placeholder="seu e-mail">
  <input type="password" name="password" placeholder="sua senha">
  <button type="submit" class="btn">Entrar</button>
</form>
</body></html>"""

LOGIN_ERROR = LOGIN_FORM.replace(
    "<h1>Bem-vindo de volta</h1>",
    '<h1>Bem-vindo de volta</h1><div role="alert">Credenciais inválidas</div>',
)

STEP_EMAIL = f"""<!doctype html><html><head><meta charset="utf-8"><title>Acesso</title>{PAGE_STYLE}</head><body>
<h1>Entrar</h1>
<form method="GET" action="/duas-etapas">
  <input type="email" name="email" placeholder="e-mail">
  <button type="submit" class="btn">Continuar</button>
</form></body></html>"""

STEP_PASSWORD = f"""<!doctype html><html><head><meta charset="utf-8"><title>Senha</title>{PAGE_STYLE}</head><body>
<h1>Sua senha</h1>
<form method="POST" action="/acesso">
  <input type="password" name="password" placeholder="senha">
  <button type="submit" class="btn">Entrar</button>
</form></body></html>"""

GOOD_CODE = "483920"

# Só e-mail: o site manda um código.
OTP_EMAIL = f"""<!doctype html><html><head><meta charset="utf-8"><title>Acesso</title>{PAGE_STYLE}</head><body>
<h1>Entrar</h1>
<form method="GET" action="/otp">
  <input type="email" name="email" placeholder="e-mail">
  <button type="submit" class="btn">Continuar</button>
</form></body></html>"""

# Código segmentado, um dígito por caixa.
OTP_CODE = f"""<!doctype html><html><head><meta charset="utf-8"><title>Código</title>{PAGE_STYLE}</head><body>
<h1>Digite o código de verificação</h1>
<p>Enviamos um código de acesso para o seu e-mail.</p>
<form method="POST" action="/otp">
  <input name="d1" maxlength="1" inputmode="numeric" autocomplete="one-time-code">
  <input name="d2" maxlength="1" inputmode="numeric">
  <input name="d3" maxlength="1" inputmode="numeric">
  <input name="d4" maxlength="1" inputmode="numeric">
  <input name="d5" maxlength="1" inputmode="numeric">
  <input name="d6" maxlength="1" inputmode="numeric">
  <button type="submit" class="btn">Verificar</button>
</form>
<script>
  // Avança de caixa sozinho, como os componentes de OTP de verdade.
  const inputs = [...document.querySelectorAll('input[maxlength="1"]')];
  inputs.forEach((el, i) => el.addEventListener('input', () => {{
    if (el.value && inputs[i + 1]) inputs[i + 1].focus();
  }}));
</script>
</body></html>"""

MAGIC_SENT = f"""<!doctype html><html><head><meta charset="utf-8"><title>Verifique seu e-mail</title>{PAGE_STYLE}</head><body>
<h1>Verifique seu e-mail</h1>
<p>Enviamos um link de acesso para você. Clique no link para entrar.</p>
</body></html>"""

CHALLENGE = f"""<!doctype html><html><head><meta charset="utf-8"><title>Verificação</title>{PAGE_STYLE}</head><body>
<h1>Confirme que você é humano</h1>
<div class="g-recaptcha" data-sitekey="abc"></div>
<input type="password" name="password" placeholder="senha">
<button type="submit" class="btn">Entrar</button>
</body></html>"""

APP = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Painel</title>{PAGE_STYLE}</head><body>
<nav><a href="/painel">Painel</a> <a href="/painel/config">Configurações</a></nav>
<h1>Painel</h1>
<div class="card"><p>Você está autenticado.</p>
<button class="btn">Ação primária</button>
<input type="text" placeholder="buscar"></div>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silencia o log do servidor nos testes
        pass

    def _send(self, body: str, status: int = 200, headers: dict[str, str] | None = None):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def _authenticated(self) -> bool:
        return SESSION_COOKIE in (self.headers.get("Cookie") or "")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/painel", "/painel/config"):
            if self._authenticated():
                self._send(APP)
            else:
                self._send("", 302, {"Location": "/acesso"})
        elif path == "/acesso":
            self._send(LOGIN_ERROR if "erro" in parsed.query else LOGIN_FORM)
        elif path == "/duas-etapas":
            query = parse_qs(parsed.query)
            self._send(STEP_PASSWORD if query.get("email") else STEP_EMAIL)
        elif path == "/otp":
            query = parse_qs(parsed.query)
            self._send(OTP_CODE if query.get("email") else OTP_EMAIL)
        elif path == "/magico":
            query = parse_qs(parsed.query)
            if query.get("email"):
                self._send(MAGIC_SENT)
            else:
                self._send(OTP_EMAIL.replace("/otp", "/magico"))
        elif path == "/magico/confirmar":
            token = (parse_qs(parsed.query).get("token") or [""])[0]
            if token == "token-valido":
                self._send("", 302, {"Location": "/painel", "Set-Cookie": f"{SESSION_COOKIE}; Path=/"})
            else:
                self._send("<html><body>Link inválido</body></html>", 403)
        elif path == "/desafio":
            self._send(CHALLENGE)
        else:
            self._send("<html><body>404</body></html>", 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8"))

        if urlparse(self.path).path == "/otp":
            digits = "".join((form.get(f"d{i}") or [""])[0] for i in range(1, 7))
            if digits == GOOD_CODE:
                self._send("", 302, {"Location": "/painel", "Set-Cookie": f"{SESSION_COOKIE}; Path=/"})
            else:
                self._send("", 302, {"Location": "/otp?email=1&erro=1"})
            return

        email = (form.get("email") or [""])[0]
        password = (form.get("password") or [""])[0]
        # No fluxo em duas etapas o e-mail veio na etapa anterior.
        ok = password == GOOD_PASS and (email in ("", GOOD_USER))
        if ok:
            self._send(
                "", 302, {"Location": "/painel", "Set-Cookie": f"{SESSION_COOKIE}; Path=/"}
            )
        else:
            self._send("", 302, {"Location": "/acesso?erro=1"})


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def isolated_profiles(tmp_path, monkeypatch):
    """Nenhum teste pode encostar em ~/.designsys."""
    root = tmp_path / "profiles"
    monkeypatch.setattr("designsys.browser.session.PROFILE_ROOT", root)
    return root


@pytest.fixture
def session(server, isolated_profiles):
    s = BrowserSession("localhost-teste", headed=False, timeout_ms=15000)
    s.start()
    yield s
    s.close()


# ============================================================== detecção
class TestDeteccao:
    def test_reconhece_tela_de_login_pelo_formulario(self, session, server):
        session.goto(f"{server}/acesso")
        assert loginmod.looks_like_login_page(session.page)
        assert loginmod.has_login_form(session.page)

    def test_redirect_para_login_e_detectado(self, session, server):
        session.goto(f"{server}/painel")  # sem cookie -> redireciona
        assert loginmod.looks_like_login_page(session.page)

    def test_pagina_de_app_nao_e_login(self, session, server):
        session.goto(f"{server}/acesso")
        loginmod.attempt_login(session.page, GOOD_USER, GOOD_PASS)
        session.goto(f"{server}/painel")
        assert not loginmod.looks_like_login_page(session.page)
        assert loginmod.is_authenticated(session.page)

    def test_detecta_captcha_como_bloqueio(self, session, server):
        session.goto(f"{server}/desafio")
        assert loginmod.detect_blockers(session.page) == "captcha detectado"


# ========================================================= login automático
class TestLoginAutomatico:
    def test_preenche_submete_e_autentica(self, session, server):
        session.goto(f"{server}/acesso")
        outcome = loginmod.attempt_login(session.page, GOOD_USER, GOOD_PASS)
        assert outcome.ok, outcome.detail
        assert outcome.method == "auto"
        assert "usuário preenchido" in outcome.steps
        assert "senha preenchida" in outcome.steps
        assert "/painel" in session.page.url

    def test_credenciais_erradas_falham_com_mensagem_do_site(self, session, server):
        session.goto(f"{server}/acesso")
        outcome = loginmod.attempt_login(session.page, GOOD_USER, "senha-errada")
        assert not outcome.ok
        assert "inválidas" in outcome.detail.lower()

    def test_fluxo_em_duas_etapas(self, session, server):
        session.goto(f"{server}/duas-etapas")
        outcome = loginmod.attempt_login(session.page, GOOD_USER, GOOD_PASS)
        assert outcome.ok, outcome.detail
        assert any("avançou" in step for step in outcome.steps)

    def test_nao_tenta_quando_ha_captcha(self, session, server):
        session.goto(f"{server}/desafio")
        outcome = loginmod.attempt_login(session.page, GOOD_USER, GOOD_PASS)
        assert not outcome.ok
        assert "captcha" in outcome.detail

    def test_sem_formulario_reporta_claramente(self, session, server):
        session.goto(f"{server}/nao-existe")
        outcome = loginmod.attempt_login(session.page, GOOD_USER, GOOD_PASS)
        assert not outcome.ok
        assert "nenhum campo de login" in outcome.detail


# ================================================= acesso sem senha (OTP)
class TestSemSenha:
    def test_detecta_tela_de_codigo(self, session, server):
        session.goto(f"{server}/otp?email=1")
        assert loginmod.detect_passwordless(session.page) == "otp"
        assert len(loginmod.otp_inputs(session.page)) == 6

    def test_detecta_magic_link(self, session, server):
        session.goto(f"{server}/magico?email=1")
        assert loginmod.detect_passwordless(session.page) == "magic-link"

    def test_login_so_com_email_mais_codigo(self, session, server):
        """O fluxo inteiro: e-mail -> código de 6 dígitos -> autenticado."""
        session.goto(f"{server}/otp")
        pedidos = []

        outcome = loginmod.attempt_login(
            session.page,
            GOOD_USER,
            password=None,
            ask_otp=lambda hint: (pedidos.append(hint), GOOD_CODE)[1],
        )

        assert outcome.ok, outcome.detail
        assert outcome.method == "otp"
        assert pedidos, "deveria ter pedido o código ao usuário"
        assert "/painel" in session.page.url

    def test_codigo_errado_reporta_falha(self, session, server):
        session.goto(f"{server}/otp")
        outcome = loginmod.attempt_login(session.page, GOOD_USER, None, ask_otp=lambda h: "000000")
        assert not outcome.ok

    def test_codigo_segmentado_preenchido_digito_a_digito(self, session, server):
        session.goto(f"{server}/otp?email=1")
        loginmod.fill_otp(session.page, GOOD_CODE)
        assert "/painel" in session.page.url

    def test_codigo_aceita_formatacao_do_usuario(self, session, server):
        session.goto(f"{server}/otp?email=1")
        assert loginmod.fill_otp(session.page, " 483-920 ").ok

    def test_sem_callback_de_otp_reporta_o_motivo(self, session, server):
        session.goto(f"{server}/otp")
        outcome = loginmod.attempt_login(session.page, GOOD_USER, None)
        assert not outcome.ok
        assert "código" in outcome.detail

    def test_magic_link_colado_autentica_na_mesma_sessao(self, session, server):
        session.goto(f"{server}/magico")
        outcome = loginmod.attempt_login(
            session.page,
            GOOD_USER,
            None,
            ask_magic_link=lambda: f"{server}/magico/confirmar?token=token-valido",
        )
        assert outcome.ok, outcome.detail
        assert outcome.method == "magic-link"
        assert loginmod.is_authenticated(session.page)

    def test_magic_link_invalido_nao_autentica(self, session, server):
        session.goto(f"{server}/magico")
        outcome = loginmod.attempt_login(
            session.page, GOOD_USER, None, ask_magic_link=lambda: f"{server}/magico/confirmar?token=xx"
        )
        assert not outcome.ok

    def test_link_que_nao_e_url_e_rejeitado(self, session, server):
        session.goto(f"{server}/magico?email=1")
        assert not loginmod.follow_magic_link(session.page, "não é link").ok

    def test_site_com_senha_avisa_quando_ela_falta(self, session, server):
        session.goto(f"{server}/acesso")
        outcome = loginmod.attempt_login(session.page, GOOD_USER, None)
        assert not outcome.ok
        assert "senha" in outcome.detail

    def test_extracao_ponta_a_ponta_com_otp(self, server, isolated_profiles, tmp_path):
        from designsys.extractors.web import WebExtractor, WebOptions

        class _OtpReporter(Reporter):
            def ask_credentials(self, url):
                return (GOOD_USER, "")  # sem senha: só e-mail

            def ask_otp(self, hint):
                return GOOD_CODE

        ds = WebExtractor(
            WebOptions(url=f"{server}/otp", login=True, pages=0, out=tmp_path, no_assets=True),
            _OtpReporter(),
        ).run()

        assert ds.raw["login"]["ok"] is True
        assert ds.raw["login"]["method"] == "otp"
        assert "#7c3aed" in {c["hex"] for c in ds.colors["clusters"]}


# ======================================================= sessão persistente
class TestSessaoPersistente:
    def test_cookie_sobrevive_ao_fechar_o_navegador(self, server, isolated_profiles):
        primeira = BrowserSession("persistencia-teste", headed=False, timeout_ms=15000)
        primeira.start()
        try:
            primeira.goto(f"{server}/acesso")
            assert loginmod.attempt_login(primeira.page, GOOD_USER, GOOD_PASS).ok
            profile = profile_dir_for("persistencia-teste")
            assert profile.exists()
        finally:
            primeira.close()

        segunda = BrowserSession("persistencia-teste", headed=False, timeout_ms=15000)
        segunda.start()
        try:
            segunda.goto(f"{server}/painel")
            # Sem novo login: a sessão veio do profile dir.
            assert loginmod.is_authenticated(segunda.page)
            assert "/painel" in segunda.page.url
        finally:
            segunda.close()

    def test_perfis_ficam_isolados_por_dominio(self, server, isolated_profiles):
        outra = BrowserSession("outro-dominio-teste", headed=False, timeout_ms=15000)
        outra.start()
        try:
            outra.goto(f"{server}/painel")
            assert loginmod.looks_like_login_page(outra.page)  # não herdou a sessão
        finally:
            outra.close()

    def test_profile_dir_derivado_do_dominio(self, isolated_profiles):
        assert profile_dir_for("app.exemplo.com").name == "app.exemplo.com"
        assert "/" not in profile_dir_for("a/b").name


# =========================================================== fallback manual
class _FakeSession:
    """Dublê que registra o que o extractor tentou fazer com o navegador."""

    def __init__(self, page, headed=False):
        self.page = page
        self.headed = headed
        self.restarts: list[bool] = []
        self.settled = 0

    def restart(self, *, headed: bool):
        self.restarts.append(headed)
        self.headed = headed

    def settle(self, *args, **kwargs):
        self.settled += 1


class _SpyReporter(Reporter):
    def __init__(self, aceitar=True):
        self.aceitar = aceitar
        self.manual_calls = 0
        self.warnings: list[str] = []
        self.steps: list[str] = []

    def step(self, message):
        self.steps.append(message)

    def warn(self, message):
        self.warnings.append(message)

    def ask_manual_login(self, url):
        self.manual_calls += 1
        return self.aceitar

    def ask_credentials(self, url):
        return (GOOD_USER, "senha-errada")


class TestFallbackManual:
    def _extractor(self, server, reporter):
        from designsys.extractors.web import WebExtractor, WebOptions

        options = WebOptions(url=f"{server}/acesso", login=True, pages=0)
        return WebExtractor(options, reporter)

    def test_login_automatico_falho_aciona_navegador_visivel(self, session, server):
        """Credenciais erradas: precisa abrir headed e pedir login manual."""
        session.goto(f"{server}/acesso")
        reporter = _SpyReporter(aceitar=True)
        extractor = self._extractor(server, reporter)
        fake = _FakeSession(session.page, headed=False)

        extractor._handle_login(fake)

        assert fake.restarts == [True], "o navegador deveria ter reaberto visível"
        assert reporter.manual_calls == 1
        assert extractor.login_result.method == "manual"
        assert any("não concluiu" in w for w in reporter.warnings)

    def test_captcha_pula_direto_para_o_manual(self, session, server):
        session.goto(f"{server}/desafio")
        reporter = _SpyReporter(aceitar=True)
        extractor = self._extractor(server, reporter)
        fake = _FakeSession(session.page, headed=False)

        extractor._handle_login(fake)

        assert reporter.manual_calls == 1
        assert fake.restarts == [True]

    def test_ja_headed_nao_reabre_o_navegador(self, session, server):
        session.goto(f"{server}/acesso")
        reporter = _SpyReporter(aceitar=True)
        extractor = self._extractor(server, reporter)
        fake = _FakeSession(session.page, headed=True)

        extractor._handle_login(fake)

        assert fake.restarts == []
        assert reporter.manual_calls == 1

    def test_usuario_pode_abortar_o_login_manual(self, session, server):
        session.goto(f"{server}/acesso")
        reporter = _SpyReporter(aceitar=False)
        extractor = self._extractor(server, reporter)

        extractor._handle_login(_FakeSession(session.page))

        assert extractor.login_result.ok is False
        assert "cancelado" in extractor.ds.warnings[0]


# ============================================================ ponta a ponta
class TestExtracaoAutenticada:
    def test_extrai_tokens_de_dentro_do_app(self, server, isolated_profiles, tmp_path):
        """O teste que importa: logar e sair com os tokens do app protegido."""
        from designsys.extractors.web import WebExtractor, WebOptions

        class _Creds(Reporter):
            def ask_credentials(self, url):
                return (GOOD_USER, GOOD_PASS)

        options = WebOptions(
            url=f"{server}/painel",
            login=True,
            pages=1,
            out=tmp_path,
            no_assets=True,
        )
        ds = WebExtractor(options, _Creds()).run()

        assert ds.raw["login"]["ok"] is True
        assert ds.raw["login"]["method"] == "auto"
        hexes = {c["hex"] for c in ds.colors["clusters"]}
        assert "#7c3aed" in hexes, "a cor primária do app protegido não foi extraída"
        assert ds.colors["roles"]["primary"]["hex"] == "#7c3aed"
        assert any("Inter" in f["family"] for f in ds.typography["families"])
        assert "--color-primary" in ds.css_variables
        assert any(c.kind.startswith("button") for c in ds.components)
