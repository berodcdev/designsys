"""Documento de impressão e geração do PDF."""

import json

import pytest

from designsys.models import Asset, ComponentSnapshot, DesignSystem
from designsys.output.pdfdoc import build_print_html
from designsys.output.pdfrender import PdfError, render_pdf

pytest_plugins: list[str] = []


@pytest.fixture
def ds() -> DesignSystem:
    d = DesignSystem(mode="url", target="https://exemplo.com", name="exemplo.com")
    d.colors = {
        "theme": "light",
        "clusters": [
            {"hex": "#635bff", "value": "#635bff", "count": 120, "properties": {"color": 120}, "oklch": [0.5, 0.2, 280]},
            {"hex": "#ffffff", "value": "#ffffff", "count": 300, "properties": {"background-color": 300}, "oklch": [1, 0, 0]},
        ],
        "roles": {
            "primary": {"value": "#635bff", "hex": "#635bff", "count": 120, "reason": "fundo de botões"},
            "background": {"value": "#ffffff", "hex": "#ffffff", "count": 300, "reason": "body"},
            "text": {"value": "#111827", "hex": "#111827", "count": 200, "reason": "body"},
            "border": {"value": "#e5e7eb", "hex": "#e5e7eb", "count": 40, "reason": "bordas"},
        },
        "neutrals": [
            {"hex": "#ffffff", "value": "#ffffff", "count": 300, "lightness": 1.0},
            {"hex": "#111827", "value": "#111827", "count": 90, "lightness": 0.2},
        ],
        "accents": [{"hex": "#00d924", "value": "#00d924", "count": 12, "hue": 149.0}],
        "named": {"brand-500": "#2b6cf6"},
    }
    d.typography = {
        "families": [{"family": "Inter", "count": 900, "stack": "Inter, sans-serif", "generic": False}],
        "scale": [
            {"name": "h1", "fontSize": 48.0, "fontWeight": "700", "lineHeight": "1.1", "letterSpacing": "-0.02em", "fontFamily": "Inter", "textTransform": "none", "count": 3, "sample": "Olá mundo"},
            {"name": "body", "fontSize": 16.0, "fontWeight": "400", "lineHeight": "1.5", "letterSpacing": "normal", "fontFamily": "Inter", "textTransform": "none", "count": 200, "sample": "Texto"},
        ],
        "font_faces": [{"family": "Inter", "weight": "400", "style": "normal", "urls": [], "display": "swap", "unicodeRange": None, "localPath": None}],
        "sizes": [12.0, 16.0, 48.0],
        "weights": [400, 700],
    }
    d.spacing = {"scale": [4.0, 8.0, 16.0], "base_unit": 4.0, "named": {"1": 4.0, "2": 8.0, "4": 16.0}}
    d.radii = {"scale": [4.0, 8.0], "named": {"sm": 4.0, "md": 8.0}}
    d.shadows = [{"value": "0 1px 2px rgba(0, 0, 0, 0.05)", "count": 40}]
    d.borders = {"widths": [1.0]}
    d.breakpoints = [640, 768]
    d.containers = [1200.0]
    d.z_index = [10]
    d.motion = {"durations": ["150ms"], "easings": ["ease-in-out"]}
    d.opacity = [0.5]
    d.css_variables = {"--color-primary": {"value": "#635bff", "origin": "app.css", "scope": ":root"}}
    d.components = [
        ComponentSnapshot(
            kind="button-primary",
            selector="body > button",
            label="Comprar",
            html="<button>Comprar</button>",
            base={"background-color": "#635bff", "color": "#ffffff", "border-radius": "8px", "font-size": "16px"},
            hover={"background-color": "#5145e5"},
            focus={"outline-width": "3px"},
            page="https://exemplo.com",
        )
    ]
    d.assets = [
        Asset(kind="logo", url="https://x/logo.svg", path="assets/logo/logo.svg", inline_svg="<svg viewBox='0 0 10 10'><rect width='10' height='10'/></svg>"),
        Asset(kind="screenshot", url="https://exemplo.com", path="screenshots/01-home.png"),
    ]
    d.pages = [{"url": "https://exemplo.com", "title": "Exemplo", "elements": 100, "rules": 50, "screenshot": "screenshots/01-home.png"}]
    return d


class TestDocumentoDeImpressao:
    def test_html_completo(self, ds):
        doc = build_print_html(ds)
        assert doc.startswith("<!doctype html>")
        assert doc.rstrip().endswith("</html>")

    def test_tem_capa_sumario_e_secoes(self, ds):
        doc = build_print_html(ds)
        assert 'class="page cover"' in doc
        assert "Neste documento" in doc
        assert doc.count('class="page"') >= 6

    def test_capa_traz_nome_e_contagens(self, ds):
        doc = build_print_html(ds)
        assert "exemplo.com" in doc
        assert "cover-stats" in doc
        assert "cover-roles" in doc  # papéis principais na capa

    def test_sem_nada_interativo(self, ds):
        """Num PDF, script e toggle de tema não fazem sentido."""
        doc = build_print_html(ds)
        assert "<script" not in doc
        assert "theme-toggle" not in doc
        assert "data-copy" not in doc

    def test_usa_a_cor_primaria_do_site_como_destaque(self, ds):
        assert "--accent: #635bff" in build_print_html(ds)

    def test_accent_claro_demais_nao_vira_cor_de_texto(self, ds):
        ds.colors["roles"]["primary"] = {"value": "#fefefe", "hex": "#fefefe", "count": 1, "reason": ""}
        assert "--accent: #fefefe" not in build_print_html(ds)

    def test_conteudo_das_secoes(self, ds):
        doc = build_print_html(ds)
        for esperado in ("Cores", "Tipografia", "Espaçamento", "Componentes", "Assets", "Como usar"):
            assert esperado in doc

    def test_componentes_mostram_estados(self, ds):
        doc = build_print_html(ds)
        assert "hover: #5145e5" in doc
        assert "focus: 3px" in doc

    def test_screenshots_referenciados(self, ds):
        assert "screenshots/01-home.png" in build_print_html(ds)

    def test_paginacao_por_grupos_de_dois_componentes(self, ds):
        ds.components = ds.components * 5
        doc = build_print_html(ds)
        assert doc.count("Componentes (cont.)") >= 1

    def test_escapa_conteudo_hostil(self):
        d = DesignSystem(name="<img src=x onerror=alert(1)>")
        assert "<img src=x onerror" not in build_print_html(d)

    def test_design_system_vazio_nao_quebra(self):
        assert build_print_html(DesignSystem()).startswith("<!doctype html>")

    def test_avisos_aparecem(self, ds):
        ds.warnings = ["algo não pôde ser lido"]
        assert "algo não pôde ser lido" in build_print_html(ds)

    def test_login_documentado_no_sumario(self, ds):
        ds.raw["login"] = {"ok": True, "method": "otp", "detail": "autenticado por código", "steps": []}
        doc = build_print_html(ds)
        assert "código de uso único" in doc
        assert "Nenhuma senha foi gravada" in doc


class TestRenderPdf:
    def test_gera_pdf_valido(self, ds, tmp_path):
        destino = tmp_path / "design-system.pdf"
        render_pdf(build_print_html(ds), destino, base_dir=tmp_path, title="teste")
        assert destino.exists()
        assert destino.read_bytes()[:5] == b"%PDF-"
        assert destino.stat().st_size > 8000

    def test_limpa_o_html_temporario(self, ds, tmp_path):
        render_pdf(build_print_html(ds), tmp_path / "a.pdf", base_dir=tmp_path)
        assert not (tmp_path / ".designsys-print.html").exists()

    def test_html_invalido_nao_deixa_lixo(self, tmp_path):
        render_pdf("<html><body>oi</body></html>", tmp_path / "b.pdf", base_dir=tmp_path)
        assert (tmp_path / "b.pdf").exists()
        assert not (tmp_path / ".designsys-print.html").exists()


class TestRegeneracao:
    def test_from_dict_reconstroi_o_suficiente_para_o_pdf(self, ds, tmp_path):
        """`designsys pdf` monta o documento a partir do raw.json."""
        from designsys.output.writer import write_all

        write_all(ds, tmp_path)
        dados = json.loads((tmp_path / "raw.json").read_text())
        recuperado = DesignSystem.from_dict(dados)

        assert recuperado.name == ds.name
        assert recuperado.colors["roles"]["primary"]["hex"] == "#635bff"
        assert recuperado.components[0].hover["background-color"] == "#5145e5"
        assert [a.kind for a in recuperado.assets] == ["logo", "screenshot"]
        doc = build_print_html(recuperado)
        assert "exemplo.com" in doc and "button-primary" in doc
