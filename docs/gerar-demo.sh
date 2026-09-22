#!/usr/bin/env bash
# Gera docs/img/demo.gif — o GIF do topo do README.
#
#   bash docs/gerar-demo.sh
#
# Duas etapas. Primeiro o VHS grava docs/demo.tape em MP4, em tempo real: a
# extração roda de verdade contra stripe.com e, com a captura de frames por
# cima, leva vários minutos. Depois o ffmpeg acelera esse vídeo em ACELERACAO×
# e o converte em GIF com paleta própria.
#
# Gravar em tempo real e acelerar depois é o que permite ter a barra de
# progresso fluida e, ainda assim, um GIF de meio minuto. O tape compensa a
# aceleração na origem: a digitação e as pausas de lá já estão multiplicadas
# por ACELERACAO. Mexeu num, mexa no outro.
#
# Para calibrar sem regravar (a gravação é a parte cara):
#
#   MANTER_MP4=1 bash docs/gerar-demo.sh      # guarda o vídeo bruto
#   PULAR_GRAVACAO=1 bash docs/gerar-demo.sh  # reprocessa o vídeo guardado
set -euo pipefail

ACELERACAO=8      # quantas vezes o vídeo é acelerado
FPS=13            # frames por segundo do GIF final
LARGURA=900       # largura do GIF em px (altura sai proporcional)

cd "$(dirname "$0")/.."

for prog in vhs ffmpeg designsys; do
  command -v "$prog" >/dev/null 2>&1 || {
    echo "falta o $prog no PATH." >&2
    exit 1
  }
done

mp4="docs/img/demo.mp4"

if [ "${PULAR_GRAVACAO:-0}" = "1" ]; then
  [ -f "$mp4" ] || { echo "não há $mp4 para reprocessar." >&2; exit 1; }
  echo "==> reaproveitando $mp4"
else
  echo "==> gravando docs/demo.tape (a extração roda de verdade; leva alguns minutos)"
  vhs docs/demo.tape
fi

gif="docs/img/demo.gif"
paleta="$(mktemp -t designsys-paleta).png"
trap 'rm -f "$paleta"' EXIT

bruto=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$mp4")
alvo=$(awk -v d="$bruto" -v a="$ACELERACAO" 'BEGIN{printf "%.0f", d/a}')
echo "==> vídeo bruto: ${bruto%.*}s · acelerando ${ACELERACAO}× → ~${alvo}s"

filtro="setpts=PTS/${ACELERACAO},fps=${FPS},scale=${LARGURA}:-1:flags=lanczos"

# Duas passadas: a primeira aprende as cores do vídeo, a segunda aplica. Sem
# isso o GIF fica com os degradês da barra de progresso em faixas.
ffmpeg -v error -y -i "$mp4" -vf "${filtro},palettegen=max_colors=192:stats_mode=diff" "$paleta"
ffmpeg -v error -y -i "$mp4" -i "$paleta" \
  -lavfi "${filtro}[v];[v][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle" \
  "$gif"

[ "${MANTER_MP4:-0}" = "1" ] || rm -f "$mp4"

echo "==> pronto: $gif ($(du -h "$gif" | cut -f1))"
