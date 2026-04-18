# LocalScript — Docker образ
# Использует Ollama как внешний LLM-сервер (запускается отдельно).
# Сам контейнер содержит только Python-агентов + Lua для валидации.

FROM ubuntu:24.04

LABEL description="LocalScript - локальная агентская система генерации Lua-кода"
LABEL model="qwen2.5-coder:7b-instruct-q4_K_M via Ollama"

RUN apt-get update && apt-get install -y \
    python3.12 \
    python3-pip \
    lua5.4 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# luac нужен для синтаксической проверки
RUN lua5.4 -e "print('Lua OK: ' .. _VERSION)"

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt

COPY . .

# Проверяем что Python-зависимости установлены корректно
RUN python3 -c "import requests, yaml; print('Python deps OK')"

# Проверяем что тесты проходят (без LLM)
RUN python3 tests/test_agents.py

EXPOSE 11434

CMD ["python3", "main.py"]
