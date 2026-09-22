# Fonte da verdade do GIF do README (docs/img/demo.gif).
#
# Regerar:  bash docs/gerar-demo.sh
# Requer:   vhs (charmbracelet/vhs), ttyd, ffmpeg e o designsys no PATH.
#
# A extração roda de verdade contra stripe.com — os números que aparecem são
# medidos na hora, não encenados.
#
# Este tape produz um MP4 em tempo real; quem transforma em GIF é o
# gerar-demo.sh, que acelera o vídeo em ACELERACAO×. Por isso a digitação e as
# pausas aqui estão multiplicadas por 8: depois da aceleração elas voltam ao
# ritmo natural (~55 ms por tecla). Se mudar a aceleração no script, mude estes
# números junto.
#
# O tema do terminal é o design system que a própria ferramenta extraiu da
# Stripe: fundo #0a2540 (secondary), verde #15be53 (success), âmbar #ffbb00
# (warning), laranja #ff6118 (error) — e o cyan do Rich mapeado no roxo da
# marca, #7c6cff.

Output docs/img/demo.mp4

Require designsys

Set Shell bash
Set FontFamily "MesloLGS Nerd Font Mono"
Set FontSize 14
Set Width 960
Set Height 720
Set Padding 20
Set LineHeight 1.2
Set Framerate 30
Set TypingSpeed 440ms
Set WaitTimeout 600s

# O VHS lê a linha do prompt sem o espaço final — daí o padrão sem espaço.
Set WaitPattern /❯$/

Set Theme { "background": "#0a2540", "foreground": "#e6ebf1", "cursor": "#7c6cff", "selection": "#425466", "black": "#0a2540", "red": "#ff6118", "green": "#15be53", "yellow": "#ffbb00", "blue": "#533afd", "magenta": "#e0489e", "cyan": "#7c6cff", "white": "#e6ebf1", "brightBlack": "#5b7a99", "brightRed": "#ff8a5c", "brightGreen": "#4fd67f", "brightYellow": "#ffd04d", "brightBlue": "#7c6cff", "brightMagenta": "#f472b6", "brightCyan": "#a897ff", "brightWhite": "#ffffff" }

# --- preparo, fora do quadro -------------------------------------------------
# Diretório temporário: deixa o caminho que aparece na saída livre de qualquer
# coisa pessoal, e a pasta gerada fora do repositório.
Hide
Type 'export PATH="$HOME/.local/bin:$PATH"' Enter
Type 'export PS1="❯ "' Enter
Type 'rm -rf /tmp/designsys-demo && mkdir -p /tmp/designsys-demo && cd /tmp/designsys-demo' Enter
Type 'clear' Enter
Show

Sleep 8s

# --- o comando estrela -------------------------------------------------------
Type "designsys url stripe.com --pages 3 --no-viewports" Sleep 5s Enter

# Spinner e barra por página, ✓ com contagem de elementos e regras, depois o
# painel de tokens e a lista de arquivos gerados. O Sleep dá tempo de o comando
# começar antes de o Wait procurar o prompt de volta.
Sleep 3s
Wait

Sleep 28s

# --- o diagnóstico -----------------------------------------------------------
Type "designsys audit designsys-stripe.com-*" Sleep 5s Enter
Sleep 3s
Wait

Sleep 40s
