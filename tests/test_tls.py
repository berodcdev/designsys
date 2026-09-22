"""O padrão é validar o certificado; --insecure desliga isso nas duas pontas.

A ferramenta digita senha em sistemas autenticados, e antes aceitava qualquer
certificado — inclusive na execução do `--login`. Estes testes existem para que
isso não volte por descuido: o default é a garantia, não a flag.

Nenhum navegador é aberto aqui. `BrowserSession.__init__` só guarda a opção; o
Chromium só sobe em `start()`.
"""

from __future__ import annotations

from designsys.browser.session import BrowserSession, _friendly_nav_error
from designsys.extractors.web import WebOptions
from designsys.util import net


class TestPadraoSeguro:
    def test_sessao_valida_certificado_por_padrao(self):
        assert BrowserSession("exemplo.com").insecure is False

    def test_opcoes_de_extracao_validam_por_padrao(self):
        assert WebOptions(url="https://exemplo.com").insecure is False

    def test_downloads_validam_por_padrao(self):
        assert net._session.verify is True


class TestInsecure:
    def test_sessao_aceita_a_opcao(self):
        assert BrowserSession("exemplo.com", insecure=True).insecure is True

    def test_downloads_seguem_a_opcao(self):
        """Navegador e downloads diretos precisam concordar.

        O CSS bloqueado por CORS e os assets são baixados por HTTP, fora do
        navegador: se só o navegador relaxasse, a flag não resolveria o ambiente
        que ela existe para atender.
        """
        try:
            net.set_insecure(True)
            assert net._session.verify is False
        finally:
            net.set_insecure(False)
        assert net._session.verify is True


class TestMensagem:
    def test_erro_de_certificado_sugere_a_flag(self):
        msg = _friendly_nav_error(
            "https://interno.exemplo.com",
            Exception("net::ERR_CERT_AUTHORITY_INVALID at https://interno.exemplo.com"),
        )
        assert "certificado TLS inválido" in msg
        assert "--insecure" in msg
