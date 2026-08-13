"""Superfície da CLI: help, validações e mensagens de erro humanas."""

import pytest
from typer.testing import CliRunner

from designsys.cli import _normalize_url, app

runner = CliRunner()


def saida(result) -> str:
    """stdout + stderr — mensagens de erro saem por stderr, como deve ser."""
    texto = result.stdout or ""
    try:
        texto += result.stderr or ""
    except ValueError:
        pass
    return texto


class TestHelp:
    def test_help_geral_lista_comandos(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ("url", "repo", "open", "pdf", "doctor"):
            assert cmd in result.stdout

    def test_help_geral_traz_exemplos(self):
        assert "designsys url stripe.com" in runner.invoke(app, ["--help"]).stdout

    def test_help_geral_lista_o_que_e_gerado(self):
        out = runner.invoke(app, ["--help"]).stdout
        for arquivo in ("design-system.pdf", "tokens.json", "variables.css", "tailwind.config.js"):
            assert arquivo in out

    def test_help_geral_explica_o_login(self):
        out = runner.invoke(app, ["--help"]).stdout
        for camada in ("sessão salva", "magic link", "manual"):
            assert camada in out

    def test_help_agrupa_os_exemplos(self):
        out = runner.invoke(app, ["--help"]).stdout
        for grupo in ("extrair", "ajustar a extração", "depois da extração"):
            assert grupo in out

    def test_help_mostra_os_comandos_e_flags_novos(self):
        out = runner.invoke(app, ["--help"]).stdout
        for trecho in ("audit", "--exhaustive", "--no-dark", "--no-viewports"):
            assert trecho in out

    def test_help_descreve_o_que_e_analisado(self):
        out = runner.invoke(app, ["--help"]).stdout
        for assunto in ("tema claro e escuro", "escala responsiva", "diagnóstico", "assinatura visual"):
            assert assunto in out

    def test_sem_argumentos_mostra_o_mesmo_menu(self):
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "COMANDOS" in result.stdout

    def test_argumento_com_colchetes_nao_some_no_markup(self):
        """`[caminho]` seria interpretado como markup do Rich e sumiria."""
        assert "[caminho]" in runner.invoke(app, ["--help"]).stdout


class TestBannerDoMenu:
    def test_gradiente_tem_cor_em_cada_bloco(self):
        """`mix()` em OKLab devolve cor no espaço OKLab; sem converter para
        sRGB o Rich descarta o estilo em silêncio e a barra sai cinza."""
        from designsys.cli import _gradiente

        faixa = _gradiente(24)
        assert len(faixa.spans) == 24
        estilos = [str(s.style) for s in faixa.spans]
        assert all(e.startswith("#") and len(e) == 7 for e in estilos), estilos

    def test_gradiente_interpola_entre_as_cores(self):
        from designsys.cli import BANNER_COLORS, _gradiente

        faixa = _gradiente(30)
        estilos = [str(s.style) for s in faixa.spans]
        assert estilos[0].lower() == BANNER_COLORS[0].lower()
        # tons intermediários que não estão na paleta original
        assert any(e.lower() not in [c.lower() for c in BANNER_COLORS] for e in estilos)

    def test_gradiente_com_largura_minima(self):
        from designsys.cli import _gradiente

        assert len(_gradiente(1).spans) >= 1

    @pytest.mark.parametrize("cmd", ["url", "repo", "open", "doctor"])
    def test_help_de_cada_comando(self, cmd):
        result = runner.invoke(app, [cmd, "--help"])
        assert result.exit_code == 0
        assert "Exemplos" in result.stdout or "exemplo" in result.stdout.lower()

    def test_url_documenta_opcoes_principais(self):
        """As opções existem no comando.

        Verificado por introspecção do Click, não pelo texto renderizado: o
        painel do Rich muda de forma conforme a largura e o ambiente, e um teste
        que depende disso passa na sua máquina e falha no CI.
        """
        from typer.main import get_command

        comando = get_command(app).commands["url"]
        declaradas = {opcao for parametro in comando.params for opcao in parametro.opts}
        esperadas = {
            "--login", "--user", "--pass", "--pages", "--path", "--out",
            "--no-assets", "--no-pdf", "--no-dark", "--no-viewports",
            "--exhaustive", "--headed", "--verbose", "--timeout",
        }
        assert esperadas <= declaradas, f"faltando: {esperadas - declaradas}"

    def test_url_help_renderiza(self):
        """O help sai inteiro, com uso e exemplos."""
        resultado = runner.invoke(app, ["url", "--help"])
        assert resultado.exit_code == 0
        assert "Usage" in resultado.stdout or "designsys url" in resultado.stdout
        assert "Exemplos" in resultado.stdout

    def test_versao(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0 and "designsys" in result.stdout


class TestNormalizeUrl:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("stripe.com", "https://stripe.com"),
            ("https://stripe.com", "https://stripe.com"),
            ("http://a.com/x", "http://a.com/x"),
            ("  stripe.com  ", "https://stripe.com"),
        ],
    )
    def test_completa_esquema(self, entrada, esperado):
        assert _normalize_url(entrada) == esperado

    def test_aceita_localhost_com_porta(self):
        assert _normalize_url("http://localhost:8000") == "http://localhost:8000"


class TestErros:
    def test_repo_com_caminho_inexistente(self, tmp_path):
        result = runner.invoke(app, ["repo", str(tmp_path / "nao-existe")])
        assert result.exit_code == 1
        assert "não encontrado" in saida(result)
        assert "Traceback" not in saida(result)

    def test_repo_apontando_para_arquivo(self, tmp_path):
        arquivo = tmp_path / "a.txt"
        arquivo.write_text("x")
        result = runner.invoke(app, ["repo", str(arquivo)])
        assert result.exit_code == 1
        assert "não é um diretório" in saida(result)

    def test_open_sem_style_guide(self, tmp_path):
        result = runner.invoke(app, ["open", str(tmp_path)])
        assert result.exit_code == 1
        assert "style-guide.html" in saida(result)

    def test_url_invalida(self):
        result = runner.invoke(app, ["url", "isso-nao-e-url"])
        assert result.exit_code == 1
        assert "inválida" in saida(result)

    def test_pass_sem_user(self):
        result = runner.invoke(app, ["url", "exemplo.com", "--pass", "x"])
        assert result.exit_code == 1
        assert "--user" in saida(result)


class TestRepoPontaAPonta:
    def test_gera_pasta_completa(self, tmp_path):
        repo = tmp_path / "projeto"
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "app.css").write_text(
            ":root { --color-primary: #2b6cf6; --space-2: 8px; }\n"
            ".btn { background: #2b6cf6; border-radius: 6px; padding: 8px 16px; }"
        )
        out = tmp_path / "saida"

        result = runner.invoke(app, ["repo", str(repo), "--out", str(out)])

        assert result.exit_code == 0, result.stdout
        for nome in ("tokens.json", "variables.css", "tailwind.config.js", "style-guide.html", "README.md", "raw.json", "components.json"):
            assert (out / nome).exists(), nome
        assert "#2b6cf6" in (out / "tokens.json").read_text()

    def test_repo_vazio_avisa_sem_quebrar(self, tmp_path):
        repo = tmp_path / "vazio"
        repo.mkdir()
        out = tmp_path / "saida"
        result = runner.invoke(app, ["repo", str(repo), "--out", str(out)])
        assert result.exit_code == 0
        assert "nenhum token" in saida(result).lower()
        assert (out / "style-guide.html").exists()
