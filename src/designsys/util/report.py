"""Canal de progresso entre extratores e CLI.

Os extratores nunca importam Rich: falam com um Reporter. Assim dá para rodar
tudo em teste com o `SilentReporter`.
"""

from __future__ import annotations

from typing import Any


class Reporter:
    """Implementação silenciosa; a CLI substitui pelos widgets do Rich."""

    verbose = False

    def step(self, message: str) -> None: ...

    def detail(self, message: str) -> None:
        """Só aparece com --verbose."""

    def warn(self, message: str) -> None: ...

    def success(self, message: str) -> None: ...

    def page_start(self, index: int, total: int, url: str) -> None: ...

    def page_done(self, url: str, stats: dict[str, Any]) -> None: ...

    def ask_manual_login(self, url: str) -> bool:
        """Bloqueia até o usuário terminar o login manual. False = abortar."""
        return False

    def ask_credentials(self, url: str) -> tuple[str, str] | None:
        """(usuário, senha). A senha pode vir vazia em acesso por OTP/magic link."""
        return None

    def ask_otp(self, hint: str) -> str | None:
        """Código de uso único que o usuário recebeu por e-mail/SMS."""
        return None

    def ask_magic_link(self) -> str | None:
        """URL do link de acesso enviado por e-mail, colada pelo usuário."""
        return None
