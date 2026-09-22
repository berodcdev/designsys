<div align="center">

# designsys

**Extrai o design system completo de um site ao vivo — inclusive atrás de login — ou de um repositório local.**

Um comando, e você recebe um PDF pronto para circular, os design tokens no padrão W3C,
CSS vars, um `tailwind.config.js` colável, um guia visual navegável e um diagnóstico
de acessibilidade e consistência.

[![CI](https://github.com/berodcdev/designsys/actions/workflows/ci.yml/badge.svg)](https://github.com/berodcdev/designsys/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/designsys.svg)](https://pypi.org/project/designsys/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-green.svg)](https://github.com/berodcdev/designsys/blob/main/LICENSE)
[![Testes](https://img.shields.io/badge/testes-400-brightgreen.svg)](https://github.com/berodcdev/designsys/blob/main/tests/)

<img src="https://raw.githubusercontent.com/berodcdev/designsys/main/docs/img/demo.gif" alt="Terminal: designsys extrai o design system da stripe.com em três páginas, lista os arquivos gerados e roda o diagnóstico de acessibilidade" width="820">

</div>

---

```bash
designsys url https://stripe.com --pages 5        # um site público
designsys url https://app.suaempresa.com --login  # um SaaS atrás de login
designsys repo ~/dev/meu-projeto                  # um repositório local
designsys audit designsys-stripe.com-2026-08-13   # o diagnóstico
```

## O que sai disso

<table>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/berodcdev/designsys/main/docs/img/pdf-capa.png" alt="Capa do PDF gerado"></td>
<td width="50%"><img src="https://raw.githubusercontent.com/berodcdev/designsys/main/docs/img/pdf-resumo.png" alt="Resumo executivo no PDF"></td>
</tr>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/berodcdev/designsys/main/docs/img/pdf-temas.png" alt="Tema claro e escuro pareados"></td>
<td width="50%"><img src="https://raw.githubusercontent.com/berodcdev/designsys/main/docs/img/pdf-diagnostico.png" alt="Diagnóstico de acessibilidade e consistência"></td>
</tr>
</table>

Uma pasta por extração:

| arquivo | o que é |
| --- | --- |
| **`design-system.pdf`** | O documento completo: capa, resumo executivo, sumário com números de página, paleta, tipografia, escalas, componentes, temas, diagnóstico e apêndice. |
| `DESIGN-SYSTEM.md` | As regras do sistema em forma acionável, escritas para um **agente de código** (Claude Code, Cursor) seguir dentro do seu projeto. |
| `tokens.json` | Design tokens no padrão [W3C DTCG](https://tr.designtokens.org/format/) (`$value`/`$type`). |
| `variables.css` | Os mesmos tokens como CSS custom properties, com bloco de tema escuro e `clamp()` fluido. |
| `tailwind.config.js` | `theme.extend` pronto para colar. |
| `tokens.studio.json` | Formato do plugin Tokens Studio, para levar ao Figma — claro e escuro como *modes*. |
| `style-guide.html` | Guia navegável; clique numa cor e o hex vai para a área de transferência. |
| `components.json` | Estilos computados dos componentes, com `:hover`, `:focus` e `:active`. |
| `raw.json` | Frequência e procedência de cada valor — para auditar qualquer decisão da extração. |
| `assets/` · `screenshots/` | Logo, ícones (com `sprite.svg`), fontes, imagens e capturas de tela. |

## Instalação

```bash
pipx install designsys
designsys doctor --fix     # baixa o Chromium do Playwright
```

São **dois** comandos porque o `pip` não executa nada depois de instalar: o Chromium que
a ferramenta usa para renderizar as páginas vem do Playwright, e é o `doctor --fix` que o
baixa. Sem ele, a instalação está completa mas a extração não roda.

### Uma linha só

O instalador confere o Python, instala o pipx se faltar, instala a ferramenta e já baixa
o Chromium:

```bash
curl -fsSL https://raw.githubusercontent.com/berodcdev/designsys/main/install.sh | bash
```

Se preferir ler antes de executar (boa prática com qualquer `curl | bash`):

```bash
curl -fsSL https://raw.githubusercontent.com/berodcdev/designsys/main/install.sh -o install.sh
less install.sh && bash install.sh
```

### Direto do repositório

Para acompanhar o que ainda não saiu em versão:

```bash
pipx install git+https://github.com/berodcdev/designsys.git
designsys doctor --fix
```

### Para desenvolver

```bash
git clone https://github.com/berodcdev/designsys.git
pipx install --editable ./designsys
designsys doctor --fix
```

Python 3.11+. Testado em macOS e Linux. Para atualizar: `pipx upgrade designsys`.

## Comandos

<div align="center">
<img src="https://raw.githubusercontent.com/berodcdev/designsys/main/docs/img/menu.svg" alt="Menu da ferramenta no terminal" width="820">
</div>

| comando | o que faz |
| --- | --- |
| `designsys url <URL>` | Extrai de um site ao vivo, com JavaScript renderizado. |
| `designsys repo [caminho]` | Extrai de um repositório local (padrão: diretório atual). |
| `designsys audit <pasta>` | Diagnóstico de uma extração: acessibilidade, consistência, assinatura. Grava `audit.md`. |
| `designsys open <pasta>` | Abre o PDF (ou o guia navegável, com `--html`). |
| `designsys pdf <pasta>` | Regera o PDF a partir do `raw.json`, sem repetir a extração. |
| `designsys doctor [--fix]` | Diagnostica e conserta o ambiente. |

### Opções do `url`

| opção | efeito |
| --- | --- |
| `--login` | Autentica antes de extrair (prompt seguro; a senha nunca é ecoada). |
| `--user` / `--pass` | Credenciais na linha de comando. **`--pass` fica no histórico do shell** — prefira o prompt. |
| `--pages N` | Teto de páginas internas a visitar (padrão 8). |
| `--path /rota` | Rota específica a visitar depois do login (repetível). |
| `--out <dir>` | Pasta de saída (padrão `./designsys-<domínio>-<data>/`). |
| `--exhaustive` | Visita todas as páginas, mesmo as que não trazem token novo. |
| `--no-dark` | Não tenta capturar o tema escuro. |
| `--no-viewports` | Não recoleta em mobile/tablet (extração mais rápida). |
| `--no-assets` · `--no-pdf` | Pula o download de assets · não gera o PDF. |
| `--headed` | Abre o navegador visível (útil para 2FA e captcha). |
| `--insecure` | Aceita certificado TLS inválido. Só em ambiente interno de confiança. |
| `--verbose` | Detalhes e tracebacks. |

## Login

O que torna a ferramenta útil em SaaS real. Funciona em camadas, da mais automática
para a manual:

1. **Sessão salva** — cookies (inclusive os de sessão, sem expiração) e `localStorage`
   ficam em `~/.designsys/profiles/<domínio>/` e são reinjetados. Se a sessão ainda vale,
   o login é pulado.
2. **Usuário e senha** — o formulário é detectado por heurística, inclusive em fluxos de
   duas etapas (e-mail → avançar → senha).
3. **Código de uso único (OTP)** — reconhece a tela de código, incluindo os seis
   quadradinhos de um dígito, pede o código no terminal e digita como uma pessoa faria.
   Vale também como **2FA** depois da senha.
4. **Magic link** — você copia o link do e-mail e cola no terminal; ele é aberto **dentro
   da mesma sessão do Chromium**, então a autenticação fica com a ferramenta (clicar no
   link no seu navegador normal não adiantaria).
5. **Manual** — captcha, SSO ou qualquer coisa que o resto não resolva: o navegador abre
   visível e espera você entrar.

Como a sessão persiste, isso acontece **uma vez por domínio**.

> **Senha nunca é gravada em disco.** O que persiste são os cookies — e um token de sessão
> vale tanto quanto a senha enquanto não expira. Trate `~/.designsys/profiles/` como
> material sensível: `rm -rf ~/.designsys/profiles/<domínio>`. Detalhes em
> [`SECURITY.md`](https://github.com/berodcdev/designsys/blob/main/SECURITY.md).

Mais a fundo em [`docs/login.md`](https://github.com/berodcdev/designsys/blob/main/docs/login.md).

## Além dos tokens

Listar valores é a parte fácil. O que a ferramenta faz com eles:

**Tema claro e escuro.** Três estratégias em ordem — `prefers-color-scheme`,
classe/atributo na raiz (`.dark`, `[data-theme]`) e o botão de tema do próprio site —
cada uma seguida de verificação objetiva. Se a página não muda de aparência, **nada é
gerado**: nenhum token escuro é derivado por cálculo.

**Escala responsiva.** Remede em mobile (390px) e tablet (820px) e revela o que as media
queries não dizem: `h1: 36px → 48px → 96px`. Vira `clamp()` interpolado entre os extremos
medidos.

**Diagnóstico.** Contraste sobre pares texto/fundo **reais** (o fundo é o primeiro
ancestral opaco, com a regra do WCAG para texto grande), componentes cujo `:focus` não
muda nada visível, alvos de toque pequenos, valores fora da grade de espaçamento, cores
usadas uma única vez com vizinha próxima, tokens declarados que ninguém referencia com
`var()`, e divergências entre páginas.

**Assinatura visual.** Cinco eixos — densidade, forma, peso, saturação, temperatura — e
uma frase: *"Sistema compacto e anguloso, de tipografia regular, com paleta sóbria e
fria."*

**Contexto.** Qual kit de UI está por trás, com a evidência que sustenta a conclusão
(acertou *"Tailwind CSS v4, junto de Headless UI"* no tailwindcss.com e *"CSS próprio"* na
Stripe); o nome de cada cor — o **declarado pelo site** quando existe (`--color-blue-500`
→ `blue-500`) e um derivado do matiz OKLCH quando não; e a origem das fontes, com
alternativa livre para as comerciais (Söhne → Inter).

> **Uma regra orienta tudo isso:** quando não é possível medir, o relatório **omite** em
> vez de estimar. Toda nota vem acompanhada das parcelas que a compõem, e o que não foi
> verificado não é pontuado.

## Como funciona

**Modo `url`.** O Chromium carrega a página com JavaScript renderizado e percorre todos os
elementos visíveis lendo `getComputedStyle`. As custom properties vêm do CSSOM; folhas
bloqueadas por CORS são baixadas por HTTP e analisadas com tinycss2. Cores quase idênticas
são agrupadas por distância perceptual em OKLab, e o representante de cada grupo é sempre
um valor que existe de verdade no site — nunca uma média. Componentes são detectados por
heurística e capturados também nos estados de interação.

**Modo `repo`.** Nada é executado: o `tailwind.config.*` passa por um parser tolerante de
objetos JavaScript, e o CSS/SCSS/LESS por um parser de CSS. Também lê `@theme` do Tailwind
v4, temas de styled-components/emotion e arquivos de tokens (DTCG, Style Dictionary, Figma
Tokens), respeitando o `.gitignore`. Valores que dependem de execução aparecem como
avisos, não como palpites.

## Documentação

- [`docs/arquitetura.md`](https://github.com/berodcdev/designsys/blob/main/docs/arquitetura.md) — como o código está organizado e por quê.
- [`docs/login.md`](https://github.com/berodcdev/designsys/blob/main/docs/login.md) — as camadas de autenticação em detalhe.
- [`docs/saidas.md`](https://github.com/berodcdev/designsys/blob/main/docs/saidas.md) — o formato de cada arquivo gerado.
- [`docs/diagnostico.md`](https://github.com/berodcdev/designsys/blob/main/docs/diagnostico.md) — como as notas são calculadas.
- [`CHANGELOG.md`](https://github.com/berodcdev/designsys/blob/main/CHANGELOG.md) — histórico de versões.

## Contribuindo

Contribuições são bem-vindas. O [`CONTRIBUTING.md`](https://github.com/berodcdev/designsys/blob/main/CONTRIBUTING.md) tem o essencial:
como rodar, como testar (`pytest -m "not browser"` para o ciclo rápido) e o que se espera
de um PR.

```bash
git clone https://github.com/berodcdev/designsys.git && cd designsys
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]' && playwright install chromium
pytest
```

## Aviso de uso

A ferramenta lê o CSS público de páginas que **você tem o direito de acessar**. Extrair o
design system de um site não transfere direitos sobre marca, tipografia licenciada ou
identidade visual: fontes comerciais continuam exigindo licença, e logotipo e marca são
protegidos. Use para auditar o seu próprio produto, documentar um sistema que já é seu ou
estudar — não para clonar a identidade de outra pessoa.

## Licença

[MIT](https://github.com/berodcdev/designsys/blob/main/LICENSE) — © 2026 Bernardo.

---

<div align="center">

Desenvolvido por **[dev@bernardorodc.com](mailto:dev@bernardorodc.com)**

</div>
