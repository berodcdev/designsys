# Arquitetura

Um mapa do código e das decisões que explicam por que ele está assim.

## O fluxo

```
                 ┌─────────────────┐
   designsys url │  extractors/web │──┐
                 └─────────────────┘  │
                                      ├──▶  DesignSystem  ──▶  output/*  ──▶  pasta
                 ┌─────────────────┐  │      (models.py)
  designsys repo │ extractors/repo │──┘
                 └─────────────────┘
```

`DesignSystem` (em `models.py`) é o **formato canônico**. Os dois modos de extração
produzem esse objeto e nada mais; todos os escritores consomem só ele. Essa fronteira é o
que permite que `designsys pdf` reconstrua um documento a partir do `raw.json` de uma
extração antiga, e que um modo ganhe capacidade sem tocar no outro.

## Pacotes

| pacote | responsabilidade |
| --- | --- |
| `extractors/` | Obter dados crus: navegador, DOM, arquivos do repositório. |
| `analysis/` | Transformar dados crus em decisões: agrupar, classificar, medir, opinar. |
| `output/` | Escrever arquivos. Nenhuma decisão nova aqui — só apresentação. |
| `browser/` | Sessão do Chromium e autenticação. |
| `util/` | Rede, parsing de CSS, canal de progresso. |

A separação importa: `analysis/` não conhece navegador nem arquivo, então é testável sem
subir nada — é onde vive a maior parte da suíte rápida.

## extractors/

**`js_collect.py`** guarda os scripts injetados na página. Tudo que precisa do DOM roda
lá dentro e volta **já agregado** — devolver 8.000 objetos de estilo por página seria
lento e inútil. Há quatro scripts: a coleta completa, uma coleta enxuta para os viewports
secundários, o detector de componentes e o leitor de estados passivos.

**`web.py`** orquestra: sessão, login, fila de páginas, coleta, contextos extras
(tema escuro e viewports), download de assets, agregação final.

**`buckets.py`** — `TokenBucket` acumula os valores de **um contexto** (`light`, `dark`,
`mobile`, `tablet`). Sem isso, suportar dois temas exigiria duplicar vinte contadores.
O bucket `light` é o canônico: é dele que saem `ds.colors`, `ds.spacing` e companhia.

**`themes.py`** aplica o tema escuro em três estratégias e **verifica objetivamente** se
a página mudou. Se não mudou, o site não tem tema escuro e nada é gerado.

**`repo.py`** varre o repositório respeitando `.gitignore`. **Não executa código:**
`tailwind.config.js` passa por `jsobj.py`, um parser tolerante de objetos JavaScript que
devolve `JSRaw` para o que não é literal — o que não pôde ser resolvido vira aviso, nunca
palpite.

## analysis/

| módulo | o que decide |
| --- | --- |
| `color.py` | Parsing de qualquer notação CSS, distância perceptual em OKLab, agrupamento. |
| `classify.py` | Que cor é `primary`, `background`, `surface`, `text`, `border`, estados. |
| `scales.py` | Quais valores formam uma escala intencional em meio ao ruído. |
| `typography.py` | Famílias, escala tipográfica por papel, nomes de tamanho. |
| `a11y.py` | Contraste, foco visível, tamanhos, alvos de toque. |
| `consistency.py` | Grade, cores órfãs, tokens fantasma, divergência entre páginas. |
| `signature.py` | Os cinco eixos do caráter visual. |
| `frameworks.py` | Qual kit de UI, com a evidência. |
| `known.py` | Nome de cada cor: o declarado pelo site ou o derivado do matiz. |
| `fonts.py` | Origem das fontes e alternativa livre. |
| `report.py` | Junta diagnóstico e contexto — o mesmo relatório para os dois modos. |

### Duas decisões que valem explicação

**Agrupamento guloso, representante real.** As cores são ordenadas por frequência e cada
uma tenta entrar num grupo existente; a mais usada vira o representante. Assim o token
final é sempre um valor que **existe de verdade** no site, e não uma média que não aparece
em lugar nenhum.

**Escala por concentração, não por contagem.** Uma página produz milhares de valores de
padding, a maioria ruído. `infer_scale` mantém os degraus que respondem por uma fatia
mínima das ocorrências, e depois reordena por valor — porque é assim que uma escala se lê.

## output/

Cada escritor é uma função pura: recebe `DesignSystem`, devolve texto.

| módulo | arquivo |
| --- | --- |
| `tokens.py` | `tokens.json` (DTCG) |
| `css.py` | `variables.css` |
| `tailwind.py` | `tailwind.config.js` |
| `styleguide.py` | `style-guide.html` |
| `agentdoc.py` | `DESIGN-SYSTEM.md` |
| `tokensstudio.py` | `tokens.studio.json` |
| `sprite.py` | `assets/icons/sprite.svg` |
| `pdfdoc.py` + `pdfrender.py` | `design-system.pdf` |
| `writer.py` | orquestra e escreve `README.md` e `raw.json` |

### O PDF

`pdfdoc.py` monta um HTML **próprio para papel** — não é o style guide impresso: capa,
resumo executivo, sumário, quebras controladas, nada interativo. `pdfrender.py` abre esse
HTML no Chromium e chama `page.pdf()`.

O sumário tem números de página **exatos**, e chegar nisso deu trabalho:

1. Somar alturas dos blocos errava por dezenas de pixels — margens entre blocos não
   aparecem em `height`.
2. A solução foi simular a quebra pela **posição de cada bloco no fluxo**, respeitando
   `break-inside: avoid` e tratando grid/flex como blocos inteiros (os filhos ficam lado a
   lado, somá-los não descreve empilhamento).
3. A medição acontece com a viewport do tamanho da folha: numa janela mais larga o texto
   ocupa menos linhas e a conta muda.

Resultado verificado contra o PDF real: **exato em todas as seções** nos três alvos de
teste.

## Invariantes

Coisas que não devem ser quebradas por uma mudança futura:

1. **Nunca inventar dado.** Sem medição, o relatório omite. Sem tema escuro no site, não
   há token escuro. Sem fundo opaco, não há contraste calculado.
2. **Nunca executar código do usuário.** Configs são analisadas, jamais avaliadas.
3. **Senha nunca em disco.** Ver [`login.md`](login.md).
4. **Caminho absoluto não vaza para documentos** — só para o `raw.json`. Ver
   `DesignSystem.display_target`.
5. **Nenhum teste depende da internet.** Os que precisam de rede sobem um servidor local.

## Testes

389 testes. Os que precisam de navegador são marcados automaticamente (`tests/conftest.py`),
então `pytest -m "not browser"` roda a suíte rápida em segundos.

| arquivo | cobre |
| --- | --- |
| `test_color.py`, `test_scales.py` | parsing, distância, agrupamento, escalas |
| `test_cssparse.py`, `test_tailwind_parser.py` | os dois parsers |
| `test_analysis_v2.py` | diagnóstico, contexto, nomes, fontes |
| `test_tokens_writer.py`, `test_outputs_v2.py`, `test_pdf.py` | todos os escritores |
| `test_login.py` | as cinco camadas de autenticação, contra um app de mentira |
| `test_themes.py` | tema escuro, viewports e diagnóstico de ponta a ponta |
| `test_cli.py` | menu, validações e mensagens de erro |
