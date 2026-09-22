"""designsys — extrai o design system completo de um site ao vivo ou de um repositório."""

from importlib.metadata import PackageNotFoundError, version as _version

try:
    # A versão mora só no pyproject.toml. Mantê-la aqui também significaria, um
    # dia, publicar uma versão que o `--version` do CLI relata errado.
    __version__ = _version("designsys")
except PackageNotFoundError:  # rodando direto do fonte, sem instalar
    __version__ = "0+desconhecida"

__all__ = ["__version__"]
