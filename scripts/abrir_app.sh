#!/usr/bin/env bash
# Sobe a interface Streamlit do Sigilo e abre o navegador.
# Idempotente: derruba a instância anterior pelo PID dono da porta (nunca
# pkill por substring — lição do protocolo-ouroboros) e faz readiness poll.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIZ="$(dirname "${SCRIPT_DIR}")"
cd "${RAIZ}"

PORT="${PORT:-8511}"   # 8501/8590 pertencem ao protocolo-ouroboros
URL="http://localhost:${PORT}"
LOG="/tmp/sigilo_app.log"

derrubar_instancia() {
    local pid
    pid="$(ss -ltnp "sport = :${PORT}" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1 || true)"
    if [ -n "${pid}" ]; then
        echo "Derrubando instância anterior (pid ${pid})..."
        kill "${pid}" 2>/dev/null || true
        sleep 1
    fi
}

abrir_navegador() {
    if command -v google-chrome &> /dev/null; then
        (google-chrome "${URL}" &> /dev/null &)
    elif command -v xdg-open &> /dev/null; then
        (xdg-open "${URL}" &> /dev/null &)
    else
        echo "Nenhum navegador encontrado; acesse manualmente: ${URL}"
    fi
}

derrubar_instancia

echo "Forjando o sigilo em ${URL}..."
# -m streamlit (e não venv/bin/streamlit): imune a shebang quebrado por
# renomeação da pasta do projeto.
setsid venv/bin/python3 -m streamlit run ui/app.py \
    --server.port "${PORT}" --server.address 127.0.0.1 \
    --server.headless true < /dev/null >> "${LOG}" 2>&1 &

for _ in $(seq 1 60); do
    if [ "$(curl -s -o /dev/null -w '%{http_code}' "${URL}" 2>/dev/null || true)" = "200" ]; then
        echo "Interface pronta em ${URL}."
        abrir_navegador
        exit 0
    fi
    sleep 0.5
done

echo "ERRO: a interface não respondeu em 30 s. Últimas linhas de ${LOG}:"
tail -20 "${LOG}"
exit 1
