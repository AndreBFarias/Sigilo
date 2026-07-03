#!/bin/bash

echo "=== Iniciando o Ritual de Instalação (Sigilo) ==="
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
APP_NAME="sigilo"
APP_DISPLAY_NAME="Sigilo"
ICON_NAME="${APP_NAME}"
ICON_SOURCE_PATH="${SCRIPT_DIR}/assets/icon.png"

DESKTOP_ENTRY_DIR_USER="${HOME}/.local/share/applications"
ICON_INSTALL_SIZE_DIR_USER="${HOME}/.local/share/icons/hicolor/64x64/apps"

mkdir -p "${DESKTOP_ENTRY_DIR_USER}"
mkdir -p "${ICON_INSTALL_SIZE_DIR_USER}"
DESKTOP_FILE_PATH="${DESKTOP_ENTRY_DIR_USER}/${APP_NAME}.desktop"
ICON_INSTALL_PATH="${ICON_INSTALL_SIZE_DIR_USER}/${ICON_NAME}.png"

echo "[1/5] Atualizando selos arcanos (apt update)..."
sudo apt update || { echo "ERRO: Falha ao atualizar repositórios apt."; exit 1; }

echo "[2/5] Invocando dependências (Python, LibreOffice)..."
sudo apt install -y python3-venv desktop-file-utils libreoffice-writer \
    || { echo "ERRO: Falha ao instalar dependências do sistema."; exit 1; }

echo "[3/5] Desenhando círculo de proteção (venv)..."
if [ -d "${SCRIPT_DIR}/venv" ]; then
    echo "Removendo venv antigo..."
    rm -rf "${SCRIPT_DIR}/venv"
fi
# /usr/bin/python3 explícito: garante o Python do sistema mesmo com pyenv ativo.
/usr/bin/python3 -m venv "${SCRIPT_DIR}/venv" \
    || { echo "ERRO: Falha ao criar ambiente virtual."; exit 1; }

echo "[4/5] Instalando pacotes Python no venv..."
if [ ! -f "${SCRIPT_DIR}/requirements.txt" ]; then
    echo "ERRO: requirements.txt não encontrado em ${SCRIPT_DIR}!"
    exit 1
fi
# python3 -m pip (e não venv/bin/pip): imune a shebang quebrado se a pasta
# do projeto for renomeada — foi exatamente o que aconteceu em 02/07/2026.
"${SCRIPT_DIR}/venv/bin/python3" -m pip install --upgrade pip || echo "Aviso: Falha ao atualizar pip."
"${SCRIPT_DIR}/venv/bin/python3" -m pip install -r "${SCRIPT_DIR}/requirements.txt" \
    || { echo "ERRO: Falha ao instalar pacotes Python."; exit 1; }

echo "[5/5] Consagrando o ícone e forjando o sigilo..."
ICON_ENTRY="document-edit-sign"
if [ -f "${ICON_SOURCE_PATH}" ]; then
    if command -v convert &> /dev/null; then
        convert "${ICON_SOURCE_PATH}" -resize 64x64 "${ICON_INSTALL_PATH}" \
            && ICON_ENTRY="${ICON_NAME}"
    else
        cp "${ICON_SOURCE_PATH}" "${ICON_INSTALL_PATH}" && ICON_ENTRY="${ICON_NAME}"
    fi
    if command -v gtk-update-icon-cache &> /dev/null; then
        gtk-update-icon-cache "${HOME}/.local/share/icons/hicolor/" -f -t
    fi
else
    echo "Aviso: assets/icon.png ausente; usando ícone do tema (${ICON_ENTRY})."
fi

# Sem MimeType/%f: abrir um arquivo "com o Sigilo" pelo gerenciador assinaria
# em silêncio, sem janela de feedback. O menu abre sempre a interface (run.sh).
EXEC_COMMAND="\"${SCRIPT_DIR}/run.sh\""
CATEGORIES="Office;"

printf "[Desktop Entry]\nVersion=1.0\nName=%s\nComment=Sela PDF/DOCX/imagens com carimbo de assinatura e timestamp\nExec=%s\nIcon=%s\nTerminal=false\nType=Application\nCategories=%s\nStartupNotify=true\nPath=%s\n" \
    "${APP_DISPLAY_NAME}" \
    "${EXEC_COMMAND}" \
    "${ICON_ENTRY}" \
    "${CATEGORIES}" \
    "${SCRIPT_DIR}" \
    > "${DESKTOP_FILE_PATH}" || { echo "ERRO: Falha ao criar arquivo .desktop."; exit 1; }

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "${DESKTOP_ENTRY_DIR_USER}"
fi

echo "=== Ritual Concluído ==="
echo "Você agora pode encontrar '${APP_DISPLAY_NAME}' no seu menu de aplicativos."
echo "Uso: ./run.sh (interface no navegador) | ./run.sh arquivo.pdf (linha de comando)"
