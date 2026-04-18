# =============================================================================
# LocalScript — Makefile (кросс-платформенный)
# =============================================================================
.DEFAULT_GOAL := help
PYTHON        := python3
ifeq ($(OS),Windows_NT)
    PYTHON    := python
endif

MODEL_TAG     := qwen2.5-coder:7b-instruct-q4_K_M

##@ Быстрый старт

.PHONY: help
help: ## Показать все команды
	@awk 'BEGIN {FS = ":.*##"; printf "\n\033[1;36mLocalScript — команды:\033[0m\n\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  \033[32m%-20s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1;33m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)

.PHONY: setup
setup: ## Установить все Python-зависимости
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	@echo "✅ Зависимости установлены"

.PHONY: install-lua
install-lua: ## Установить Lua + luac (для валидатора)
ifeq ($(shell uname -s),Darwin)
	brew install lua
else ifeq ($(shell uname -s),Linux)
	sudo apt update && sudo apt install -y lua5.4
else
	@echo "Windows: установи Lua через WSL или Chocolatey (choco install lua)"
endif

.PHONY: model
model: ## Скачать модель Ollama
	ollama pull $(MODEL_TAG)
	@echo "✅ Модель загружена"

.PHONY: server
server: ## Запустить Ollama сервер (в отдельном терминале)
	ollama serve

.PHONY: run
run: ## Запустить агента (интерактивный режим)
	$(PYTHON) main.py

.PHONY: demo
demo: ## Запустить демо без LLM (быстрая проверка)
	$(PYTHON) demo.py

##@ Запуск одной задачи

.PHONY: task
task: ## Запустить одну задачу: make task TASK="напиши функцию сортировки"
	$(PYTHON) main.py --task "$(TASK)"

##@ Тестирование

.PHONY: test
test: ## Все тесты (без LLM)
	$(PYTHON) tests/test_agents.py

.PHONY: test-lua
test-lua: ## Проверить Lua
	lua -e "print('Lua OK: ' .. _VERSION)"
	luac -v 2>&1 | head -1 || echo "luac не найден"

.PHONY: test-rag
test-rag: ## Тест RAG
	$(PYTHON) -c "from rag.knowledge_base import KnowledgeBase; kb=KnowledgeBase(); print('Найдено сниппетов:', len(kb.search('sort')))"

##@ RAG (база знаний)

.PHONY: rag-list
rag-list: ## Показать все сниппеты
	@ls -1 rag/snippets/*.lua 2>/dev/null || echo "Сниппетов пока нет"

.PHONY: rag-add
rag-add: ## Добавить сниппет: make rag-add TASK="описание" FILE=code.lua
	$(PYTHON) -c "\
from rag.knowledge_base import KnowledgeBase; \
kb = KnowledgeBase(); \
code = open('$(FILE)').read(); \
kb.add_snippet('$(TASK)', code); \
print('✅ Сниппет добавлен')"

##@ Docker

.PHONY: docker-build
docker-build: ## Собрать Docker-образ
	docker compose build

.PHONY: docker-up
docker-up: ## Запустить через Docker
	docker compose up lua-agent

.PHONY: docker-down
docker-down: ## Остановить Docker
	docker compose down

##@ Очистка

.PHONY: clean
clean: ## Очистить временные файлы и кэш
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find /tmp -name "lua_agent_*.lua" -delete 2>/dev/null || true
	@echo "✅ Очищено"

.PHONY: vram
vram: ## Показать использование VRAM (только NVIDIA)
	nvidia-smi --query-gpu=name,memory.used,memory.free,memory.total --format=csv,noheader,nounits || echo "nvidia-smi не найден"