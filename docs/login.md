# Login

Extrair o design system de um site público é o caso fácil. O valor está em conseguir
entrar no produto — e é aí que quase toda ferramenta desse tipo para. Este documento
explica como as camadas funcionam e o que fazer quando alguma falha.

## As cinco camadas

Elas são tentadas nesta ordem, e a primeira que resolver encerra o assunto.

### 1. Sessão salva

O Chromium roda com um perfil persistente em `~/.designsys/profiles/<domínio>/`. Se a
sessão anterior ainda vale, a página abre autenticada e o login é pulado inteiro.

Cookies de sessão (sem `Expires`) são descartados pelo navegador ao fechar — e é
justamente o que muitos SaaS usam. Por isso o `designsys` guarda o `storage_state` num
arquivo à parte (`designsys-state.json`, permissão `600`) e o reinjeta na abertura,
incluindo `localStorage`, onde SPAs modernas costumam guardar o token.

### 2. Usuário e senha

O formulário é encontrado por uma lista de seletores, do mais específico para o mais
genérico (`input[type=email]`, `input[autocomplete=username]`, `input[name*=user]`…),
inclusive dentro de iframes — Auth0 e afins.

Fluxos de **duas etapas** (e-mail → avançar → senha) são detectados: se não há campo de
senha, a ferramenta avança e espera o campo aparecer.

O sucesso é verificado, não presumido: o campo de senha desapareceu e a página não é mais
uma tela de login. Se falhou, a mensagem de erro do próprio site é lida e reportada.

### 3. Código de uso único (OTP)

Quando o site pede só o e-mail, ou pede um segundo fator depois da senha:

- a tela de código é reconhecida pelo campo (`autocomplete=one-time-code`,
  `inputmode=numeric`, `maxlength=1`) ou pelo texto ("código de verificação");
- o código é pedido no terminal;
- se o campo é **segmentado** (os seis quadradinhos), a ferramenta foca o primeiro e
  digita pelo teclado, deixando o componente avançar de caixa sozinho — como uma pessoa
  faria. Preencher os campos um a um por JavaScript quebra em muitos componentes;
- muitos apps submetem sozinhos ao completar; se não, o botão é clicado.

A senha é **opcional**: num fluxo só de código, deixe em branco no prompt.

### 4. Magic link

Se o site manda um link em vez de código, a ferramenta pede que você **cole o link** no
terminal e o abre **dentro da mesma sessão do Chromium**.

Isso é o ponto: clicar no link no seu navegador normal autentica *aquele* navegador, não o
que está fazendo a extração. Um link expirado ou já usado responde 4xx, e isso é
reportado como falha em vez de passar por sucesso.

### 5. Manual

Captcha, SSO corporativo, ou qualquer coisa que as camadas acima não resolvam: o navegador
reabre **visível** (preservando o perfil) e espera. Você entra à mão, aperta Enter no
terminal, e a extração segue com a sessão autenticada.

É a camada que torna a ferramenta à prova de qualquer SaaS — e a razão de ela nunca
precisar "suportar" um provedor específico.

## Usando

```bash
# o caminho comum: prompt seguro, senha não ecoada
designsys url https://app.suaempresa.com --login

# acesso por código ou link: informe só o e-mail
designsys url https://app.suaempresa.com --login --user voce@empresa.com

# já sei que vai cair no manual (captcha, SSO)
designsys url https://app.suaempresa.com --login --headed

# rotas específicas depois de entrar
designsys url https://app.suaempresa.com --login --path /dashboard --path /settings
```

`--pass` existe, mas **fica no histórico do shell**. Prefira o prompt.

## Quando algo dá errado

**"a página pede login — rode de novo com `--login`"** — a extração encontrou uma tela de
autenticação sem que você tenha pedido para autenticar.

**O login automático não conclui** — a ferramenta reporta o motivo (campo não encontrado,
mensagem de erro do site, captcha detectado) e cai para o manual. Rodar com `--verbose`
mostra cada passo: qual campo foi preenchido, por qual seletor foi submetido.

**A sessão não é reaproveitada** — o site pode invalidar sessões por user-agent ou IP.
Apague o perfil e refaça: `rm -rf ~/.designsys/profiles/<domínio>`.

**O site bloqueia automação** — `--headed` costuma resolver, porque muitas proteções
avaliam sinais que só aparecem em modo headless.

## Segurança

**Senha, código OTP e o conteúdo do magic link nunca vão para disco.** Existem só em
memória, durante a execução.

**Os cookies vão.** É o que permite não repetir o login — e significa que
`~/.designsys/profiles/` guarda material tão sensível quanto a senha enquanto a sessão
não expira:

```bash
rm -rf ~/.designsys/profiles/app.suaempresa.com   # encerrou o trabalho? apague
```

A pasta de saída também merece cuidado: `raw.json`, `screenshots/` e o HTML capturado dos
componentes podem conter dados internos do sistema que você extraiu. O `.gitignore` do
projeto já ignora `designsys-*/` por isso.

Mais em [`SECURITY.md`](../SECURITY.md).
