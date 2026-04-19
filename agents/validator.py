"""
VALIDATOR AGENT — трёхуровневая проверка Lua-кода:
1. luac -p  — синтаксический анализ (реальный компилятор)
2. lua + subprocess + timeout — sandbox-выполнение
3. LLM self-review — проверка логики (краткий промпт, 256 токенов)
"""
from __future__ import annotations
import subprocess, tempfile, os, textwrap, json
from dataclasses import dataclass, field
from .contracts import ValidationStatus
from typing import Optional
from .base import BaseAgent  

REVIEW_SYSTEM = 'You are a Lua code reviewer. Reply ONLY with JSON: {"ok":true} or {"ok":false,"issue":"brief description"}'

@dataclass
class ValidationResult:
    status: ValidationStatus
    ok: bool
    error_message: Optional[str] = None
    checks: dict = field(default_factory=dict)

class ValidatorAgent(BaseAgent):
    
    def __init__(self, verbose: bool = True,
                 sandbox_timeout: int = 5, llm_self_review: bool = True):
        super().__init__(verbose=verbose) 
        self.sandbox_timeout = sandbox_timeout
        self.llm_self_review = llm_self_review

    def validate(self, code: str, task_summary: str = "") -> ValidationResult:
        self._log("[VALIDATOR] Запускаю проверку...", "cyan")
        checks = {}

        # ── 1. Синтаксис (luac -p) ────────────────────────────────────────
        syntax_ok, syntax_err = self._check_syntax(code)
        checks["syntax"] = "OK" if syntax_ok else f"FAIL: {syntax_err}"
        if not syntax_ok:
            self._log(f"[VALIDATOR] ✗ Синтаксис: {syntax_err}", "red")
            return ValidationResult(ValidationStatus.SYNTAX_ERROR, False, syntax_err, checks)
        self._log("[VALIDATOR] ✓ Синтаксис OK", "green")

        # ── 2. Sandbox ────────────────────────────────────────────────────
        runtime_ok, runtime_err = self._run_sandbox(self._wrap(code))
        if runtime_err == "__timeout__":
            checks["sandbox"] = "TIMEOUT"
            self._log("[VALIDATOR] ✗ Sandbox timeout (бесконечный цикл?)", "red")
            return ValidationResult(ValidationStatus.TIMEOUT, False,
                                    "Код превысил лимит выполнения", checks)
        checks["sandbox"] = "OK" if runtime_ok else f"FAIL: {runtime_err}"
        if not runtime_ok:
            self._log(f"[VALIDATOR] ✗ Sandbox: {runtime_err}", "red")
            return ValidationResult(ValidationStatus.RUNTIME_ERROR, False, runtime_err, checks)
        self._log("[VALIDATOR] ✓ Sandbox OK", "green")

        # ── 3. LLM self-review ────────────────────────────────────────────
        if self.llm_self_review and task_summary:
            review_ok, issue = self._llm_review(code, task_summary)
            checks["llm_review"] = "OK" if review_ok else f"FAIL: {issue}"
            if not review_ok:
                self._log(f"[VALIDATOR] ✗ LLM review: {issue}", "yellow")
                return ValidationResult(ValidationStatus.LOGIC_ERROR, False, issue, checks)
            self._log("[VALIDATOR] ✓ LLM self-review OK", "green")

        self._log("[VALIDATOR] ✓ Все проверки пройдены", "green")
        return ValidationResult(ValidationStatus.OK, True, checks=checks)

    # ── Вспомогательные методы ────────────────────────────────────────────

    def _check_syntax(self, code: str) -> tuple[bool, Optional[str]]:
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code); tmp = f.name
        try:
            r = subprocess.run(["luac", "-p", tmp], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return True, None
            return False, r.stderr.replace(tmp, "<code>").strip()
        except FileNotFoundError:
            self._log("[VALIDATOR] ⚠ luac не найден, пропускаю синтаксис", "yellow")
            return True, None
        except subprocess.TimeoutExpired:
            return False, "Timeout при синтаксическом анализе"
        finally:
            os.unlink(tmp)

    def _wrap(self, code: str) -> str:
        """Оборачивает код в минимальное LowCode-окружение для sandbox-теста."""
        indented = textwrap.indent(code, "    ")

        return """\
-- ================================================
-- LowCode Lua sandbox mock (для валидатора)
-- wf.vars / wf.initVariables / _utils.array
-- ================================================

local wf = {
    vars = {},
    initVariables = {}
}

local _utils = {
    array = {
        new = function()
            return {}
        end,
        markAsArray = function(arr)
            return arr
        end
    }
}

-- ================================================
-- Сгенерированный пользователем код
""" + indented + "\n"
    
    def _run_sandbox(self, code: str) -> tuple[bool, Optional[str]]:
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code); tmp = f.name
        try:
            r = subprocess.run(["lua", tmp], capture_output=True, text=True,
                               timeout=self.sandbox_timeout)
            if r.returncode == 0:
                return True, None
            return False, r.stderr.strip()
        except FileNotFoundError:
            self._log("[VALIDATOR] ⚠ lua не найден, пропускаю sandbox", "yellow")
            return True, None
        except subprocess.TimeoutExpired:
            return False, "__timeout__"
        finally:
            os.unlink(tmp)

    def _llm_review(self, code: str, task: str) -> tuple[bool, Optional[str]]:
        code_preview = "\n".join(code.split("\n")[:20])
        prompt = f"Task: {task}\nCode:\n```lua\n{code_preview}\n```\nIs it correct?"
        try:
            resp = self.llm.chat(
                system=REVIEW_SYSTEM,
                messages=[{"role": "user", "content": prompt}]
            )
            clean = resp.strip()
            s = clean.find("{"); e = clean.rfind("}") + 1
            if s >= 0 and e > s:
                data = json.loads(clean[s:e])
                if data.get("ok"):
                    return True, None
                return False, data.get("issue", "Логическая ошибка")
        except Exception:
            pass
        return True, None 