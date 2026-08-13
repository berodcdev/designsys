"""Renderização do documento de impressão para PDF (Chromium do Playwright)."""

from __future__ import annotations

from pathlib import Path

FOOTER_TEMPLATE = """
<div style="width:100%;font-size:7px;color:#8c95a1;padding:0 15mm;
            font-family:-apple-system,Helvetica,Arial,sans-serif;
            display:flex;justify-content:space-between;">
  <span>__TITLE__</span>
  <span><span class="pageNumber"></span> / <span class="totalPages"></span></span>
</div>
"""

EMPTY_HEADER = '<div style="display:none"></div>'

# Mede onde cada seção começa e escreve o número da página no sumário.
# É feito no próprio DOM, já em mídia de impressão: o Chromium quebra as páginas
# na mesma altura útil que usamos aqui, então a contagem bate com o PDF.
PAGINATE_JS = r"""
(alturaUtilPx) => {
  // A posição no DOM não serve: com `break-after: page`, cada seção começa numa
  // folha nova e o espaço em branco até o fim da anterior não existe no fluxo.
  // Então contamos folha a folha: cada seção ocupa ceil(altura / altura útil).
  const secoes = Array.from(document.querySelectorAll("section.page"));
  if (!secoes.length) return {};

  // A simulação trabalha com a POSIÇÃO de cada bloco no fluxo da seção, não com
  // a soma das alturas: margens entre blocos não aparecem em `height` e somá-las
  // erra por dezenas de pixels ao longo de uma página.
  const folhasDaSecao = (secao) => {
    const base = secao.getBoundingClientRect().top;
    const estado = { folhas: 1, inicioDaFolha: 0 };

    const visitar = (elemento, profundidade) => {
      const rect = elemento.getBoundingClientRect();
      if (rect.height <= 0) return;
      const inicio = rect.top - base;
      const fim = inicio + rect.height;
      if (fim - estado.inicioDaFolha <= alturaUtilPx) return;  // ainda cabe

      const estilo = getComputedStyle(elemento);
      const inteiro = estilo.breakInside === "avoid";
      // Em grid e flex os filhos ficam lado a lado: descer neles não descreve o
      // empilhamento, então o container quebra como um todo.
      const bidimensional =
        estilo.display.indexOf("grid") >= 0 || estilo.display.indexOf("flex") >= 0;
      const filhos =
        inteiro || bidimensional || profundidade >= 4
          ? []
          : Array.from(elemento.children).filter((f) => f.getBoundingClientRect().height > 0);

      if (filhos.length) {
        for (const filho of filhos) visitar(filho, profundidade + 1);
        return;
      }
      // Não coube: este bloco começa uma folha nova.
      estado.folhas += 1;
      estado.inicioDaFolha = inicio;
      // Bloco maior que uma folha inteira: continua fatiando.
      while (fim - estado.inicioDaFolha > alturaUtilPx) {
        estado.folhas += 1;
        estado.inicioDaFolha += alturaUtilPx;
      }
    };

    for (const bloco of Array.from(secao.children)) visitar(bloco, 0);
    return estado.folhas;
  };

  const paginas = {};
  let folha = 1;
  for (const secao of secoes) {
    const indice = secao.getAttribute("data-section");
    if (indice) paginas[indice] = folha;
    folha += folhasDaSecao(secao);
  }
  for (const alvo of document.querySelectorAll("[data-toc]")) {
    const numero = paginas[alvo.getAttribute("data-toc")];
    if (numero) alvo.textContent = String(numero);
  }
  return paginas;
}
"""


class PdfError(RuntimeError):
    """Falha previsível ao gerar o PDF, com mensagem legível."""


def render_pdf(
    html_text: str,
    pdf_path: Path,
    *,
    base_dir: Path,
    title: str = "",
    timeout_ms: int = 60000,
) -> Path:
    """Escreve `html_text` como PDF A4.

    O HTML é gravado temporariamente dentro de `base_dir` para que caminhos
    relativos (assets/, screenshots/) resolvam como no style-guide.html.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise PdfError("Playwright não está instalado — rode: designsys doctor --fix") from exc

    base_dir.mkdir(parents=True, exist_ok=True)
    temp_html = base_dir / ".designsys-print.html"
    temp_html.write_text(html_text, encoding="utf-8")

    footer = FOOTER_TEMPLATE.replace("__TITLE__", _escape(title))
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1240, "height": 1754})
                page.goto(temp_html.as_uri(), wait_until="load", timeout=timeout_ms)
                # As fontes reais do site vêm da rede: sem esperar, o PDF sai
                # com a fonte de fallback.
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                try:
                    page.evaluate("() => document.fonts && document.fonts.ready")
                except Exception:
                    pass
                page.wait_for_timeout(600)
                page.emulate_media(media="print")
                page.wait_for_timeout(250)
                _paginate(page)
                pdf_path.parent.mkdir(parents=True, exist_ok=True)
                page.pdf(
                    path=str(pdf_path),
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    display_header_footer=True,
                    header_template=EMPTY_HEADER,
                    footer_template=footer,
                    # Margens no papel (não em padding do HTML): o conteúdo que
                    # transborda de uma seção continua respeitando-as.
                    margin={"top": "14mm", "bottom": "16mm", "left": "15mm", "right": "15mm"},
                )
            finally:
                browser.close()
    except Exception as exc:
        if isinstance(exc, PdfError):
            raise
        message = str(exc).splitlines()[0][:200]
        if "Executable doesn't exist" in message or "playwright install" in message:
            raise PdfError(
                "o Chromium do Playwright não está instalado — rode: designsys doctor --fix"
            ) from exc
        raise PdfError(f"não consegui gerar o PDF: {message}") from exc
    finally:
        temp_html.unlink(missing_ok=True)

    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise PdfError("o PDF saiu vazio")
    return pdf_path


MM_TO_PX = 96 / 25.4
A4_WIDTH_PX = round(210 * MM_TO_PX)
A4_HEIGHT_PX = round(297 * MM_TO_PX)


def _paginate(page: Any) -> None:
    """Escreve no sumário a página em que cada seção começa.

    A medição precisa acontecer com a viewport do tamanho da folha: numa janela
    mais larga o texto ocupa menos linhas e as imagens ficam mais baixas, e a
    contagem sai diferente da que o PDF vai produzir.
    """
    altura_util_px = (297 - 14 - 16) * MM_TO_PX  # A4 menos as margens de `page.pdf`
    try:
        page.set_viewport_size({"width": A4_WIDTH_PX, "height": A4_HEIGHT_PX})
        page.wait_for_timeout(350)
        page.evaluate(PAGINATE_JS, altura_util_px)
    except Exception:
        pass  # sem números de página o documento continua válido


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
