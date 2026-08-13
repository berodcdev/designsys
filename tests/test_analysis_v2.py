"""Diagnóstico, contexto e nomenclatura — as análises da v0.2."""

import pytest

from designsys.analysis import a11y, consistency, fonts, frameworks, known, signature
from designsys.analysis.color import parse_color
from designsys.models import ComponentSnapshot


# ============================================================ acessibilidade
class TestContraste:
    def _par(self, fg, bg, size="16px", weight="400", count=1):
        return {"fg": fg, "bg": bg, "size": size, "weight": weight, "count": count, "sample": "x"}

    def test_texto_normal_precisa_de_4_5(self):
        assert a11y.required_ratio(16, "400") == 4.5

    def test_texto_grande_precisa_de_3(self):
        assert a11y.required_ratio(24, "400") == 3.0

    def test_texto_medio_e_negrito_conta_como_grande(self):
        assert a11y.required_ratio(19, "700") == 3.0
        assert a11y.required_ratio(19, "400") == 4.5

    def test_reprova_contraste_baixo(self):
        falhas, avaliados, ocorrencias = a11y.audit_pairs([self._par("#b8c0c8", "#ffffff", count=4)])
        assert avaliados == 1 and len(falhas) == 1
        assert ocorrencias == 4
        assert falhas[0].ratio < 4.5

    def test_aprova_contraste_bom(self):
        falhas, avaliados, _ = a11y.audit_pairs([self._par("#111827", "#ffffff")])
        assert avaliados == 1 and not falhas

    def test_ignora_fundo_translucido(self):
        """Contra fundo translúcido não dá para afirmar o contraste."""
        falhas, avaliados, _ = a11y.audit_pairs([self._par("#888888", "rgba(255,255,255,0.1)")])
        assert avaliados == 0 and not falhas

    def test_ignora_texto_transparente(self):
        _, avaliados, _ = a11y.audit_pairs([self._par("rgba(0,0,0,0.1)", "#ffffff")])
        assert avaliados == 0

    def test_ordena_pelos_mais_frequentes(self):
        falhas, _, _ = a11y.audit_pairs(
            [self._par("#bbbbbb", "#ffffff", count=2), self._par("#cccccc", "#ffffff", count=50)]
        )
        assert falhas[0].count == 50

    def test_gravidade(self):
        falhas, _, _ = a11y.audit_pairs([self._par("#f0f0f0", "#ffffff")])
        assert falhas[0].severity == "grave"


class TestFoco:
    def _comp(self, kind, base, focus):
        return ComponentSnapshot(kind=kind, base=base, focus=focus)

    def test_aponta_foco_que_nao_muda_nada(self):
        comp = self._comp("button-primary", {"color": "#fff", "outline-width": "0px"}, {"color": "#fff", "outline-width": "0px"})
        faltando, avaliados = a11y.audit_focus([comp])
        assert faltando == ["button-primary"] and avaliados == 1

    def test_aceita_outline(self):
        comp = self._comp("button", {"outline-width": "0px"}, {"outline-width": "3px"})
        assert a11y.audit_focus([comp])[0] == []

    def test_aceita_box_shadow_como_anel(self):
        comp = self._comp("input", {"box-shadow": "none"}, {"box-shadow": "0 0 0 3px #abc"})
        assert a11y.audit_focus([comp])[0] == []

    def test_mudar_so_a_cor_do_texto_nao_basta(self):
        comp = self._comp("link", {"color": "#333"}, {"color": "#444"})
        assert a11y.audit_focus([comp])[0] == ["link"]

    def test_ignora_componente_nao_interativo(self):
        comp = self._comp("card", {"color": "#000"}, {"color": "#000"})
        assert a11y.audit_focus([comp]) == ([], 0)

    def test_sem_foco_capturado_nao_e_avaliado(self):
        comp = self._comp("button", {"color": "#000"}, {})
        assert a11y.audit_focus([comp]) == ([], 0)


class TestNotaA11y:
    def test_sem_problemas_e_cem(self):
        nota, partes = a11y.score(a11y.A11yReport(contrast_checked=10))
        assert nota == 100 and partes

    def test_desconta_e_explica(self):
        rel = a11y.A11yReport(
            contrast=[a11y.ContrastIssue("#aaa", "#fff", 2.0, 4.5, 16, "400", 3)],
            contrast_checked=10,
        )
        nota, partes = a11y.score(rel)
        assert nota < 100
        assert any("pares de texto" in p for p in partes)


# ============================================================== consistência
class TestGradeDeEspacamento:
    def test_valores_fora_da_grade(self):
        fora, proporcao = consistency.spacing_grid({"8px": 10, "16px": 10, "13px": 5}, 8)
        assert proporcao == pytest.approx(20 / 25)
        assert fora[0]["value"] == "13px" and fora[0]["nearest"] == "16px"

    def test_meio_degrau_conta_como_dentro(self):
        _, proporcao = consistency.spacing_grid({"8px": 5, "4px": 5}, 8)
        assert proporcao == 1.0

    def test_grade_pequena_demais_e_ignorada(self):
        """Com passo de 2px tudo 'cai na grade' e a métrica não diz nada."""
        fora, proporcao = consistency.spacing_grid({"13px": 9}, 2)
        assert fora == [] and proporcao == 1.0


class TestPaletaEOrfas:
    def test_tamanho_da_paleta_por_cobertura(self):
        # 500+300+150 = 950 de 1000: são 3 cores para passar de 90%.
        clusters = [{"count": 500}, {"count": 300}, {"count": 150}, {"count": 30}, {"count": 20}]
        assert consistency.core_palette_size(clusters) == 3

    def test_uma_cor_dominante_conta_como_paleta_de_uma(self):
        assert consistency.core_palette_size([{"count": 950}, {"count": 50}]) == 1

    def test_paleta_vazia(self):
        assert consistency.core_palette_size([]) == 0

    def test_cor_orfa_com_vizinha_proxima(self):
        clusters = [
            {"hex": "#2b6cf6", "value": "#2b6cf6", "count": 200},
            {"hex": "#2b6df6", "value": "#2b6df6", "count": 1},
        ]
        orfas = consistency.orphan_colors(clusters)
        assert orfas[0]["hex"] == "#2b6df6"
        assert orfas[0]["near"] == "#2b6cf6"


class TestTokensFantasma:
    def test_declarado_e_nunca_usado(self):
        fantasmas = consistency.ghost_tokens(
            ["--usado", "--esquecido"], [":root{--usado:red}.a{color:var(--usado)}"]
        )
        assert fantasmas == ["--esquecido"]

    def test_uso_com_fallback_conta(self):
        assert consistency.ghost_tokens(["--x"], ["color: var(--x, red)"]) == []

    def test_sem_fontes_nao_acusa(self):
        assert consistency.ghost_tokens(["--x"], []) == ["--x"]


class TestNotaConsistencia:
    def test_desconta_paleta_larga(self):
        rel = consistency.ConsistencyReport(base_unit=8, spacing_on_grid_ratio=1.0, palette_size=40)
        nota, partes = consistency.score(rel)
        assert nota < 100 and any("paleta larga" in p for p in partes)

    def test_sistema_impecavel(self):
        rel = consistency.ConsistencyReport(base_unit=8, spacing_on_grid_ratio=1.0, palette_size=12)
        assert consistency.score(rel)[0] == 100


# ================================================================ assinatura
class TestAssinatura:
    def test_eixos_e_frase(self):
        s = signature.compute(
            spacing_scale=[4, 8, 16, 24],
            radii_scale=[4, 8],
            weights=[400, 700],
            accents=[{"hex": "#3b82f6", "value": "#3b82f6"}],
        )
        assert len(s.axes) == 5
        assert s.sentence.startswith("Sistema")
        assert s.get("density") is not None

    def test_sistema_arejado_e_arredondado(self):
        s = signature.compute(
            spacing_scale=[24, 32, 48], radii_scale=[16, 24], weights=[400], accents=[]
        )
        assert s.get("density").label == "arejado"
        assert s.get("shape").label == "arredondado"

    def test_concordancia_no_feminino(self):
        s = signature.compute(
            spacing_scale=[8], radii_scale=[2], weights=[400],
            accents=[{"hex": "#3b82f6", "value": "#3b82f6"}],
        )
        assert "paleta moderado" not in s.sentence
        assert "paleta moderada" in s.sentence or "paleta sóbria" in s.sentence or "paleta vibrante" in s.sentence

    def test_entrada_vazia_nao_quebra(self):
        s = signature.compute(spacing_scale=[], radii_scale=[], weights=[], accents=[])
        assert len(s.axes) == 5


# ================================================================ frameworks
class TestDeteccaoDeFramework:
    def test_tailwind_por_classes(self):
        classes = {"flex": 40, "px-4": 30, "text-sm": 25, "bg-white": 20, "items-center": 18, "rounded-lg": 9}
        achados = frameworks.detect(classes)
        assert achados and achados[0].name == "Tailwind CSS"

    def test_tailwind_v4_pelas_variaveis(self):
        vars_v4 = [f"--color-blue-{i}00" for i in range(1, 10)] + ["--spacing", "--text-sm", "--radius-lg", "--font-sans"]
        achados = frameworks.detect({"flex": 10}, vars_v4)
        tailwind = next(d for d in achados if d.name == "Tailwind CSS")
        assert tailwind.version == "v4"

    def test_bootstrap_pelas_variaveis(self):
        achados = frameworks.detect({}, ["--bs-primary", "--bs-body-bg"])
        assert achados[0].name == "Bootstrap"

    def test_variavel_alheia_nao_dispara_deteccao(self):
        """Uma tupla de prefixo mal escrita fazia qualquer `--x` casar."""
        achados = frameworks.detect({}, ["--hds-color-accent", "--custom-thing"])
        assert not any(d.name == "Chakra UI" for d in achados)

    def test_prefixo_escrito_como_string_nao_quebra(self):
        assinatura = frameworks.Signature(name="X", vars_prefix="--x-")
        assert assinatura.vars_prefix == ("--x-",)

    def test_site_sem_framework(self):
        assert frameworks.summarize([]).startswith("nenhum kit")

    def test_resumo_cita_o_principal(self):
        achados = frameworks.detect({"flex": 40, "px-4": 30, "text-sm": 30, "bg-white": 20})
        assert "Tailwind" in frameworks.summarize(achados)


# ===================================================================== cores
class TestNomesDeCor:
    @pytest.mark.parametrize(
        "hexv,familia",
        [("#ef4444", "red"), ("#3b82f6", "blue"), ("#22c55e", "green"), ("#8b5cf6", "violet"), ("#f59e0b", "amber")],
    )
    def test_familia_correta(self, hexv, familia):
        assert known.color_name(parse_color(hexv)).startswith(familia)

    def test_cinza_azulado_nao_vira_azul(self):
        assert known.color_name(parse_color("#64748b")).startswith("slate")

    def test_branco_e_preto(self):
        assert known.color_name(parse_color("#ffffff")) == "white"
        assert known.color_name(parse_color("#000000")) == "black"

    def test_nome_declarado_vence_o_derivado(self):
        nomes = known.name_palette(
            [{"hex": "#3b82f6", "value": "#3b82f6"}],
            {"--color-brand": {"value": "#3b82f6"}},
        )
        assert nomes["#3b82f6"] == "brand"

    def test_variavel_interna_de_framework_e_ignorada(self):
        nomes = known.names_from_css_vars({"--tw-mask-bottom-from-color": {"value": "#000000"}})
        assert nomes == {}

    def test_nomes_nao_se_repetem(self):
        nomes = known.name_palette(
            [{"hex": "#3b82f6", "value": "#3b82f6"}, {"hex": "#3b83f6", "value": "#3b83f6"}]
        )
        assert len(set(nomes.values())) == 2

    def test_reconhece_paleta_do_tailwind(self):
        cores = [parse_color(h) for h in ("#ef4444", "#3b82f6", "#22c55e", "#f59e0b")]
        achado = known.match_tailwind(cores)
        assert achado["count"] >= 4


# ==================================================================== fontes
class TestFontes:
    def test_normaliza_camel_case(self):
        assert fonts.normalize("SourceCodePro") == "source code pro"
        assert fonts.normalize("IBMPlexMono") == "ibm plex mono"

    def test_sufixo_de_variacao_so_no_simplify(self):
        assert fonts.normalize("sohne-var") == "sohne var"
        assert fonts.simplify("sohne-var") == "sohne"

    def test_fonte_livre_nao_recebe_alternativa(self):
        assert fonts.is_libre("SourceCodePro")
        assert fonts.alternative_for("Inter") is None

    def test_alternativa_para_comercial(self):
        assert fonts.alternative_for("Söhne")[0] == "Inter"
        assert fonts.alternative_for("Circular Std")[0] == "Manrope"

    @pytest.mark.parametrize(
        "url,esperado",
        [
            ("https://fonts.gstatic.com/s/inter.woff2", "Google Fonts"),
            ("https://use.typekit.net/x.woff", "Adobe Fonts"),
            ("/fonts/local.woff2", "self-hosted"),
        ],
    )
    def test_origem(self, url, esperado):
        assert fonts.source_of([url]) == esperado

    def test_descricao_completa(self):
        saida = fonts.describe(
            [{"family": "Söhne", "count": 10, "stack": "Söhne, sans-serif"}],
            [{"family": "Söhne", "urls": ["https://x.com/sohne.woff2"]}],
        )
        assert saida[0]["alternative"] == "Inter"
        assert saida[0]["libre"] is False

    def test_generica_e_do_sistema(self):
        saida = fonts.describe([{"family": "monospace", "count": 1, "generic": True}], [])
        assert saida[0]["libre"] is True
