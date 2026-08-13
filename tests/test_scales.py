"""Inferência de escalas numéricas e de strings."""

import pytest

from designsys.analysis.scales import (
    detect_base_unit,
    duration_ms,
    infer_breakpoints,
    infer_scale,
    infer_string_scale,
    name_size_steps,
    name_spacing_steps,
    normalize_duration,
    parse_length,
    round_px,
    shadow_weight,
)


class TestParseLength:
    @pytest.mark.parametrize(
        "value,expected",
        [("16px", 16), ("1rem", 16), ("2rem", 32), ("0.5rem", 8), ("12pt", 16), ("0", 0), (24, 24), ("1.5em", 24)],
    )
    def test_converte_para_px(self, value, expected):
        assert parse_length(value) == pytest.approx(expected, abs=0.01)

    @pytest.mark.parametrize("value", ["auto", "normal", "50%", "100vh", "none", "", None, "calc(100% - 2px)"])
    def test_nao_comprimentos(self, value):
        assert parse_length(value) is None

    def test_root_font_size_customizado(self):
        assert parse_length("1rem", root_px=10) == 10


class TestInferScale:
    def test_extrai_escala_frequente_ignorando_ruido(self):
        counts = {"4px": 100, "8px": 200, "16px": 300, "24px": 150, "32px": 90, "13.328px": 2, "7.5px": 1}
        escala = infer_scale(counts, min_share=0.02)
        assert escala == [4, 8, 16, 24, 32]

    def test_resultado_ordenado_por_valor_nao_por_frequencia(self):
        escala = infer_scale({"32px": 500, "4px": 400, "16px": 300})
        assert escala == [4, 16, 32]

    def test_zero_excluido_por_padrao(self):
        assert 0 not in infer_scale({"0px": 999, "8px": 10})

    def test_zero_incluido_sob_demanda(self):
        assert 0 in infer_scale({"0px": 999, "8px": 10}, include_zero=True)

    def test_respeita_limites(self):
        escala = infer_scale({"4px": 10, "800px": 10, "16px": 10}, max_value=100)
        assert 800 not in escala and 16 in escala

    def test_respeita_max_items(self):
        counts = {f"{i * 4}px": 100 - i for i in range(1, 30)}
        assert len(infer_scale(counts, max_items=8)) == 8

    def test_normaliza_rem(self):
        assert infer_scale({"1rem": 10, "2rem": 10}) == [16, 32]

    def test_entrada_vazia(self):
        assert infer_scale({}) == []
        assert infer_scale({"auto": 10, "none": 5}) == []

    def test_aceita_sequencia_simples(self):
        assert infer_scale(["8px", "8px", "16px"]) == [8, 16]

    def test_colapsa_erros_de_arredondamento(self):
        assert infer_scale({"15.9998px": 50, "16px": 50}) == [16]


class TestBaseUnit:
    def test_detecta_grade_de_8(self):
        assert detect_base_unit([8, 16, 24, 32, 64]) == 8

    def test_detecta_grade_de_4(self):
        assert detect_base_unit([4, 12, 20, 28]) == 4

    def test_sem_grade_reconhecivel(self):
        assert detect_base_unit([3, 7, 13, 29, 55, 111]) is None

    def test_poucos_valores(self):
        assert detect_base_unit([8, 16]) is None


class TestNomes:
    def test_spacing_estilo_tailwind(self):
        assert name_spacing_steps([4, 8, 16]) == {"1": 4, "2": 8, "4": 16}

    def test_spacing_meio_passo(self):
        assert "0.5" in name_spacing_steps([2, 4])

    def test_size_steps_sem_none_quando_nao_ha_zero(self):
        nomes = name_size_steps([2, 4, 8])
        assert "none" not in nomes
        assert list(nomes) == ["xs", "sm", "md"]

    def test_size_steps_com_none_quando_ha_zero(self):
        assert list(name_size_steps([0, 4]))[0] == "none"

    def test_raio_gigante_vira_full(self):
        nomes = name_size_steps([4, 8, 9999])
        assert nomes["full"] == 9999


class TestStringScale:
    def test_ordena_por_frequencia_e_limita(self):
        result = infer_string_scale({"a": 5, "b": 50, "c": 1}, max_items=2)
        assert [v for v, _ in result] == ["b", "a"]

    def test_descarta_none(self):
        assert infer_string_scale({"none": 99, "0 1px 2px red": 5}) == [("0 1px 2px red", 5)]

    def test_normaliza_espacos(self):
        result = infer_string_scale({"0  1px   2px": 3, "0 1px 2px": 2})
        assert len(result) == 1 and result[0][1] == 5

    def test_ordenacao_por_peso_de_sombra(self):
        sombras = {"0 20px 40px rgba(0,0,0,.2)": 5, "0 1px 2px rgba(0,0,0,.1)": 5}
        result = infer_string_scale(sombras, sort_key=shadow_weight)
        assert result[0][0].startswith("0 1px")

    def test_normalize_callback(self):
        result = infer_string_scale({".3s": 2, "300ms": 3}, normalize=normalize_duration)
        assert result == [("300ms", 5)]


class TestDuracoes:
    @pytest.mark.parametrize("value,ms", [("300ms", 300), ("0.3s", 300), (".3s", 300), ("1s", 1000), ("x", 0)])
    def test_duration_ms(self, value, ms):
        assert duration_ms(value) == ms

    @pytest.mark.parametrize("value,expected", [(".3s", "300ms"), ("0.3s", "300ms"), ("1s", "1s"), ("2000ms", "2s")])
    def test_normalize(self, value, expected):
        assert normalize_duration(value) == expected


class TestBreakpoints:
    def test_extrai_de_media_queries(self):
        queries = ["(min-width: 640px)", "(min-width: 768px)", "(max-width: 1024px)"]
        assert infer_breakpoints(queries) == [640, 768, 1024]

    def test_funde_pares_min_max_vizinhos(self):
        assert infer_breakpoints(["(max-width: 639px)", "(min-width: 640px)"]) == [640]

    def test_converte_em_rem(self):
        assert infer_breakpoints(["(min-width: 40rem)"]) == [640]

    def test_ignora_larguras_absurdas(self):
        assert infer_breakpoints(["(min-width: 1px)", "(min-width: 99999px)"]) == []

    def test_sem_media_queries(self):
        assert infer_breakpoints([]) == []


def test_round_px_colapsa_ruido_de_subpixel():
    assert round_px(15.9998) == 16.0
    assert round_px(16.5) == 16.5
