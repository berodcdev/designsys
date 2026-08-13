"""Writers: tokens.json (DTCG), variables.css, tailwind.config.js e style guide."""

import json

import pytest

from designsys.models import Asset, ComponentSnapshot, DesignSystem
from designsys.output.css import build_variables_css
from designsys.output.styleguide import build_style_guide
from designsys.output.tailwind import build_tailwind_config
from designsys.output.tokens import DTCG_SCHEMA, build_dtcg, token_name
from designsys.output.writer import build_readme, write_all


@pytest.fixture
def ds() -> DesignSystem:
    d = DesignSystem(mode="url", target="https://exemplo.com", name="exemplo.com")
    d.colors = {
        "theme": "light",
        "clusters": [{"hex": "#635bff", "value": "#635bff", "count": 120, "properties": {"color": 120}, "oklch": [0.5, 0.2, 280]}],
        "roles": {
            "primary": {"value": "#635bff", "hex": "#635bff", "count": 120, "reason": "botões"},
            "background": {"value": "#ffffff", "hex": "#ffffff", "count": 300, "reason": "body"},
        },
        "neutrals": [
            {"hex": "#ffffff", "value": "#ffffff", "count": 300, "lightness": 1.0},
            {"hex": "#111827", "value": "#111827", "count": 90, "lightness": 0.2},
        ],
        "accents": [{"hex": "#00d924", "value": "#00d924", "count": 12, "hue": 149.0}],
        "named": {"brand-500": "#2b6cf6"},
    }
    d.typography = {
        "families": [{"family": "Inter", "count": 900, "stack": "Inter, system-ui, sans-serif", "generic": False}],
        "scale": [
            {"name": "h1", "fontSize": 48.0, "fontWeight": "700", "lineHeight": "1.1", "letterSpacing": "-0.02em", "fontFamily": "Inter", "textTransform": "none", "count": 3, "sample": "Olá"},
            {"name": "body", "fontSize": 16.0, "fontWeight": "400", "lineHeight": "1.5", "letterSpacing": "normal", "fontFamily": "Inter", "textTransform": "none", "count": 200, "sample": "Texto"},
        ],
        "font_faces": [{"family": "Inter", "weight": "400", "style": "normal", "urls": ["https://x/inter.woff2"], "display": "swap", "unicodeRange": None, "localPath": "assets/fonts/inter.woff2"}],
        "sizes": [12.0, 16.0, 48.0],
        "weights": [400, 700],
    }
    d.spacing = {"scale": [4.0, 8.0, 16.0], "base_unit": 4.0, "named": {"1": 4.0, "2": 8.0, "4": 16.0}}
    d.radii = {"scale": [4.0, 8.0, 9999.0], "named": {"sm": 4.0, "md": 8.0, "full": 9999.0}}
    d.shadows = [{"value": "0 1px 2px rgba(0, 0, 0, 0.05)", "count": 40}, {"value": "0 10px 20px rgba(0,0,0,.1), 0 2px 4px rgba(0,0,0,.06)", "count": 10}]
    d.borders = {"widths": [1.0, 2.0]}
    d.breakpoints = [640, 768, 1024]
    d.containers = [1200.0]
    d.z_index = [10, 50]
    d.motion = {"durations": ["150ms", "300ms"], "easings": ["cubic-bezier(0.4, 0, 0.2, 1)", "ease-in-out"]}
    d.opacity = [0.5, 0.75]
    d.css_variables = {"--color-primary": {"value": "#635bff", "origin": "app.css", "scope": ":root"}}
    d.components = [
        ComponentSnapshot(
            kind="button-primary",
            selector="body > button",
            label="Comprar",
            html="<button>Comprar</button>",
            base={"background-color": "#635bff", "color": "#ffffff", "border-radius": "8px", "padding-top": "12px"},
            hover={"background-color": "#5145e5", "color": "#ffffff"},
            focus={"outline-color": "#635bff"},
        )
    ]
    d.assets = [Asset(kind="logo", url="https://x/logo.svg", path="assets/logo/logo.svg", inline_svg="<svg><rect/></svg>")]
    d.pages = [{"url": "https://exemplo.com", "title": "Exemplo", "elements": 100, "rules": 50, "screenshot": None}]
    return d


class TestDTCG:
    def test_schema_e_estrutura(self, ds):
        t = build_dtcg(ds)
        assert t["$schema"] == DTCG_SCHEMA
        assert t["color"]["primary"] == {
            "$value": "#635bff",
            "$type": "color",
            "$description": "botões",
            "$extensions": {"designsys": {"usageCount": 120}},
        }

    def test_todo_leaf_tem_value_e_type(self, ds):
        def walk(node, path=""):
            if isinstance(node, dict):
                if "$value" in node:
                    assert "$type" in node, f"sem $type em {path}"
                    return 1
                return sum(walk(v, f"{path}.{k}") for k, v in node.items() if not k.startswith("$"))
            return 0

        assert walk(build_dtcg(ds)) > 15

    def test_serializa_em_json(self, ds):
        assert json.loads(json.dumps(build_dtcg(ds)))["color"]["primary"]["$value"] == "#635bff"

    def test_escala_neutra_nomeada(self, ds):
        neutral = build_dtcg(ds)["color"]["neutral"]
        assert neutral["50"]["$value"] == "#ffffff"
        assert neutral["950"]["$value"] == "#111827"

    def test_paleta_nomeada_aninhada(self, ds):
        assert build_dtcg(ds)["color"]["palette"]["brand"]["500"]["$value"] == "#2b6cf6"

    def test_dimensoes_com_unidade(self, ds):
        t = build_dtcg(ds)
        assert t["spacing"]["1"]["$value"] == "4px"
        assert t["spacing"]["1"]["$type"] == "dimension"
        assert t["borderRadius"]["full"]["$value"] == "9999px"

    def test_sombra_simples_vira_objeto(self, ds):
        shadow = build_dtcg(ds)["shadow"]["xs"]
        assert shadow["$type"] == "shadow"
        assert shadow["$value"]["offsetY"] == "1px"
        assert shadow["$value"]["blur"] == "2px"

    def test_sombra_multipla_vira_lista(self, ds):
        assert isinstance(build_dtcg(ds)["shadow"]["sm"]["$value"], list)

    def test_typography_composite(self, ds):
        h1 = build_dtcg(ds)["typography"]["h1"]
        assert h1["$type"] == "typography"
        assert h1["$value"]["fontSize"] == "48px"
        assert h1["$value"]["fontWeight"] == 700

    def test_cubic_bezier_vira_array(self, ds):
        easings = build_dtcg(ds)["easing"]
        cubic = [v for v in easings.values() if v["$type"] == "cubicBezier"]
        assert cubic and cubic[0]["$value"] == [0.4, 0.0, 0.2, 1.0]

    def test_easing_nomeado_nao_vira_cubic(self, ds):
        assert build_dtcg(ds)["easing"]["ease-in-out"]["$type"] == "other"

    def test_breakpoints_nomeados(self, ds):
        assert build_dtcg(ds)["breakpoint"]["sm"]["$value"] == "640px"

    def test_design_system_vazio_nao_quebra(self):
        t = build_dtcg(DesignSystem())
        assert t["$schema"] == DTCG_SCHEMA
        assert json.dumps(t)

    @pytest.mark.parametrize(
        "raw,expected",
        [("Color/Primary", "Color-Primary"), ("brand.500", "brand-500"), ("  --x  ", "x"), ("a  b", "a-b"), ("", "token")],
    )
    def test_token_name_sanitiza(self, raw, expected):
        assert token_name(raw) == expected


class TestVariablesCss:
    def test_gera_root_com_papeis(self, ds):
        css = build_variables_css(ds)
        assert ":root {" in css and css.count("}") >= 1
        assert "--color-primary: #635bff;" in css

    def test_inclui_todas_as_categorias(self, ds):
        css = build_variables_css(ds)
        for needle in ["--color-neutral-50", "--spacing-1", "--radius-sm", "--shadow-", "--font-base", "--text-h1-size", "--breakpoint-sm", "--z-10", "--opacity-50", "--duration-1", "--ease-1", "--border-1"]:
            assert needle in css, needle

    def test_font_face_com_arquivo_local(self, ds):
        assert "@font-face" in build_variables_css(ds)
        assert "assets/fonts/inter.woff2" in build_variables_css(ds)

    def test_chaves_balanceadas(self, ds):
        css = build_variables_css(ds)
        assert css.count("{") == css.count("}")

    def test_vazio_nao_quebra(self):
        assert ":root {" in build_variables_css(DesignSystem())


class TestTailwindConfig:
    def test_estrutura_module_exports(self, ds):
        js = build_tailwind_config(ds)
        assert js.startswith("/**") and "module.exports = {" in js
        assert "theme: {" in js and "extend: {" in js

    def test_cores_e_paleta_aninhada(self, ds):
        js = build_tailwind_config(ds)
        assert "primary: '#635bff'" in js
        assert "'500': '#2b6cf6'" in js or "500: '#2b6cf6'" in js

    def test_screens_e_sombras(self, ds):
        js = build_tailwind_config(ds)
        assert "sm: '640px'" in js
        assert "boxShadow" in js

    def test_font_family_como_lista(self, ds):
        assert "sans: ['Inter', 'system-ui', 'sans-serif']" in build_tailwind_config(ds)

    def test_chaves_balanceadas(self, ds):
        js = build_tailwind_config(ds)
        assert js.count("{") == js.count("}") and js.count("[") == js.count("]")

    def test_escapa_aspas(self):
        d = DesignSystem()
        d.colors = {"roles": {"primary": {"value": "var(--x, 'y')", "hex": "#000", "count": 1, "reason": ""}}}
        assert '"' in build_tailwind_config(d)


class TestStyleGuide:
    def test_html_completo(self, ds):
        html = build_style_guide(ds)
        assert html.startswith("<!doctype html>")
        assert html.rstrip().endswith("</html>")
        assert "<title>" in html

    def test_self_contained(self, ds):
        """Sem <script src> nem <link rel=stylesheet> externos."""
        html = build_style_guide(ds)
        assert "<script src" not in html
        assert "rel=\"stylesheet\"" not in html and "rel='stylesheet'" not in html

    def test_secoes_presentes(self, ds):
        html = build_style_guide(ds)
        for anchor in ["id=\"cores\"", "id=\"tipografia\"", "id=\"espacamento\"", "id=\"componentes\""]:
            assert anchor in html, anchor

    def test_swatch_copiavel(self, ds):
        assert 'data-copy="#635bff"' in build_style_guide(ds)

    def test_toggle_de_tema(self, ds):
        assert 'id="theme-toggle"' in build_style_guide(ds)
        assert "data-theme" in build_style_guide(ds)

    def test_componente_reconstruido_com_hover(self, ds):
        html = build_style_guide(ds)
        assert "background-color:#635bff" in html
        assert ":hover{" in html

    def test_sanitiza_script_do_html_capturado(self):
        d = DesignSystem()
        d.components = [ComponentSnapshot(kind="card", selector="div", html="<div onclick='x()'><script>alert(1)</script>oi</div>", base={"color": "red"})]
        html = build_style_guide(d)
        assert "<script>alert(1)</script>" not in html
        assert "onclick" not in html

    def test_escapa_conteudo_hostil(self):
        d = DesignSystem(name="<img src=x onerror=alert(1)>")
        assert "<img src=x onerror" not in build_style_guide(d)

    def test_vazio_nao_quebra(self):
        assert build_style_guide(DesignSystem()).startswith("<!doctype html>")


class TestWriteAll:
    def test_escreve_todos_os_arquivos(self, ds, tmp_path):
        written = write_all(ds, tmp_path)
        esperados = {"tokens.json", "variables.css", "tailwind.config.js", "style-guide.html", "components.json", "raw.json", "README.md"}
        assert esperados <= set(written)
        for path in written.values():
            assert path.exists() and path.stat().st_size > 0

    def test_components_json_valido(self, ds, tmp_path):
        write_all(ds, tmp_path)
        data = json.loads((tmp_path / "components.json").read_text())
        assert data["components"][0]["kind"] == "button-primary"
        assert data["components"][0]["hover"]["background-color"] == "#5145e5"

    def test_raw_json_serializavel(self, ds, tmp_path):
        ds.raw = {"frequencies": {"a": {"b": 1}}, "set": {1, 2}}
        write_all(ds, tmp_path)
        assert json.loads((tmp_path / "raw.json").read_text())["target"] == "https://exemplo.com"

    def test_readme_menciona_arquivos_e_papeis(self, ds):
        readme = build_readme(ds)
        assert "tokens.json" in readme and "style-guide.html" in readme
        assert "`primary`" in readme

    def test_readme_avisa_sobre_cookies_quando_houve_login(self, ds):
        ds.raw["login"] = {"ok": True, "method": "manual", "detail": "ok", "steps": []}
        assert "profiles" in build_readme(ds)
