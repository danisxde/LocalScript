"""
ORCHESTRATOR — управляет пайплайном агентов.

Ключевые изменения:
  1. Поддержка сессии: после выдачи результата пользователь может
     уточнять/изменять код без начала новой задачи (SessionMode.REFINEMENT).
  2. Использует контракты из agents/contracts.py.
  3. run() принимает явный SessionState — состояние живёт в main.py.
"""
from __future__ import annotations
import time
from typing import Optional
from .base import get_llm, get_llm_config, BaseAgent
from .clarifier import ClarifierAgent
from .generator import GeneratorAgent
from .validator import ValidatorAgent
from .contracts import (
    ClarifierInput, PlannerInput, GeneratorInput, ValidatorInput,
    SessionState, SessionMode, ValidationStatus,
)
import sys
from pathlib import Path

try:
    from .planner import PlannerAgent
    _has_planner = True
except ImportError:
    _has_planner = False

_has_rag = False
KnowledgeBase = None
rag_path = Path(__file__).parent.parent / "rag"
try:
    from rag.knowledge_base import KnowledgeBase
    _has_rag = True
    print(f"[RAG] Модуль загружен из {rag_path}")
except ImportError as e:
    print(f"[RAG] Не удалось импортировать KnowledgeBase: {e}")


class Orchestrator:

    def __init__(self, config: dict, verbose: bool = True):
        self.verbose = verbose
        self.config = config

        self.llm = get_llm()
        self.llm_config = get_llm_config()

        model_cfg = config.get("model", {})
        if model_cfg.get("name") and model_cfg["name"] != self.llm_config.model:
            print(f"[WARN] Конфиг модели {model_cfg['name']} != {self.llm_config.model}")
            print(f"[WARN] Использую глобальную модель: {self.llm_config.model}")

        self.clarifier = ClarifierAgent(verbose=verbose)
        self.generator = GeneratorAgent(verbose=verbose)

        val_cfg = config.get("validator", {})
        self.validator = ValidatorAgent(
            verbose=verbose,
            sandbox_timeout=val_cfg.get("sandbox_timeout", 5),
            llm_self_review=val_cfg.get("llm_self_review", True),
        )

        self.planner = PlannerAgent(verbose=verbose) if _has_planner else None
        self.max_retries = config.get("agent", {}).get("max_retries", 3)

        # RAG
        self.kb = None
        if _has_rag and config.get("rag", {}).get("enabled", False):
            rag_cfg = config.get("rag", {})
            try:
                self._log("[RAG] Инициализация базы знаний...", "cyan")
                self.kb = KnowledgeBase(
                    persist_directory=rag_cfg.get("db_path", "./rag/chroma_db")
                )
                stats = self.kb.get_statistics()
                self._log(f"[RAG] База знаний готова: {stats['knowledge_documents']} документов", "green")
                self._add_to_history("system", "LocalScript session started",
                                     {"session_start": time.time()})
            except Exception as e:
                self._log(f"[RAG] Ошибка инициализации: {e}", "red")
                self.kb = None
        else:
            if _has_rag:
                self._log("[RAG] RAG отключён в конфигурации", "yellow")

    # ══════════════════════════════════════════════════════════════════════
    #  ПУБЛИЧНЫЙ API
    # ══════════════════════════════════════════════════════════════════════

    def run(self, task: str, state: Optional[SessionState] = None,
            user_answers: str = "") -> SessionState:
        """
        Запускает пайплайн агентов.

        task        — ввод пользователя (новая задача ИЛИ уточнение)
        state       — существующее состояние сессии (None = новая сессия)
        user_answers — ответы на уточняющие вопросы агента

        Возвращает обновлённый SessionState.
        """
        if state is None:
            state = SessionState()
            state.reset_for_new_task(task)
        elif state.has_result and state.mode == SessionMode.NEW_TASK:
            # Пользователь вводит что-то после получения результата.
            # Определяем: уточнение или новая задача.
            if self._is_refinement_request(task, state):
                self._log(f"[SESSION] Режим уточнения: \"{task[:60]}\"", "cyan")
                state.start_refinement(task)
            else:
                self._log("[SESSION] Новая задача — сброс сессии", "cyan")
                state.reset_for_new_task(task)

        start_time = time.time()
        self._log(f"\n{'='*60}")
        mode_label = {
            SessionMode.NEW_TASK: "Задача",
            SessionMode.REFINEMENT: "Уточнение",
            SessionMode.CLARIFYING: "Ответ на уточнение",
        }.get(state.mode, "Задача")
        self._log(f"{mode_label}: {task}")
        if user_answers:
            self._log(f"Ответы: {user_answers}")
        self._log(f"{'='*60}")

        self._add_to_history("user", task, {"type": "input", "mode": str(state.mode)})

        # Режим REFINEMENT: пропускаем Clarifier/Planner
        if state.mode == SessionMode.REFINEMENT:
            return self._run_refinement(task, state, start_time)

        # Шаг 1: CLARIFIER
        clarifier_in = ClarifierInput(
            task=state.original_task,
            context=user_answers,
        )
        clarifier_in.validate()
        clarifier_result = self.clarifier.analyze(
            clarifier_in.task,
            context=clarifier_in.context,
            prior_code=clarifier_in.prior_code,
            refinement_mode=clarifier_in.refinement_mode,
        )

        if not clarifier_result.ready:
            state.needs_clarification = True
            state.clarification_questions = clarifier_result.questions or []
            state.task_summary = state.original_task
            state.mode = SessionMode.CLARIFYING
            self._add_to_history("assistant",
                                 f"Clarification needed: {clarifier_result.questions}",
                                 {"type": "clarification"})
            return state

        state.needs_clarification = False
        state.task_summary = clarifier_result.summary or state.original_task
        self._add_to_history("assistant", f"Task understood: {state.task_summary}",
                             {"type": "summary"})

        # Шаг 2: RAG
        if self.kb:
            self._log("[RAG] Поиск релевантного контекста...", "cyan")
            state.context_snippets = self._search_context(state.task_summary)
            if state.context_snippets:
                self._add_to_history("system",
                                     f"Retrieved {len(state.context_snippets)} snippets",
                                     {"type": "rag_results"})

        # Шаг 3: PLANNER
        if self.planner:
            try:
                planner_in = PlannerInput(
                    task_summary=state.task_summary,
                    context_snippets=state.context_snippets,
                )
                planner_in.validate()
                plan_result = self.planner.plan(planner_in.task_summary,
                                                planner_in.context_snippets)
                state.plan = plan_result.plan_text
                self._add_to_history("assistant", f"Plan: {state.plan}", {"type": "plan"})
            except Exception as e:
                self._log(f"[PLANNER] Пропущен: {e}", "yellow")
                state.plan = ""

        # Шаг 4: GENERATE → VALIDATE → REPAIR
        return self._generation_loop(state, start_time)

    # ══════════════════════════════════════════════════════════════════════
    #  ВНУТРЕННИЕ МЕТОДЫ
    # ══════════════════════════════════════════════════════════════════════

    def _is_refinement_request(self, user_input: str, state: SessionState) -> bool:
        """Эвристика: уточнение vs новая задача."""
        if not state.final_code:
            return False

        refinement_keywords = [
            "измени", "добавь", "убери", "исправь", "переделай", "сделай",
            "теперь", "ещё", "также", "дополни", "замени", "уточни",
            "а если", "что если", "а ещё", "плюс", "ещё нужно",
            "change", "add", "remove", "fix", "modify", "now", "also",
            "make it", "but", "what if", "plus", "additionally",
        ]
        low = user_input.lower()
        for kw in refinement_keywords:
            if kw in low:
                return True
        # Короткий ввод после результата — скорее всего уточнение
        if len(user_input.split()) <= 8:
            return True
        return False

    def _run_refinement(self, refinement_request: str, state: SessionState,
                        start_time: float) -> SessionState:
        """Пайплайн уточнения — генерация на основе предыдущего кода."""
        last_error = None
        # Составной summary для валидатора: оригинал + что изменить
        refinement_summary = (
            f"{state.task_summary or state.original_task} | Refinement: {refinement_request}"
        )

        for attempt in range(1, self.max_retries + 1):
            state.iteration = attempt

            try:
                gen_in = GeneratorInput(
                    task_summary=state.task_summary or state.original_task,
                    plan=state.plan,
                    context_snippets=state.context_snippets,
                    iteration=attempt,
                    previous_error=last_error,
                    # При retry используем последний сгенерированный код, не финальный
                    prior_code=state.generated_code if last_error else state.final_code,
                    refinement_request=refinement_request,
                )
                gen_in.validate()

                gen_result = self.generator.generate(
                    task_summary=gen_in.task_summary,
                    plan=gen_in.plan,
                    context_snippets=gen_in.context_snippets,
                    iteration=attempt,
                    previous_error=last_error,
                    prior_code=gen_in.prior_code,
                    refinement_request=gen_in.refinement_request,
                )
                state.generated_code = gen_result.code
                self._add_to_history("assistant",
                                     f"Refined (attempt {attempt}):\n{gen_result.code[:200]}...",
                                     {"type": "refinement", "attempt": attempt})
            except Exception as e:
                self._log(f"[GENERATOR] Ошибка: {e}", "red")
                break

            # Валидатор получает составной summary чтобы LLM-review
            # не отклонял правильно изменённый код по старому заданию
            val_in = ValidatorInput(code=state.generated_code,
                                    task_summary=refinement_summary)
            val_in.validate()
            val_result = self.validator.validate(
                code=val_in.code, task_summary=val_in.task_summary,
            )
            state.validation_history.append({
                "attempt": attempt,
                "status": val_result.status.value,
                "checks": val_result.checks,
                "error": val_result.error_message,
            })

            if val_result.ok:
                state.final_code = state.generated_code
                state.success = True
                state.has_result = True
                state.mode = SessionMode.NEW_TASK
                break
            else:
                last_error = val_result.error_message
                self._log(f"[REPAIR] Попытка {attempt}/{self.max_retries}: {last_error}", "yellow")
                if attempt == self.max_retries:
                    state.final_code = state.generated_code
                    state.has_result = True
                    state.mode = SessionMode.NEW_TASK

        elapsed = time.time() - start_time
        self._log(f"\n[DONE] {elapsed:.1f}с | Успех: {state.success}",
                  "green" if state.success else "yellow")
        return state

    def _generation_loop(self, state: SessionState, start_time: float) -> SessionState:
        """Основной цикл генерации → валидации → исправления."""
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            state.iteration = attempt

            try:
                gen_in = GeneratorInput(
                    task_summary=state.task_summary,
                    plan=state.plan,
                    context_snippets=state.context_snippets,
                    iteration=attempt,
                    previous_error=last_error,
                    prior_code=state.generated_code if attempt > 1 else "",
                )
                gen_in.validate()

                gen_result = self.generator.generate(
                    task_summary=gen_in.task_summary,
                    plan=gen_in.plan,
                    context_snippets=gen_in.context_snippets,
                    iteration=attempt,
                    previous_error=last_error,
                    prior_code=gen_in.prior_code,
                )
                state.generated_code = gen_result.code
                self._add_to_history("assistant",
                                     f"Generated (attempt {attempt}):\n{gen_result.code[:200]}...",
                                     {"type": "generation", "attempt": attempt})
            except Exception as e:
                self._log(f"[GENERATOR] Ошибка: {e}", "red")
                self._add_to_history("system", f"Generation error: {e}", {"type": "error"})
                break

            val_in = ValidatorInput(code=state.generated_code,
                                    task_summary=state.task_summary)
            val_in.validate()
            val_result = self.validator.validate(
                code=val_in.code, task_summary=val_in.task_summary,
            )
            state.validation_history.append({
                "attempt": attempt,
                "status": val_result.status.value,
                "checks": val_result.checks,
                "error": val_result.error_message,
            })

            if val_result.ok:
                state.final_code = state.generated_code
                state.success = True
                state.has_result = True
                state.mode = SessionMode.NEW_TASK

                if self.kb and self.config.get("rag", {}).get("auto_save", False):
                    try:
                        self.kb.add_snippet(task=state.task_summary,
                                            code=state.final_code,
                                            tags=["generated", "successful"])
                        self._log("[RAG] Успешный код сохранён в базу знаний", "green")
                    except Exception as e:
                        self._log(f"[RAG] Не удалось сохранить код: {e}", "yellow")
                break
            else:
                last_error = val_result.error_message
                self._log(f"[REPAIR] Попытка {attempt}/{self.max_retries}: {last_error}", "yellow")
                if attempt == self.max_retries:
                    state.final_code = state.generated_code
                    state.has_result = True
                    state.mode = SessionMode.NEW_TASK
                    self._log("[REPAIR] Исчерпаны попытки. Возвращаю лучшую версию.", "red")

        elapsed = time.time() - start_time
        self._log(
            f"\n[DONE] Завершено за {elapsed:.1f}с | Итераций: {state.iteration} | "
            f"Успех: {state.success}",
            "green" if state.success else "yellow",
        )
        self._add_to_history("system",
                             f"Completed: success={state.success}, iter={state.iteration}",
                             {"type": "completion", "success": state.success})
        return state

    # RAG helpers
    def _search_context(self, query: str) -> list[str]:
        if not self.kb:
            return []
        try:
            snippets = self.kb.search(
                query=query,
                top_k=self.config.get("rag", {}).get("top_k", 3),
                doc_type="lua_snippet",
            )
            if snippets:
                self._log(f"[RAG] Найдено {len(snippets)} сниппетов", "green")
            else:
                self._log("[RAG] Сниппеты не найдены", "yellow")
            return snippets
        except Exception as e:
            self._log(f"[RAG] Ошибка поиска: {e}", "red")
            return []

    def _add_to_history(self, role: str, content: str, metadata: dict = None):
        if self.kb:
            try:
                self.kb.add_message(role, content, metadata)
            except Exception as e:
                self._log(f"[RAG] Не удалось сохранить в историю: {e}", "yellow")

    def _log(self, msg: str, color: str = "reset"):
        if self.verbose:
            codes = {"cyan": "\033[96m", "green": "\033[92m",
                     "yellow": "\033[93m", "red": "\033[91m", "reset": "\033[0m"}
            print(f"{codes.get(color, '')}{msg}\033[0m")

    def check_server(self) -> bool:
        return self.llm.is_available()

    def get_rag_stats(self) -> dict:
        return self.kb.get_statistics() if self.kb else {}

    def clear_session(self):
        if self.kb:
            self.kb.clear_session()
            self._log("[RAG] История сессии очищена", "green")
