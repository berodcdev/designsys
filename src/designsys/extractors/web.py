"""Extração de design system a partir de um site ao vivo (Playwright)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from ..analysis import classify, color as colormod, report, scales, typography
from ..browser import login as loginmod
from ..browser.session import BrowserError, BrowserSession
from ..models import Asset, ComponentSnapshot, DesignSystem, FontFace
from ..util import net
from ..util.cssparse import parse_css
from ..util.report import Reporter
from . import themes as thememod
from .buckets import DARK, MAIN, VIEWPORTS, TokenBucket, color_fingerprint
from .js_collect import (
    ASSETS_JS,
    COLLECT_JS,
    COLLECT_VIEWPORT_JS,
    COMPONENT_PROPS,
    COMPONENTS_JS,
    LINKS_JS,
    PASSIVE_STATES_JS,
    STYLE_OF_JS,
)

# Rotas que costumam concentrar o design system de um SaaS.
PRIORITY_PATTERNS = [
    r"^/(dashboard|app|home)",
    r"^/(settings|preferences|config)",
    r"^/(profile|account|me)",
    r"^/(billing|subscription|plans?|pricing)",
    r"^/(projects?|workspaces?|teams?|organizations?)",
    r"^/(users?|members?|admin)",
    r"^/(reports?|analytics|insights)",
    r"^/(docs?|documentation|guides?)",
    r"^/(products?|features?|solutions?)",
    r"^/(blog|news|customers|about|contact)",
    r"^/(login|signup|register)",
]

SKIP_PATTERNS = re.compile(
    r"\.(pdf|zip|dmg|exe|csv|xlsx?|docx?|mp4|mp3|png|jpe?g|gif|svg|webp|ico|txt|xml|rss)$"
    r"|/(logout|signout|sign-out|api/|cdn-cgi/|feed)",
    re.I,
)


@dataclass
class WebOptions:
    url: str
    pages: int = 8
    paths: list[str] = field(default_factory=list)
    out: Path | None = None
    no_assets: bool = False
    headed: bool = False
    login: bool = False
    username: str | None = None
    password: str | None = None
    verbose: bool = False
    timeout_ms: int = 30000
    keep_open: bool = False
    no_dark: bool = False
    viewports: bool = True
    exhaustive: bool = False


class WebExtractor:
    def __init__(self, options: WebOptions, reporter: Reporter | None = None) -> None:
        self.opt = options
        self.rep = reporter or Reporter()
        self.origin = _origin_of(options.url)
        self.domain = urlparse(options.url).netloc
        self.ds = DesignSystem(mode="url", target=options.url, name=self.domain)
        self.out_dir: Path = options.out or Path.cwd()

        # Um acumulador por contexto (tema × viewport); `light` é o canônico.
        self.buckets: dict[str, TokenBucket] = {MAIN: TokenBucket(name=MAIN)}

        # Acumuladores que não dependem de tema nem de viewport.
        self.media_queries: list[str] = []
        self.font_faces: dict[str, FontFace] = {}
        self.blocked_sheets: set[str] = set()
        self.components: dict[str, ComponentSnapshot] = {}
        self.assets: dict[str, Asset] = {}
        self.icon_hashes: set[str] = set()
        self.login_result: loginmod.LoginOutcome | None = None
        self.visited: list[str] = []
        self.class_tokens: Counter = Counter()
        self.attr_hints: Counter = Counter()
        self.button_variants: list[dict[str, Any]] = []
        self.passive_states: dict[str, Any] = {}
        self.page_fingerprints: list[dict[str, Any]] = []
        self.theme_report: dict[str, Any] = {"dark": False, "strategy": "none", "detail": ""}
        self.stopped_early: str = ""

    # ------------------------------------------------------------- contextos
    def bucket(self, name: str) -> TokenBucket:
        if name not in self.buckets:
            self.buckets[name] = TokenBucket(name=name)
        return self.buckets[name]

    @property
    def main(self) -> TokenBucket:
        return self.buckets[MAIN]

    # ===================================================================== run
    def run(self) -> DesignSystem:
        session = BrowserSession(
            self.domain,
            headed=self.opt.headed,
            verbose=self.opt.verbose,
            log=self.rep.detail,
            timeout_ms=self.opt.timeout_ms,
        )
        session.start()
        try:
            self.rep.step(f"abrindo {self.opt.url}")
            session.goto(self.opt.url)
            self._handle_login(session)
            queue = self._build_queue(session)
            total = len(queue)
            for index, url in enumerate(queue, start=1):
                if index > 1:
                    try:
                        self.rep.page_start(index, total, url)
                        session.goto(url)
                    except BrowserError as exc:
                        self.rep.warn(str(exc))
                        continue
                else:
                    self.rep.page_start(index, total, url)
                self._collect_page(session, url, first=(index == 1))
                if self._saturated(index, total):
                    break
                # Descobre novas páginas conforme navega (SPAs revelam rotas depois do login).
                if len(queue) < self.opt.pages + 1:
                    for candidate in self._discover_links(session):
                        if candidate not in queue and len(queue) < self.opt.pages + 1:
                            queue.append(candidate)
                            total = len(queue)
            self._fetch_blocked_stylesheets(session)
            if not self.opt.no_assets:
                self._download_assets(session)
        finally:
            if not self.opt.keep_open:
                session.close()
        self._aggregate()
        return self.ds

    # =================================================================== login
    def _handle_login(self, session: BrowserSession) -> None:
        page = session.page
        needs_login = loginmod.looks_like_login_page(page)

        if not needs_login and not self.opt.login:
            return
        if not needs_login and self.opt.login:
            # --login explícito: procura a tela de login se ainda não estamos nela.
            if not loginmod.has_login_form(page):
                self.rep.detail("sessão já parece autenticada (perfil persistente)")
                self.login_result = loginmod.LoginOutcome(
                    True, "session", "sessão persistente reaproveitada"
                )
                return

        if not self.opt.login and needs_login:
            self.rep.warn(
                "a página pede login — rode de novo com --login para autenticar."
            )
            return

        username, password = self.opt.username, self.opt.password
        if not username:
            creds = self.rep.ask_credentials(self.opt.url)
            if creds:
                username, password = creds

        # A senha é opcional: sites com OTP ou magic link pedem só o e-mail.
        if username:
            self.rep.step("tentando login automático")
            outcome = loginmod.attempt_login(
                page,
                username,
                password,
                log=self.rep.detail,
                timeout_ms=self.opt.timeout_ms,
                ask_otp=self.rep.ask_otp,
                ask_magic_link=self.rep.ask_magic_link,
            )
            self.login_result = outcome
            if outcome.ok:
                self.rep.success(f"login automático: {outcome.detail}")
                session.settle()
                return
            self.rep.warn(f"login automático não concluiu: {outcome.detail}")
        else:
            self.rep.detail("sem credenciais: indo direto para o login manual")

        # ------------------------------------------------- fallback manual
        if not session.headed:
            self.rep.step("abrindo navegador visível para login manual")
            session.restart(headed=True)
        ok = self.rep.ask_manual_login(session.page.url)
        if not ok:
            self.ds.warnings.append("login manual cancelado pelo usuário")
            self.login_result = loginmod.LoginOutcome(False, "manual", "cancelado")
            return
        session.settle()
        authenticated = loginmod.is_authenticated(session.page)
        self.login_result = loginmod.LoginOutcome(
            authenticated,
            "manual",
            "sessão autenticada manualmente" if authenticated else "ainda parece deslogado",
        )
        if authenticated:
            self.rep.success("login manual concluído — sessão salva no perfil")
        else:
            self.rep.warn("depois do login manual a página ainda parece deslogada; seguindo mesmo assim")

    def _saturated(self, index: int, total: int) -> bool:
        """Para quando as páginas deixam de trazer token novo.

        `--pages` é um teto, não uma meta: visitar mais dez páginas que só
        repetem o que já temos custa tempo e não melhora o design system.
        """
        if self.opt.exhaustive or index < 3 or index >= total:
            return False
        ultimas = self.page_fingerprints[-2:]
        if len(ultimas) < 2:
            return False
        total_visto = max(1, len(self.main.token_signature()))
        if all(p["new_tokens"] / total_visto < 0.02 for p in ultimas):
            self.stopped_early = (
                f"parei na {index}ª de {total} páginas — as duas últimas não trouxeram "
                "token novo (use --exhaustive para varrer todas)"
            )
            self.rep.step(self.stopped_early)
            return True
        return False

    # ============================================================== navegação
    def _build_queue(self, session: BrowserSession) -> list[str]:
        queue = [session.page.url]
        for path in self.opt.paths:
            url = urljoin(self.origin, path)
            if url not in queue:
                queue.append(url)
        if len(queue) - 1 < self.opt.pages:
            for url in self._discover_links(session):
                if url not in queue:
                    queue.append(url)
                if len(queue) - 1 >= self.opt.pages:
                    break
        return queue[: self.opt.pages + 1]

    def _discover_links(self, session: BrowserSession) -> list[str]:
        try:
            links = session.page.evaluate(LINKS_JS) or []
        except Exception:
            return []
        scored: list[tuple[int, str]] = []
        for link in links:
            url = link.get("url") or ""
            path = link.get("path") or "/"
            if not url or SKIP_PATTERNS.search(url):
                continue
            if url in self.visited:
                continue
            depth = path.strip("/").count("/")
            score = 100 - depth * 10
            for i, pattern in enumerate(PRIORITY_PATTERNS):
                if re.search(pattern, path, re.I):
                    score += 200 - i * 5
                    break
            if path in ("/", ""):
                score -= 150
            scored.append((score, url))
        scored.sort(key=lambda s: (-s[0], s[1]))
        seen: set[str] = set()
        out: list[str] = []
        for _, url in scored:
            norm = url.rstrip("/")
            if norm in seen:
                continue
            seen.add(norm)
            out.append(url)
        return out

    # ================================================================= coleta
    def _collect_page(self, session: BrowserSession, url: str, first: bool) -> None:
        session.scroll_through()
        try:
            data = session.page.evaluate(COLLECT_JS)
        except Exception as exc:
            self.rep.warn(f"não consegui coletar estilos de {url}: {exc}")
            return

        self.visited.append(session.page.url)
        antes = self.main.token_signature()
        self._merge_page_data(data)
        novos = len(self.main.token_signature() - antes)

        stats = {
            "elementos": data.get("elementCount", 0),
            "regras CSS": data.get("ruleCount", 0),
            "cores": sum(len(v) for v in (data.get("colors") or {}).values()),
            "tokens novos": novos,
        }
        self.page_fingerprints.append(
            {
                "url": session.page.url,
                "new_tokens": novos,
                "buttons": dict(Counter(data.get("buttonBackgrounds") or {}).most_common(3)),
                "families": [f for f, _ in Counter(
                    {s.get("fontFamily", ""): s.get("count", 1) for s in (data.get("typography") or [])}
                ).most_common(3) if f],
            }
        )

        # Contextos extras: tema escuro e viewports menores.
        if first and not self.opt.no_dark:
            self._collect_dark(session)
        if self.opt.viewports:
            self._collect_viewports(session, first=first)

        if not self.opt.no_assets:
            try:
                assets = session.page.evaluate(ASSETS_JS)
                self._merge_assets(assets, session.page.url)
            except Exception as exc:
                self.rep.detail(f"coleta de assets falhou: {exc}")

        self._collect_components(session, first=first)

        shot = self.out_dir / "screenshots" / f"{len(self.visited):02d}-{_slug(session.page.url)}.png"
        if session.screenshot(shot):
            self.ds.assets.append(
                Asset(kind="screenshot", url=session.page.url, path=str(shot.relative_to(self.out_dir)))
            )

        self.ds.pages.append(
            {
                "url": session.page.url,
                "title": data.get("title", ""),
                "elements": data.get("elementCount", 0),
                "rules": data.get("ruleCount", 0),
                "screenshot": str(shot.relative_to(self.out_dir)) if shot.exists() else None,
            }
        )
        self.rep.page_done(session.page.url, stats)

    def _merge_page_data(self, data: dict[str, Any], bucket: TokenBucket | None = None) -> None:
        alvo = bucket or self.main
        alvo.merge_page(data, page_url=data.get("url", ""))

        # Fatos globais, que não pertencem a um contexto específico.
        self.media_queries.extend(data.get("mediaQueries") or [])
        for ff in data.get("fontFaces") or []:
            self._add_font_face(ff)
        for href in data.get("blockedSheets") or []:
            self.blocked_sheets.add(href)
        for token, count in (data.get("classTokens") or {}).items():
            self.class_tokens[token] += count
        for attr, count in (data.get("attrHints") or {}).items():
            self.attr_hints[attr] += count

    # ------------------------------------------------------ contextos extras
    def _collect_dark(self, session: BrowserSession) -> None:
        """Coloca a página em tema escuro e recoleta, se o site tiver um."""
        tentativa = thememod.apply_dark(session.page, log=self.rep.detail)
        if not tentativa.ok:
            self.theme_report = {"dark": False, "strategy": "none", "detail": tentativa.detail}
            thememod.restore_light(session.page)
            return
        try:
            dados = session.page.evaluate(COLLECT_JS)
        except Exception as exc:
            self.rep.detail(f"coleta do tema escuro falhou: {exc}")
            thememod.restore_light(session.page)
            return

        escuro = self.bucket(DARK)
        escuro.merge_page(dados, page_url=session.page.url)

        # Confirmação final: se a paleta saiu igual à clara, não era um tema.
        if color_fingerprint(escuro) == color_fingerprint(self.main):
            self.buckets.pop(DARK, None)
            self.theme_report = {
                "dark": False,
                "strategy": tentativa.strategy,
                "detail": "a paleta não mudou de verdade",
            }
        else:
            self.theme_report = {
                "dark": True,
                "strategy": tentativa.strategy,
                "detail": tentativa.detail or "tema escuro capturado",
            }
            self.rep.success(f"tema escuro capturado ({tentativa.strategy})")
        thememod.restore_light(session.page)
        session.settle(400)

    def _collect_viewports(self, session: BrowserSession, first: bool) -> None:
        """Recoleta tipografia e espaçamento em telas menores."""
        original = dict(session.page.viewport_size or {"width": 1440, "height": 900})
        for nome, tamanho in VIEWPORTS.items():
            try:
                session.page.set_viewport_size(tamanho)
                session.page.wait_for_timeout(500)
                if first:
                    session.scroll_through(steps=2)
                dados = session.page.evaluate(COLLECT_VIEWPORT_JS)
            except Exception as exc:
                self.rep.detail(f"coleta em {nome} falhou: {exc}")
                continue
            self.bucket(nome).merge_page(dados, page_url=session.page.url, light=True)
        try:
            session.page.set_viewport_size(original)
            session.page.wait_for_timeout(300)
        except Exception:
            pass

    def _add_font_face(self, ff: dict[str, Any]) -> None:
        family = (ff.get("family") or ff.get("font-family") or "").strip().strip("\"'")
        if not family:
            return
        weight = str(ff.get("weight") or ff.get("font-weight") or "400").strip()
        style = str(ff.get("style") or ff.get("font-style") or "normal").strip()
        src = ff.get("src") or ""
        urls = [
            urljoin(ff.get("href") or self.origin, u)
            for u in re.findall(r"url\(\s*[\"']?([^\"')]+)", src)
        ]
        key = f"{family}|{weight}|{style}"
        existing = self.font_faces.get(key)
        if existing:
            for u in urls:
                if u not in existing.urls:
                    existing.urls.append(u)
            return
        self.font_faces[key] = FontFace(
            family=family,
            weight=weight,
            style=style,
            urls=urls,
            display=(ff.get("display") or ff.get("font-display") or None),
            unicode_range=(ff.get("unicodeRange") or ff.get("unicode-range") or None),
        )

    # ============================================================ componentes
    def _collect_components(self, session: BrowserSession, first: bool) -> None:
        try:
            found = session.page.evaluate(COMPONENTS_JS, COMPONENT_PROPS) or []
        except Exception as exc:
            self.rep.detail(f"detecção de componentes falhou: {exc}")
            return

        page_url = session.page.url
        budget = 14 if first else 6
        captured = 0
        for item in found:
            kind = item.get("kind")
            if not kind:
                continue
            if kind == "__button_variants__":
                if first:
                    self.button_variants = item.get("variants") or []
                continue
            key = kind
            suffix = 1
            while key in self.components and not first:
                break
            if kind in self.components:
                # Já temos esse tipo; só substitui se o novo tiver mais estilos.
                if len(item.get("base") or {}) <= len(self.components[kind].base):
                    continue
            if captured >= budget:
                break
            snap = ComponentSnapshot(
                kind=kind,
                selector=item.get("selector", ""),
                label=item.get("label", ""),
                html=item.get("html", ""),
                base=item.get("base") or {},
                page=page_url,
            )
            snap.hover = self._state_styles(session, snap.selector, "hover")
            snap.focus = self._state_styles(session, snap.selector, "focus")
            if kind.startswith("button") or kind in ("link", "input"):
                snap.active = self._state_styles(session, snap.selector, "active")
            self.components[kind] = snap
            captured += 1

        if first and not self.passive_states:
            try:
                self.passive_states = session.page.evaluate(PASSIVE_STATES_JS, COMPONENT_PROPS) or {}
            except Exception as exc:
                self.rep.detail(f"estados passivos falharam: {exc}")

    def _state_styles(self, session: BrowserSession, selector: str, state: str) -> dict[str, str]:
        if not selector:
            return {}
        try:
            loc = session.page.locator(selector).first
            if loc.count() == 0:
                return {}
            if state == "hover":
                loc.hover(timeout=2500)
            elif state == "active":
                # :active só existe com o botão do mouse pressionado.
                loc.hover(timeout=2500)
                session.page.mouse.down()
            else:
                # O mouse fica onde o hover anterior o deixou: sem tirá-lo daqui,
                # o "foco" capturado viria misturado com o estado de hover.
                try:
                    session.page.mouse.move(0, 0)
                    session.page.wait_for_timeout(120)
                except Exception:
                    pass
                loc.focus(timeout=2500)
            session.page.wait_for_timeout(180)
            styles = session.page.evaluate(STYLE_OF_JS, [selector, COMPONENT_PROPS, None]) or {}
            if state == "active":
                try:
                    session.page.mouse.up()
                except Exception:
                    pass
            if state == "focus":
                try:
                    loc.blur(timeout=1000)
                except Exception:
                    pass
            return styles
        except Exception:
            try:
                if state == "active":
                    session.page.mouse.up()
            except Exception:
                pass
            return {}

    # ========================================================= CSS bloqueado
    def _fetch_blocked_stylesheets(self, session: BrowserSession) -> None:
        if not self.blocked_sheets:
            return
        headers = session.cookies_header_for(self.opt.url)
        self.rep.step(f"baixando {len(self.blocked_sheets)} folha(s) de estilo bloqueada(s) por CORS")
        for href in sorted(self.blocked_sheets)[:40]:
            text = net.fetch_text(href, headers=headers)
            if not text:
                self.ds.warnings.append(f"não consegui baixar o CSS de {href}")
                continue
            facts = parse_css(text, origin=href)
            self._merge_css_facts(facts, href)

    def _merge_css_facts(self, facts: Any, origin: str) -> None:
        alvo = self.main
        for prop, counter in facts.colors_by_prop.items():
            for value, count in counter.items():
                alvo.colors_by_prop[prop][value] += count
        alvo.spacing.update(facts.spacing)
        alvo.radii.update(facts.radii)
        alvo.shadows.update(facts.shadows)
        alvo.border_widths.update(facts.border_widths)
        alvo.durations.update(facts.durations)
        alvo.easings.update(facts.easings)
        alvo.containers.update(facts.max_widths)
        alvo.font_stacks.update(facts.font_families)
        self.media_queries.extend(facts.media_queries)
        for ff in facts.font_faces:
            self._add_font_face({**ff, "href": origin})
        for prop in facts.custom_props:
            name = prop["name"]
            if name.startswith("--") and name not in alvo.css_vars:
                alvo.css_vars[name] = {
                    "value": prop["value"],
                    "origin": origin,
                    "scope": prop.get("selector", ""),
                }

    # ================================================================= assets
    def _merge_assets(self, data: dict[str, Any], page_url: str) -> None:
        for logo in (data.get("logos") or [])[:4]:
            if logo.get("inlineSvg"):
                h = net.content_hash(logo["inlineSvg"])
                key = f"logo-svg-{h[:8]}"
                if key not in self.assets:
                    self.assets[key] = Asset(
                        kind="logo",
                        url=page_url,
                        inline_svg=logo["inlineSvg"],
                        width=logo.get("width"),
                        height=logo.get("height"),
                        note="SVG inline",
                    )
            elif logo.get("url"):
                key = f"logo-{logo['url']}"
                if key not in self.assets:
                    self.assets[key] = Asset(
                        kind="logo",
                        url=logo["url"],
                        width=logo.get("width"),
                        height=logo.get("height"),
                    )
        for fav in data.get("favicons") or []:
            if fav.get("url"):
                self.assets.setdefault(
                    f"favicon-{fav['url']}",
                    Asset(kind="favicon", url=fav["url"], note=fav.get("rel", "")),
                )
        for icon in data.get("inlineSvg") or []:
            svg = icon.get("svg") or ""
            normalized = re.sub(r'\s+(class|style|id|aria-label|data-[\w-]+)="[^"]*"', "", svg)
            h = net.content_hash(normalized)
            if h in self.icon_hashes:
                continue
            self.icon_hashes.add(h)
            self.assets[f"icon-{h[:10]}"] = Asset(
                kind="icon",
                url=page_url,
                inline_svg=svg,
                width=icon.get("width"),
                height=icon.get("height"),
            )
        for img in (data.get("images") or [])[:8]:
            if img.get("url"):
                self.assets.setdefault(
                    f"image-{img['url']}",
                    Asset(
                        kind="image",
                        url=img["url"],
                        width=img.get("width"),
                        height=img.get("height"),
                        note=img.get("alt", ""),
                    ),
                )
        if data.get("manifest"):
            self.assets.setdefault(
                f"manifest-{data['manifest']}",
                Asset(kind="manifest", url=data["manifest"]),
            )

    def _download_assets(self, session: BrowserSession) -> None:
        headers = session.cookies_header_for(self.opt.url)
        folders = {
            "logo": "logo",
            "favicon": "icons",
            "icon": "icons",
            "image": "images",
            "font": "fonts",
            "manifest": ".",
        }

        # Fontes vêm dos @font-face coletados.
        for ff in self.font_faces.values():
            for url in ff.urls[:2]:
                if not url.startswith("http"):
                    continue
                self.assets.setdefault(f"font-{url}", Asset(kind="font", url=url, note=ff.family))

        downloadable = [a for a in self.assets.values() if a.url and a.url.startswith("http") and a.inline_svg is None]
        if downloadable:
            self.rep.step(f"baixando {len(downloadable)} asset(s)")
        for asset in downloadable:
            sub = folders.get(asset.kind, "images")
            dest = self.out_dir / "assets" / sub / net.safe_name(asset.url, asset.kind)
            got = net.download(asset.url, dest, headers=headers)
            if got:
                asset.path = str(got.relative_to(self.out_dir))
                if asset.kind == "font":
                    for ff in self.font_faces.values():
                        if asset.url in ff.urls:
                            ff.local_path = asset.path
            else:
                asset.note = (asset.note + " (download falhou)").strip()

        # SVGs inline viram arquivos.
        for asset in self.assets.values():
            if not asset.inline_svg:
                continue
            sub = "logo" if asset.kind == "logo" else "icons"
            name = net.safe_name(
                f"{asset.kind}-{net.content_hash(asset.inline_svg)[:10]}.svg", asset.kind
            )
            dest = self.out_dir / "assets" / sub / name
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(asset.inline_svg, encoding="utf-8")
                asset.path = str(dest.relative_to(self.out_dir))
            except OSError:
                pass

    def _page_background(self, bucket: TokenBucket) -> Any:
        """Fundo real da página.

        `body` e `html` costumam ser transparentes (o fundo vem de um wrapper),
        e uma cor com alpha baixo é overlay, não fundo — nesses casos deixamos a
        classificação cair para o background-color mais frequente da página.
        """
        for key in ("background", "htmlBackground"):
            rgba = colormod.parse_color(bucket.body_info.get(key))
            if rgba is not None and rgba[3] >= 0.9:
                return rgba
        return None

    def _colors_of(self, bucket: TokenBucket) -> dict[str, Any]:
        """Paleta classificada de um contexto — roda igual para claro e escuro."""
        totals: Counter = Counter()
        props_by_hex: dict[str, dict[str, int]] = {}
        for prop, counter in bucket.colors_by_prop.items():
            for value, count in counter.items():
                rgba = colormod.parse_color(value)
                if rgba is None:
                    continue
                hexv = colormod.to_hex(rgba)
                totals[hexv] += count
                props_by_hex.setdefault(hexv, {})
                props_by_hex[hexv][prop] = props_by_hex[hexv].get(prop, 0) + count

        # Variáveis CSS de cor são declarações intencionais: entram com peso extra.
        for info in bucket.css_vars.values():
            rgba = colormod.parse_color(info.get("value", ""))
            if rgba is None:
                continue
            info["type"] = "color"
            if rgba[3] <= 0.001:  # var totalmente transparente não é token de cor
                continue
            hexv = colormod.to_hex(rgba)
            totals[hexv] += 5
            slot = props_by_hex.setdefault(hexv, {})
            slot["css-var"] = slot.get("css-var", 0) + 5

        clusters = colormod.cluster_colors(
            [(h, c) for h, c in totals.items()], threshold=0.022, properties=props_by_hex
        )[:80]

        classification = classify.classify_colors(
            clusters,
            body_background=self._page_background(bucket),
            body_text=colormod.parse_color(bucket.body_info.get("color")),
            accent_hints=[
                (colormod.parse_color(v), c)
                for v, c in bucket.button_bgs.items()
                if colormod.parse_color(v)
            ],
            link_hints=[
                (colormod.parse_color(v), c)
                for v, c in bucket.link_colors.items()
                if colormod.parse_color(v)
            ],
        )
        return _colors_payload(clusters, classification)

    # ============================================================== agregação
    def _aggregate(self) -> None:
        ds = self.ds
        principal = self.main

        ds.colors = self._colors_of(principal)

        # --- temas
        escuro = self.buckets.get(DARK)
        if escuro is not None and not escuro.is_empty():
            cores_escuras = self._colors_of(escuro)
            ds.themes = {
                "light": ds.colors,
                "dark": cores_escuras,
                "pairs": thememod.pair_roles(ds.colors, cores_escuras),
                "detection": self.theme_report,
            }
        else:
            ds.themes = {"detection": self.theme_report}

        # --- tipografia
        families = typography.rank_families(principal.font_stacks.items())
        type_scale = typography.build_type_scale(principal.type_samples)
        ds.typography = {
            "families": families,
            "scale": [t.to_dict() for t in type_scale],
            "font_faces": [f.to_dict() for f in self.font_faces.values()],
            "sizes": typography.font_size_scale(principal.type_samples),
            "weights": typography.weight_scale(principal.type_samples),
            "base": {
                "family": principal.body_info.get("fontFamily", ""),
                "size": principal.body_info.get("fontSize", ""),
                "lineHeight": principal.body_info.get("lineHeight", ""),
            },
        }

        # --- escalas
        spacing_scale = scales.infer_scale(principal.spacing, max_items=14, max_value=320)
        ds.spacing = {
            "scale": spacing_scale,
            "base_unit": scales.detect_base_unit(spacing_scale),
            "named": scales.name_spacing_steps(spacing_scale),
        }
        radii_scale = scales.infer_scale(principal.radii, max_items=8, max_value=100, min_share=0.01)
        if any(scales.parse_length(v) and scales.parse_length(v) >= 999 for v in principal.radii):
            radii_scale = radii_scale + [9999.0]
        ds.radii = {"scale": radii_scale, "named": scales.name_size_steps(radii_scale)}

        ds.shadows = [
            {"value": v, "count": c}
            for v, c in scales.infer_string_scale(
                principal.shadows, max_items=8, sort_key=scales.shadow_weight
            )
        ]
        ds.borders = {
            "widths": scales.infer_scale(principal.border_widths, max_items=5, max_value=16, min_share=0.0),
        }
        ds.breakpoints = scales.infer_breakpoints(self.media_queries)
        ds.containers = scales.infer_scale(
            principal.containers, max_items=6, min_value=320, max_value=2000
        )
        ds.z_index = sorted({int(v) for v in principal.z_index if v.lstrip("-").isdigit()})[:12]
        ds.motion = {
            "durations": [v for v, _ in scales.infer_string_scale(principal.durations, max_items=6, sort_key=scales.duration_ms, normalize=scales.normalize_duration)],
            "easings": [v for v, _ in scales.infer_string_scale(principal.easings, max_items=6)],
        }
        ds.opacity = sorted(
            {round(float(v), 2) for v in principal.opacity if _is_float(v) and 0 < float(v) < 1}
        )[:8]

        # --- responsivo
        ds.responsive = self._responsive_payload()

        ds.css_variables = principal.css_vars
        ds.components = list(self.components.values())
        ds.assets.extend(self.assets.values())
        if self.button_variants:
            ds.raw["button_variants"] = self.button_variants
        if self.passive_states:
            ds.raw["passive_states"] = self.passive_states

        # --- leitura sobre os dados
        ds.context = report.build_context(
            ds,
            class_tokens=dict(self.class_tokens),
            attr_hints=dict(self.attr_hints),
            site_origin=self.origin,
        )
        ds.diagnostics = report.build_diagnostics(
            ds,
            contrast_pairs=principal.contrast_pairs,
            small_targets=principal.small_targets,
            spacing_frequencies=dict(principal.spacing),
            fingerprints=self.page_fingerprints,
        )

        self._fill_raw()

    def _responsive_payload(self) -> dict[str, Any]:
        """Escala tipográfica e containers por largura de tela."""
        contextos = [(nome, self.buckets[nome]) for nome in VIEWPORTS if nome in self.buckets]
        if not contextos:
            return {}

        larguras = {"mobile": VIEWPORTS["mobile"]["width"], "tablet": VIEWPORTS["tablet"]["width"], "desktop": 1440}
        escalas: dict[str, dict[str, float]] = {}
        for nome, bucket in contextos + [("desktop", self.main)]:
            for style in typography.build_type_scale(bucket.type_samples):
                escalas.setdefault(style.name, {})[nome] = style.font_size

        # Só interessa o que realmente muda de tamanho entre as telas.
        fluidos = {
            papel: tamanhos
            for papel, tamanhos in escalas.items()
            if len(tamanhos) > 1 and max(tamanhos.values()) - min(tamanhos.values()) >= 1
        }
        return {
            "widths": larguras,
            "type_scale": escalas,
            "fluid": fluidos,
            "spacing": {
                nome: scales.infer_scale(bucket.spacing, max_items=10, max_value=320)
                for nome, bucket in contextos
            },
            "containers": {
                nome: scales.infer_scale(bucket.containers, max_items=4, min_value=280, max_value=2000)
                for nome, bucket in contextos
            },
        }

    def _fill_raw(self) -> None:
        """Dump de auditoria: frequências, procedência e o que sustenta cada escolha."""
        ds = self.ds
        principal = self.main
        if self.login_result:
            ds.raw["login"] = {
                "ok": self.login_result.ok,
                "method": self.login_result.method,
                "detail": self.login_result.detail,
                "steps": self.login_result.steps,
            }
        ds.raw["frequencies"] = {
            "colors_by_prop": {k: dict(v.most_common(60)) for k, v in principal.colors_by_prop.items()},
            "spacing": dict(principal.spacing.most_common(60)),
            "radii": dict(principal.radii.most_common(30)),
            "shadows": dict(principal.shadows.most_common(30)),
            "border_widths": dict(principal.border_widths.most_common(20)),
            "z_index": dict(principal.z_index.most_common(20)),
            "durations": dict(principal.durations.most_common(20)),
            "easings": dict(principal.easings.most_common(20)),
            "opacity": dict(principal.opacity.most_common(20)),
            "containers": dict(principal.containers.most_common(20)),
            "font_stacks": dict(principal.font_stacks.most_common(30)),
            "button_backgrounds": dict(principal.button_bgs.most_common(20)),
            "link_colors": dict(principal.link_colors.most_common(20)),
        }
        ds.raw["media_queries"] = sorted(set(self.media_queries))[:120]
        ds.raw["blocked_stylesheets"] = sorted(self.blocked_sheets)
        ds.raw["body"] = principal.body_info
        ds.raw["type_samples"] = principal.type_samples[:400]
        ds.raw["contexts"] = sorted(self.buckets)
        ds.raw["page_fingerprints"] = self.page_fingerprints
        if self.stopped_early:
            ds.raw["crawl_stop"] = self.stopped_early
            ds.warnings.append(self.stopped_early)


def _colors_payload(clusters, classification) -> dict[str, Any]:
    return {
        "theme": classify.theme_pair(classification),
        "clusters": [
            {
                "hex": c.hex,
                "value": c.css,
                "count": c.count,
                "properties": c.properties,
                "oklch": [round(x, 4) for x in c.oklch],
                "members": [colormod.to_hex(m) for m, _ in c.members[:8]],
            }
            for c in clusters
        ],
        "roles": {
            role: {
                "value": sc.cluster.css,
                "hex": sc.cluster.hex,
                "count": sc.cluster.count,
                "reason": sc.reason,
            }
            for role, sc in classification.roles.items()
        },
        "neutrals": [
            {"hex": c.hex, "value": c.css, "count": c.count, "lightness": round(c.oklch[0], 3)}
            for c in classification.neutrals[:14]
        ],
        "accents": [
            {"hex": c.hex, "value": c.css, "count": c.count, "hue": round(c.oklch[2], 1)}
            for c in classification.accents[:14]
        ],
    }


def _origin_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _slug(url: str) -> str:
    p = urlparse(url)
    path = (p.path or "/").strip("/").replace("/", "-") or "home"
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", path)[:50] or "page"


def _is_float(v: Any) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False
