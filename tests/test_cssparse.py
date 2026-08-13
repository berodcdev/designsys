"""Parser de CSS/SCSS/LESS e classificação de tokens do modo repo."""

import pytest

from designsys.util.cssparse import parse_css, parse_preprocessor

CSS = """
:root {
  --color-primary: #6a35d9;
  --space-4: 16px;
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.12);
}
@font-face {
  font-family: 'Satoshi';
  font-weight: 500;
  font-style: normal;
  src: url('/fonts/satoshi.woff2') format('woff2');
  font-display: swap;
}
.btn {
  color: #ffffff;
  background-color: #6a35d9;
  padding: 12px 20px;
  border: 1px solid #4c1d95;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  transition: background-color 200ms ease-in-out;
  z-index: 10;
  opacity: 0.9;
}
@media (min-width: 768px) {
  .btn { padding: 16px 28px; }
}
@supports (display: grid) {
  .grid { gap: 24px; }
}
.container { max-width: 1200px; }
"""


@pytest.fixture(scope="module")
def facts():
    return parse_css(CSS, origin="app.css")


class TestParseCss:
    def test_custom_properties_com_procedencia(self, facts):
        nomes = {p["name"]: p for p in facts.custom_props}
        assert nomes["--color-primary"]["value"] == "#6a35d9"
        assert nomes["--color-primary"]["origin"] == "app.css"
        assert nomes["--color-primary"]["selector"] == ":root"

    def test_cores_agrupadas_por_propriedade(self, facts):
        assert facts.colors_by_prop["color"]["#ffffff"] >= 1
        assert facts.colors_by_prop["background-color"]["#6a35d9"] >= 1
        assert facts.colors_by_prop["border-color"]["#4c1d95"] >= 1

    def test_espacamento_e_raio(self, facts):
        assert facts.spacing["12px"] >= 1 and facts.spacing["20px"] >= 1
        assert facts.spacing["24px"] >= 1  # dentro de @supports
        assert facts.radii["8px"] >= 1

    def test_sombras(self, facts):
        assert any("0 1px 2px" in s for s in facts.shadows)

    def test_media_queries(self, facts):
        assert any("768px" in q for q in facts.media_queries)

    def test_media_query_nao_esconde_declaracoes(self, facts):
        assert facts.spacing["16px"] >= 1  # padding dentro do @media

    def test_font_face_completo(self, facts):
        ff = facts.font_faces[0]
        assert "Satoshi" in ff["font-family"]
        assert ff["font-weight"] == "500"
        assert "satoshi.woff2" in ff["src"]

    def test_transicoes(self, facts):
        assert facts.durations["200ms"] >= 1
        assert facts.easings["ease-in-out"] >= 1

    def test_z_index_opacidade_max_width(self, facts):
        assert facts.z_indexes["10"] >= 1
        assert facts.opacities["0.9"] >= 1
        assert facts.max_widths["1200px"] >= 1

    def test_css_vazio(self):
        assert parse_css("").rule_count == 0

    def test_css_quebrado_nao_lanca(self):
        f = parse_css(".a { color: ; } } garbage {{{ .b { color: #fff }")
        assert isinstance(f.rule_count, int)

    def test_tailwind_v4_theme(self):
        f = parse_css("@theme { --color-brand: #2b6cf6; --spacing-lg: 24px; }", "app.css")
        assert f.theme_blocks and f.theme_blocks[0]["--color-brand"] == "#2b6cf6"
        assert any(p["name"] == "--color-brand" for p in f.custom_props)
        assert f.colors["#2b6cf6"] >= 1

    def test_import_capturado(self):
        assert parse_css('@import url("outro.css");').imports == ["outro.css"]


class TestPreprocessador:
    def test_variaveis_scss(self):
        f = parse_preprocessor("$brand: #ff8800;\n$gap: 12px;\n.a { color: $brand; }", "a.scss")
        nomes = {p["name"]: p["value"] for p in f.custom_props}
        assert nomes["$brand"] == "#ff8800"
        assert f.colors["#ff8800"] >= 1
        assert f.spacing["12px"] >= 1

    def test_variaveis_less(self):
        f = parse_preprocessor("@brand: #00aa88;\n.a { color: @brand; }", "a.less")
        assert {p["name"] for p in f.custom_props} >= {"@brand"}
        assert f.colors["#00aa88"] >= 1

    def test_at_rules_do_less_nao_viram_variaveis(self):
        f = parse_preprocessor("@media (min-width: 700px) { .a { color: red } }", "a.less")
        assert not any(p["name"] == "@media" for p in f.custom_props)

    def test_mixins_scss_nao_quebram(self):
        source = "@mixin botao($cor) { color: $cor; }\n.b { @include botao(#123456); border-radius: 4px; }"
        f = parse_preprocessor(source, "a.scss")
        assert f.radii["4px"] >= 1


class TestMerge:
    def test_soma_contadores_de_arquivos_diferentes(self):
        a = parse_css(".x { color: #fff }", "a.css")
        b = parse_css(".y { color: #fff }", "b.css")
        a.merge(b)
        assert a.colors_by_prop["color"]["#fff"] == 2
        assert a.rule_count == 2
