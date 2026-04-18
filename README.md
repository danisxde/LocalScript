# LocalScript — локальная агентская система генерации Lua-кода

**Полностью оффлайн агент** для генерации и валидации Lua-скриптов под LowCode-платформу.

Использует:
- **Ollama** + `qwen2.5-coder:7b`
- Python-агенты (Clarifier → RAG → Planner → Generator → Validator)
- Реальную валидацию через `luac` + sandbox

---

## Требования

| Компонент | Версия | Назначение |
|---|---|---|
| Python | 3.10+ | среда выполнения агентов |
| Ollama | последняя | локальный LLM-сервер |
| Lua | 5.4 | sandbox + синтаксическая проверка |
| NVIDIA GPU | 8 GB VRAM | выполнение модели |

---

## Шаг 1 — Установить Ollama

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**
```bash
# Скачать установщик .pkg с https://ollama.com/download
# После установки Ollama появится в строке меню (иконка ламы)
```

**Windows (два варианта):**

*Вариант А — нативно через WSL2 (рекомендуется):*
```powershell
# 1. Установить WSL2 (если ещё нет) — в PowerShell от администратора:
wsl --install

# 2. Перезагрузить компьютер, затем в терминале WSL (Ubuntu):
curl -fsSL https://ollama.com/install.sh | sh
```

*Вариант Б — нативный Windows-установщик:*
```
1. Скачать OllamaSetup.exe с https://ollama.com/download
2. Запустить установщик — Ollama появится в системном трее
3. Все команды ollama выполнять в PowerShell или cmd
```

> **Lua на Windows (для валидатора):**
> ```powershell
> # Через winget:
> winget install DEVCOM.Lua
> # Или скачать бинарник с https://luabinaries.sourceforge.net/
> # (lua54_Win64_bin.zip) и добавить в PATH
> ```
> Без Lua синтаксическая проверка и sandbox будут пропущены —
> агент продолжит работу, но без этих уровней валидации.

> **Python на Windows:**
> ```powershell
> winget install Python.Python.3.12
> # или скачать с https://www.python.org/downloads/
> # При установке отметить "Add Python to PATH"
> ```

Проверить Ollama:
```bash
ollama --version
```

---

## Шаг 2 — Скачать модель

```bash
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
```

**Почему эта модель:**
- Квантизация Q4_K_M → веса ~4.1 GB в VRAM
- KV-кэш при `num_ctx=4096` → ~0.9 GB
- Итого пиковое потребление: **~5.0–5.5 GB VRAM** (в рамках лимита 8 GB)
- Специализирована на генерации кода, поддерживает Lua

Проверить загрузку:
```bash
ollama list
# должна быть строка: qwen2.5-coder:7b-instruct-q4_K_M
```

---

## Шаг 3 — Установить Python-зависимости

```bash
pip install -r requirements.txt
```

Зависимости минимальны и зафиксированы:

```
requests==2.32.3    # HTTP к Ollama
pyyaml==6.0.2       # чтение config.yaml
pygments==2.18.0    # подсветка Lua (опционально)
rich==13.9.4        # форматированный вывод (опционально)
chromadb>=0.5.0     # векторное хранилище
```

---

## Шаг 4 — Установить Lua

```bash
# Ubuntu / Debian
sudo apt install lua5.4

# macOS
brew install lua

# Windows — в PowerShell:
winget install DEVCOM.Lua
# или скачать lua54_Win64_bin.zip с https://luabinaries.sourceforge.net/
# и распаковать lua54.exe + luac54.exe в папку из PATH

# Проверка
lua -e "print(_VERSION)"   # --> Lua 5.4
luac -v                    # --> Lua 5.4.x
```

Lua нужна для двух вещей:
- `luac -p` — синтаксическая проверка сгенерированного кода
- `lua` — sandbox-запуск кода с таймаутом

---

## Шаг 5 — Запуск

**Linux / macOS:**

**Терминал 1** (держим открытым):
```bash
ollama serve
```

**Терминал 2**:
```bash
python main.py
```

**Windows (нативно, PowerShell):**
```powershell
# Терминал 1 — Ollama обычно уже запущена как служба после установки.
# Если нет — запустить вручную:
ollama serve

# Терминал 2:
python main.py
```

**Windows (через WSL2):**
```bash
# Всё внутри WSL-терминала (Ubuntu):
ollama serve &
python3 main.py
```

**Или через Makefile (Linux / macOS / WSL):**
```bash
make setup    # установить Python-зависимости
make model    # ollama pull qwen2.5-coder:7b-instruct-q4_K_M
make server   # в отдельном терминале
make run      # запустить агента

## Параметры модели

```bash
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
```

В `config.yaml` зафиксированы параметры запуска:

```yaml
model:
  name: "qwen2.5-coder:7b-instruct-q4_K_M"
  num_ctx: 4096       # размер контекста
  num_predict: 256    # макс. токенов в ответе
  num_batch: 1        # batch size
  num_parallel: 1     # параллельных запросов
  num_gpu: -1         # все слои на GPU (без CPU offload)
```

---

## Архитектура пайплайна

```
Пользователь вводит задачу (RU или EN)
          │
          ▼
    ┌─ CLARIFIER ───────────────────────────────────────────┐
    │  Анализирует задачу через LLM (JSON-ответ).           │
    │  Если задача неоднозначна — задаёт 1-2 вопроса.       │
    │  Пользователь отвечает → цикл повторяется.            │
    │  CONTRACT: ClarifierInput → ClarifierOutput           │
    └───────────────────────────────────────────────────────┘
          │ задача понятна
          ▼
    ┌─ RAG / KNOWLEDGE ─────────────────────────────────────┐
    │  Офлайн TF-IDF поиск по rag/snippets/*.lua            │
    │  Возвращает top-3 релевантных шаблона.                │
    │  Никаких внешних запросов, никаких нейросетевых моделей│
    └───────────────────────────────────────────────────────┘
          │
          ▼
    ┌─ PLANNER ─────────────────────────────────────────────┐
    │  Декомпозирует задачу на 2-5 шагов (chain-of-thought) │
    │  CONTRACT: PlannerInput → PlannerOutput               │
    └───────────────────────────────────────────────────────┘
          │
          ▼
    ┌─ GENERATOR ───────────────────────────────────────────┐
    │  Три режима (выбирается автоматически):               │
    │    • generate_fresh — генерация с нуля                │
    │    • refine — изменение по запросу пользователя       │
    │    • repair — исправление ошибки валидации            │
    │  CONTRACT: GeneratorInput → GeneratorOutput           │
    └───────────────────────────────────────────────────────┘
          │
          ▼
    ┌─ VALIDATOR (3 уровня) ────────────────────────────────┐
    │  1. luac -p         → синтаксический анализ           │
    │  2. lua + subprocess → sandbox-запуск с таймаутом     │
    │  3. LLM self-review → проверка логики (1 вызов LLM)   │
    │  CONTRACT: ValidatorInput → ValidatorOutput           │
    └───────────────────────────────────────────────────────┘
          │ OK → вывод результата + ожидание уточнений
          │ FAIL ↓
    ┌─ REPAIR (автоматически через Generator.repair) ───────┐
    │  Передаёт ошибку в Generator._repair().               │
    │  Повторяет до max_retries раз.                        │
    └───────────────────────────────────────────────────────┘
          │
          ▼
    ┌─ SESSION MANAGER (в Orchestrator) ────────────────────┐
    │  Хранит SessionState между вводами пользователя.      │
    │  Режимы: NEW_TASK | REFINEMENT | CLARIFYING           │
    │  Уточнения → Generator._refine() (берёт prior_code)  │
    └───────────────────────────────────────────────────────┘
```

Все LLM-вызовы идут через `http://127.0.0.1:11434` (Ollama). Внешних запросов нет.

---

## Контракты агентов (`agents/contracts.py`)

Каждый агент имеет формальный Input/Output контракт с инвариантами и методом `.validate()`.

### ClarifierInput / ClarifierOutput
```python
ClarifierInput(task: str, context: str = "", prior_code: str = "", refinement_mode: bool = False)
# Инварианты: task не пустой
# Метод: full_prompt — собирает полный контекст для LLM

ClarifierOutput(ready: bool, summary: str = "", questions: list[str] = [])
# Инварианты: ready=True → summary непустой
#             ready=False → 1-3 вопроса в questions
```

### PlannerInput / PlannerOutput
```python
PlannerInput(task_summary: str, context_snippets: list[str] = [])
# Инварианты: task_summary непустой

PlannerOutput(plan_text: str, steps: list[str] = [])
# Инварианты: не более 6 шагов
```

### GeneratorInput / GeneratorOutput
```python
GeneratorInput(
    task_summary: str,
    plan: str = "",
    context_snippets: list[str] = [],
    iteration: int = 1,
    previous_error: Optional[str] = None,
    prior_code: str = "",           # для repair/refine
    refinement_request: str = "",   # что изменить
)
# Свойства: is_repair, is_refinement
# Инварианты: iteration>=1; если iteration>1 — нужен prior_code или previous_error

GeneratorOutput(code: str, raw_response: str, iteration: int = 1)
# Инварианты: code непустой и содержит return
```

### ValidatorInput / ValidatorOutput
```python
ValidatorInput(code: str, task_summary: str = "")
# Инварианты: code непустой

ValidatorOutput(status: ValidationStatus, ok: bool, error_message: Optional[str], checks: dict)
# Инварианты: ok=True → status=OK; ok=False → error_message непустой
```

### SessionState (сессия пользователя)
```python
SessionState(
    original_task: str,
    task_summary: str,
    final_code: str,
    has_result: bool,          # True = пользователю уже показан результат
    mode: SessionMode,         # NEW_TASK | REFINEMENT | CLARIFYING
    refinement_history: list,  # история уточнений в рамках задачи
)
# Методы:
#   .start_refinement(request) — переключить в режим уточнения
#   .reset_for_new_task(task)  — сбросить для новой задачи
```

---

## Поддержка сессий — уточнение без начала новой задачи

После получения результата пользователь может уточнять код в той же сессии:

```
LocalScript> найди максимальный элемент в массиве wf.vars.prices

[...генерация, валидация...]
──────────────────────────────────────────────
 РЕЗУЛЬТАТ
──────────────────────────────────────────────
local max_val = wf.vars.prices[1]
for i = 2, #wf.vars.prices do
  if wf.vars.prices[i] > max_val then
    max_val = wf.vars.prices[i]
  end
end
return max_val

  [Подсказка: вы можете уточнить/изменить код или начать новую задачу]

LocalScript [уточнить/новая задача]> добавь проверку что массив не пустой
[SESSION] Режим уточнения: "добавь проверку что массив не пустой"

[...refine пайплайн — берёт предыдущий код как основу...]
──────────────────────────────────────────────
 УТОЧНЁННЫЙ РЕЗУЛЬТАТ
──────────────────────────────────────────────
if #wf.vars.prices == 0 then return nil end
local max_val = wf.vars.prices[1]
for i = 2, #wf.vars.prices do
  if wf.vars.prices[i] > max_val then
    max_val = wf.vars.prices[i]
  end
end
return max_val
```

**Как определяется режим (эвристика):**
- Ключевые слова: "добавь", "измени", "исправь", "убери", "теперь", "add", "change", "fix"...
- Короткий ввод (≤8 слов) после результата → уточнение
- `/new` — принудительный сброс сессии

---

## Ограничения платформы LowCode (Lua 5.5)

Кодогенератор соблюдает следующие ограничения (прописаны в промптах):

- Переменные только через `wf.vars.<поле>` и `wf.initVariables.<поле>`
- Массивы: `_utils.array.new()` для создания, `_utils.array.markAsArray(arr)` для пометки
- Скрипт **обязан** заканчиваться `return <значение>`
- Разрешены: `if/then/else`, `while/do/end`, `for/do/end`, `repeat/until`
- Разрешены типы: nil, boolean, number, string, array, table, function
- Запрещено: io, os, require, loadfile, dofile, coroutine, pcall, xpcall
- Нет комментариев `--` (ломают JSON-обёртку)
- Нет JsonPath выражений (только прямое обращение к полям)

---

## Команды REPL

| Команда | Действие |
|---|---|
| `<задача>` | Сгенерировать Lua-код |
| `<уточнение>` | Изменить/улучшить последний код (в рамках сессии) |
| `/new` | Принудительно начать новую задачу |
| `/save [file]` | Сохранить последний код в файл (по умолчанию `output.lua`) |
| `/history` | История задач текущей сессии (с числом уточнений) |
| `/config` | Показать параметры модели |
| `/rag_stats` | Статистика базы знаний |
| `/rag_search` | Поиск по базе знаний |
| `/rag_clear` | Очистить историю сессии RAG |
| `/help` | Справка |
| `/quit` | Выход |

---

## Структура проекта

```
agent3/
├── main.py                    # REPL, точка входа, управление сессией
├── config.yaml                # параметры модели, агентов, валидатора
├── requirements.txt           # зафиксированные зависимости
├── Makefile
├── Dockerfile
├── docker-compose.yml
│
├── agents/
│   ├── contracts.py           # контракты всех агентов
│   ├── base.py                # LLMClient (Ollama /api/chat), BaseAgent
│   ├── clarifier.py           # уточняющие вопросы, JSON-ответ
│   ├── planner.py             # декомпозиция задачи
│   ├── generator.py           # генерация / refine / repair
│   ├── validator.py           # luac + sandbox + LLM self-review
│   └── orchestrator.py        # state machine, управление SessionState
│
├── rag/
│   ├── knowledge_base.py      # LocalTFIDF, KnowledgeBase, add_snippet
│   └── snippets/              # Lua-шаблоны (поставляются в репозитории)
│       ├── lc_array_new.lua
│       ├── lc_build_object.lua
│       ├── lc_conditional.lua
│       ├── lc_count_filter.lua
│       ├── lc_find_by_field.lua
│       ├── lc_initvars.lua
│       ├── lc_last_element.lua
│       ├── lc_mark_as_array.lua
│       ├── lc_number_ops.lua
│       ├── lc_string_concat.lua
│       ├── lc_string_ops.lua
│       ├── lc_sum_field.lua
│       ├── lc_while_loop.lua
│       └── ... (общие Lua паттерны)
│
├── prompts/
│   ├── clarifier.txt          # системный промпт кларификатора
│   ├── generator.txt          # правила генерации + шаблоны
│   ├── validator.txt          # критерии проверки
│   └── repair.txt             # инструкции для исправления
│
└── tests/
    └── test_agents.py         # тесты без LLM
```

---

## База знаний (RAG)

RAG реализован через офлайн TF-IDF поверх `.lua` файлов — без нейросетевых embedding-моделей:

1. При старте загружаются все `rag/snippets/*.lua`
2. Строится TF-IDF индекс в памяти
3. Запрос пользователя векторизуется тем же методом
4. Возвращаются top-k по косинусному сходству

Никаких загрузок, никаких GPU, никаких внешних зависимостей.

---

## Тесты

```bash
make test
# или
python -m pytest tests/ -v
```

Тесты не требуют запущенного LLM. Покрывают:
- Синтаксический анализ через `luac -p`
- Sandbox-выполнение Lua-кода
- RAG TF-IDF поиск
- Парсинг JSON-ответов агентов
- Валидацию контрактов

---

## Устранение неполадок

**Ollama не запускается:**
```bash
ollama serve
# Проверить: curl http://localhost:11434/api/tags
```

**VRAM недостаточно:**
```bash
nvidia-smi
ollama stop <другая-модель>
```

**luac / lua не найдены:**
```bash
sudo apt install lua5.4   # Ubuntu
brew install lua          # macOS
```

**Модуль RAG не найден:**
```bash
cd agent3
python -c "from rag.knowledge_base import KnowledgeBase; print('OK')"
```
