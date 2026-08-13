# As saídas

O que cada arquivo da pasta gerada contém e como consumi-lo.

```
designsys-<nome>-<data>/
├── design-system.pdf     # o documento
├── DESIGN-SYSTEM.md      # regras para agentes de código
├── tokens.json           # W3C DTCG
├── tokens.studio.json    # Tokens Studio (Figma)
├── variables.css         # CSS custom properties
├── tailwind.config.js    # theme.extend
├── style-guide.html      # guia navegável
├── components.json       # estilos computados dos componentes
├── README.md             # resumo da extração
├── raw.json              # dump de auditoria
├── audit.md              # (após `designsys audit`)
├── assets/
│   ├── logo/  icons/  fonts/  images/
│   └── icons/sprite.svg
└── screenshots/          # (modo url)
```

## design-system.pdf

O entregável principal: A4, capa com a paleta e as fontes reais, resumo executivo, sumário
com números de página exatos, e uma seção por assunto. A cor primária extraída do site vira
a cor de destaque do próprio documento.

Regerável a qualquer momento sem repetir a extração:

```bash
designsys pdf .          # lê o raw.json da pasta
designsys pdf . --open
```

## DESIGN-SYSTEM.md

Escrito para um **agente de código** ler. Contém a paleta por papel com o uso de cada uma
("`primary` → ação principal, CTA"), a escala tipográfica, a grade de espaçamento, o CSS do
botão primário como está implementado, uma lista de regras ("não escreva cor literal", "todo
espaçamento múltiplo de 8px") e os erros de acessibilidade que **não devem ser repetidos**.

Enxuto de propósito — cabe num prompt. O uso pretendido:

```bash
cp designsys-*/DESIGN-SYSTEM.md meu-projeto/
# e no CLAUDE.md / .cursorrules do projeto:
#   "Siga as regras de DESIGN-SYSTEM.md ao escrever interface."
```

## tokens.json

Padrão [W3C Design Tokens](https://tr.designtokens.org/format/): cada folha tem `$value` e
`$type`. Grupos: `color`, `spacing`, `borderRadius`, `shadow`, `fontFamily`, `fontSize`,
`fontWeight`, `typography` (composto), `breakpoint`, `borderWidth`, `container`, `duration`,
`easing`, `zIndex`, `opacity`.

```json
{
  "color": {
    "primary": {
      "$value": "#533afd",
      "$type": "color",
      "$description": "cor de fundo dominante em botões",
      "$extensions": { "designsys": { "usageCount": 1172, "dark": "#7c74ff" } }
    }
  }
}
```

Duas extensões próprias, ambas em `$extensions.designsys`: `usageCount` (quantas vezes o
valor aparece) e `dark` (o par no tema escuro). O DTCG não tem *modes*; esta é a convenção
menos invasiva — nenhum consumidor padrão quebra por causa dela.

Entrada direta para Style Dictionary e afins.

## variables.css

Os mesmos tokens como custom properties, com comentários de seção e a razão de cada papel:

```css
:root {
  /* cores semânticas */
  --color-primary: #533afd;  /* cor de fundo dominante em botões */
  --color-background: #ffffff;
  ...
}

@media (prefers-color-scheme: dark) { :root { --color-background: #0b0f14; } }
[data-theme="dark"], .dark   { --color-background: #0b0f14; }

/* escala fluida, interpolada entre os tamanhos medidos em cada tela */
:root { --text-h1-fluid: clamp(32px, 1.443rem + 2.29vw, 56px); }
```

Os dois seletores de tema escuro existem porque os sites usam ambos: `prefers-color-scheme`
atende quem não tem toggle, `[data-theme]`/`.dark` atende quem tem.

Inclui também as regras `@font-face` capturadas, apontando para as cópias em
`assets/fonts/` com as URLs remotas como alternativa.

## tailwind.config.js

Tudo dentro de `theme.extend`, então os defaults do Tailwind continuam valendo. Cores
escuras entram sob `colors.dark.*` (o Tailwind não tem *modes*) e `darkMode` é definido
quando há tema escuro.

```bash
cp designsys-*/tailwind.config.js meu-projeto/   # ou copie só o bloco theme.extend
```

## tokens.studio.json

Formato do plugin [Tokens Studio](https://tokens.studio): conjuntos no topo (`global`,
`light`, `dark`), com `$themes` e `$metadata` descrevendo como se combinam. Claro e escuro
viram *modes* que compartilham o `global`.

Importe no plugin pelo painel de Token Sets.

## style-guide.html

Arquivo único, com as fontes reais do site. Clique numa cor e o hex vai para a área de
transferência (há um fallback para `file://`, onde a Clipboard API pode ser negada). Tem
toggle de tema e mostra os componentes reconstruídos a partir dos estilos computados, com
as diferenças de estado destacadas.

```bash
designsys open . --html
```

## components.json

Os estilos computados completos de cada componente detectado, com `base`, `hover`, `focus`
e `active`, além do seletor de origem e do HTML capturado:

```json
{
  "components": [
    {
      "kind": "button-primary",
      "selector": "#main-content > section:nth-of-type(6) > div > a",
      "base": { "background-color": "rgb(83, 58, 253)", "border-radius": "4px", ... },
      "hover": { "background-color": "rgb(93, 99, 254)" },
      "focus": { "outline-width": "3px", "outline-color": "rgba(84, 82, 251, 0.725)" }
    }
  ]
}
```

Útil para reproduzir um componente com fidelidade, ou para comparar o que o código diz com
o que está no ar.

## raw.json

O dump de auditoria: `DesignSystem` inteiro serializado mais `raw`, que contém as
frequências por propriedade, a procedência de cada token (no modo repo, o arquivo de
origem), as media queries encontradas, as folhas bloqueadas por CORS, o resultado do login
e as assinaturas de página.

É o que permite **contestar** uma decisão da ferramenta: se a cor primária parece errada,
`frequencies.button_backgrounds` mostra em que ela se baseou. Também é a entrada de
`designsys pdf` e `designsys audit`.

É o único arquivo que registra o caminho absoluto do repositório — e pode conter conteúdo
interno de um sistema autenticado. Pense antes de compartilhar.

## audit.md

Gerado por `designsys audit`: as três notas, as parcelas de cada uma, a tabela de pares
abaixo do AA e a assinatura visual. Feito para colar num ticket ou numa PR.

## assets/ e screenshots/

Logo (SVG inline preservado quando possível), ícones deduplicados por hash, arquivos de
fonte, imagens de conteúdo e um `icons/sprite.svg` com todos os ícones como `<symbol>`:

```html
<svg width="24" height="24" aria-hidden="true">
  <use href="assets/icons/sprite.svg#icon-3" />
</svg>
```

No sprite, cor fixa é trocada por `currentColor` e as dimensões são removidas — é o que
torna um sprite reutilizável fora do site de origem.

`screenshots/` tem uma captura full-page por página visitada, referenciada no PDF e no
guia.
