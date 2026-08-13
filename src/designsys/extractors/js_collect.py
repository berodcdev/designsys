"""Scripts injetados na página pelo Playwright.

Tudo que precisa do DOM/CSSOM roda aqui dentro e volta como JSON já agregado —
devolver 8.000 objetos de estilo por página seria lento e inútil.
"""

# Propriedades computadas capturadas por componente.
COMPONENT_PROPS = [
    "color",
    "background-color",
    "background-image",
    "border-top-width",
    "border-right-width",
    "border-bottom-width",
    "border-left-width",
    "border-top-color",
    "border-style",
    "border-radius",
    "border-top-left-radius",
    "box-shadow",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "margin-top",
    "margin-bottom",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "line-height",
    "letter-spacing",
    "text-transform",
    "text-decoration-line",
    "text-align",
    "display",
    "align-items",
    "justify-content",
    "gap",
    "width",
    "height",
    "min-height",
    "min-width",
    "max-width",
    "opacity",
    "outline",
    "outline-color",
    "outline-offset",
    "outline-width",
    "transition",
    "transition-duration",
    "transition-timing-function",
    "cursor",
    "overflow",
    "white-space",
    "z-index",
    "backdrop-filter",
]

COLLECT_JS = r"""
() => {
  const MAX_ELEMENTS = 12000;
  const bump = (obj, key, n) => {
    if (key === undefined || key === null) return;
    const k = String(key).trim();
    if (!k) return;
    obj[k] = (obj[k] || 0) + (n || 1);
  };

  const out = {
    colors: {},            // propriedade -> { valor: contagem }
    cssVars: {},           // --nome -> valor (escopo raiz)
    varsFromRules: [],     // { name, value, selector, href }
    fontFaces: [],
    mediaQueries: [],
    typography: {},        // assinatura -> amostra agregada
    spacing: { margin: {}, padding: {}, gap: {} },
    radii: {},
    shadows: {},
    borderWidths: {},
    zIndex: {},
    durations: {},
    easings: {},
    opacity: {},
    containers: {},
    body: {},
    buttonBackgrounds: {},
    buttonColors: {},
    linkColors: {},
    blockedSheets: [],
    contrastPairs: [],     // pares texto/fundo reais, para a auditoria de contraste
    smallTargets: [],      // botões/links pequenos demais para o dedo
    classTokens: {},       // assinatura de framework de UI
    attrHints: {},
    sheetCount: 0,
    ruleCount: 0,
    elementCount: 0,
    title: document.title || "",
    lang: document.documentElement.getAttribute("lang") || "",
    url: location.href,
  };

  // ---------------------------------------------------------------- CSSOM
  const walkRules = (rules, href, depth) => {
    if (!rules || depth > 6) return;
    for (const rule of rules) {
      out.ruleCount++;
      try {
        if (rule.type === CSSRule.STYLE_RULE || rule.selectorText !== undefined) {
          const style = rule.style;
          if (style) {
            for (let i = 0; i < style.length; i++) {
              const prop = style[i];
              if (prop && prop.startsWith("--")) {
                out.varsFromRules.push({
                  name: prop,
                  value: style.getPropertyValue(prop).trim(),
                  selector: rule.selectorText || "",
                  href: href || "inline",
                });
              }
            }
          }
        }
        if (rule.type === CSSRule.MEDIA_RULE || rule.conditionText !== undefined) {
          if (rule.conditionText) out.mediaQueries.push(rule.conditionText);
          walkRules(rule.cssRules, href, depth + 1);
        } else if (rule.cssRules) {
          walkRules(rule.cssRules, href, depth + 1);
        }
        if (rule.type === CSSRule.FONT_FACE_RULE || (rule.style && rule.style.src !== undefined && rule.cssText && rule.cssText.indexOf("@font-face") === 0)) {
          const s = rule.style;
          out.fontFaces.push({
            family: (s.getPropertyValue("font-family") || "").trim(),
            weight: (s.getPropertyValue("font-weight") || "400").trim(),
            style: (s.getPropertyValue("font-style") || "normal").trim(),
            display: (s.getPropertyValue("font-display") || "").trim(),
            unicodeRange: (s.getPropertyValue("unicode-range") || "").trim(),
            src: (s.getPropertyValue("src") || "").trim(),
            href: href || "inline",
          });
        }
      } catch (e) { /* regra exótica: ignora */ }
    }
  };

  for (const sheet of Array.from(document.styleSheets)) {
    out.sheetCount++;
    let rules = null;
    try {
      rules = sheet.cssRules;
    } catch (e) {
      if (sheet.href) out.blockedSheets.push(sheet.href);
      continue;
    }
    if (rules === null && sheet.href) { out.blockedSheets.push(sheet.href); continue; }
    walkRules(rules, sheet.href, 0);
  }

  // Custom properties resolvidas nos escopos raiz.
  for (const el of [document.documentElement, document.body]) {
    if (!el) continue;
    const cs = getComputedStyle(el);
    for (let i = 0; i < cs.length; i++) {
      const prop = cs[i];
      if (prop && prop.startsWith("--")) {
        const v = cs.getPropertyValue(prop).trim();
        if (v && !(prop in out.cssVars)) out.cssVars[prop] = v;
      }
    }
  }
  // Fallback: resolve os nomes vistos nas regras contra o elemento raiz.
  const rootStyle = getComputedStyle(document.documentElement);
  for (const v of out.varsFromRules) {
    if (!(v.name in out.cssVars)) {
      const resolved = rootStyle.getPropertyValue(v.name).trim();
      if (resolved) out.cssVars[v.name] = resolved;
    }
  }

  // ------------------------------------------------------------- elementos
  // border-color e outline-color existem em TODO elemento (herdam de `color`
  // mesmo sem borda desenhada). Coletá-los sem checar width/style inflaria a
  // cor de texto em ordens de magnitude, então cada um tem sua condição.
  const COLOR_PROPS = [
    ["color", "color", null],
    ["backgroundColor", "background-color", null],
    ["borderTopColor", "border-color", ["borderTopWidth", "borderTopStyle"]],
    ["borderRightColor", "border-color", ["borderRightWidth", "borderRightStyle"]],
    ["borderBottomColor", "border-color", ["borderBottomWidth", "borderBottomStyle"]],
    ["borderLeftColor", "border-color", ["borderLeftWidth", "borderLeftStyle"]],
    ["outlineColor", "outline-color", ["outlineWidth", "outlineStyle"]],
    ["fill", "fill", null],
    ["stroke", "stroke", null],
    ["textDecorationColor", "text-decoration-color", ["__decoration__", null]],
    ["caretColor", "caret-color", null],
    ["columnRuleColor", "border-color", ["columnRuleWidth", "columnRuleStyle"]],
  ];

  const drawn = (cs, guard) => {
    if (!guard) return true;
    const [widthProp, styleProp] = guard;
    if (widthProp === "__decoration__") {
      return cs.textDecorationLine && cs.textDecorationLine !== "none";
    }
    const w = parseFloat(cs[widthProp]);
    if (!(w > 0)) return false;
    if (styleProp && (cs[styleProp] === "none" || cs[styleProp] === "hidden")) return false;
    return true;
  };

  const isSkippable = (tag) =>
    tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT" || tag === "META" ||
    tag === "LINK" || tag === "HEAD" || tag === "TITLE" || tag === "BR";

  const textOf = (el) => {
    let t = "";
    for (const node of el.childNodes) {
      if (node.nodeType === 3) t += node.nodeValue;
    }
    return t.trim().replace(/\s+/g, " ");
  };

  // Contraste só faz sentido contra o fundo que o olho enxerga: sobe a árvore
  // até o primeiro fundo praticamente opaco.
  // Precisa cobrir as notações modernas: `oklch(1 0 0 / 0.1)` e
  // `color(srgb 1 1 1 / 0.1)` são translúcidas, e ler só `rgba()` faria um
  // fundo de 10% de opacidade passar por sólido.
  const opacidadeDe = (cor) => {
    if (!cor || cor === "transparent" || cor === "none") return 0;
    const barra = cor.match(/\/\s*([\d.]+)(%?)\s*\)/);
    if (barra) {
      const valor = parseFloat(barra[1]);
      return barra[2] === "%" ? valor / 100 : valor;
    }
    const funcional = cor.match(/rgba?\(([^)]+)\)/);
    if (funcional) {
      const partes = funcional[1].split(",").map((s) => parseFloat(s));
      return partes.length > 3 ? partes[3] : 1;
    }
    const hex = cor.match(/^#[0-9a-fA-F]{8}$/);
    if (hex) return parseInt(cor.slice(7, 9), 16) / 255;
    return 1;
  };
  const fundoEfetivo = (el) => {
    let node = el, profundidade = 0;
    while (node && node.nodeType === 1 && profundidade < 12) {
      const cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage.indexOf("gradient") >= 0) return null;
      if (opacidadeDe(cs.backgroundColor) >= 0.85) return cs.backgroundColor;
      node = node.parentElement;
      profundidade++;
    }
    return "rgb(255, 255, 255)";
  };

  const paresVistos = new Map();
  const registrarPar = (fg, bg, cs, texto, el) => {
    const chave = fg + "|" + bg + "|" + cs.fontSize + "|" + cs.fontWeight;
    const existente = paresVistos.get(chave);
    if (existente) { existente.count++; return; }
    if (paresVistos.size >= 300) return;
    paresVistos.set(chave, {
      fg: fg, bg: bg, size: cs.fontSize, weight: cs.fontWeight,
      tag: el.tagName.toLowerCase(), sample: texto.slice(0, 48), count: 1,
    });
  };

  const contarClasse = (valor) => {
    if (!valor || typeof valor !== "string") return;
    for (const token of valor.split(/\s+/)) {
      if (!token || token.length > 40) continue;
      out.classTokens[token] = (out.classTokens[token] || 0) + 1;
    }
  };

  const all = document.querySelectorAll("*");
  const limit = Math.min(all.length, MAX_ELEMENTS);
  for (let i = 0; i < limit; i++) {
    const el = all[i];
    const tag = el.tagName;
    if (isSkippable(tag)) continue;
    let rect;
    try { rect = el.getBoundingClientRect(); } catch (e) { continue; }
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    const visible = (rect.width > 0 && rect.height > 0);
    if (!visible && tag !== "SVG") continue;
    out.elementCount++;

    // cores
    for (const [jsProp, group, guard] of COLOR_PROPS) {
      const v = cs[jsProp];
      if (!v || v === "none" || v === "rgba(0, 0, 0, 0)" || v === "transparent") continue;
      if (v.indexOf("gradient") >= 0 || v.indexOf("url(") >= 0) continue;
      if (!drawn(cs, guard)) continue;
      if (!out.colors[group]) out.colors[group] = {};
      bump(out.colors[group], v, 1);
    }
    const bgImage = cs.backgroundImage;
    if (bgImage && bgImage.indexOf("gradient") >= 0) {
      const found = bgImage.match(/(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\)|oklch\([^)]*\))/g);
      if (found) {
        if (!out.colors["gradient"]) out.colors["gradient"] = {};
        for (const c of found) bump(out.colors["gradient"], c, 1);
      }
    }

    // espaçamento
    for (const p of ["marginTop", "marginRight", "marginBottom", "marginLeft"]) bump(out.spacing.margin, cs[p], 1);
    for (const p of ["paddingTop", "paddingRight", "paddingBottom", "paddingLeft"]) bump(out.spacing.padding, cs[p], 1);
    for (const p of ["rowGap", "columnGap"]) {
      const v = cs[p];
      if (v && v !== "normal") bump(out.spacing.gap, v, 1);
    }

    // raios, sombras, bordas
    for (const p of ["borderTopLeftRadius", "borderTopRightRadius", "borderBottomLeftRadius", "borderBottomRightRadius"]) {
      const v = cs[p];
      if (v && v !== "0px") bump(out.radii, v, 1);
    }
    if (cs.boxShadow && cs.boxShadow !== "none") bump(out.shadows, cs.boxShadow, 1);
    for (const p of ["borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth"]) {
      const v = cs[p];
      if (v && v !== "0px" && cs.borderTopStyle !== "none") bump(out.borderWidths, v, 1);
    }
    if (cs.zIndex && cs.zIndex !== "auto") bump(out.zIndex, cs.zIndex, 1);
    if (cs.opacity && cs.opacity !== "1") bump(out.opacity, cs.opacity, 1);
    if (cs.transitionDuration && cs.transitionDuration !== "0s") {
      for (const d of cs.transitionDuration.split(",")) bump(out.durations, d.trim(), 1);
      for (const e of (cs.transitionTimingFunction || "").split(/,(?![^(]*\))/)) bump(out.easings, e.trim(), 1);
    }
    if (cs.animationDuration && cs.animationDuration !== "0s") {
      for (const d of cs.animationDuration.split(",")) bump(out.durations, d.trim(), 1);
    }
    if (cs.maxWidth && cs.maxWidth !== "none" && rect.width > 320) bump(out.containers, cs.maxWidth, 1);

    // assinatura de framework de UI
    contarClasse(typeof el.className === "string" ? el.className : null);
    for (const attr of el.attributes || []) {
      const nome = attr.name;
      if (nome.indexOf("data-") === 0 && nome.length < 32) {
        out.attrHints[nome] = (out.attrHints[nome] || 0) + 1;
      }
    }

    // tipografia: só onde há texto próprio
    const txt = textOf(el);
    if (txt && txt.length > 1) {
      const fundo = fundoEfetivo(el);
      if (fundo && cs.color) registrarPar(cs.color, fundo, cs, txt, el);
    }
    if (txt && txt.length > 1) {
      const sig = [tag, cs.fontSize, cs.fontWeight, cs.lineHeight, cs.letterSpacing, cs.textTransform, cs.fontFamily].join("|");
      if (!out.typography[sig]) {
        out.typography[sig] = {
          tag: tag.toLowerCase(),
          fontSize: cs.fontSize,
          fontWeight: cs.fontWeight,
          lineHeight: cs.lineHeight,
          letterSpacing: cs.letterSpacing,
          textTransform: cs.textTransform,
          fontFamily: cs.fontFamily,
          color: cs.color,
          text: txt.slice(0, 80),
          count: 0,
        };
      }
      out.typography[sig].count++;
    }

    // sinais de accent
    const role = (el.getAttribute && el.getAttribute("role")) || "";
    const cls = (typeof el.className === "string" ? el.className : "") || "";
    const looksButton = tag === "BUTTON" || role === "button" ||
      (tag === "INPUT" && (el.type === "submit" || el.type === "button")) ||
      /\b(btn|button|cta)\b/i.test(cls);
    if (looksButton && rect.width > 20 && rect.height > 12) {
      if (cs.backgroundColor && cs.backgroundColor !== "rgba(0, 0, 0, 0)") {
        bump(out.buttonBackgrounds, cs.backgroundColor, 1);
      }
      bump(out.buttonColors, cs.color, 1);
    }
    if (tag === "A" && txt) bump(out.linkColors, cs.color, 1);

    // Alvo de toque (WCAG 2.2 AA pede 24×24 CSS px como mínimo).
    if ((looksButton || tag === "A" || tag === "INPUT") && txt) {
      if ((rect.width < 24 || rect.height < 24) && rect.width > 0 && out.smallTargets.length < 60) {
        out.smallTargets.push({
          tag: tag.toLowerCase(),
          label: txt.slice(0, 40),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        });
      }
    }
  }

  out.contrastPairs = Array.from(paresVistos.values());
  // Só os tokens de classe recorrentes interessam para identificar o framework.
  const classesFrequentes = {};
  for (const [token, n] of Object.entries(out.classTokens)) {
    if (n >= 2) classesFrequentes[token] = n;
  }
  out.classTokens = Object.fromEntries(
    Object.entries(classesFrequentes).sort((a, b) => b[1] - a[1]).slice(0, 400)
  );

  const bodyStyle = getComputedStyle(document.body);
  out.body = {
    background: bodyStyle.backgroundColor,
    color: bodyStyle.color,
    fontFamily: bodyStyle.fontFamily,
    fontSize: bodyStyle.fontSize,
    lineHeight: bodyStyle.lineHeight,
    htmlBackground: getComputedStyle(document.documentElement).backgroundColor,
  };
  out.typography = Object.values(out.typography);
  return out;
}
"""


# Coleta reduzida para os viewports secundários: só o que muda com a largura da
# tela. Recoletar a paleta inteira em mobile e tablet triplicaria o custo sem
# acrescentar nada — cor não muda com media query na prática, tamanho muda.
COLLECT_VIEWPORT_JS = r"""
() => {
  const MAX_ELEMENTS = 9000;
  const out = { typography: {}, spacing: { margin: {}, padding: {}, gap: {} }, containers: {} };
  const bump = (obj, key, n) => {
    if (!key) return;
    const k = String(key).trim();
    if (k) obj[k] = (obj[k] || 0) + (n || 1);
  };
  const textOf = (el) => {
    let t = "";
    for (const node of el.childNodes) if (node.nodeType === 3) t += node.nodeValue;
    return t.trim().replace(/\s+/g, " ");
  };

  const all = document.querySelectorAll("*");
  const limite = Math.min(all.length, MAX_ELEMENTS);
  for (let i = 0; i < limite; i++) {
    const el = all[i];
    const tag = el.tagName;
    if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT" || tag === "HEAD") continue;
    let rect;
    try { rect = el.getBoundingClientRect(); } catch (e) { continue; }
    if (!(rect.width > 0 && rect.height > 0)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;

    for (const p of ["marginTop", "marginRight", "marginBottom", "marginLeft"]) bump(out.spacing.margin, cs[p], 1);
    for (const p of ["paddingTop", "paddingRight", "paddingBottom", "paddingLeft"]) bump(out.spacing.padding, cs[p], 1);
    for (const p of ["rowGap", "columnGap"]) {
      if (cs[p] && cs[p] !== "normal") bump(out.spacing.gap, cs[p], 1);
    }
    if (cs.maxWidth && cs.maxWidth !== "none" && rect.width > 320) bump(out.containers, cs.maxWidth, 1);

    const txt = textOf(el);
    if (txt && txt.length > 1) {
      const sig = [tag, cs.fontSize, cs.fontWeight, cs.lineHeight, cs.letterSpacing, cs.textTransform, cs.fontFamily].join("|");
      if (!out.typography[sig]) {
        out.typography[sig] = {
          tag: tag.toLowerCase(), fontSize: cs.fontSize, fontWeight: cs.fontWeight,
          lineHeight: cs.lineHeight, letterSpacing: cs.letterSpacing,
          textTransform: cs.textTransform, fontFamily: cs.fontFamily,
          text: txt.slice(0, 60), count: 0,
        };
      }
      out.typography[sig].count++;
    }
  }
  out.typography = Object.values(out.typography);
  return out;
}
"""


# Descobre componentes e devolve um seletor estável para cada um.
COMPONENTS_JS = r"""
(props) => {
  const cssPath = (el) => {
    if (el.id && /^[A-Za-z][\w-]*$/.test(el.id)) return "#" + el.id;
    const parts = [];
    let node = el;
    let depth = 0;
    while (node && node.nodeType === 1 && depth < 6) {
      let sel = node.tagName.toLowerCase();
      if (node.id && /^[A-Za-z][\w-]*$/.test(node.id)) {
        parts.unshift("#" + node.id);
        break;
      }
      const parent = node.parentElement;
      if (parent) {
        const sameTag = Array.from(parent.children).filter((c) => c.tagName === node.tagName);
        if (sameTag.length > 1) sel += ":nth-of-type(" + (sameTag.indexOf(node) + 1) + ")";
      }
      parts.unshift(sel);
      node = node.parentElement;
      depth++;
    }
    return parts.join(" > ");
  };

  const styleOf = (el) => {
    const cs = getComputedStyle(el);
    const o = {};
    for (const p of props) {
      const v = cs.getPropertyValue(p);
      if (v) o[p] = v.trim();
    }
    return o;
  };

  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 8 && r.height > 8 && cs.display !== "none" && cs.visibility !== "hidden" && cs.opacity !== "0";
  };

  const results = [];
  const seen = new Set();
  const push = (kind, el, label) => {
    if (!el || !visible(el)) return;
    const path = cssPath(el);
    const key = kind + "|" + path;
    if (seen.has(key)) return;
    seen.add(key);
    const html = el.outerHTML || "";
    results.push({
      kind: kind,
      selector: path,
      label: (el.innerText || el.value || el.placeholder || "").trim().slice(0, 40),
      // Nunca truncar markup: um corte no meio de um atributo (o `d` de um
      // <path>, por exemplo) gera HTML inválido que quebra o style guide.
      html: html.length > 8000 ? "" : html,
      htmlOmitted: html.length > 8000,
      base: styleOf(el),
      rect: (() => { const r = el.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) }; })(),
    });
  };

  const q = (sel) => Array.from(document.querySelectorAll(sel)).filter(visible);

  // Botões. A flag `i` no seletor de atributo importa: classes reais vão de
  // `CtaButton` a `hds-button`, e sem ela metade dos botões escapa.
  const BUTTON_SEL = [
    "button", "[role=button]", "input[type=submit]", "input[type=button]",
    "[class*='btn' i]", "[class*='button' i]", "[class*='cta' i]",
  ].join(", ");

  // Um wrapper que contém outros botões é container, não botão.
  const isContainer = (el) => el.querySelector("button, a[href], input[type=submit]") !== null;

  const scored = q(BUTTON_SEL).map((el) => {
    const cs = getComputedStyle(el);
    const bg = cs.backgroundColor || "";
    const m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    let solid = 0, sat = 0;
    if (m) {
      const a = m[4] === undefined ? 1 : parseFloat(m[4]);
      const r = +m[1], g = +m[2], b = +m[3];
      solid = a;
      sat = (Math.max(r, g, b) - Math.min(r, g, b)) / 255;
    }
    const rect = el.getBoundingClientRect();
    const text = (el.innerText || el.value || "").trim();
    return { el, solid, sat, w: rect.width, h: rect.height, area: rect.width * rect.height,
             text: text, container: isContainer(el) };
  }).filter((s) => !s.container);

  // O botão primário tem rótulo e tamanho de botão — um ícone de 40x40 sem
  // texto é controle de carrossel, não a ação principal da página.
  const rotulados = scored.filter((s) => s.text && s.text.indexOf("\n") < 0 && s.w >= 64 && s.h >= 26);
  const pool = rotulados.length ? rotulados : scored;

  const primary = pool.filter((s) => s.solid > 0.5)
    .sort((a, b) => (b.sat - a.sat) || (b.area - a.area))[0];
  if (primary) push("button-primary", primary.el, "");
  const secondary = pool.filter((s) => !primary || s.el !== primary.el)
    .sort((a, b) => (a.sat - b.sat) || (b.area - a.area))[0];
  if (secondary) push("button-secondary", secondary.el, "");
  for (const s of pool.slice(0, 6)) push("button", s.el, "");

  // Variantes: agrupa os botões pela assinatura visual. É assim que
  // primary/secondary/ghost/link aparecem de verdade, em vez de escolhermos um
  // de cada e chamar de dois.
  const variantes = new Map();
  for (const s of pool) {
    const cs = getComputedStyle(s.el);
    const assinatura = [
      cs.backgroundColor, cs.color, cs.borderTopLeftRadius,
      cs.paddingTop + "/" + cs.paddingLeft,
      cs.borderTopWidth + " " + cs.borderTopColor,
      cs.fontSize, cs.fontWeight,
    ].join("|");
    const existente = variantes.get(assinatura);
    if (existente) {
      existente.count++;
      continue;
    }
    if (variantes.size >= 8) continue;
    variantes.set(assinatura, {
      count: 1,
      label: (s.text || "").slice(0, 32),
      selector: cssPath(s.el),
      height: Math.round(s.h),
      base: styleOf(s.el),
    });
  }
  results.push({ kind: "__button_variants__", variants: Array.from(variantes.values()) });

  for (const el of q("input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=checkbox]):not([type=radio])").slice(0, 4)) push("input", el, "");
  for (const el of q("textarea").slice(0, 2)) push("textarea", el, "");
  for (const el of q("select").slice(0, 2)) push("select", el, "");
  for (const el of q("input[type=checkbox]").slice(0, 2)) push("checkbox", el, "");
  for (const el of q("label").slice(0, 3)) push("label", el, "");
  for (const el of q("a:not(.btn):not(.button)").slice(0, 6)) push("link", el, "");
  for (const el of q("nav, header nav, [role=navigation]").slice(0, 2)) push("nav", el, "");
  for (const el of q("header, [role=banner]").slice(0, 1)) push("header", el, "");
  for (const el of q("footer").slice(0, 1)) push("footer", el, "");
  for (const el of q("table").slice(0, 1)) push("table", el, "");
  for (const el of q("[role=alert], .alert, .toast, .notification").slice(0, 2)) push("alert", el, "");

  // Cards: caixa com raio e (sombra ou borda), com filhos, tamanho de card.
  const cards = Array.from(document.querySelectorAll("div, article, section, li")).filter((el) => {
    if (!visible(el)) return false;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const radius = parseFloat(cs.borderTopLeftRadius) || 0;
    const hasShadow = cs.boxShadow && cs.boxShadow !== "none";
    const hasBorder = (parseFloat(cs.borderTopWidth) || 0) > 0 && cs.borderTopStyle !== "none";
    return radius >= 4 && (hasShadow || hasBorder) && r.width >= 140 && r.width <= 900 &&
      r.height >= 60 && el.children.length >= 1;
  }).sort((a, b) => (b.getBoundingClientRect().width * b.getBoundingClientRect().height) - (a.getBoundingClientRect().width * a.getBoundingClientRect().height));
  for (const el of cards.slice(0, 3)) push("card", el, "");

  // Badges/pills: pequenos, arredondados, texto curto.
  const badges = Array.from(document.querySelectorAll("span, div, a, li")).filter((el) => {
    if (!visible(el)) return false;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const radius = parseFloat(cs.borderTopLeftRadius) || 0;
    const txt = (el.innerText || "").trim();
    return radius >= 8 && r.height <= 40 && r.width <= 220 && txt.length > 0 && txt.length < 28 &&
      cs.backgroundColor !== "rgba(0, 0, 0, 0)" && el.children.length <= 1;
  });
  for (const el of badges.slice(0, 3)) push("badge", el, "");

  return results;
}
"""


STYLE_OF_JS = r"""
([selector, props, pseudo]) => {
  const el = document.querySelector(selector);
  if (!el) return null;
  const cs = getComputedStyle(el, pseudo || null);
  const o = {};
  for (const p of props) {
    const v = cs.getPropertyValue(p);
    if (v) o[p] = v.trim();
  }
  return o;
}
"""


# Estilos de estados que não dependem de interação do mouse: elementos com o
# atributo `disabled` e o pseudo-elemento ::placeholder.
PASSIVE_STATES_JS = r"""
(props) => {
  const out = { disabled: null, placeholder: null, selection: null };
  const styleOf = (el, pseudo) => {
    const cs = getComputedStyle(el, pseudo || null);
    const o = {};
    for (const p of props) {
      const v = cs.getPropertyValue(p);
      if (v) o[p] = v.trim();
    }
    return o;
  };
  const visivel = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 8 && r.height > 8;
  };

  const desabilitado = Array.from(
    document.querySelectorAll("button[disabled], input[disabled], select[disabled], [aria-disabled=true]")
  ).filter(visivel)[0];
  if (desabilitado) {
    out.disabled = { styles: styleOf(desabilitado), tag: desabilitado.tagName.toLowerCase() };
  }

  const campo = Array.from(
    document.querySelectorAll("input[placeholder], textarea[placeholder]")
  ).filter(visivel)[0];
  if (campo) out.placeholder = styleOf(campo, "::placeholder");

  return out;
}
"""


ASSETS_JS = r"""
() => {
  const abs = (u) => { try { return new URL(u, location.href).href; } catch (e) { return null; } };
  const out = { logos: [], icons: [], images: [], favicons: [], inlineSvg: [], manifest: null };

  // favicons e ícones de app
  for (const link of document.querySelectorAll("link[rel*='icon'], link[rel='apple-touch-icon'], link[rel='mask-icon'], link[rel='manifest']")) {
    const href = abs(link.getAttribute("href"));
    if (!href) continue;
    const rel = (link.getAttribute("rel") || "").toLowerCase();
    if (rel.indexOf("manifest") >= 0) { out.manifest = href; continue; }
    out.favicons.push({ url: href, rel: rel, sizes: link.getAttribute("sizes") || "" });
  }
  if (!out.favicons.length) out.favicons.push({ url: abs("/favicon.ico"), rel: "icon", sizes: "" });

  // logo: <img>/<svg> dentro de header/nav, ou com "logo" no atributo
  const header = document.querySelector("header, [role=banner], nav, .navbar, #header");
  const logoScore = (el) => {
    let score = 0;
    const attrs = [el.getAttribute("class"), el.getAttribute("id"), el.getAttribute("alt"),
                   el.getAttribute("src"), el.getAttribute("aria-label"), el.getAttribute("data-testid")]
                   .filter(Boolean).join(" ").toLowerCase();
    if (/logo|brand|wordmark/.test(attrs)) score += 10;
    if (header && header.contains(el)) score += 6;
    if (el.closest("a[href='/'], a[href='" + location.origin + "/']")) score += 4;
    const r = el.getBoundingClientRect();
    if (r.top < 200 && r.width > 16 && r.height > 8) score += 3;
    if (r.width > 400) score -= 4;
    return score;
  };

  // Um SVG com <foreignObject> carrega HTML dentro e não sobrevive fora da
  // página original; e truncar markup gera SVG inválido. Melhor descartar.
  const usableSvg = (html) =>
    html && html.length <= 20000 && html.indexOf("<foreignObject") < 0 && html.indexOf("</div>") < 0;

  const candidates = Array.from(document.querySelectorAll("img, svg, [class*=logo], [class*=Logo]"));
  const scoredLogos = candidates.map((el) => ({ el, score: logoScore(el) }))
    .filter((s) => s.score >= 9)
    .sort((a, b) => b.score - a.score)
    .slice(0, 4);
  for (const { el, score } of scoredLogos) {
    const r = el.getBoundingClientRect();
    if (el.tagName.toLowerCase() === "svg") {
      if (!usableSvg(el.outerHTML)) continue;
      out.logos.push({ inlineSvg: el.outerHTML, url: null, width: Math.round(r.width), height: Math.round(r.height), score });
    } else {
      const src = el.getAttribute("src") || el.getAttribute("data-src") ||
        (getComputedStyle(el).backgroundImage.match(/url\(["']?([^"')]+)/) || [])[1];
      const u = src ? abs(src) : null;
      if (u) out.logos.push({ url: u, inlineSvg: null, width: Math.round(r.width), height: Math.round(r.height), score });
    }
  }

  // ícones SVG inline (dedup por conteúdo, feito no Python via hash)
  for (const svg of Array.from(document.querySelectorAll("svg")).slice(0, 400)) {
    const r = svg.getBoundingClientRect();
    if (r.width > 96 || r.height > 96) continue;
    const html = svg.outerHTML;
    if (!usableSvg(html) || html.length > 12000) continue;
    out.inlineSvg.push({ svg: html, width: Math.round(r.width), height: Math.round(r.height) });
  }

  // imagens de conteúdo (as maiores)
  const imgs = Array.from(document.querySelectorAll("img")).map((el) => {
    const r = el.getBoundingClientRect();
    return { url: abs(el.currentSrc || el.src), width: Math.round(r.width), height: Math.round(r.height), alt: el.alt || "" };
  }).filter((i) => i.url && i.width >= 48 && i.height >= 48);
  imgs.sort((a, b) => (b.width * b.height) - (a.width * a.height));
  out.images = imgs.slice(0, 12);

  return out;
}
"""


LINKS_JS = r"""
() => {
  const origin = location.origin;
  const seen = new Set();
  const out = [];
  for (const a of document.querySelectorAll("a[href]")) {
    let u;
    try { u = new URL(a.getAttribute("href"), location.href); } catch (e) { continue; }
    if (u.origin !== origin) continue;
    if (!/^https?:$/.test(u.protocol)) continue;
    u.hash = "";
    const href = u.href;
    if (seen.has(href)) continue;
    seen.add(href);
    out.push({ url: href, text: (a.innerText || "").trim().slice(0, 60), path: u.pathname });
  }
  return out;
}
"""
