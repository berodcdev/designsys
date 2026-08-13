# Diagnóstico

Como as notas são calculadas, o que cada uma mede e — principalmente — o que elas **não**
afirmam.

```bash
designsys audit designsys-stripe.com-2026-08-13
```

A mesma análise aparece como seção do PDF em toda extração.

## O princípio

Um índice sem os casos que o produziram não serve para agir, e um índice que não se sustenta
é pior que nenhum. Por isso:

- toda nota vem acompanhada das **parcelas** que a compõem;
- todo desconto vem com os **ofensores** citados;
- **o que não pôde ser medido não é pontuado** — não entra como zero nem como estimativa.

A nota geral é `acessibilidade × 0,55 + consistência × 0,45` quando houve o que medir em
acessibilidade; caso contrário, é só a consistência. Acessibilidade pesa mais porque um
sistema bonito e inacessível é um problema maior que um sistema irregular e legível.

## Acessibilidade

### Contraste

Não é simulação: cada par vem de texto que existe na página, com o fundo que estava atrás
dele. O fundo é resolvido subindo a árvore até o primeiro ancestral **praticamente opaco**
(≥ 85%) — e se nesse caminho aparece um gradiente, o par é descartado, porque não há um
valor único contra o qual calcular.

Pares com fundo translúcido também são descartados: o contraste real dependeria do que está
atrás, e afirmar um número ali seria inventar.

O mínimo exigido segue o WCAG 2.2 AA:

| texto | mínimo |
| --- | --- |
| normal | 4.5:1 |
| grande (≥ 24px, ou ≥ 18.66px em negrito) | 3.0:1 |

A lista é ordenada por **ocorrências**, não por gravidade: um par ruim que aparece 242 vezes
importa mais que um que aparece uma.

### Foco visível

Usa o estado `:focus` já capturado de cada componente. Um componente é apontado quando o
foco **não muda nada perceptível** — mudar só a cor do texto não conta como indicação de
foco. O anel padrão do navegador conta: o problema real é o `outline: none` sem nada no
lugar.

### Tamanhos e alvos

Estilos de texto abaixo de 12px, e botões, links e campos com menos de 24px de altura ou
largura (WCAG 2.2, *Target Size (Minimum)*, nível AA).

### A nota

Parte de 100 e desconta:

| descon­to | por |
| --- | --- |
| até −45 | proporção de pares de texto abaixo do AA |
| até −25 | proporção de componentes sem foco visível |
| até −12 | estilos de texto abaixo de 12px |
| até −10 | alvos de toque pequenos |

Sem pares medidos e sem componentes com foco capturado, a acessibilidade não é avaliada — é
o caso do modo `repo`, que não tem navegador.

## Consistência

### Grade de espaçamento

Qual fração dos valores de `margin`, `padding` e `gap` cai na grade detectada. Meio degrau
(4px numa grade de 8) conta como dentro, porque é intencional em praticamente todo sistema.

Grades abaixo de 4px são rejeitadas: com passo de 2px quase todo valor "cai na grade", e a
métrica deixaria de dizer qualquer coisa. Nesse caso o relatório afirma que **não há grade
reconhecível** — o que é mais honesto.

### Tamanho da paleta

Não é o número de cores encontradas, que bate no teto da própria extração. É **quantas cores
respondem por 90% das ocorrências**: uma paleta disciplinada cobre quase todo o uso com
poucas cores.

### Cores órfãs

Cores usadas uma ou duas vezes. As mais reveladoras são as que têm uma **vizinha próxima**
na paleta principal — `#3a3a3c` solitário ao lado de um `#3a3a3b` estabelecido é o sintoma
clássico de cor escrita à mão onde havia um token.

### Tokens fantasma

Custom properties declaradas que ninguém referencia com `var()`. Só é avaliado no modo
`repo`, onde os arquivos de origem estão disponíveis para procurar os usos.

### Divergência entre páginas

Cores de botão ou famílias tipográficas que aparecem em algumas páginas e não em outras —
sinal de que a mesma coisa foi implementada duas vezes.

### A nota

| desconto | por |
| --- | --- |
| até −60 | proporção do espaçamento fora da grade |
| −10 | não haver grade reconhecível |
| até −20 | paleta larga (acima de 20 cores para cobrir 90% do uso) |
| até −15 | cores usadas uma única vez |
| até −10 | tokens declarados e nunca usados |
| até −10 | mais de três famílias tipográficas |
| −4 cada | divergência entre páginas |

## Assinatura visual

Cinco eixos, todos derivados de valores já coletados, que distinguem sistemas que a lista de
tokens não distingue — dois sites podem ter a mesma paleta e parecer completamente
diferentes.

| eixo | de onde vem | extremos |
| --- | --- | --- |
| densidade | espaçamento mediano | compacto ↔ arejado |
| forma | raio mediano (ignorando o pill) | anguloso ↔ arredondado |
| peso | maior peso tipográfico em uso | leve ↔ encorpado |
| saturação | croma mediano dos destaques | sóbrio ↔ vibrante |
| temperatura | matiz predominante | quente ↔ frio |

E uma frase que os resume: *"Sistema compacto e anguloso, de tipografia regular, com paleta
sóbria e fria."*

É descritivo, não avaliativo: não existe posição certa em nenhum desses eixos.

## O que o diagnóstico não é

**Não é uma auditoria de acessibilidade completa.** Ele mede o que dá para medir a partir do
CSS computado: contraste, foco, tamanhos. Não avalia estrutura semântica, ordem de
tabulação, rótulos de formulário, texto alternativo, ARIA nem navegação por leitor de tela.
Passar com nota alta aqui **não** significa estar conforme o WCAG.

**Não é um juízo sobre o design.** Uma paleta larga pode ser uma escolha; três famílias
tipográficas podem ser corretas para o produto. Os descontos apontam onde o sistema é
irregular, e irregularidade nem sempre é erro — mas quase sempre vale uma olhada.

**Não substitui teste com pessoas.** Nenhuma métrica automática substitui.
