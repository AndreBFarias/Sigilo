#!/usr/bin/env bash
cd "$(dirname "$(readlink -f "$0")")"
if [ $# -gt 0 ]; then
    exec venv/bin/python3 main.py "$@"   # CLI: ./run.sh arquivo.pdf
fi
exec bash scripts/abrir_app.sh            # sem argumento: interface no navegador
