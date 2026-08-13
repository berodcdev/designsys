"""Identificação das fontes: de onde vêm e o que usar no lugar.

As sugestões de alternativa são aproximações de *estilo* — proporção, largura e
peso parecidos — não equivalências métricas. Uma troca de fonte sempre pede
ajuste de tamanho e entrelinha; o objetivo aqui é dar um ponto de partida livre
para quem não pode licenciar a original.
"""

from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urlparse

# Serviço de origem, pela URL do @font-face.
SOURCES: list[tuple[str, str]] = [
    ("fonts.gstatic.com", "Google Fonts"),
    ("fonts.googleapis.com", "Google Fonts"),
    ("use.typekit.net", "Adobe Fonts"),
    ("p.typekit.net", "Adobe Fonts"),
    ("use.fontawesome.com", "Font Awesome"),
    ("fonts.bunny.net", "Bunny Fonts"),
    ("cdn.jsdelivr.net", "CDN pública"),
    ("unpkg.com", "CDN pública"),
    ("fontlibrary.org", "Font Library"),
    ("cloud.typography.com", "Hoefler&Co"),
    ("fast.fonts.net", "Monotype"),
    ("use.fonts.net", "Monotype"),
]

# Fontes que já são livres — não precisam de alternativa.
LIBRE = {
    "inter", "roboto", "open sans", "lato", "montserrat", "poppins", "nunito", "nunito sans",
    "raleway", "work sans", "dm sans", "dm serif display", "manrope", "space grotesk",
    "space mono", "ibm plex sans", "ibm plex serif", "ibm plex mono", "source sans 3",
    "source serif 4", "source code pro", "jetbrains mono", "fira sans", "fira code",
    "playfair display", "merriweather", "lora", "karla", "rubik", "public sans", "figtree",
    "outfit", "plus jakarta sans", "instrument sans", "geist", "geist mono", "noto sans",
    "libre franklin", "archivo", "epilogue", "sora", "urbanist", "jost", "cabin", "mulish",
}

# Alternativas livres para fontes comerciais frequentes. Chave em minúsculas e
# sem sufixos de peso/variação.
ALTERNATIVES: dict[str, tuple[str, str]] = {
    "sohne": ("Inter", "grotesca neutra de mesma proporção"),
    "söhne": ("Inter", "grotesca neutra de mesma proporção"),
    "circular": ("Manrope", "geométrica de terminais arredondados"),
    "circular std": ("Manrope", "geométrica de terminais arredondados"),
    "gt america": ("Inter", "grotesca americana neutra"),
    "gt walsheim": ("Poppins", "geométrica de formas amplas"),
    "graphik": ("Public Sans", "grotesca de baixo contraste"),
    "gilroy": ("Poppins", "geométrica de traço uniforme"),
    "proxima nova": ("Montserrat", "humanista de esqueleto geométrico"),
    "avenir": ("Nunito Sans", "geométrica humanista"),
    "avenir next": ("Nunito Sans", "geométrica humanista"),
    "helvetica neue": ("Inter", "neogrotesca de mesma cor de texto"),
    "helvetica": ("Inter", "neogrotesca de mesma cor de texto"),
    "arial": ("Inter", "substituição direta em tela"),
    "futura": ("Jost", "geométrica desenhada a partir da Futura"),
    "tiempos": ("Source Serif 4", "serifada de texto para tela"),
    "tiempos text": ("Source Serif 4", "serifada de texto para tela"),
    "canela": ("Playfair Display", "serifada de display com contraste alto"),
    "suisse int'l": ("Inter", "grotesca suíça neutra"),
    "suisse": ("Inter", "grotesca suíça neutra"),
    "basier": ("Inter", "grotesca neutra"),
    "aeonik": ("Inter", "grotesca contemporânea"),
    "tt norms": ("Poppins", "geométrica de largura regular"),
    "maison neue": ("Inter", "grotesca neutra"),
    "founders grotesk": ("Archivo", "grotesca condensada"),
    "national": ("Archivo", "grotesca de texto"),
    "apercu": ("Work Sans", "grotesca levemente humanista"),
    "sf pro": ("Inter", "desenhada para telas, métricas próximas"),
    "sf pro display": ("Inter", "desenhada para telas, métricas próximas"),
    "sf pro text": ("Inter", "desenhada para telas, métricas próximas"),
    "sf mono": ("JetBrains Mono", "monoespaçada de tela"),
    "segoe ui": ("Inter", "grotesca de interface"),
    "-apple-system": ("Inter", "grotesca de interface"),
    "system-ui": ("Inter", "grotesca de interface"),
    "roobert": ("Plus Jakarta Sans", "grotesca geométrica"),
    "monument extended": ("Archivo Expanded", "expandida de display"),
    "sharp grotesk": ("Archivo", "grotesca de display"),
    "recoleta": ("Fraunces", "serifada suave de display"),
}

# Sufixos de peso/variação. "pro" e "display" também são parte de nomes legítimos
# (Source Code Pro, Playfair Display), por isso a remoção é uma segunda tentativa,
# nunca a forma canônica.
_SUFFIXES = re.compile(
    r"[-_ ]?(variable|var|vf|regular|medium|bold|light|semibold|book|web|std)$", re.I
)


def normalize(family: str) -> str:
    """Forma canônica: minúsculas, separadores uniformes, camelCase aberto.

    `SourceCodePro` → `source code pro`; `IBMPlexMono` → `ibm plex mono`.
    """
    nome = (family or "").strip().strip("\"'")
    nome = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", nome)
    nome = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", nome)
    nome = nome.lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", nome).strip()


def simplify(family: str) -> str:
    """Como `normalize`, mas sem os sufixos de peso/variação (`sohne var` → `sohne`)."""
    nome = normalize(family)
    anterior = None
    while anterior != nome:
        anterior = nome
        nome = _SUFFIXES.sub("", nome).strip()
    return nome


def source_of(urls: Iterable[str], site_origin: str = "") -> str:
    """Onde a fonte está hospedada."""
    lista = [u for u in (urls or []) if u]
    if not lista:
        return "não identificada"
    for url in lista:
        for marca, nome in SOURCES:
            if marca in url:
                return nome
    if site_origin:
        host_site = urlparse(site_origin).netloc
        for url in lista:
            if url.startswith("/") or urlparse(url).netloc == host_site:
                return "self-hosted"
    if any(u.startswith("/") for u in lista):
        return "self-hosted"
    return "terceiro"


def is_libre(family: str) -> bool:
    """Nome cheio primeiro: `source code pro` é livre, `source code` não existe."""
    return normalize(family) in LIBRE or simplify(family) in LIBRE


def alternative_for(family: str) -> tuple[str, str] | None:
    """Alternativa livre sugerida, ou None quando a fonte já é livre."""
    if is_libre(family):
        return None
    for nome in (normalize(family), simplify(family)):
        if nome and nome in ALTERNATIVES:
            return ALTERNATIVES[nome]
    # `sohne mono`, `circular book`: tenta a primeira palavra.
    primeira = simplify(family).split(" ")[0]
    if primeira in ALTERNATIVES:
        return ALTERNATIVES[primeira]
    return None


def describe(
    families: list[dict[str, Any]],
    font_faces: list[dict[str, Any]],
    site_origin: str = "",
) -> list[dict[str, Any]]:
    """Junta cada família com origem, licença aparente e alternativa."""
    urls_por_familia: dict[str, list[str]] = {}
    for face in font_faces or []:
        for chave in {normalize(face.get("family", "")), simplify(face.get("family", ""))}:
            if chave:
                urls_por_familia.setdefault(chave, []).extend(face.get("urls") or [])

    saida: list[dict[str, Any]] = []
    for familia in families or []:
        nome = familia.get("family", "")
        chave = normalize(nome)
        urls = urls_por_familia.get(chave) or urls_por_familia.get(simplify(nome)) or []
        alternativa = alternative_for(nome)
        saida.append(
            {
                "family": nome,
                "normalized": chave,
                "count": familia.get("count", 0),
                "stack": familia.get("stack", ""),
                "generic": bool(familia.get("generic")),
                "source": source_of(urls, site_origin) if urls else ("do sistema" if familia.get("generic") else "não identificada"),
                # Genérica (`monospace`, `system-ui`) é do sistema: não há licença em jogo.
                "libre": True if familia.get("generic") else is_libre(nome),
                "alternative": alternativa[0] if alternativa else None,
                "alternative_reason": alternativa[1] if alternativa else "",
            }
        )
    return saida
