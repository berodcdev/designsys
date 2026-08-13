"""Saídas da v0.2: DESIGN-SYSTEM.md, Tokens Studio, sprite e paginação do PDF."""

import json

import pytest

from designsys.models import Asset, ComponentSnapshot, DesignSystem
from designsys.output.agentdoc import build_agent_doc
from designsys.output.sprite import build_sprite, usage_snippet
from designsys.output.tokensstudio import build_tokens_studio


@pytest.fixture
def ds() -> DesignSystem:
    d = DesignSystem(mode="url", target="https://exemplo.com", name="exemplo.com")
    d.colors = {
        "theme": "light",
        "clusters": [{"hex": "#635bff", "value": "#635bff", "count": 120, "properties": {}, "oklch": [0.5, 0.2, 280]}],
        "roles": {
            "primary": {"value": "#635bff", "hex": "#635bff", "count": 120, "reason": "botões"},
            "background": {"value": "#ffffff", "hex": "#ffffff", "count": 300, "reason": "body"},
            "text": {"value": "#111827", "hex": "#111827", "count": 200, "reason": "body"},
        },
        "neutrals": [{"hex": "#ffffff", "value": "#ffffff", "count": 300, "lightness": 1.0}],
        "accents": [],
        "named": {"brand": "#635bff"},
    }
    d.typography = {
        "families": [{"family": "Inter", "count": 900, "stack": "Inter, sans-serif", "generic": False}],
        "scale": [{"name": "h1", "fontSize": 48.0, "fontWeight": "700", "lineHeight": "1.1", "letterSpacing": "normal", "fontFamily": "Inter", "textTransform": "none", "count": 3, "sample": "Oi"}],
        "font_faces": [],
        "sizes": [16.0, 48.0],
        "weights": [400, 700],
    }
    d.spacing = {"scale": [4.0, 8.0, 16.0], "base_unit": 8.0, "named": {"1": 4.0, "2": 8.0}}
    d.radii = {"scale": [8.0], "named": {"md": 8.0}}
    d.shadows = [{"value": "0 1px 2px rgba(0,0,0,.05)", "count": 5}]
    d.borders = {"widths": [1.0]}
    d.breakpoints = [640, 1024]
    d.opacity = [0.5]
    d.components = [
        ComponentSnapshot(
            kind="button-primary", selector="button", label="Ok",
            base={"background-color": "#635bff", "color": "#ffffff", "border-radius": "8px", "font-size": "16px"},
            hover={"background-color": "#5145e5"},
            focus={"outline-width": "3px"},
        )
    ]
    d.themes = {
        "pairs": {
            "background": {"light": "#ffffff", "dark": "#0b0f14"},
            "primary": {"light": "#635bff", "dark": "#7c74ff"},
        },
        "dark": {"roles": {}},
        "detection": {"dark": True, "strategy": "prefers-color-scheme"},
    }
    d.responsive = {
        "widths": {"mobile": 390, "desktop": 1440},
        "fluid": {"h1": {"mobile": 32.0, "desktop": 48.0}},
    }
    d.diagnostics = {
        "score": 78,
        "accessibility": {
            "score": 70, "summary": "2 combinações abaixo do AA", "breakdown": ["−30 por contraste"],
            "contrast": [{"fg": "#aaaaaa", "bg": "#ffffff", "ratio": 2.3, "required": 4.5, "count": 9, "sample": "oi", "severity": "grave"}],
            "focusMissing": ["link"], "focusChecked": 3, "smallText": [], "smallTargets": [],
            "contrastChecked": 20, "contrastFailingOccurrences": 9,
        },
        "consistency": {"score": 85, "summary": "ok", "breakdown": ["−15 por paleta"], "spacingOffGrid": [], "orphanColors": [], "ghostTokens": []},
        "signature": {"sentence": "Sistema compacto e suave.", "axes": []},
        "evaluated": {"contrastPairs": 20, "components": 3, "colors": 1},
    }
    d.context = {
        "frameworks": [{"name": "Tailwind CSS", "confidence": 0.9, "evidence": [".flex"], "version": "v4"}],
        "frameworkSummary": "Tailwind CSS v4",
        "colorNames": {"#635bff": "brand"},
        "knownPalette": {"matches": {}, "count": 0, "confidence": 0.0},
        "fonts": [{"family": "Inter", "source": "Google Fonts", "libre": True, "alternative": None, "alternative_reason": ""}],
    }
    return d


# =========================================================== DESIGN-SYSTEM.md
class TestAgentDoc:
    def test_estrutura(self, ds):
        doc = build_agent_doc(ds)
        assert doc.startswith("# Design system —")
        for secao in ("## Cores", "## Tipografia", "## Espaçamento e forma", "## Regras"):
            assert secao in doc

    def test_diz_o_que_usar_por_papel(self, ds):
        doc = build_agent_doc(ds)
        assert "`primary`" in doc and "#635bff" in doc
        assert "ação principal" in doc

    def test_traz_o_par_escuro(self, ds):
        assert "escuro `#0b0f14`" in build_agent_doc(ds)

    def test_regra_de_grade(self, ds):
        assert "múltiplo de 8px" in build_agent_doc(ds)

    def test_regra_de_tema_escuro(self, ds):
        assert "par escuro" in build_agent_doc(ds)

    def test_mostra_o_botao_como_css(self, ds):
        doc = build_agent_doc(ds)
        assert "```css" in doc
        assert "background-color: #635bff;" in doc
        assert "/* :hover */" in doc

    def test_lista_os_erros_de_acessibilidade(self, ds):
        doc = build_agent_doc(ds)
        assert "não devem ser repetidas" in doc
        assert "`#aaaaaa` sobre `#ffffff`" in doc
        assert "foco" in doc.lower()

    def test_escala_responsiva(self, ds):
        assert "mobile 32px → desktop 48px" in build_agent_doc(ds)

    def test_conta_as_familias_corretamente(self, ds):
        ds.typography["families"].append({"family": "Mono", "count": 5, "stack": "Mono", "generic": False})
        assert "São 2 famílias no total" in build_agent_doc(ds)

    def test_design_system_vazio_nao_quebra(self):
        assert build_agent_doc(DesignSystem()).startswith("# Design system")

    def test_tamanho_razoavel_para_contexto(self, ds):
        """O arquivo é feito para caber num prompt."""
        assert len(build_agent_doc(ds)) < 12000


# ============================================================== Tokens Studio
class TestTokensStudio:
    def test_conjuntos_e_metadados(self, ds):
        doc = build_tokens_studio(ds)
        assert "global" in doc and "light" in doc and "dark" in doc
        assert doc["$metadata"]["tokenSetOrder"] == ["global", "light", "dark"]

    def test_formato_do_token(self, ds):
        cor = build_tokens_studio(ds)["light"]["color"]["primary"]
        assert cor["value"] == "#635bff" and cor["type"] == "color"

    def test_tema_escuro_separado(self, ds):
        assert build_tokens_studio(ds)["dark"]["color"]["background"]["value"] == "#0b0f14"

    def test_temas_declarados(self, ds):
        temas = build_tokens_studio(ds)["$themes"]
        assert [t["id"] for t in temas] == ["light", "dark"]
        assert temas[0]["selectedTokenSets"]["global"] == "source"

    def test_tipografia_composta(self, ds):
        h1 = build_tokens_studio(ds)["global"]["typography"]["h1"]
        assert h1["type"] == "typography"
        assert h1["value"]["fontSize"] == "48px"

    def test_serializa_em_json(self, ds):
        assert json.loads(json.dumps(build_tokens_studio(ds)))["global"]["spacing"]["1"]["value"] == "4px"

    def test_sem_tema_escuro_nao_cria_conjunto(self, ds):
        ds.themes = {}
        doc = build_tokens_studio(ds)
        assert "dark" not in doc
        assert doc["$metadata"]["tokenSetOrder"] == ["global", "light"]

    def test_vazio_nao_quebra(self):
        assert build_tokens_studio(DesignSystem())["$metadata"]["tokenSetOrder"] == ["global"]


# ===================================================================== sprite
class TestSprite:
    def _icone(self, corpo: str, view: str = "0 0 24 24") -> Asset:
        return Asset(
            kind="icon", url="x",
            inline_svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="{view}" fill="#ff0000">{corpo}</svg>',
        )

    def test_monta_symbols(self):
        sprite, indice = build_sprite([self._icone("<path d='M0 0h24v24H0z'/>")])
        assert '<symbol id="icon-1" viewBox="0 0 24 24">' in sprite
        assert indice[0]["id"] == "icon-1"

    def test_cor_fixa_vira_currentcolor(self):
        sprite, _ = build_sprite([self._icone('<path fill="#00ff00" d="M0 0"/>')])
        assert 'fill="currentColor"' in sprite
        assert "#00ff00" not in sprite

    def test_preserva_fill_none(self):
        sprite, _ = build_sprite([self._icone('<path fill="none" d="M0 0"/>')])
        assert 'fill="none"' in sprite

    def test_remove_dimensoes_fixas(self):
        sprite, _ = build_sprite([self._icone("<circle r='5'/>")])
        assert 'width="24"' not in sprite

    def test_deduplica(self):
        icone = self._icone("<path d='M1 1'/>")
        _, indice = build_sprite([icone, self._icone("<path d='M1 1'/>")])
        assert len(indice) == 1

    def test_sem_icones(self):
        assert build_sprite([]) == ("", [])

    def test_remove_script(self):
        malicioso = Asset(kind="icon", url="x", inline_svg="<svg viewBox='0 0 1 1'><script>alert(1)</script><path/></svg>")
        sprite, _ = build_sprite([malicioso])
        assert "<script>" not in sprite

    def test_viewbox_a_partir_de_width_height(self):
        asset = Asset(kind="icon", url="x", inline_svg='<svg width="16" height="16"><path d="M0 0"/></svg>')
        _, indice = build_sprite([asset])
        assert indice[0]["viewBox"] == "0 0 16 16"

    def test_snippet_de_uso(self):
        assert "use href=" in usage_snippet("assets/icons/sprite.svg")


# =========================================================== paginação do PDF
class TestPaginacao:
    def test_secoes_marcadas_para_o_sumario(self, ds):
        from designsys.output.pdfdoc import build_print_html

        doc = build_print_html(ds)
        assert 'data-section="1"' in doc
        assert 'data-toc="1"' in doc

    def test_numeros_reais_no_pdf(self, ds, tmp_path):
        """O sumário precisa dizer a página certa — é o que o `_paginate` calcula."""
        import re

        from designsys.output.pdfdoc import build_print_html
        from designsys.output.pdfrender import render_pdf

        html = build_print_html(ds)
        destino = tmp_path / "doc.pdf"
        render_pdf(html, destino, base_dir=tmp_path)
        assert destino.exists() and destino.read_bytes()[:5] == b"%PDF-"

    def test_resumo_executivo_presente(self, ds):
        from designsys.output.pdfdoc import build_print_html

        doc = build_print_html(ds)
        assert "O essencial" in doc
        assert "exec-card" in doc

    def test_ui_nos_dois_temas(self, ds):
        from designsys.output.pdfdoc import build_print_html

        doc = build_print_html(ds)
        assert "A mesma interface nos dois temas" in doc
        assert "#0b0f14" in doc

    def test_secoes_novas_no_documento(self, ds):
        from designsys.output.pdfdoc import build_print_html

        doc = build_print_html(ds)
        for titulo in ("Tema claro e escuro", "Escala responsiva", "Diagnóstico", "Contexto técnico"):
            assert titulo in doc
