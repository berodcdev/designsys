"""Extração multi-contexto: tema escuro, viewports e saturação do crawl.

O site de mentira servido aqui tem as três formas de tema escuro (preferência do
sistema, classe na raiz e botão próprio), tipografia que muda por media query e
um botão sem foco visível — assim cada mecanismo é exercitado sem depender da
internet.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pytest

from designsys.extractors import themes as thememod
from designsys.extractors.buckets import DARK, VIEWPORTS, TokenBucket, color_fingerprint
from designsys.util.report import Reporter

# --------------------------------------------------------------- páginas
BASE_CSS = """
:root {
  --color-bg: #ffffff;
  --color-text: #101418;
  --color-primary: #3b5bdb;
  --color-surface: #f1f3f5;
}
body {
  margin: 0; background: var(--color-bg); color: var(--color-text);
  font-family: Inter, sans-serif; font-size: 16px;
}
h1 { font-size: 56px; font-weight: 700; margin: 24px; }
p  { font-size: 16px; margin: 16px 24px; }
.card {
  background: var(--color-surface); border: 1px solid #dee2e6;
  border-radius: 12px; padding: 24px; margin: 24px;
}
.btn {
  background: var(--color-primary); color: #ffffff; border: 0;
  border-radius: 8px; padding: 12px 24px; font-size: 16px; font-weight: 600;
}
.btn:hover { background: #364fc7; }
/* Apaga o foco do navegador sem pôr nada no lugar — o erro clássico que o
   diagnóstico precisa apontar. */
.btn:focus, .btn:focus-visible { outline: none; }
.baixo-contraste { color: #b8c0c8; background: #ffffff; font-size: 14px; }
@media (max-width: 700px) {
  h1 { font-size: 32px; }
  p  { font-size: 14px; }
  .card { padding: 12px; margin: 12px; }
}
"""

DARK_MEDIA = """
@media (prefers-color-scheme: dark) {
  :root {
    --color-bg: #0b0f14;
    --color-text: #e9edf1;
    --color-surface: #161b22;
  }
  .card { border-color: #2b333c; }
}
"""

DARK_CLASS = """
html.dark {
  --color-bg: #0b0f14;
  --color-text: #e9edf1;
  --color-surface: #161b22;
}
"""

CORPO = """
<h1>Título da página</h1>
<p>Um parágrafo de texto normal, com tamanho de corpo.</p>
<p class="baixo-contraste">Texto de baixo contraste, propositalmente ruim.</p>
<div class="card"><h2>Um cartão</h2><p>Conteúdo do cartão.</p>
<button class="btn">Ação principal</button>
<input type="text" placeholder="Digite algo"></div>
<a href="/outra">Ir para outra página</a>
"""


def _pagina(extra_css: str, extra_html: str = "", titulo: str = "Teste") -> str:
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>{titulo}</title><style>{BASE_CSS}{extra_css}</style></head>
<body>{CORPO}{extra_html}</body></html>"""


TOGGLE_HTML = """
<button id="tema" aria-label="Alternar tema">tema</button>
<script>
  document.getElementById('tema').addEventListener('click', () => {
    document.documentElement.classList.toggle('dark');
  });
</script>
"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, body: str):
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        caminho = urlparse(self.path).path
        if caminho in ("/", "/media"):
            self._send(_pagina(DARK_MEDIA))
        elif caminho == "/classe":
            self._send(_pagina(DARK_CLASS))
        elif caminho == "/toggle":
            self._send(_pagina(DARK_CLASS, TOGGLE_HTML))
        elif caminho == "/sem-tema":
            self._send(_pagina(""))
        elif caminho == "/outra":
            self._send(_pagina(DARK_MEDIA, titulo="Outra"))
        else:
            self._send(_pagina(""))


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
    monkeypatch.setattr("designsys.browser.session.PROFILE_ROOT", tmp_path / "profiles")


@pytest.fixture
def session(server, isolated_profiles):
    from designsys.browser.session import BrowserSession

    s = BrowserSession("temas-teste", headed=False, timeout_ms=15000)
    s.start()
    yield s
    s.close()


def _extrair(url: str, tmp_path, **kwargs):
    from designsys.extractors.web import WebExtractor, WebOptions

    opcoes = WebOptions(url=url, pages=0, out=tmp_path, no_assets=True, **kwargs)
    return WebExtractor(opcoes, Reporter()).run()


# ================================================================== temas
class TestDeteccaoDeTema:
    def test_prefers_color_scheme(self, session, server):
        session.goto(f"{server}/media")
        tentativa = thememod.apply_dark(session.page)
        assert tentativa.ok
        assert tentativa.strategy == "prefers-color-scheme"

    def test_classe_na_raiz(self, session, server):
        session.goto(f"{server}/classe")
        tentativa = thememod.apply_dark(session.page)
        assert tentativa.ok
        # `prefers-color-scheme` não muda esta página; a classe muda.
        assert tentativa.strategy == "class"

    def test_site_sem_tema_escuro_nao_inventa(self, session, server):
        session.goto(f"{server}/sem-tema")
        assert not thememod.apply_dark(session.page).ok

    def test_restaurar_volta_ao_claro(self, session, server):
        session.goto(f"{server}/classe")
        thememod.apply_dark(session.page)
        thememod.restore_light(session.page)
        classes = session.page.evaluate("() => document.documentElement.className")
        assert "dark" not in classes


class TestExtracaoComTema:
    def test_tokens_dos_dois_temas(self, server, isolated_profiles, tmp_path):
        ds = _extrair(f"{server}/media", tmp_path)

        assert ds.has_dark, ds.themes.get("detection")
        pares = ds.themes["pairs"]
        assert pares["background"]["light"].lower() == "#ffffff"
        assert pares["background"]["dark"].lower() == "#0b0f14"
        assert pares["text"]["light"] != pares["text"]["dark"]

    def test_desligar_o_tema_escuro(self, server, isolated_profiles, tmp_path):
        ds = _extrair(f"{server}/media", tmp_path, no_dark=True)
        assert not ds.has_dark

    def test_sem_tema_escuro_o_relatorio_diz(self, server, isolated_profiles, tmp_path):
        ds = _extrair(f"{server}/sem-tema", tmp_path)
        assert not ds.has_dark
        assert ds.themes["detection"]["dark"] is False

    def test_css_gerado_traz_os_dois_temas(self, server, isolated_profiles, tmp_path):
        from designsys.output.css import build_variables_css

        css = build_variables_css(_extrair(f"{server}/media", tmp_path))
        assert "@media (prefers-color-scheme: dark)" in css
        assert '[data-theme="dark"]' in css
        assert "#0b0f14" in css


# ============================================================== viewports
class TestResponsivo:
    def test_escala_muda_entre_telas(self, server, isolated_profiles, tmp_path):
        ds = _extrair(f"{server}/media", tmp_path)

        fluidos = ds.responsive.get("fluid") or {}
        assert "h1" in fluidos, fluidos
        assert fluidos["h1"]["mobile"] == 32.0
        assert fluidos["h1"]["desktop"] == 56.0

    def test_desligar_viewports(self, server, isolated_profiles, tmp_path):
        ds = _extrair(f"{server}/media", tmp_path, viewports=False)
        assert not ds.responsive

    def test_clamp_no_css(self, server, isolated_profiles, tmp_path):
        from designsys.output.css import build_variables_css

        css = build_variables_css(_extrair(f"{server}/media", tmp_path))
        assert "clamp(" in css and "--text-h1-fluid" in css


# ============================================================ diagnóstico
class TestDiagnosticoPontaAPonta:
    def test_contraste_ruim_e_apontado(self, server, isolated_profiles, tmp_path):
        ds = _extrair(f"{server}/media", tmp_path)

        falhas = ds.diagnostics["accessibility"]["contrast"]
        assert falhas, "o texto de baixo contraste deveria ter sido pego"
        assert any(i["fg"].lower() == "#b8c0c8" for i in falhas)

    def test_foco_invisivel_e_apontado(self, server, isolated_profiles, tmp_path):
        """O CSS de teste faz `outline: none` no botão e não repõe nada."""
        ds = _extrair(f"{server}/media", tmp_path)
        sem_foco = ds.diagnostics["accessibility"]["focusMissing"]
        assert any(k.startswith("button") for k in sem_foco), sem_foco

    def test_foco_do_navegador_conta_como_visivel(self, server, isolated_profiles, tmp_path):
        """O input não mexe no outline: o do navegador basta, e não é apontado."""
        ds = _extrair(f"{server}/media", tmp_path)
        assert "input" not in ds.diagnostics["accessibility"]["focusMissing"]

    def test_notas_vem_com_as_parcelas(self, server, isolated_profiles, tmp_path):
        diag = _extrair(f"{server}/media", tmp_path).diagnostics
        assert 0 <= diag["score"] <= 100
        assert diag["accessibility"]["breakdown"]
        assert diag["consistency"]["breakdown"]

    def test_assinatura_descreve_o_sistema(self, server, isolated_profiles, tmp_path):
        assinatura = _extrair(f"{server}/media", tmp_path).diagnostics["signature"]
        assert len(assinatura["axes"]) == 5
        assert assinatura["sentence"].startswith("Sistema")


# ================================================================ buckets
class TestBuckets:
    def test_merge_separa_contextos(self):
        claro = TokenBucket(name="light")
        escuro = TokenBucket(name=DARK)
        claro.merge_page({"colors": {"color": {"#fff": 3}}, "spacing": {"padding": {"8px": 2}}})
        escuro.merge_page({"colors": {"color": {"#000": 3}}})
        assert claro.colors_by_prop["color"]["#fff"] == 3
        assert "#fff" not in escuro.colors_by_prop["color"]

    def test_modo_light_ignora_cores(self):
        bucket = TokenBucket(name="mobile")
        bucket.merge_page(
            {"colors": {"color": {"#fff": 3}}, "spacing": {"padding": {"8px": 2}}}, light=True
        )
        assert not bucket.colors_by_prop
        assert bucket.spacing["8px"] == 2

    def test_assinatura_cresce_com_novidade(self):
        bucket = TokenBucket()
        bucket.merge_page({"colors": {"color": {"#fff": 1}}})
        antes = len(bucket.token_signature())
        bucket.merge_page({"colors": {"color": {"#000": 1}}})
        assert len(bucket.token_signature()) > antes

    def test_fingerprint_detecta_paleta_igual(self):
        a, b = TokenBucket(), TokenBucket()
        a.merge_page({"colors": {"color": {"#fff": 2}}})
        b.merge_page({"colors": {"color": {"#fff": 9}}})
        assert color_fingerprint(a) == color_fingerprint(b)

    def test_viewports_declarados(self):
        assert set(VIEWPORTS) == {"mobile", "tablet"}
        assert VIEWPORTS["mobile"]["width"] < VIEWPORTS["tablet"]["width"]
