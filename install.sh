#!/usr/bin/env bash
#
# Instalador do designsys.
#
#   curl -fsSL https://raw.githubusercontent.com/berodcdev/designsys/main/install.sh | bash
#
# Cuida de tudo: confere o Python, instala o pipx se faltar, instala a
# ferramenta e baixa o Chromium do Playwright. Não mexe em nada além disso.

set -euo pipefail

REPO="https://github.com/berodcdev/designsys.git"
PYTHON_MINIMO="3.11"

# Cores só quando a saída é um terminal — em pipe ou log, texto limpo.
if [ -t 1 ]; then
  ROXO=$'\033[38;5;99m'; VERDE=$'\033[32m'; AMARELO=$'\033[33m'
  VERMELHO=$'\033[31m'; CINZA=$'\033[2m'; FIM=$'\033[0m'
else
  ROXO=""; VERDE=""; AMARELO=""; VERMELHO=""; CINZA=""; FIM=""
fi

passo()  { printf "%s›%s %s\n" "$CINZA" "$FIM" "$1"; }
ok()     { printf "%s✓%s %s\n" "$VERDE" "$FIM" "$1"; }
aviso()  { printf "%s!%s %s\n" "$AMARELO" "$FIM" "$1"; }
erro()   { printf "\n%serro%s %s\n\n" "$VERMELHO" "$FIM" "$1" >&2; exit 1; }

tem() { command -v "$1" >/dev/null 2>&1; }

banner() {
  printf "\n%s  designsys%s  %sinstalador%s\n" "$ROXO" "$FIM" "$CINZA" "$FIM"
  printf "  %so design system completo de qualquer site ou repositório%s\n\n" "$CINZA" "$FIM"
}

# ---------------------------------------------------------------- Python
verificar_python() {
  local python=""
  for candidato in python3.13 python3.12 python3.11 python3; do
    if tem "$candidato"; then
      local versao
      versao=$("$candidato" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "0.0")
      if [ "$(printf '%s\n%s\n' "$PYTHON_MINIMO" "$versao" | sort -V | head -1)" = "$PYTHON_MINIMO" ]; then
        python="$candidato"
        ok "Python $versao ($candidato)"
        break
      fi
    fi
  done

  [ -n "$python" ] || erro "preciso de Python $PYTHON_MINIMO ou mais novo.
  macOS: brew install python@3.12
  Debian/Ubuntu: sudo apt install python3.12"
}

# ------------------------------------------------------------------ pipx
instalar_pipx() {
  if tem pipx; then
    ok "pipx já instalado"
    return
  fi

  passo "instalando o pipx"
  if tem brew; then
    brew install pipx >/dev/null 2>&1 || erro "não consegui instalar o pipx com o Homebrew"
  elif tem apt-get; then
    if ! { sudo apt-get update -qq && sudo apt-get install -y -qq pipx; }; then
      erro "não consegui instalar o pipx com o apt"
    fi
  elif tem dnf; then
    sudo dnf install -y -q pipx || erro "não consegui instalar o pipx com o dnf"
  elif tem pacman; then
    sudo pacman -S --noconfirm --quiet python-pipx || erro "não consegui instalar o pipx com o pacman"
  else
    python3 -m pip install --user -q pipx || erro "não consegui instalar o pipx com o pip"
  fi

  tem pipx || export PATH="$HOME/.local/bin:$PATH"
  tem pipx || erro "instalei o pipx mas ele não está no PATH. Abra um terminal novo e rode de novo."
  ok "pipx instalado"
}

# ------------------------------------------------------------- designsys
# Preferimos o PyPI: é uma versão publicada, não o topo de main. O repositório
# fica como reserva, para o caso de a versão ainda não estar no índice.
instalar_designsys() {
  local acao="instalando" flags=""
  if pipx list --short 2>/dev/null | grep -q '^designsys '; then
    acao="atualizando"
    flags="--force"
  fi

  passo "$acao o designsys a partir do PyPI"
  # shellcheck disable=SC2086 # $flags é vazio ou --force, intencionalmente sem aspas
  if pipx install $flags designsys >/dev/null 2>&1; then
    ok "designsys ${acao%ndo}do"
    pipx ensurepath >/dev/null 2>&1 || true
    return
  fi

  passo "PyPI não respondeu como esperado — usando o repositório"
  # shellcheck disable=SC2086
  pipx install $flags "git+$REPO" >/dev/null 2>&1 \
    || erro "falhou ao instalar. Rode sem o script para ver o motivo: pipx install designsys"
  ok "designsys ${acao%ndo}do a partir do repositório"

  pipx ensurepath >/dev/null 2>&1 || true
}

# ---------------------------------------------------------------- browser
instalar_chromium() {
  passo "baixando o Chromium do Playwright (uma vez só, ~150 MB)"
  local designsys="${PIPX_BIN_DIR:-$HOME/.local/bin}/designsys"
  [ -x "$designsys" ] || designsys="designsys"

  if "$designsys" doctor --fix >/dev/null 2>&1; then
    ok "Chromium pronto"
  else
    # O doctor sai com código 1 enquanto houver pendência; a segunda passada diz
    # se o navegador ficou de fato disponível.
    if "$designsys" doctor 2>/dev/null | grep -q "lançar navegador"; then
      ok "Chromium pronto"
    else
      aviso "não consegui preparar o Chromium automaticamente."
      aviso "rode depois: designsys doctor --fix"
    fi
  fi
}

# ----------------------------------------------------------------- final
final() {
  printf "\n%s  tudo pronto.%s\n\n" "$VERDE" "$FIM"
  printf "  %sexperimente:%s\n" "$CINZA" "$FIM"
  printf "    designsys url stripe.com --pages 3\n"
  printf "    designsys repo .\n"
  printf "    designsys --help\n\n"

  if ! tem designsys; then
    aviso "abra um terminal novo (ou rode: source ~/.zshrc) para o comando ficar disponível."
    printf "\n"
  fi
}

main() {
  banner
  verificar_python
  instalar_pipx
  instalar_designsys
  instalar_chromium
  final
}

main "$@"
