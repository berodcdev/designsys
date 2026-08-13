"""Parser tolerante de objetos literais JavaScript/TypeScript.

Não executa JS — varre o texto. Valores que não são literais (chamadas de
função, imports, spreads, template literals interpolados) viram `JSRaw`, que
os consumidores registram como "não resolvido" em vez de descartar em silêncio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_NUMBER = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+)")


@dataclass
class JSRaw:
    """Trecho que não é um literal — guardado como veio, para diagnóstico."""

    text: str

    def __repr__(self) -> str:  # pragma: no cover - debug
        return f"JSRaw({self.text[:40]!r})"


class JSObjectParser:
    def __init__(self, text: str, pos: int = 0) -> None:
        self.s = text
        self.i = pos
        self.unresolved: list[str] = []

    # ------------------------------------------------------------------ util
    def _skip(self) -> None:
        s, n = self.s, len(self.s)
        while self.i < n:
            c = s[self.i]
            if c in " \t\r\n,;":
                self.i += 1
            elif c == "/" and self.i + 1 < n and s[self.i + 1] == "/":
                j = s.find("\n", self.i)
                self.i = n if j < 0 else j + 1
            elif c == "/" and self.i + 1 < n and s[self.i + 1] == "*":
                j = s.find("*/", self.i + 2)
                self.i = n if j < 0 else j + 2
            else:
                return

    def _string(self) -> str:
        quote = self.s[self.i]
        self.i += 1
        out = []
        n = len(self.s)
        while self.i < n:
            c = self.s[self.i]
            if c == "\\" and self.i + 1 < n:
                nxt = self.s[self.i + 1]
                out.append({"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt))
                self.i += 2
                continue
            if c == quote:
                self.i += 1
                break
            out.append(c)
            self.i += 1
        return "".join(out)

    def _template(self) -> Any:
        start = self.i
        self.i += 1
        n = len(self.s)
        interpolated = False
        out = []
        while self.i < n:
            c = self.s[self.i]
            if c == "\\" and self.i + 1 < n:
                out.append(self.s[self.i + 1])
                self.i += 2
                continue
            if c == "$" and self.i + 1 < n and self.s[self.i + 1] == "{":
                interpolated = True
                depth = 1
                self.i += 2
                while self.i < n and depth:
                    if self.s[self.i] == "{":
                        depth += 1
                    elif self.s[self.i] == "}":
                        depth -= 1
                    self.i += 1
                continue
            if c == "`":
                self.i += 1
                break
            out.append(c)
            self.i += 1
        text = "".join(out)
        if interpolated:
            raw = self.s[start : self.i]
            self.unresolved.append(raw[:80])
            return JSRaw(raw)
        return text

    def _raw_until_delimiter(self) -> JSRaw:
        """Consome uma expressão arbitrária respeitando aninhamento e strings."""
        start = self.i
        depth = 0
        n = len(self.s)
        while self.i < n:
            c = self.s[self.i]
            if c in "\"'`":
                if c == "`":
                    self._template()
                else:
                    self._string()
                continue
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif c in ",;" and depth == 0:
                break
            elif c == "\n" and depth == 0:
                # quebra de linha só encerra se o próximo token começa uma chave
                ahead = self.s[self.i + 1 : self.i + 80]
                if re.match(r"\s*[\}\]]", ahead):
                    break
            self.i += 1
        text = self.s[start : self.i].strip()
        self.unresolved.append(text[:80])
        return JSRaw(text)

    # ----------------------------------------------------------------- parse
    def parse_value(self) -> Any:
        self._skip()
        if self.i >= len(self.s):
            return None
        c = self.s[self.i]
        if c == "{":
            return self.parse_object()
        if c == "[":
            return self.parse_array()
        if c in "\"'":
            return self._string()
        if c == "`":
            return self._template()
        if self.s.startswith("true", self.i):
            self.i += 4
            return True
        if self.s.startswith("false", self.i):
            self.i += 5
            return False
        if self.s.startswith("null", self.i):
            self.i += 4
            return None
        m = _NUMBER.match(self.s, self.i)
        if m:
            end = m.end()
            # "12px" ou "2rem" não são número JS, mas aparecem sem aspas em configs quebrados.
            after = self.s[end : end + 1]
            if after.isalpha() or after == "%":
                return self._raw_until_delimiter()
            self.i = end
            text = m.group(0)
            try:
                return int(text, 0) if not any(ch in text for ch in ".eE") else float(text)
            except ValueError:
                return float(text)
        return self._raw_until_delimiter()

    def parse_array(self) -> list[Any]:
        assert self.s[self.i] == "["
        self.i += 1
        out: list[Any] = []
        n = len(self.s)
        while self.i < n:
            self._skip()
            if self.i >= n:
                break
            if self.s[self.i] == "]":
                self.i += 1
                break
            out.append(self.parse_value())
        return out

    def parse_object(self) -> dict[str, Any]:
        assert self.s[self.i] == "{"
        self.i += 1
        out: dict[str, Any] = {}
        n = len(self.s)
        while self.i < n:
            self._skip()
            if self.i >= n:
                break
            c = self.s[self.i]
            if c == "}":
                self.i += 1
                break
            # chave
            if c in "\"'":
                key = self._string()
            elif c == "[":
                # chave computada: pula
                depth = 0
                start = self.i
                while self.i < n:
                    if self.s[self.i] == "[":
                        depth += 1
                    elif self.s[self.i] == "]":
                        depth -= 1
                        if depth == 0:
                            self.i += 1
                            break
                    self.i += 1
                key = self.s[start : self.i]
            elif c == ".":
                # spread: ...colors
                m = re.match(r"\.\.\.([^,}\n]+)", self.s[self.i :])
                if m:
                    self.unresolved.append(f"...{m.group(1).strip()}")
                    self.i += m.end()
                    continue
                self.i += 1
                continue
            else:
                m = _IDENT.match(self.s, self.i)
                if m:
                    key = m.group(0)
                    self.i = m.end()
                else:
                    m2 = _NUMBER.match(self.s, self.i)
                    if m2:
                        key = m2.group(0)
                        self.i = m2.end()
                    else:
                        self.i += 1
                        continue
            self._skip()
            if self.i < n and self.s[self.i] == ":":
                self.i += 1
                out[key] = self.parse_value()
            elif self.i < n and self.s[self.i] == "(":
                # método abreviado: pula o corpo
                self._raw_until_delimiter()
                out[key] = JSRaw("<function>")
            else:
                out[key] = JSRaw(key)  # shorthand { colors }
                self.unresolved.append(key)
        return out


_EXPORT_PATTERNS = [
    r"module\.exports\s*=\s*",
    r"export\s+default\s+",
    r"export\s*=\s*",
    r"exports\.default\s*=\s*",
]

_WRAPPERS = [
    r"defineConfig\s*\(",
    r"satisfies\s+\w+",
    r"withOpacity\s*\(",
]


def find_config_object(text: str) -> tuple[dict[str, Any], list[str]]:
    """Extrai o objeto de configuração exportado por um módulo JS/TS."""
    for pattern in _EXPORT_PATTERNS:
        for m in re.finditer(pattern, text):
            pos = m.end()
            # pula wrappers como defineConfig(
            sub = text[pos : pos + 60]
            wm = re.match(r"\s*(defineConfig|withTV|createConfig)\s*\(", sub)
            if wm:
                pos += wm.end()
            # identificador exportado: procura a declaração dele
            im = re.match(r"\s*([A-Za-z_$][\w$]*)\s*(?:;|$|\n)", text[pos : pos + 60])
            if im:
                name = im.group(1)
                decl = re.search(
                    rf"(?:const|let|var)\s+{re.escape(name)}\s*(?::[^=]+)?=\s*(?:defineConfig\s*\()?\s*\{{",
                    text,
                )
                if decl:
                    start = text.index("{", decl.start())
                    parser = JSObjectParser(text, start)
                    return parser.parse_object(), parser.unresolved
                continue
            brace = text.find("{", pos)
            if brace >= 0 and brace - pos < 80:
                parser = JSObjectParser(text, brace)
                return parser.parse_object(), parser.unresolved

    # Sem export reconhecível: tenta o primeiro objeto que contenha "theme".
    m = re.search(r"\btheme\s*:\s*\{", text)
    if m:
        start = text.rindex("{", 0, m.start())
        parser = JSObjectParser(text, start)
        return parser.parse_object(), parser.unresolved
    return {}, []


def find_named_object(text: str, names: list[str]) -> tuple[dict[str, Any], list[str]]:
    """Procura `const <name> = { ... }` ou `createTheme({ ... })`."""
    for name in names:
        decl = re.search(
            rf"(?:const|let|var|export\s+const)\s+{re.escape(name)}\s*(?::[^=]+)?=\s*\{{",
            text,
        )
        if decl:
            start = text.index("{", decl.start())
            parser = JSObjectParser(text, start)
            return parser.parse_object(), parser.unresolved
    for call in ("createTheme", "extendTheme", "createGlobalTheme", "createMuiTheme"):
        m = re.search(rf"{call}\s*\(\s*\{{", text)
        if m:
            start = text.index("{", m.start())
            parser = JSObjectParser(text, start)
            return parser.parse_object(), parser.unresolved
    return {}, []


def flatten(obj: Any, prefix: str = "", sep: str = "-") -> dict[str, Any]:
    """Achata um objeto aninhado em chaves tipo `colors-brand-500`."""
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            name = f"{prefix}{sep}{key}" if prefix else str(key)
            name = name.replace(f"{sep}DEFAULT", "")
            out.update(flatten(value, name, sep))
    elif isinstance(obj, list):
        if obj and all(isinstance(x, str) for x in obj):
            out[prefix] = obj
        else:
            for idx, value in enumerate(obj):
                out.update(flatten(value, f"{prefix}{sep}{idx}", sep))
    elif isinstance(obj, JSRaw):
        pass
    elif obj is not None:
        out[prefix] = obj
    return out
