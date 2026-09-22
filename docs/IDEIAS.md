# Ideias

Coisas que valem a pena e ainda não foram feitas. Não é roadmap com prazo — é o que
está em aberto, com o motivo, para não se perder.

## 2026-09-21 · a partir de "Auditoria de segurança do repo público e GIF do README"

- [ ] **Apagar sessões pelo próprio CLI** (P) — o `doctor` já lista os perfis salvos
  (`cli.py:967`), mas mandar apagar é `rm -rf` na mão, como SECURITY.md e README instruem.
  São 6 perfis e 157 MB guardados aqui hoje, com cookies que valem tanto quanto a senha.
  O dado já é coletado; falta o verbo · `src/designsys/cli.py` · _proposta_
- [ ] **Senha por variável de ambiente ou stdin** (P) — hoje a única via não interativa é
  `--pass`, que o próprio código avisa que fica no histórico do shell (`cli.py:521`). Não há
  `os.environ`/`stdin` em lugar nenhum do código para isso, então quem automatiza não tem
  saída segura · `src/designsys/cli.py` · _proposta_
- [ ] **Gerar o `menu.svg` por tape também** (P) — o `demo.gif` agora tem fonte versionada e
  o CONTRIBUTING diz que o `.tape` é a fonte da verdade; o `menu.svg` (84 KB) continua sendo
  o único asset sem gerador, feito à mão uma vez. O VHS tem `Screenshot`, então é o mesmo
  ferramental · `docs/demo.tape` · _proposta_

## Distribuição

**Release por tag e PyPI — feitos na 0.3.0.** `.github/workflows/release.yml` publica com
Trusted Publishing (sem token guardado), e o `install.sh` passou a instalar a versão
publicada, caindo para o repositório só se ela ainda não estiver no índice.

## Cadeia de dependências

**Fixar as actions por SHA.** `actions/checkout@v4` e companhia são tags móveis: o que
elas apontam pode mudar. Com o Dependabot já configurado, trocar as tags por SHA custa
pouco de manutenção, porque os bumps chegam em PR.

## Qualidade

**Linter.** Não há `ruff`/`black` no projeto, então a consistência de estilo depende de
revisão manual — o que não escala quando chega PR de fora. Um extra `dev` com `ruff` e um
step no CI resolveria.

**Canal de segurança além do e-mail.** O `SECURITY.md` aponta para um e-mail pessoal.
Habilitar GitHub Security Advisories dá um caminho privado padrão, que quem pesquisa
segurança já conhece e procura primeiro.
