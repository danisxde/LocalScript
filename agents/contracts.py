"""
CONTRACTS — формальные контракты для всех агентов системы.

Каждый контракт описывает:
  - Входные данные (Input)
  - Выходные данные (Output)
  - Инварианты (что всегда должно быть истиной)
  - Ограничения
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ══════════════════════════════════════════════════════════
#  CLARIFIER CONTRACT
# ══════════════════════════════════════════════════════════

@dataclass
class ClarifierInput:
    """
    Входные данные для ClarifierAgent.
    
    Инварианты:
      - task не может быть пустой строкой
      - context может быть пустым (при первом вызове)
      - prior_code заполняется только при режиме refinement
    """
    task: str
    context: str = ""
    prior_code: str = ""          # код из предыдущей итерации (для уточнений)
    refinement_mode: bool = False  # True = пользователь уточняет уже выданный результат

    def validate(self) -> None:
        if not self.task or not self.task.strip():
            raise ValueError("ClarifierInput.task не может быть пустым")

    @property
    def full_prompt(self) -> str:
        """Полный контекст для агента."""
        parts = [f"Task: {self.task}"]
        if self.context:
            parts.append(f"User clarification: {self.context}")
        if self.refinement_mode and self.prior_code:
            parts.append(f"Existing code to refine:\n```lua\n{self.prior_code[:400]}\n```")
        return "\n".join(parts)


@dataclass
class ClarifierOutput:
    """
    Выходные данные ClarifierAgent.
    
    Инварианты:
      - Если ready=True, то summary не пустой
      - Если ready=False, то questions содержит 1-2 вопроса
      - questions и summary не могут быть оба непустыми одновременно
    """
    ready: bool
    summary: str = ""
    questions: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if self.ready and not self.summary:
            raise ValueError("ClarifierOutput: ready=True требует непустого summary")
        if not self.ready and not self.questions:
            raise ValueError("ClarifierOutput: ready=False требует хотя бы одного вопроса")
        if not self.ready and len(self.questions) > 3:
            raise ValueError("ClarifierOutput: не более 3 уточняющих вопросов")


# ══════════════════════════════════════════════════════════
#  PLANNER CONTRACT
# ══════════════════════════════════════════════════════════

@dataclass
class PlannerInput:
    """
    Входные данные для PlannerAgent.
    
    Инварианты:
      - task_summary — результат ClarifierOutput.summary (не пустой)
      - context_snippets — список строк (может быть пустым)
    """
    task_summary: str
    context_snippets: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.task_summary or not self.task_summary.strip():
            raise ValueError("PlannerInput.task_summary не может быть пустым")


@dataclass
class PlannerOutput:
    """
    Выходные данные PlannerAgent.
    
    Инварианты:
      - plan_text — читаемый текст с шагами (может быть пустым при пропуске)
      - steps — распарсенный список шагов (от 1 до 5 элементов)
    """
    plan_text: str
    steps: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if len(self.steps) > 6:
            raise ValueError("PlannerOutput: слишком много шагов (макс 6)")


# ══════════════════════════════════════════════════════════
#  GENERATOR CONTRACT
# ══════════════════════════════════════════════════════════

@dataclass
class GeneratorInput:
    """
    Входные данные для GeneratorAgent.
    
    Инварианты:
      - task_summary — непустая строка
      - iteration >= 1
      - previous_error заполняется только начиная со 2-й итерации
      - refinement_request — пользовательское уточнение для улучшения кода
    """
    task_summary: str
    plan: str = ""
    context_snippets: list[str] = field(default_factory=list)
    iteration: int = 1
    previous_error: Optional[str] = None
    prior_code: str = ""             # код предыдущей генерации (для repair)
    refinement_request: str = ""     # что пользователь хочет изменить

    def validate(self) -> None:
        if not self.task_summary or not self.task_summary.strip():
            raise ValueError("GeneratorInput.task_summary не может быть пустым")
        if self.iteration < 1:
            raise ValueError("GeneratorInput.iteration >= 1")
        if self.iteration > 1 and not self.previous_error and not self.prior_code:
            raise ValueError("GeneratorInput: iteration>1 требует previous_error или prior_code")

    @property
    def is_repair(self) -> bool:
        return self.previous_error is not None and self.iteration > 1

    @property
    def is_refinement(self) -> bool:
        return bool(self.refinement_request) and bool(self.prior_code)


@dataclass
class GeneratorOutput:
    """
    Выходные данные GeneratorAgent.
    
    Инварианты:
      - code — непустая строка с Lua-кодом
      - code содержит хотя бы один оператор return
      - raw_response — исходный ответ LLM
    """
    code: str
    raw_response: str
    iteration: int = 1

    def validate(self) -> None:
        if not self.code or not self.code.strip():
            raise ValueError("GeneratorOutput.code не может быть пустым")
        if "return" not in self.code:
            raise ValueError("GeneratorOutput.code должен содержать оператор return")


# ══════════════════════════════════════════════════════════
#  VALIDATOR CONTRACT
# ══════════════════════════════════════════════════════════

class ValidationStatus(str, Enum):
    OK            = "ok"
    SYNTAX_ERROR  = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    LOGIC_ERROR   = "logic_error"
    TIMEOUT       = "timeout"


@dataclass
class ValidatorInput:
    """
    Входные данные для ValidatorAgent.
    
    Инварианты:
      - code — непустая строка Lua-кода (результат GeneratorOutput.code)
      - task_summary — строка для LLM self-review (может быть пустой — тогда review пропускается)
    """
    code: str
    task_summary: str = ""

    def validate(self) -> None:
        if not self.code or not self.code.strip():
            raise ValueError("ValidatorInput.code не может быть пустым")


@dataclass
class ValidatorOutput:
    """
    Выходные данные ValidatorAgent.
    
    Инварианты:
      - Если ok=True, то status=OK и error_message=None
      - Если ok=False, то status != OK и error_message непустой
      - checks содержит результаты каждой проверки
    """
    status: ValidationStatus
    ok: bool
    error_message: Optional[str] = None
    checks: dict = field(default_factory=dict)

    def validate(self) -> None:
        if self.ok and self.status != ValidationStatus.OK:
            raise ValueError("ValidatorOutput: ok=True требует status=OK")
        if not self.ok and not self.error_message:
            raise ValueError("ValidatorOutput: ok=False требует error_message")


# ══════════════════════════════════════════════════════════
#  ORCHESTRATOR SESSION CONTRACT
# ══════════════════════════════════════════════════════════

class SessionMode(str, Enum):
    NEW_TASK    = "new_task"     # новая задача пользователя
    REFINEMENT  = "refinement"   # уточнение к уже сгенерированному коду
    CLARIFYING  = "clarifying"   # ответ на уточняющий вопрос агента


@dataclass
class SessionState:
    """
    Состояние текущей сессии. Сохраняется между итерациями.
    
    Инварианты:
      - original_task непустой после первого run()
      - final_code непустой только если генерация завершилась
      - iteration >= 0
      - mode определяет, как интерпретируется следующий ввод пользователя
    """
    original_task: str = ""
    task_summary: str = ""
    plan: str = ""
    context_snippets: list[str] = field(default_factory=list)
    generated_code: str = ""
    validation_history: list[dict] = field(default_factory=list)
    iteration: int = 0
    final_code: str = ""
    success: bool = False
    clarification_answers: str = ""
    needs_clarification: bool = False
    clarification_questions: list[str] = field(default_factory=list)
    # ── Поля для поддержки сессий ──
    mode: SessionMode = SessionMode.NEW_TASK
    has_result: bool = False      # True = пользователю уже показан результат
    refinement_history: list[str] = field(default_factory=list)  # история уточнений

    def start_refinement(self, user_request: str) -> None:
        """Переключает сессию в режим уточнения."""
        self.mode = SessionMode.REFINEMENT
        self.refinement_history.append(user_request)
        self.success = False
        self.validation_history = []
        self.iteration = 0

    def reset_for_new_task(self, task: str) -> None:
        """Сбрасывает состояние для новой задачи."""
        self.original_task = task
        self.task_summary = ""
        self.plan = ""
        self.context_snippets = []
        self.generated_code = ""
        self.validation_history = []
        self.iteration = 0
        self.final_code = ""
        self.success = False
        self.clarification_answers = ""
        self.needs_clarification = False
        self.clarification_questions = []
        self.mode = SessionMode.NEW_TASK
        self.has_result = False
        self.refinement_history = []
