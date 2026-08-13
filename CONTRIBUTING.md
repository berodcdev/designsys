# Contribuindo

Obrigado pelo interesse. Este documento diz o mínimo para você conseguir rodar,
testar e propor mudanças sem perder tempo.

## Rodando o projeto

> Só quer **usar** a ferramenta? O instalador resolve:
> `curl -fsSL https://raw.githubusercontent.com/berodcdev/designsys/main/install.sh | bash`
>
> O que segue é para trabalhar no código.

```bash
git clone https://github.com/berodcdev/designsys.git
cd designsys
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
playwright install chromium
designsys doctor            # confirma que está tudo no lugar
```

Requer **Python 3.11+**. Funciona em macOS e Linux.

## Testes

```bash
pytest                      # tudo (~5 min, sobe o Chromium várias vezes)
pytest -m "not browser"     # só os rápidos (~15 s), sem navegador
pytest tests/test_color.py  # um arquivo
pytest -k contraste         # por nome
```

Os testes que precisam de navegador são marcados automaticamente com `browser`
(veja `tests/conftest.py`). Eles sobem um servidor HTTP local com páginas de
mentira — **nenhum teste depende da internet**, e isso é uma regra: um teste que
quebra porque um site de terceiro mudou não é um teste.

## O que esperamos de um PR

**Teste junto.** Toda correção vem com um teste que falharia antes dela. Toda
heurística nova vem com o caso que ela resolve e, se possível, o caso em que ela
não deve disparar — falso positivo em heurística é o defeito mais comum aqui.

**Verifique de verdade.** Se a mudança afeta extração, rode contra um site real
e olhe o resultado, não só o código de saída:

```bash
designsys url https://tailwindcss.com --pages 2 --out /tmp/teste
designsys audit /tmp/teste
open /tmp/teste/design-system.pdf
```

`tailwindcss.com` é um bom alvo: tem tema escuro real, é Tailwind v4 e expõe a
paleta em variáveis CSS. `stripe.com` é o oposto útil — design system próprio,
sem framework reconhecível.

**Nunca invente dado.** A regra que orienta o projeto inteiro: quando não é
possível medir algo, o relatório **omite** em vez de estimar. Um token de tema
escuro derivado por cálculo, um contraste calculado contra fundo translúcido ou
uma nota sobre algo que não foi verificado são piores que a ausência da
informação. Se a sua mudança precisa adivinhar, ela precisa dizer que adivinhou.

**Escreva em português.** Código, comentários, docstrings, mensagens da CLI e
documentação. Nomes de API pública podem ficar em inglês quando o termo é o
usual (`build_dtcg`, `TokenBucket`).

## Estilo

- Linhas até ~100 colunas.
- Comentário explica **por quê**, não o quê. Se o código já diz o que faz, o
  comentário é ruído; se há uma decisão não óbvia (um limiar, uma ordem de
  tentativas, um caso de borda do navegador), aí ele é obrigatório.
- Sem dependência nova sem necessidade real. São sete hoje, e cada uma foi
  escolhida por não ter substituto razoável na biblioteca padrão.

## Onde mexer

Um mapa rápido — os detalhes estão em [`docs/arquitetura.md`](docs/arquitetura.md):

| quero mudar | vá para |
| --- | --- |
| o que é coletado da página | `src/designsys/extractors/js_collect.py` |
| como as páginas são percorridas | `src/designsys/extractors/web.py` |
| leitura de Tailwind, CSS, temas JS | `src/designsys/extractors/repo.py` |
| agrupamento e classificação de cor | `src/designsys/analysis/color.py`, `classify.py` |
| diagnóstico e notas | `src/designsys/analysis/a11y.py`, `consistency.py` |
| detecção de framework, nomes, fontes | `src/designsys/analysis/frameworks.py`, `known.py`, `fonts.py` |
| o PDF | `src/designsys/output/pdfdoc.py`, `pdfrender.py` |
| os outros arquivos gerados | `src/designsys/output/` |
| o menu e os comandos | `src/designsys/cli.py` |

## Relatando um problema de extração

O mais útil é o `raw.json` da pasta gerada: ele tem as frequências e a
procedência de cada valor, e é o que permite reproduzir a decisão que a
ferramenta tomou. Se o site for público, a URL e o número de páginas bastam.

Cuidado: `raw.json` de um site autenticado pode conter conteúdo interno da sua
empresa. Nesse caso descreva o comportamento em vez de anexar o arquivo.

## Segurança e privacidade

Duas invariantes que não devem ser quebradas:

1. **Senha nunca vai para disco.** O que persiste é o perfil do Chromium e o
   `designsys-state.json` (cookies e `localStorage`), em `~/.designsys/profiles/`.
2. **O caminho absoluto do repositório não aparece nos documentos**, só no
   `raw.json`. Ver `DesignSystem.display_target`.

Se encontrar uma falha de segurança, veja [`SECURITY.md`](SECURITY.md).
