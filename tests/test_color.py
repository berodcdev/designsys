"""Parsing, distância e clustering de cores."""

import pytest

from designsys.analysis.color import (
    ColorCluster,
    cluster_colors,
    contrast_ratio,
    distance,
    is_neutral,
    parse_color,
    scale_name,
    to_css,
    to_hex,
    to_oklch,
)


class TestParseColor:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("#fff", "#ffffff"),
            ("#FFF", "#ffffff"),
            ("#000000", "#000000"),
            ("#635BFF", "#635bff"),
            ("rgb(99, 91, 255)", "#635bff"),
            ("rgba(99, 91, 255, 1)", "#635bff"),
            ("rgb(99 91 255)", "#635bff"),
            ("hsl(0, 100%, 50%)", "#ff0000"),
            ("white", "#ffffff"),
            ("black", "#000000"),
            ("#12345678", "#12345678"),
        ],
    )
    def test_formatos_validos(self, value, expected):
        assert to_hex(parse_color(value)) == expected

    @pytest.mark.parametrize(
        "value",
        ["none", "transparent", "inherit", "", "auto", "url(x.png)", "linear-gradient(red, blue)", None, "not-a-color"],
    )
    def test_nao_cores(self, value):
        assert parse_color(value) is None

    def test_alpha_preservado(self):
        rgba = parse_color("rgba(0, 0, 0, 0.5)")
        assert rgba[3] == pytest.approx(0.5, abs=0.01)
        assert to_css(rgba).startswith("rgba(")

    def test_notacoes_modernas(self):
        """oklch/lab aparecem em sites com Tailwind v4."""
        assert parse_color("oklch(0.7 0.15 250)") is not None
        assert parse_color("lab(63.3038% -18.433 -51.0407)") is not None

    def test_transparente_tem_alpha_zero(self):
        assert parse_color("rgba(0, 0, 0, 0)")[3] == 0.0

    def test_percentuais_rgb(self):
        assert to_hex(parse_color("rgb(100%, 0%, 0%)")) == "#ff0000"


class TestDistancia:
    def test_cores_quase_identicas_ficam_perto(self):
        assert distance(parse_color("#ff0000"), parse_color("#fe0101")) < 0.02

    def test_cores_distintas_ficam_longe(self):
        assert distance(parse_color("#ff0000"), parse_color("#00ff00")) > 0.3

    def test_alpha_afasta(self):
        opaco = parse_color("#000000")
        translucido = parse_color("rgba(0, 0, 0, 0.2)")
        assert distance(opaco, translucido) > 0.3

    def test_simetrica(self):
        a, b = parse_color("#123456"), parse_color("#654321")
        assert distance(a, b) == pytest.approx(distance(b, a))


class TestClustering:
    def test_agrupa_quase_identicas_mantendo_a_mais_frequente(self):
        clusters = cluster_colors([("#ff0000", 100), ("#fe0101", 5), ("#ff0100", 3)])
        assert len(clusters) == 1
        assert clusters[0].hex == "#ff0000"  # representante = mais usada
        assert clusters[0].count == 108
        assert len(clusters[0].members) == 3

    def test_nao_agrupa_cores_distintas(self):
        clusters = cluster_colors([("#ff0000", 10), ("#00ff00", 10), ("#0000ff", 10)])
        assert len(clusters) == 3

    def test_ordena_por_frequencia(self):
        clusters = cluster_colors([("#ff0000", 5), ("#00ff00", 50), ("#0000ff", 20)])
        assert [c.hex for c in clusters] == ["#00ff00", "#0000ff", "#ff0000"]

    def test_descarta_totalmente_transparente(self):
        assert cluster_colors([("rgba(0, 0, 0, 0)", 99)]) == []

    def test_ignora_valores_invalidos(self):
        clusters = cluster_colors([("#ff0000", 10), ("banana", 10), ("none", 3)])
        assert len(clusters) == 1

    def test_soma_duplicatas_exatas(self):
        clusters = cluster_colors([("#ff0000", 10), ("rgb(255,0,0)", 15)])
        assert len(clusters) == 1
        assert clusters[0].count == 25

    def test_threshold_controla_agressividade(self):
        entries = [("#ff0000", 10), ("#f01010", 10)]
        assert len(cluster_colors(entries, threshold=0.001)) == 2
        assert len(cluster_colors(entries, threshold=0.5)) == 1

    def test_propaga_propriedades(self):
        clusters = cluster_colors(
            [("#ff0000", 10), ("#fe0101", 4)],
            properties={"#ff0000": {"color": 10}, "#fe0101": {"background-color": 4}},
        )
        assert clusters[0].properties == {"color": 10, "background-color": 4}

    def test_entrada_vazia(self):
        assert cluster_colors([]) == []

    def test_aceita_tuplas_rgba(self):
        clusters = cluster_colors([((1.0, 0.0, 0.0, 1.0), 7)])
        assert clusters[0].hex == "#ff0000"


class TestNeutralidadeEContraste:
    @pytest.mark.parametrize("value", ["#ffffff", "#000000", "#808080", "#f5f5f5", "#1f2937"])
    def test_neutros(self, value):
        assert is_neutral(parse_color(value))

    @pytest.mark.parametrize("value", ["#ff0000", "#635bff", "#00d924", "#f6339a"])
    def test_nao_neutros(self, value):
        assert not is_neutral(parse_color(value))

    def test_contraste_maximo(self):
        assert contrast_ratio(parse_color("#000000"), parse_color("#ffffff")) == pytest.approx(21, abs=0.1)

    def test_contraste_minimo(self):
        assert contrast_ratio(parse_color("#777777"), parse_color("#777777")) == pytest.approx(1.0)


class TestOklch:
    def test_hue_do_vermelho(self):
        _, chroma, hue = to_oklch(parse_color("#ff0000"))
        assert chroma > 0.1
        assert 15 <= hue <= 45

    def test_lightness_ordena_claro_para_escuro(self):
        assert to_oklch(parse_color("#ffffff"))[0] > to_oklch(parse_color("#888888"))[0]
        assert to_oklch(parse_color("#888888"))[0] > to_oklch(parse_color("#000000"))[0]


class TestScaleName:
    def test_extremos(self):
        assert scale_name(0, 11) == "50"
        assert scale_name(10, 11) == "950"

    def test_escala_unica(self):
        assert scale_name(0, 1) == "500"

    def test_monotonico(self):
        nomes = [int(scale_name(i, 6)) for i in range(6)]
        assert nomes == sorted(nomes)


def test_cluster_expõe_css_e_hex():
    cluster = ColorCluster(color=parse_color("rgba(0,0,0,0.5)"), count=1)
    assert cluster.hex.startswith("#000000")
    assert cluster.css.startswith("rgba(")
