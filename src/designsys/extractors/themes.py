"""Descoberta do tema escuro de um site.

Três estratégias, da menos à mais invasiva. Todas terminam com uma verificação
objetiva: se a página não mudou de cara, o site não tem tema escuro e nada é
inventado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# Marcas usadas pelos toggles mais comuns (Tailwind `darkMode: 'class'`,
# next-themes, data-attributes).
FORCE_DARK_JS = r"""
() => {
  const raiz = document.documentElement;
  const antes = {
    classe: raiz.className,
    dataTheme: raiz.getAttribute("data-theme"),
    dataMode: raiz.getAttribute("data-mode"),
    colorScheme: raiz.style.colorScheme,
    bodyClasse: document.body ? document.body.className : "",
  };
  raiz.classList.add("dark");
  raiz.setAttribute("data-theme", "dark");
  raiz.setAttribute("data-mode", "dark");
  raiz.setAttribute("data-color-mode", "dark");
  raiz.style.colorScheme = "dark";
  if (document.body) document.body.classList.add("dark");
  return antes;
}
"""

RESTORE_JS = r"""
(antes) => {
  const raiz = document.documentElement;
  raiz.className = antes.classe;
  if (antes.dataTheme === null) raiz.removeAttribute("data-theme");
  else raiz.setAttribute("data-theme", antes.dataTheme);
  if (antes.dataMode === null) raiz.removeAttribute("data-mode");
  else raiz.setAttribute("data-mode", antes.dataMode);
  raiz.removeAttribute("data-color-mode");
  raiz.style.colorScheme = antes.colorScheme || "";
  if (document.body) document.body.className = antes.bodyClasse;
}
"""

# Um controle de tema quase sempre se anuncia em algum destes lugares.
TOGGLE_SELECTORS = [
    "[data-theme-toggle]",
    "[data-testid*='theme' i]",
    "button[aria-label*='dark' i]",
    "button[aria-label*='theme' i]",
    "button[aria-label*='tema' i]",
    "button[aria-label*='modo escuro' i]",
    "button[title*='dark' i]",
    "button[title*='theme' i]",
    "[role=switch][aria-label*='theme' i]",
    "button:has(svg[class*='moon' i])",
    "[class*='theme-toggle' i]",
    "[class*='darkmode' i]",
]

# Quanto o fundo precisa escurecer para considerarmos que virou tema escuro.
LUMINANCE_DROP = 0.18


@dataclass
class ThemeAttempt:
    ok: bool
    strategy: str
    detail: str = ""


def _background_luminance(page: Any) -> float | None:
    """Luminância do fundo efetivo da página."""
    try:
        valor = page.evaluate(
            """() => {
                const corpo = getComputedStyle(document.body).backgroundColor;
                const raiz = getComputedStyle(document.documentElement).backgroundColor;
                const opaca = (c) => c && c !== "transparent" && !/rgba\\(\\s*0,\\s*0,\\s*0,\\s*0\\s*\\)/.test(c);
                return opaca(corpo) ? corpo : (opaca(raiz) ? raiz : "rgb(255,255,255)");
            }"""
        )
    except Exception:
        return None
    from ..analysis.color import luminance, parse_color

    rgba = parse_color(valor)
    return luminance(rgba) if rgba else None


def _texto_clareou(page: Any) -> bool:
    """Sinal complementar: no tema escuro a cor do texto sobe de luminância."""
    try:
        valor = page.evaluate("() => getComputedStyle(document.body).color")
    except Exception:
        return False
    from ..analysis.color import luminance, parse_color

    rgba = parse_color(valor)
    return bool(rgba and luminance(rgba) > 0.45)


def apply_dark(page: Any, *, log: Callable[[str], None] = lambda m: None) -> ThemeAttempt:
    """Tenta colocar a página em tema escuro. Não recolhe nada — só aplica."""
    base = _background_luminance(page)
    if base is None:
        return ThemeAttempt(False, "none", "não consegui medir o fundo da página")

    def mudou() -> bool:
        atual = _background_luminance(page)
        if atual is None:
            return False
        if base - atual >= LUMINANCE_DROP:
            return True
        # Sites que já são escuros por padrão: aí o sinal é o texto clarear.
        return base < 0.25 and _texto_clareou(page)

    # 1) prefers-color-scheme -------------------------------------------------
    try:
        page.emulate_media(color_scheme="dark")
        page.wait_for_timeout(700)
        if mudou():
            log("tema escuro via prefers-color-scheme")
            return ThemeAttempt(True, "prefers-color-scheme")
    except Exception as exc:
        log(f"emulate_media falhou: {exc}")

    # 2) classe/atributo na raiz ---------------------------------------------
    try:
        antes = page.evaluate(FORCE_DARK_JS)
        page.wait_for_timeout(700)
        if mudou():
            log("tema escuro via classe/atributo na raiz")
            return ThemeAttempt(True, "class")
        page.evaluate(RESTORE_JS, antes)
    except Exception as exc:
        log(f"forçar classe dark falhou: {exc}")

    # 3) clicar no controle de tema ------------------------------------------
    for seletor in TOGGLE_SELECTORS:
        try:
            alvo = page.locator(seletor).first
            if alvo.count() == 0 or not alvo.is_visible():
                continue
            alvo.click(timeout=2500)
            page.wait_for_timeout(900)
            if mudou():
                log(f"tema escuro via toggle do site ({seletor})")
                return ThemeAttempt(True, "toggle", seletor)
            alvo.click(timeout=2500)  # desfaz
            page.wait_for_timeout(400)
        except Exception:
            continue

    try:
        page.emulate_media(color_scheme="light")
    except Exception:
        pass
    return ThemeAttempt(False, "none", "o site não muda de aparência em tema escuro")


def restore_light(page: Any) -> None:
    """Volta a página ao estado claro, para não contaminar as próximas coletas."""
    try:
        page.emulate_media(color_scheme="light")
    except Exception:
        pass
    try:
        page.evaluate(
            """() => {
                const raiz = document.documentElement;
                raiz.classList.remove("dark");
                raiz.removeAttribute("data-theme");
                raiz.removeAttribute("data-mode");
                raiz.removeAttribute("data-color-mode");
                raiz.style.colorScheme = "";
                if (document.body) document.body.classList.remove("dark");
            }"""
        )
    except Exception:
        pass


def pair_roles(light: dict[str, Any], dark: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Casa os papéis dos dois temas: {'primary': {'light': ..., 'dark': ...}}."""
    pares: dict[str, dict[str, str]] = {}
    papeis_claros = light.get("roles") or {}
    papeis_escuros = dark.get("roles") or {}
    for papel, info in papeis_claros.items():
        par = {"light": info["value"]}
        escuro = papeis_escuros.get(papel)
        if escuro:
            par["dark"] = escuro["value"]
        pares[papel] = par
    for papel, info in papeis_escuros.items():
        if papel not in pares:
            pares[papel] = {"dark": info["value"]}
    return pares
