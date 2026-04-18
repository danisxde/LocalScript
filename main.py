"""
LocalScript — главная точка входа.

Исправлено: после выдачи результата пользователь может вводить уточнения
в рамках той же сессии. Состояние (SessionState) сохраняется между вводами.
"""
from __future__ import annotations
import argparse
import sys
import os
import yaml
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.base import init_llm, LLMConfig
from agents.orchestrator import Orchestrator
from agents.contracts import SessionState, SessionMode

try:
    from pygments import highlight
    from pygments.lexers import LuaLexer
    from pygments.formatters import TerminalFormatter
    _has_pygments = True
except ImportError:
    _has_pygments = False


BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║      LocalScript — локальный генератор Lua-кода          ║
║               Ollama · qwen2.5-coder:7b                  ║
╚══════════════════════════════════════════════════════════╝
"""

SESSION_HINT = """\033[90m  [Подсказка: после получения результата вы можете уточнить/изменить код.
   Например: "добавь проверку на nil", "измени поле на wf.vars.items"
   Чтобы начать новую задачу — введите принципиально другой запрос.
   /new — принудительно начать новую задачу]\033[0m"""


def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    if not os.path.exists(path):
        print(f"[ERROR] Файл конфигурации {path} не найден!")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if "model" not in config:
        print("[ERROR] В config.yaml отсутствует секция 'model'")
        sys.exit(1)

    required_fields = ["host", "port", "name", "temperature", "num_ctx",
                       "num_predict", "num_batch", "num_parallel", "num_gpu",
                       "top_p", "repeat_penalty"]
    for field in required_fields:
        if field not in config["model"]:
            print(f"[ERROR] В config.yaml/model отсутствует поле '{field}'")
            sys.exit(1)
    return config


def init_llm_from_config(config: Dict[str, Any]) -> None:
    model_cfg = config["model"]
    llm_config = LLMConfig.from_dict(model_cfg)
    print("[MAIN] Инициализация LLM-модели...")
    print(f"[MAIN] Модель: {llm_config.model}")
    print(f"[MAIN] GPU: {'все слои' if llm_config.num_gpu == 0 else f'{llm_config.num_gpu} слоев'}")
    print(f"[MAIN] Контекст: {llm_config.num_ctx} токенов")
    print(f"[MAIN] Макс. ответ: {llm_config.num_predict} токенов\n")
    init_llm(llm_config)


def print_code(code: str):
    if _has_pygments:
        print(highlight(code, LuaLexer(), TerminalFormatter()))
    else:
        print(f"\033[92m{code}\033[0m")


def print_validation(history: list[dict]):
    for entry in history:
        icon = "✓" if entry["status"] == "ok" else "✗"
        print(f"  [{icon}] Попытка {entry['attempt']}: {entry['status']}", end="")
        if entry.get("error"):
            print(f" — {entry['error'][:60]}", end="")
        print()
        for check, result in entry.get("checks", {}).items():
            ci = "✓" if "OK" in str(result) else "✗"
            print(f"      {ci} {check}: {result}")


def ask_clarifications(questions: list[str]) -> str:
    print("\n\033[93m[CLARIFIER] Уточните задачу:\033[0m")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. {q}")
    try:
        answer = input("\n\033[96mВаш ответ:\033[0m ").strip()
    except (KeyboardInterrupt, EOFError):
        answer = ""
    return answer


def print_result(state: SessionState, config: dict, is_refinement: bool = False):
    label = "УТОЧНЁННЫЙ РЕЗУЛЬТАТ" if is_refinement else "РЕЗУЛЬТАТ"
    print("\n" + "─" * 60)
    print(f"\033[92m {label} \033[0m")
    print("─" * 60)
    print_code(state.final_code)

    if config.get("output", {}).get("show_validation_details", True):
        print("\n\033[90mВалидация:\033[0m")
        print_validation(state.validation_history)

    if not state.success:
        print("\n\033[93m Код сгенерирован, но валидация не прошла полностью.\033[0m")


def run_interactive(orchestrator: Orchestrator, config: dict):
    print(BANNER)

    last_code = ""
    global_history = []   # история задач за весь сеанс
    max_clarifications = config.get("agent", {}).get("clarification_turns", 2)

    # Состояние текущей сессии (сохраняется между вводами!)
    current_state: Optional[SessionState] = None

    while True:
        # Показываем подсказку если есть результат и можно уточнять
        if current_state and current_state.has_result:
            prompt_prefix = "\033[96mLocalScript [уточнить/новая задача]> \033[0m"
        else:
            prompt_prefix = "\033[96mLocalScript> \033[0m"

        try:
            task = input(prompt_prefix).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nВыход.")
            break

        if not task:
            continue

        # ── Команды ──────────────────────────────────────────────────────
        if task == "/help":
            print("""
Доступные команды:
  /new           — принудительно начать новую задачу (сбросить сессию)
  /save <file>   — сохранить последний код в файл (по умолчанию output.lua)
  /history       — показать историю задач сессии
  /config        — показать текущую конфигурацию
  /rag_stats     — статистика RAG базы знаний
  /rag_clear     — очистить историю RAG
  /rag_search    — поиск в базе знаний
  /help          — показать эту справку
  /quit          — выход

После получения результата можно уточнять код, например:
  > добавь проверку на nil
  > измени поле items на wf.vars.orders
  > теперь верни только первые 5 элементов
""")
            continue

        if task == "/quit":
            break

        if task == "/new":
            current_state = None
            print("\033[93m[SESSION] Сессия сброшена. Введите новую задачу.\033[0m")
            continue

        if task.startswith("/save"):
            parts = task.split(maxsplit=1)
            fname = parts[1] if len(parts) > 1 else "output.lua"
            if last_code:
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(last_code)
                print(f"✓ Сохранено в {fname}")
            else:
                print("Нет кода для сохранения.")
            continue

        if task == "/history":
            for i, h in enumerate(global_history, 1):
                status = "✓" if h.get("success") else "~"
                refinements = h.get("refinements", 0)
                r_label = f" (+{refinements} уточнений)" if refinements else ""
                print(f"  {i}. [{status}] {h['task'][:60]}{r_label}")
            continue

        if task == "/config":
            print("\nТекущая конфигурация:")
            print(f"  Модель: {orchestrator.llm.config.model}")
            print(f"  Temperature: {orchestrator.llm.config.temperature}")
            print(f"  Context: {orchestrator.llm.config.num_ctx}")
            print(f"  Max tokens: {orchestrator.llm.config.num_predict}")
            print(f"  GPU layers: {'all' if orchestrator.llm.config.num_gpu == 0 else orchestrator.llm.config.num_gpu}")
            continue

        if task == "/rag_stats":
            stats = orchestrator.get_rag_stats()
            print("\nRAG Statistics:")
            print(f"  Session messages: {stats.get('session_messages', 0)}")
            print(f"  Knowledge docs: {stats.get('knowledge_documents', 0)}")
            print(f"  Document types: {stats.get('document_types', {})}")
            continue

        if task == "/rag_clear":
            orchestrator.clear_session()
            print("Session history cleared")
            continue

        if task == "/rag_search":
            query = input("Search query: ").strip()
            if query:
                snippets = orchestrator._search_context(query)
                if snippets:
                    print(f"\nFound {len(snippets)} snippets:")
                    for i, snippet in enumerate(snippets[:3], 1):
                        print(f"\n--- Snippet {i} ---")
                        print(snippet[:300] + "..." if len(snippet) > 300 else snippet)
                else:
                    print("No results found")
            continue

        # ── Основной пайплайн ─────────────────────────────────────────────
        user_answers = ""
        clarification_round = 0
        was_refinement = (
            current_state is not None
            and current_state.has_result
        )

        while True:
            current_state = orchestrator.run(
                task=task,
                state=current_state,
                user_answers=user_answers,
            )

            # Агент просит уточнение
            if current_state.needs_clarification and clarification_round < max_clarifications:
                clarification_round += 1
                user_answers = ask_clarifications(current_state.clarification_questions)
                if not user_answers:
                    # Пользователь не ответил — продолжаем без уточнений
                    current_state.needs_clarification = False
                    current_state = orchestrator.run(
                        task=task,
                        state=current_state,
                        user_answers="продолжи без уточнений",
                    )
                    break
                # Повторяем с ответами пользователя
                continue
            else:
                break

        # ── Вывод результата ─────────────────────────────────────────────
        if current_state.final_code:
            print_result(current_state, config, is_refinement=was_refinement)
            last_code = current_state.final_code

            # Обновляем историю
            if was_refinement and global_history:
                global_history[-1]["refinements"] = global_history[-1].get("refinements", 0) + 1
                global_history[-1]["success"] = current_state.success
            else:
                global_history.append({
                    "task": task,
                    "code": last_code,
                    "success": current_state.success,
                    "iterations": current_state.iteration,
                    "refinements": 0,
                })

            # Показываем подсказку о возможности уточнения
            print(SESSION_HINT)

        else:
            print("\033[91m[ERROR] Не удалось сгенерировать код.\033[0m")
            if not orchestrator.check_server():
                break


def main():
    parser = argparse.ArgumentParser(
        description="LocalScript - локальная генерация Lua кода через Ollama"
    )
    parser.add_argument("--task", type=str, help="Разовая задача (без интерактивного режима)")
    parser.add_argument("--config", type=str, default="config.yaml", help="Путь к config.yaml")
    parser.add_argument("--output", type=str, help="Сохранить результат в файл")
    parser.add_argument("--no-verbose", action="store_true", help="Отключить подробный вывод")
    parser.add_argument("--show-config", action="store_true",
                        help="Показать текущую конфигурацию и выйти")
    args = parser.parse_args()

    config = load_config(args.config)
    verbose = not args.no_verbose

    if args.show_config:
        print("\nТекущая конфигурация:")
        print(yaml.dump(config, default_flow_style=False, allow_unicode=True))
        sys.exit(0)

    try:
        init_llm_from_config(config)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    orch = Orchestrator(config=config, verbose=verbose)

    if args.task:
        # Одиночный запрос
        state = orch.run(args.task)
        if state.needs_clarification:
            print("\n[CLARIFIER] Требуются уточнения:")
            for q in state.clarification_questions:
                print(f"  - {q}")
            answers = input("\nВаш ответ: ").strip()
            if answers:
                state = orch.run(args.task, state=state, user_answers=answers)

        if state.final_code:
            print("\n" + "=" * 60)
            print_code(state.final_code)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(state.final_code)
                print(f"\n✓ Сохранено в {args.output}")
            sys.exit(0 if state.success else 1)
        else:
            print("[ERROR] Не удалось сгенерировать код")
            sys.exit(1)
    else:
        run_interactive(orch, config)


if __name__ == "__main__":
    main()
