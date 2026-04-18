#!/usr/bin/env bash
# Вспомогательный скрипт: запуск Ollama и проверка модели.
# Использование: bash scripts/start_server.sh

set -e

MODEL="qwen2.5-coder:7b-instruct-q4_K_M"

echo "=== LuaAgent — проверка Ollama ==="

# 1. Проверяем установку Ollama
if ! command -v ollama &>/dev/null; then
    echo "ERROR: ollama не установлена."
    echo "Установить: curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

echo "✓ ollama найдена: $(ollama --version)"

# 2. Проверяем работающий сервер
if curl -sf http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama сервер уже запущен"
else
    echo "Запускаю ollama serve в фоне..."
    ollama serve &
    OLLAMA_PID=$!
    echo "  PID: $OLLAMA_PID"
    # Ждём старта
    for i in $(seq 1 15); do
        sleep 1
        if curl -sf http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
            echo "✓ Ollama запущена"
            break
        fi
        if [ $i -eq 15 ]; then
            echo "ERROR: Ollama не запустилась за 15 секунд"
            exit 1
        fi
    done
fi

# 3. Проверяем модель
MODELS=$(curl -sf http://127.0.0.1:11434/api/tags | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print(' '.join(m['name'] for m in d.get('models',[])))")

echo "Загруженные модели: ${MODELS:-'(нет)'}"

if echo "$MODELS" | grep -q "qwen2.5-coder"; then
    echo "✓ Модель $MODEL готова"
else
    echo "Модель не найдена. Скачиваю..."
    ollama pull "$MODEL"
    echo "✓ Модель загружена"
fi

echo ""
echo "=== Готово. Запустите агента: ==="
echo "  python main.py"
echo "  # или: make run"
