# Política de segurança

## Reportando uma falha

Mande um e-mail para **dev@bernardorodc.com** com o assunto começando por
`[designsys][security]`. Por favor, não abra issue pública para falhas que
exponham dados de quem usa a ferramenta.

Inclua o que conseguir: versão (`designsys --version`), sistema operacional,
passos para reproduzir e o impacto que você enxerga.

## Versões suportadas

| versão | suporte |
| --- | --- |
| 0.2.x | sim |
| 0.1.x | não — atualize |

## O que esta ferramenta guarda na sua máquina

Vale conhecer antes de usar em sistemas autenticados.

**Nunca é gravado:** senha, código de uso único (OTP) ou o conteúdo do magic
link. Eles existem apenas em memória, durante a execução.

**É gravado**, em `~/.designsys/profiles/<domínio>/`:

- o perfil do Chromium (que inclui os cookies do domínio);
- `designsys-state.json`, com cookies e `localStorage` — permissão `600`, e é o
  que permite reaproveitar o login na execução seguinte.

Trate essa pasta como material sensível: **um token de sessão vale tanto quanto
a senha** enquanto não expira. Para apagar o que ficou de um domínio:

```bash
rm -rf ~/.designsys/profiles/app.suaempresa.com
```

**Na pasta de saída:** o `raw.json`, os `screenshots/` e o HTML capturado dos
componentes podem conter conteúdo interno do sistema que você extraiu. Pense
duas vezes antes de versionar ou compartilhar uma pasta gerada a partir de um
ambiente autenticado — o `.gitignore` deste repositório já ignora
`designsys-*/` por esse motivo.

## Conexão

O navegador **valida o certificado TLS** de tudo que carrega. Se o site que você
quer extrair usa certificado próprio ou autoassinado — típico de ambientes de
homologação internos — a extração falha com uma mensagem explícita, e você pode
repetir com `--insecure`.

Essa flag desliga a validação para toda a execução: a conexão passa a aceitar
qualquer certificado, inclusive o de quem estiver no meio do caminho. Use apenas
em rede e ambiente de confiança, e nunca junto de `--login` numa rede que você
não controla — é exatamente aí que a senha viaja.

## Escopo

A ferramenta abre páginas num navegador e lê o CSS delas. Ela não executa código
de configuração de projetos (o `tailwind.config.js` é interpretado por um parser,
nunca avaliado) e não envia nada para nenhum servidor além das requisições
necessárias para carregar o site que você pediu.
