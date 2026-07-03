#!/bin/bash

echo "=== Iniciando o Ritual de Banimento (Sigilo) ==="
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
APP_NAME="sigilo"
ICON_NAME="${APP_NAME}"

DESKTOP_FILE_PATH="${HOME}/.local/share/applications/${APP_NAME}.desktop"
ICON_INSTALL_PATH="${HOME}/.local/share/icons/hicolor/64x64/apps/${ICON_NAME}.png"

echo "[1/3] Quebrando o círculo de proteção (venv)..."
rm -rf "${SCRIPT_DIR}/venv"

echo "[2/3] Apagando o sigilo de invocação (.desktop)..."
rm -f "${DESKTOP_FILE_PATH}"

echo "[3/3] Desconsagrando o ícone..."
rm -f "${ICON_INSTALL_PATH}"

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "${HOME}/.local/share/applications" >/dev/null 2>&1
fi
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache "${HOME}/.local/share/icons/hicolor/" -f -t >/dev/null 2>&1
fi

echo "=== Banimento Concluído ==="
