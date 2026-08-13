"""Exportação para o Tokens Studio (plugin do Figma).

O formato é próximo do DTCG, mas com particularidades próprias: `type`/`value`
em vez de `$type`/`$value`, conjuntos de tokens no topo, e `$themes`/`$metadata`
descrevendo como esses conjuntos se combinam. Claro e escuro viram dois
conjuntos que compartilham o mesmo `global`.
"""

from __future__ import annotations

from typing import Any

from ..analysis.color import scale_name
from ..analysis.typography import name_font_sizes
from ..models import DesignSystem
from .tokens import token_name


def _token(value: Any, tipo: str, description: str = "") -> dict[str, Any]:
    saida: dict[str, Any] = {"value": value, "type": tipo}
    if description:
        saida["description"] = description
    return saida


def _dim(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:g}px"
    return str(value)


def build_tokens_studio(ds: DesignSystem) -> dict[str, Any]:
    """Monta o JSON completo, com os conjuntos e a descrição dos temas."""
    global_set: dict[str, Any] = {}
    light_set: dict[str, Any] = {}
    dark_set: dict[str, Any] = {}

    # ---------------------------------------------------------------- cores
    papeis = ds.colors.get("roles") or {}
    pares = (ds.themes or {}).get("pairs") or {}
    for papel, info in papeis.items():
        nome = token_name(papel)
        light_set.setdefault("color", {})[nome] = _token(
            info["value"], "color", info.get("reason", "")
        )
        escuro = (pares.get(papel) or {}).get("dark")
        if escuro:
            dark_set.setdefault("color", {})[nome] = _token(escuro, "color", info.get("reason", ""))

    neutros = ds.colors.get("neutrals") or []
    if neutros:
        grupo = {
            scale_name(i, len(neutros)): _token(entrada["value"], "color")
            for i, entrada in enumerate(neutros)
        }
        global_set.setdefault("color", {})["neutral"] = grupo

    nomeadas = ds.colors.get("named") or {}
    for nome, valor in nomeadas.items():
        global_set.setdefault("color", {})[token_name(nome)] = _token(valor, "color")

    acentos = ds.colors.get("accents") or []
    if acentos:
        global_set.setdefault("color", {})["accent"] = {
            str(i): _token(entrada["value"], "color")
            for i, entrada in enumerate(acentos[:10], start=1)
        }

    # ------------------------------------------------------------- espaço
    for nome, valor in (ds.spacing.get("named") or {}).items():
        global_set.setdefault("spacing", {})[token_name(nome)] = _token(_dim(valor), "spacing")
    for nome, valor in (ds.radii.get("named") or {}).items():
        global_set.setdefault("borderRadius", {})[token_name(nome)] = _token(
            _dim(valor), "borderRadius"
        )
    for largura in ds.borders.get("widths") or []:
        global_set.setdefault("borderWidth", {})[token_name(f"{largura:g}")] = _token(
            _dim(largura), "borderWidth"
        )

    # -------------------------------------------------------- tipografia
    typo = ds.typography or {}
    for indice, familia in enumerate((typo.get("families") or [])[:5]):
        chave = "base" if indice == 0 else token_name(familia["family"])
        global_set.setdefault("fontFamilies", {})[chave] = _token(
            familia.get("stack") or familia["family"], "fontFamilies"
        )
    for peso in typo.get("weights") or []:
        global_set.setdefault("fontWeights", {})[str(peso)] = _token(str(peso), "fontWeights")

    tamanhos = (typo.get("named") or {}).get("fontSize") or name_font_sizes(typo.get("sizes") or [])
    for nome, valor in tamanhos.items():
        global_set.setdefault("fontSizes", {})[token_name(nome)] = _token(_dim(valor), "fontSizes")

    for estilo in typo.get("scale") or []:
        global_set.setdefault("typography", {})[token_name(estilo["name"])] = _token(
            {
                "fontFamily": estilo.get("fontFamily") or "",
                "fontSize": _dim(estilo.get("fontSize", 16)),
                "fontWeight": str(estilo.get("fontWeight", 400)),
                "lineHeight": str(estilo.get("lineHeight", "AUTO")),
                "letterSpacing": str(estilo.get("letterSpacing", "0")),
            },
            "typography",
        )

    # ------------------------------------------------------------ sombras
    for indice, sombra in enumerate(ds.shadows or []):
        nome = token_name(sombra.get("name") or f"shadow-{indice + 1}")
        global_set.setdefault("boxShadow", {})[nome] = _token(sombra["value"], "boxShadow")

    # ------------------------------------------------------------- outros
    for indice, ponto in enumerate(ds.breakpoints or []):
        nomes = ["sm", "md", "lg", "xl", "2xl", "3xl", "4xl", "5xl"]
        chave = nomes[indice] if indice < len(nomes) else f"bp{indice}"
        global_set.setdefault("sizing", {})[chave] = _token(f"{ponto}px", "sizing")
    for valor in ds.opacity or []:
        global_set.setdefault("opacity", {})[str(int(valor * 100))] = _token(
            f"{int(valor * 100)}%", "opacity"
        )

    documento: dict[str, Any] = {"global": global_set}
    conjuntos = ["global"]
    if light_set:
        documento["light"] = light_set
        conjuntos.append("light")
    if dark_set:
        documento["dark"] = dark_set
        conjuntos.append("dark")

    documento["$themes"] = _themes(ds, bool(light_set), bool(dark_set))
    documento["$metadata"] = {"tokenSetOrder": conjuntos}
    return documento


def _themes(ds: DesignSystem, tem_claro: bool, tem_escuro: bool) -> list[dict[str, Any]]:
    """Descrição dos temas: quais conjuntos ficam ativos em cada um."""
    if not tem_claro:
        return []

    def tema(nome: str, conjunto: str) -> dict[str, Any]:
        grupos = {"global": "source", conjunto: "enabled"}
        if conjunto != "light" and tem_claro:
            grupos["light"] = "disabled"
        return {
            "id": nome,
            "name": nome.capitalize(),
            "selectedTokenSets": grupos,
            "$figmaCollectionId": "",
            "$figmaModeId": "",
        }

    temas = [tema("light", "light")]
    if tem_escuro:
        temas.append(tema("dark", "dark"))
    return temas
