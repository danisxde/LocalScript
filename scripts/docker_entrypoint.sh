#!/usr/bin/env bash
# Docker entrypoint: запускает llama-server + агента

set -e

MODEL_PATH="${MODEL_PATH:-/app/models/model.gguf}"
LLAMA_HOST="${LLAMA_HOST:-127.0.0.1}"
LLAMA_PORT="${LLAMA_PORT:-8080}"

# Проверяем наличие модели
if [ ! -f "$MODEL_PATH" ]; then
    echo "═══════════════════════════════════════════════════════"
    echo " ОШИБКА: Модель не найдена в $MODEL_PATH"
    echo ""
    echo " Примонтируйте GGUF-файл при запуске контейнера:"
    echo "   docker run -v /path/to/model.gguf:/app/models/model.gguf lua-agent"
    echo ""
    echo " Или скачайте внутри контейнера:"
    echo "   python3 scripts/download_model.py qwen2.5-coder-3b"
    echo "═══════════════════════════════════════════════════════"
    exit 1
fi

# Запуск llama-server в фоне
echo "[*] Запускаю llama-server..."
GPU_ARGS=""
if [ "${USE_GPU:-0}" = "1" ]; then
    GPU_ARGS="-ngl 99"
fi

llama-server \
    -m "$MODEL_PATH" \
    --host "$LLAMA_HOST" \
    --port "$LLAMA_PORT" \
    --ctx-size 8192 \
    --chat-template chatml \
    --log-disable \
    $GPU_ARGS &

LLAMA_PID=$!

# Ждём готовности сервера
echo "[*] Жду готовности сервера..."
for i in $(seq 1 30); do
    if curl -sf "http://$LLAMA_HOST:$LLAMA_PORT/health" > /dev/null 2>&1; then
        echo "[✓] Сервер готов!"
        break
    fi
    sleep 2
    if [ $i -eq 30 ]; then
        echo "[✗] Сервер не запустился за 60 секунд"
        exit 1
    fi
done

# Запуск агента
if [ $# -gt 0 ]; then
    # Передали аргументы — выполняем как команду
    exec python3 main.py "$@"
else
    # Интерактивный режим
    exec python3 main.py
fi
