"""Download de assets e CSS, com retry único e nomes de arquivo seguros."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

DEFAULT_TIMEOUT = 20
MAX_BYTES = 12 * 1024 * 1024  # 12 MB por asset

_session = requests.Session()
_session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }
)


def fetch_text(url: str, headers: dict[str, str] | None = None, retries: int = 1) -> str | None:
    """Baixa um recurso textual (CSS). None em qualquer falha."""
    for attempt in range(retries + 1):
        try:
            r = _session.get(url, headers=headers or {}, timeout=DEFAULT_TIMEOUT)
            if r.status_code == 200:
                return r.text
            if r.status_code in (401, 403, 404):
                return None
        except requests.RequestException:
            pass
    return None


def download(
    url: str,
    dest: Path,
    headers: dict[str, str] | None = None,
    retries: int = 1,
) -> Path | None:
    """Baixa um binário para `dest`. Devolve o caminho final ou None."""
    for attempt in range(retries + 1):
        try:
            with _session.get(
                url, headers=headers or {}, timeout=DEFAULT_TIMEOUT, stream=True
            ) as r:
                if r.status_code != 200:
                    if r.status_code in (401, 403, 404):
                        return None
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Corrige a extensão quando a URL não tem uma (ex.: /avatar?id=1).
                final = _with_extension(dest, r.headers.get("Content-Type", ""))
                size = 0
                with open(final, "wb") as fh:
                    for chunk in r.iter_content(65536):
                        size += len(chunk)
                        if size > MAX_BYTES:
                            fh.close()
                            final.unlink(missing_ok=True)
                            return None
                        fh.write(chunk)
                if size == 0:
                    final.unlink(missing_ok=True)
                    return None
                return final
        except requests.RequestException:
            continue
        except OSError:
            return None
    return None


def _with_extension(dest: Path, content_type: str) -> Path:
    if dest.suffix:
        return dest
    ext = mimetypes.guess_extension((content_type or "").split(";")[0].strip()) or ""
    if ext == ".jpe":
        ext = ".jpg"
    return dest.with_suffix(ext) if ext else dest


def safe_name(url: str, fallback: str = "asset", max_len: int = 60) -> str:
    """Nome de arquivo determinístico e legível a partir de uma URL."""
    parsed = urlparse(url)
    base = os.path.basename(unquote(parsed.path)) or fallback
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-.") or fallback
    stem, dot, ext = base.rpartition(".")
    if not dot:
        stem, ext = base, ""
    stem = stem[:max_len]
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:6]
    name = f"{stem}-{digest}"
    return f"{name}.{ext}" if ext else name


def content_hash(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha1(data).hexdigest()


def same_site(url: str, origin: str) -> bool:
    try:
        a, b = urlparse(url), urlparse(origin)
        return a.netloc == b.netloc
    except ValueError:
        return False
