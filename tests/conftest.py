"""Configuração compartilhada dos testes.

Marca automaticamente o que precisa do Chromium, para que `pytest -m "not browser"`
rode a suíte rápida — útil em máquina sem o navegador instalado e para o ciclo
curto de desenvolvimento.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Arquivos em que todos os testes sobem um navegador.
ARQUIVOS_COM_NAVEGADOR = {"test_login.py", "test_themes.py"}

# Testes espalhados que também precisam dele (renderização de PDF).
TRECHOS_COM_NAVEGADOR = (
    "TestRenderPdf",
    "numeros_reais_no_pdf",
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        arquivo = Path(str(item.fspath)).name
        precisa = arquivo in ARQUIVOS_COM_NAVEGADOR or any(
            trecho in item.nodeid for trecho in TRECHOS_COM_NAVEGADOR
        )
        if precisa:
            item.add_marker(pytest.mark.browser)
