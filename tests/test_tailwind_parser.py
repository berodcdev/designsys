"""Parser tolerante de objetos JS e leitura de tailwind.config."""

import pytest

from designsys.extractors.jsobj import (
    JSObjectParser,
    JSRaw,
    find_config_object,
    find_named_object,
    flatten,
)

CONFIG_COMMONJS = """
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.tsx'],
  darkMode: 'class',
  theme: {
    screens: { sm: '640px', md: '768px' },
    extend: {
      colors: {
        brand: { 500: '#2b6cf6', DEFAULT: '#2b6cf6' },
        danger: '#e5484d',
      },
      spacing: { xs: '3px' },
      fontFamily: { display: ['Zodiak', 'Georgia', 'serif'] },
    },
  },
  plugins: [],
}
"""

CONFIG_ESM_TS = """
import type { Config } from 'tailwindcss'
import defaultTheme from 'tailwindcss/defaultTheme'

const config: Config = {
  content: ['./app/**/*.tsx'],
  theme: {
    extend: {
      colors: { primary: '#0f766e' },
      fontFamily: { sans: ['Inter', ...defaultTheme.fontFamily.sans] },
    },
  },
}

export default config
"""

CONFIG_DEFINE_CONFIG = """
export default defineConfig({
  theme: { extend: { colors: { accent: '#8b5cf6' } } },
})
"""


class TestJSObjectParser:
    def test_tipos_basicos(self):
        obj = JSObjectParser("{ a: 'x', b: 2, c: true, d: null, e: 1.5 }").parse_object()
        assert obj == {"a": "x", "b": 2, "c": True, "d": None, "e": 1.5}

    def test_aspas_duplas_e_simples(self):
        assert JSObjectParser("""{ "a": "1", 'b': '2' }""").parse_object() == {"a": "1", "b": "2"}

    def test_chaves_entre_aspas_e_numericas(self):
        obj = JSObjectParser("{ '50': '#fff', 500: '#000' }").parse_object()
        assert obj == {"50": "#fff", "500": "#000"}

    def test_aninhamento(self):
        obj = JSObjectParser("{ a: { b: { c: '#fff' } } }").parse_object()
        assert obj["a"]["b"]["c"] == "#fff"

    def test_arrays(self):
        obj = JSObjectParser("{ f: ['Inter', 'sans-serif'] }").parse_object()
        assert obj["f"] == ["Inter", "sans-serif"]

    def test_trailing_comma(self):
        assert JSObjectParser("{ a: '1', }").parse_object() == {"a": "1"}

    def test_comentarios_ignorados(self):
        src = "{ // linha\n a: '1', /* bloco */ b: '2' }"
        assert JSObjectParser(src).parse_object() == {"a": "1", "b": "2"}

    def test_template_literal_simples_vira_string(self):
        assert JSObjectParser("{ a: `plain` }").parse_object() == {"a": "plain"}

    def test_template_interpolado_fica_nao_resolvido(self):
        parser = JSObjectParser("{ a: `rgb(${r} 0 0)` }")
        obj = parser.parse_object()
        assert isinstance(obj["a"], JSRaw)
        assert parser.unresolved

    def test_expressao_vira_jsraw(self):
        parser = JSObjectParser("{ a: colors.blue[500], b: '#fff' }")
        obj = parser.parse_object()
        assert isinstance(obj["a"], JSRaw)
        assert obj["b"] == "#fff"

    def test_spread_registrado_como_nao_resolvido(self):
        parser = JSObjectParser("{ ...colors, brand: '#fff' }")
        obj = parser.parse_object()
        assert obj["brand"] == "#fff"
        assert any("colors" in u for u in parser.unresolved)

    def test_escapes_em_string(self):
        assert JSObjectParser(r"""{ a: 'it\'s' }""").parse_object() == {"a": "it's"}

    def test_funcao_nao_quebra_o_parse(self):
        obj = JSObjectParser("{ a: ({ opacityValue }) => `rgb(0 0 0)`, b: '#fff' }").parse_object()
        assert obj["b"] == "#fff"

    def test_objeto_vazio(self):
        assert JSObjectParser("{}").parse_object() == {}


class TestFindConfigObject:
    def test_module_exports(self):
        config, _ = find_config_object(CONFIG_COMMONJS)
        assert config["darkMode"] == "class"
        assert config["theme"]["extend"]["colors"]["danger"] == "#e5484d"
        assert config["theme"]["screens"]["sm"] == "640px"

    def test_export_default_por_identificador_typescript(self):
        config, _ = find_config_object(CONFIG_ESM_TS)
        assert config["theme"]["extend"]["colors"]["primary"] == "#0f766e"

    def test_define_config_wrapper(self):
        config, _ = find_config_object(CONFIG_DEFINE_CONFIG)
        assert config["theme"]["extend"]["colors"]["accent"] == "#8b5cf6"

    def test_spread_de_import_nao_apaga_os_literais(self):
        config, unresolved = find_config_object(CONFIG_ESM_TS)
        fonts = config["theme"]["extend"]["fontFamily"]["sans"]
        assert "Inter" in fonts
        assert unresolved  # o spread de defaultTheme foi reportado

    def test_texto_sem_config(self):
        config, _ = find_config_object("const x = 1")
        assert config == {}

    def test_config_sem_export_mas_com_theme(self):
        config, _ = find_config_object("const cfg = { theme: { colors: { a: '#fff' } } }")
        assert config["theme"]["colors"]["a"] == "#fff"


class TestFindNamedObject:
    def test_encontra_theme_exportado(self):
        obj, _ = find_named_object("export const theme = { colors: { a: '#fff' } }", ["theme"])
        assert obj["colors"]["a"] == "#fff"

    def test_encontra_create_theme(self):
        obj, _ = find_named_object("const t = createTheme({ palette: { main: '#111' } })", ["theme"])
        assert obj["palette"]["main"] == "#111"

    def test_nao_encontrado(self):
        assert find_named_object("const outro = 1", ["theme"])[0] == {}


class TestFlatten:
    def test_achata_com_hifen(self):
        assert flatten({"colors": {"brand": {"500": "#fff"}}}) == {"colors-brand-500": "#fff"}

    def test_default_colapsa_no_pai(self):
        assert flatten({"brand": {"DEFAULT": "#fff"}}) == {"brand": "#fff"}

    def test_lista_de_strings_preservada(self):
        assert flatten({"fontFamily": {"sans": ["Inter", "serif"]}}) == {
            "fontFamily-sans": ["Inter", "serif"]
        }

    def test_jsraw_descartado(self):
        assert flatten({"a": JSRaw("x"), "b": "#fff"}) == {"b": "#fff"}


def test_config_real_ponta_a_ponta(tmp_path):
    """O caminho completo: arquivo em disco -> tokens nomeados."""
    from designsys.extractors.repo import RepoExtractor, RepoOptions

    (tmp_path / "tailwind.config.js").write_text(CONFIG_COMMONJS)
    ds = RepoExtractor(RepoOptions(path=tmp_path, out=tmp_path / "out")).run()

    named = ds.raw["named_tokens"]
    assert named["colors"]["brand-500"]["value"] == "#2b6cf6"
    assert named["colors"]["danger"]["value"] == "#e5484d"
    assert named["spacing"]["xs"]["value"] == "3px"
    assert named["fontFamily"]["display"]["value"].startswith("Zodiak")
    assert 640 in ds.breakpoints and 768 in ds.breakpoints
    assert any(c["hex"] == "#2b6cf6" for c in ds.colors["clusters"])
