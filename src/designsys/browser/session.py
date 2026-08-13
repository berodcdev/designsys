"""Sessão de navegador persistente por domínio.

O perfil vive em ~/.designsys/profiles/<domínio>/ para que cookies de login
sobrevivam entre execuções — nenhuma senha é gravada, só o perfil do Chromium.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable

PROFILE_ROOT = Path.home() / ".designsys" / "profiles"

# Cookies de sessão (sem Expires) são descartados pelo Chromium ao fechar, e é
# justamente o que muitos SaaS usam. Guardamos o storage_state à parte e o
# reinjetamos na abertura, para que "logar uma vez" valha de verdade.
STATE_FILE = "designsys-state.json"
MAX_STATE_BYTES = 2 * 1024 * 1024

DEFAULT_VIEWPORT = {"width": 1440, "height": 900}
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--no-first-run",
    "--no-default-browser-check",
]


class BrowserError(RuntimeError):
    """Erro previsível de navegador, já com mensagem legível para o usuário."""


def profile_dir_for(domain: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", domain or "default")
    return PROFILE_ROOT / safe


class BrowserSession:
    def __init__(
        self,
        domain: str,
        *,
        headed: bool = False,
        verbose: bool = False,
        log: Callable[[str], None] = lambda m: None,
        timeout_ms: int = 30000,
    ) -> None:
        self.domain = domain
        self.headed = headed
        self.verbose = verbose
        self.log = log
        self.timeout_ms = timeout_ms
        self.profile_dir = profile_dir_for(domain)
        self._pw: Any = None
        self.context: Any = None
        self.page: Any = None
        self.blocked_requests: list[str] = []

    # ------------------------------------------------------------------ ciclo
    def __enter__(self) -> "BrowserSession":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def start(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise BrowserError(
                "Playwright não está instalado. Rode: designsys doctor --fix"
            ) from exc
        self._pw = sync_playwright().start()
        self._launch()

    def _launch(self) -> None:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.context = self._pw.chromium.launch_persistent_context(
                str(self.profile_dir),
                headless=not self.headed,
                viewport=DEFAULT_VIEWPORT,
                user_agent=DEFAULT_UA,
                args=LAUNCH_ARGS,
                locale="pt-BR",
                ignore_https_errors=True,
                accept_downloads=False,
            )
        except Exception as exc:
            msg = str(exc)
            if "Executable doesn't exist" in msg or "playwright install" in msg:
                raise BrowserError(
                    "O Chromium do Playwright não está instalado.\n"
                    "Rode: designsys doctor --fix  (ou: playwright install chromium)"
                ) from exc
            raise BrowserError(f"não consegui abrir o Chromium: {msg}") from exc

        self.context.set_default_timeout(self.timeout_ms)
        self.context.set_default_navigation_timeout(self.timeout_ms)
        # Máscara leve de automação — alguns SaaS bloqueiam navigator.webdriver.
        try:
            self.context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
        except Exception:
            pass
        self._restore_state()
        pages = self.context.pages
        self.page = pages[0] if pages else self.context.new_page()

    def restart(self, *, headed: bool) -> None:
        """Reabre o navegador no outro modo, preservando o perfil (e a sessão)."""
        current_url = None
        try:
            current_url = self.page.url if self.page else None
        except Exception:
            pass
        self._close_context()
        self.headed = headed
        self._launch()
        if current_url and current_url != "about:blank":
            try:
                self.goto(current_url)
            except Exception:
                pass

    # ------------------------------------------------------------- sessão
    @property
    def state_path(self) -> Path:
        return self.profile_dir / STATE_FILE

    def save_state(self) -> bool:
        """Grava cookies (inclusive os de sessão) e localStorage do contexto."""
        if not self.context:
            return False
        try:
            state = self.context.storage_state()
        except Exception as exc:
            self.log(f"não consegui salvar a sessão: {exc}")
            return False
        if not state.get("cookies") and not state.get("origins"):
            return False
        try:
            payload = json.dumps(state)
            if len(payload) > MAX_STATE_BYTES:
                state = {"cookies": state.get("cookies", []), "origins": []}
                payload = json.dumps(state)
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(payload, encoding="utf-8")
            os.chmod(self.state_path, 0o600)  # contém tokens de sessão
            return True
        except (OSError, TypeError, ValueError) as exc:
            self.log(f"não consegui gravar {self.state_path.name}: {exc}")
            return False

    def _restore_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        cookies = [c for c in state.get("cookies", []) if isinstance(c, dict)]
        if cookies:
            try:
                self.context.add_cookies(cookies)
                self.log(f"{len(cookies)} cookie(s) restaurados da sessão anterior")
            except Exception as exc:
                self.log(f"não consegui restaurar cookies: {exc}")
        # Tokens em localStorage são comuns em SPAs; repõe antes de qualquer JS
        # da página rodar.
        for origin in state.get("origins", []):
            items = origin.get("localStorage") or []
            if not items:
                continue
            try:
                self.context.add_init_script(
                    "(() => { if (location.origin !== %s) return;"
                    " const data = %s;"
                    " try { for (const [k, v] of data) localStorage.setItem(k, v); } catch (e) {} })();"
                    % (
                        json.dumps(origin.get("origin", "")),
                        json.dumps([[i.get("name"), i.get("value")] for i in items]),
                    )
                )
            except Exception:
                continue

    def _close_context(self) -> None:
        self.save_state()
        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        self.context = None
        self.page = None

    def close(self) -> None:
        self._close_context()
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._pw = None

    # --------------------------------------------------------------- navegação
    def goto(self, url: str, *, retries: int = 1, settle_ms: int = 1200) -> None:
        """Navega com 1 retry e espera a página assentar (fontes + rede ociosa)."""
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                self.settle(settle_ms)
                return
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    self.log(f"falha ao carregar {url}, tentando de novo…")
                    try:
                        self.page.wait_for_timeout(1500)
                    except Exception:
                        pass
        raise BrowserError(_friendly_nav_error(url, last_error))

    def settle(self, settle_ms: int = 1200) -> None:
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        try:
            self.page.evaluate("() => document.fonts && document.fonts.ready")
        except Exception:
            pass
        try:
            self.page.wait_for_timeout(settle_ms)
        except Exception:
            pass

    def scroll_through(self, steps: int = 4) -> None:
        """Rola a página para disparar lazy-loading antes da coleta."""
        try:
            for i in range(steps):
                self.page.evaluate(
                    "(i) => window.scrollTo(0, document.body.scrollHeight * i / %d)" % steps,
                    i + 1,
                )
                self.page.wait_for_timeout(250)
            self.page.evaluate("() => window.scrollTo(0, 0)")
            self.page.wait_for_timeout(200)
        except Exception:
            pass

    def screenshot(self, path: Path, full_page: bool = True) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(path), full_page=full_page)
            return True
        except Exception as exc:
            self.log(f"screenshot falhou: {exc}")
            return False

    def cookies_header_for(self, url: str) -> dict[str, str]:
        """Cookies da sessão como header, para baixar assets protegidos por login."""
        try:
            cookies = self.context.cookies(url)
        except Exception:
            return {}
        if not cookies:
            return {}
        jar = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        return {"Cookie": jar, "User-Agent": DEFAULT_UA}


def _friendly_nav_error(url: str, exc: Exception | None) -> str:
    msg = str(exc) if exc else "erro desconhecido"
    if "ERR_NAME_NOT_RESOLVED" in msg:
        return f"não consegui resolver o domínio de {url} — confira a URL ou sua conexão."
    if "ERR_CONNECTION_REFUSED" in msg:
        return f"conexão recusada por {url} — o servidor está no ar?"
    if "ERR_CERT" in msg:
        return f"certificado TLS inválido em {url}."
    if "Timeout" in msg or "timeout" in msg:
        return f"{url} demorou demais para responder (timeout)."
    if "ERR_INTERNET_DISCONNECTED" in msg:
        return "sem conexão com a internet."
    return f"não consegui carregar {url}: {msg.splitlines()[0][:200]}"


def clear_profile(domain: str) -> bool:
    d = profile_dir_for(domain)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        return True
    return False
