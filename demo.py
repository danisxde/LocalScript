#!/usr/bin/env python3
"""
demo.py — демонстрация полного pipeline без запущенного LLM/Ollama.

Generator и Clarifier эмулируются заготовленными ответами.
Validator (luac + lua sandbox) и RAG — реальные.

Запуск: python demo.py
"""
from __future__ import annotations
import sys, os, subprocess, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

C = {"reset":"\033[0m","bold":"\033[1m","cyan":"\033[96m",
     "green":"\033[92m","yellow":"\033[93m","red":"\033[91m","gray":"\033[90m"}

def c(color, text): return f"{C[color]}{text}{C['reset']}"
def log(tag, msg, color="cyan"): print(f"{c(color, f'[{tag}]')} {msg}")
def hr(): print(c("gray", "─" * 64))


DEMOS = [
    {
        "task": "напиши функцию бинарного поиска в отсортированном массиве чисел",
        "clarifier_ready": True,
        "summary": "binary_search(arr, target) — итеративный поиск, возвращает индекс или nil",
        "plan": ["1. lo=1, hi=#arr", "2. mid = floor((lo+hi)/2)", "3. сравниваем arr[mid] с target"],
        "code": """\
local function binary_search(arr, target)
    local lo, hi = 1, #arr
    while lo <= hi do
        local mid = math.floor((lo + hi) / 2)
        if arr[mid] == target then
            return mid
        elseif arr[mid] < target then
            lo = mid + 1
        else
            hi = mid - 1
        end
    end
    return nil
end
-- Пример: binary_search({1,3,5,7,9}, 5) --> 3
-- Пример: binary_search({1,3,5,7,9}, 6) --> nil
print(binary_search({1,3,5,7,9}, 5))
print(tostring(binary_search({1,3,5,7,9}, 6)))
""",
    },
    {
        "task": "разбить строку по разделителю",
        "clarifier_ready": False,
        "clarifier_questions": [
            "Разделитель — одиночный символ или произвольная строка?",
            "Нужно обрезать пробелы у каждой части?"
        ],
        "clarifier_answers": "одиночный символ, пробелы обрезать",
        "summary": "split(str, sep) — разбивает строку по символу, trim пробелов",
        "plan": ["1. gmatch по ([^sep]+)", "2. trim каждой части", "3. вернуть массив"],
        "code": """\
local function split(str, sep)
    if not str or str == "" then return {} end
    local result = {}
    for part in str:gmatch("([^" .. sep .. "]+)") do
        result[#result + 1] = part:match("^%s*(.-)%s*$")
    end
    return result
end
-- Пример:
local parts = split("alpha, beta, gamma", ",")
for i, v in ipairs(parts) do print(i, v) end
""",
    },
    {
        "task": "класс Animal с наследованием Dog через metatables",
        "clarifier_ready": True,
        "summary": "Animal.new(name,sound) + Animal:speak(); Dog наследует Animal, добавляет Dog:fetch(item)",
        "plan": ["1. Animal={} с __index", "2. Animal.new + speak()", "3. Dog через setmetatable"],
        "code": """\
local Animal = {}
Animal.__index = Animal

function Animal.new(name, sound)
    return setmetatable({name=name, sound=sound}, Animal)
end
function Animal:speak()
    return self.name .. " says " .. self.sound
end

local Dog = setmetatable({}, {__index = Animal})
Dog.__index = Dog

function Dog.new(name)
    return setmetatable(Animal.new(name, "Woof"), Dog)
end
function Dog:fetch(item)
    return self.name .. " fetches " .. item
end

local d = Dog.new("Rex")
print(d:speak())
print(d:fetch("ball"))
""",
    },
]


def run_lua(code: str, timeout: int = 4) -> tuple[bool | None, str, str]:
    with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False, encoding="utf-8") as f:
        f.write(code); tmp = f.name
    try:
        r = subprocess.run(["lua", tmp], capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return None, "", "lua not installed"
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    finally:
        os.unlink(tmp)


def run_luac(code: str) -> tuple[bool | None, str]:
    with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False, encoding="utf-8") as f:
        f.write(code); tmp = f.name
    try:
        r = subprocess.run(["luac", "-p", tmp], capture_output=True, text=True, timeout=5)
        return r.returncode == 0, r.stderr.replace(tmp, "<code>").strip()
    except FileNotFoundError:
        return None, "luac not installed"
    finally:
        os.unlink(tmp)


def run_demo(demo: dict, idx: int, total: int):
    print()
    hr()
    print(c("bold", f"  ДЕМО {idx}/{total}: {demo['task']}"))
    hr()
    time.sleep(0.3)

    # ── CLARIFIER ─────────────────────────────────────────────────────────
    log("CLARIFIER", "Анализирую задачу...")
    time.sleep(0.4)

    if not demo["clarifier_ready"]:
        log("CLARIFIER", "Нужны уточнения:", "yellow")
        for i, q in enumerate(demo["clarifier_questions"], 1):
            print(f"           {i}. {q}")
        print(f"\n  {c('gray', '[USER]')} {demo['clarifier_answers']}")
        time.sleep(0.3)

    log("CLARIFIER", demo["summary"], "green")
    time.sleep(0.2)

    # ── RAG (реальный) ────────────────────────────────────────────────────
    log("RAG", "Ищу в локальных сниппетах (офлайн TF-IDF)...", "cyan")
    from rag.knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    snippets = kb.search(demo["task"], top_k=2)
    if snippets:
        log("RAG", f"Найдено {len(snippets)} релевантных шаблонов", "green")
        print(f"  {c('gray', snippets[0].split(chr(10))[0][:70])}")
    else:
        log("RAG", "Шаблонов не найдено, генерирую с нуля", "yellow")
    time.sleep(0.2)

    # ── PLANNER ───────────────────────────────────────────────────────────
    log("PLANNER", "План:", "cyan")
    for step in demo["plan"]:
        print(f"           {c('gray', step)}")
    time.sleep(0.3)

    # ── GENERATOR (эмуляция) ──────────────────────────────────────────────
    log("GENERATOR", "Генерирую Lua-код... [эмуляция — в реальности: Ollama qwen2.5-coder:7b]", "cyan")
    time.sleep(0.5)

    # ── VALIDATOR (реальный) ──────────────────────────────────────────────
    log("VALIDATOR", "Синтаксическая проверка (luac -p)...", "cyan")
    syntax_ok, syntax_err = run_luac(demo["code"])
    if syntax_ok is None:
        log("VALIDATOR", "⚠ luac не найден, пропускаю", "yellow")
    elif syntax_ok:
        log("VALIDATOR", "✓ Синтаксис OK", "green")
    else:
        log("VALIDATOR", f"✗ Синтаксис: {syntax_err}", "red")

    log("VALIDATOR", "Sandbox-выполнение (subprocess + timeout=4s)...", "cyan")
    lua_ok, lua_out, lua_err = run_lua(demo["code"])
    if lua_ok is None:
        log("VALIDATOR", "⚠ lua не найдена, пропускаю sandbox", "yellow")
    elif lua_ok:
        log("VALIDATOR", "✓ Sandbox OK", "green")
        if lua_out:
            print(f"           stdout: {c('gray', lua_out[:100])}")
    else:
        log("VALIDATOR", f"✗ Sandbox: {lua_err[:80]}", "red")

    log("VALIDATOR", "LLM self-review: [эмуляция → OK]", "green")

    # ── РЕЗУЛЬТАТ ─────────────────────────────────────────────────────────
    print()
    print(c("bold", "── РЕЗУЛЬТАТ " + "─" * 50))
    try:
        from pygments import highlight
        from pygments.lexers import LuaLexer
        from pygments.formatters import TerminalFormatter
        print(highlight(demo["code"], LuaLexer(), TerminalFormatter()))
    except ImportError:
        print(c("green", demo["code"]))
    lines = demo["code"].count("\n")
    print(c("gray", f"  {lines} строк · валидация: luac={syntax_ok} lua={lua_ok} · итераций: 1"))


def main():
    print(c("bold", "\n╔══════════════════════════════════════════════════════════╗"))
    print(c("bold",   "║    LuaAgent DEMO — pipeline без Ollama                   ║"))
    print(c("bold",   "║    Clarifier→RAG→Planner→Generator(mock)→Validator(real) ║"))
    print(c("bold",   "╚══════════════════════════════════════════════════════════╝"))
    print(c("gray", "\nRAG и Validator работают реально. Generator эмулируется."))
    print(c("gray", "Для полного запуска: ollama serve && python main.py\n"))

    input(c("yellow", "Enter для начала..."))

    for i, demo in enumerate(DEMOS, 1):
        run_demo(demo, i, len(DEMOS))
        if i < len(DEMOS):
            input(c("yellow", "\n  [Enter] — следующий пример..."))

    print()
    hr()
    print(c("green", "  Демо завершено!"))
    print(f"  Полный запуск: {c('cyan', 'bash scripts/start_server.sh && python main.py')}")
    hr()

if __name__ == "__main__":
    main()
