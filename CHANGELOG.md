# Histórico de mudanças

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento em [SemVer](https://semver.org/lang/pt-BR/).

## [0.3.0] — 2026-09-21

Primeira versão publicada no [PyPI](https://pypi.org/project/designsys/):
`pipx install designsys`.

### Mudado

**O certificado TLS voltou a ser validado.** O Chromium subia com
`ignore_https_errors` ligado, o que aceitava qualquer certificado — inclusive na
execução em que a senha é enviada, com `--login`. Agora a validação é o padrão, e
quem precisa extrair de um ambiente com certificado próprio passa `--insecure`
explicitamente. O erro de certificado já sugere a flag.

### Adicionado

- `--insecure` no comando `url`, para ambientes internos com certificado próprio
  ou autoassinado. Imprime um aviso sempre que é usada.
- Demonstração animada no README, gerada por `docs/demo.tape` (VHS) e
  `docs/gerar-demo.sh` — a extração do GIF roda de verdade contra a rede.
- `.github/dependabot.yml`: atualizações semanais das dependências e das actions.
- O CI passou a rodar os testes rápidos também em macOS.
- `tests/test_tls.py`: o padrão seguro agora é coberto por teste.
- Publicação no PyPI por tag, via Trusted Publishing — sem token de API guardado
  no repositório. O `install.sh` passou a instalar a versão publicada, caindo para
  o repositório só se ela ainda não estiver no índice.

## [0.2.0] — 2026-08-13

Esta versão para de tirar um retrato só e passa a opinar sobre o que encontrou.

### Adicionado

**Tema claro e escuro.** Três estratégias em ordem — `prefers-color-scheme`,
classe/atributo na raiz (`.dark`, `[data-theme]`) e o botão de tema do próprio
site — cada uma seguida de uma verificação objetiva. Se a página não muda de
aparência, nada é gerado: nenhum token escuro é derivado por cálculo. Os pares
saem no `tokens.json` (`$extensions.designsys.dark`), no `variables.css` (com
`prefers-color-scheme` **e** `[data-theme="dark"]`) e no `tailwind.config.js`.

**Escala responsiva.** A extração remede em mobile (390px) e tablet (820px),
revelando o que as media queries não dizem — `h1: 36px → 48px → 96px` — e gera
`clamp()` interpolado entre os extremos medidos.

**Diagnóstico** (`designsys audit` e uma seção do PDF):

- acessibilidade sobre pares texto/fundo **reais**, com o fundo resolvido no
  primeiro ancestral opaco e a regra do WCAG para texto grande;
- componentes cujo `:focus` não muda nada visível;
- alvos de toque abaixo de 24px e texto abaixo de 12px;
- consistência: grade de espaçamento, cores que cobrem 90% do uso, cores usadas
  uma única vez com vizinha próxima, tokens declarados e nunca referenciados por
  `var()`, e divergências entre páginas;
- assinatura visual em cinco eixos (densidade, forma, peso, saturação,
  temperatura) e uma frase que os resume.

Toda nota vem acompanhada das parcelas que a compõem, e o que não pôde ser
medido não é pontuado.

**Contexto.** Detecção do kit de UI com a evidência que sustenta a conclusão
(Tailwind v3/v4, MUI, Bootstrap, Chakra, Ant, Radix/shadcn, Headless UI,
Mantine, Vuetify e outros); reconhecimento da paleta padrão do Tailwind; nome de
cada cor — o declarado pelo site quando existe (`--color-blue-500` → `blue-500`)
e um derivado do matiz OKLCH quando não; origem das fontes (Google Fonts, Adobe,
self-hosted) com alternativa livre para as comerciais.

**Saídas novas:** `DESIGN-SYSTEM.md` (regras acionáveis para agentes de código
seguirem dentro de um projeto), `tokens.studio.json` (plugin Tokens Studio, com
claro/escuro como *modes*) e `assets/icons/sprite.svg` (ícones deduplicados como
`<symbol>`, com cor fixa trocada por `currentColor`).

**Estados e variantes:** `:active`, `:disabled` e `::placeholder`, além de
`:hover` e `:focus`. Botões agrupados por assinatura visual, o que revela as
variantes reais em vez de escolher uma primária e uma secundária.

**Crawl por saturação.** Se duas páginas seguidas não trazem token novo, a
varredura encerra e diz por quê. `--pages` passou a ser teto, não meta;
`--exhaustive` desliga o comportamento.

**No PDF:** resumo executivo de uma página, sumário com números de página
exatos, e a mesma interface renderizada nos dois temas, lado a lado.

**Comandos e opções:** `designsys audit`, e as opções `--no-dark`,
`--no-viewports` e `--exhaustive`.

### Corrigido

- Uma tupla escrita como `("--chakra-")` — string, não tupla — fazia qualquer
  variável CSS casar por prefixo: a Stripe era detectada como "Chakra UI" com 75%
  de confiança.
- A leitura de opacidade entendia apenas `rgba()`, então fundos em
  `oklch(... / 0.1)` (Tailwind v4) passavam por sólidos e o contraste era
  calculado contra um fundo que não existe.
- O `:hover` continuava ativo durante a captura do `:focus`, porque o mouse
  ficava parado sobre o elemento.
- Uma grade de espaçamento de 2px era reportada como grade, o que é sempre
  verdadeiro e não diz nada; agora abaixo de 4px o relatório afirma que não há
  grade reconhecível.
- Propriedades que existem apenas no `:focus` — o anel de foco, justamente —
  não apareciam na tabela de estados dos componentes.

### Mudado

- O caminho absoluto do repositório saiu de todos os documentos gerados; só o
  `raw.json`, que é o dump de auditoria, ainda o registra.
- Cinzas tingidos deixaram de ser chamados de azul: `#64748b` agora é
  `slate-600`, não `blue-600`.

## [0.1.0] — 2026-08-12

Primeira versão.

### Adicionado

- `designsys url` — extração de site ao vivo com Playwright: cores, tipografia,
  espaçamento, raios, sombras, z-index, transições e opacidades a partir dos
  estilos computados de todos os elementos visíveis; custom properties via CSSOM
  e, para folhas bloqueadas por CORS, download e parse com tinycss2.
- Agrupamento de cores por distância perceptual em OKLab e classificação
  semântica (primary, background, surface, text, border, success/warning/error),
  cada papel com a razão da escolha registrada.
- Login em camadas: sessão persistente (cookies e `localStorage`), automático
  (inclusive em duas etapas), código de uso único (OTP, também como 2FA), magic
  link colado no terminal e fallback manual em navegador visível. Senha nunca
  gravada em disco.
- `designsys repo` — parser tolerante de `tailwind.config.*` sem executar
  código, `@theme` do Tailwind v4, CSS/SCSS/LESS, temas de
  styled-components/emotion e arquivos de tokens (DTCG, Style Dictionary, Figma
  Tokens), com procedência por token.
- Saídas: `design-system.pdf`, `tokens.json` (W3C DTCG), `variables.css`,
  `tailwind.config.js`, `style-guide.html`, `components.json`, `raw.json`,
  assets e screenshots.
- `designsys open`, `designsys pdf` e `designsys doctor`.
