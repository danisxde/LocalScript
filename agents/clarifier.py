"""
CLARIFIER AGENT - использует глобальный LLM через BaseAgent.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Optional
from .base import BaseAgent
from .contracts import ClarifierInput

_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "..", "prompts", "clarifier.txt")

def _load_system_prompt() -> str:
    try:
        with open(_PROMPT_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except (FileNotFoundError, OSError):
        pass
    # Fallback — встроенный промпт
    return """You are an assistant that analyzes Lua scripting tasks for a LowCode workflow platform.
Reply ONLY with JSON (no markdown):
{"ready":true,"summary":"one sentence: what the script must return and which wf.vars fields it uses"}
OR if critical info is missing:
{"ready":false,"questions":["question 1","question 2"]}
Max 2 questions. If task is clear → always ready:true."""

SYSTEM_PROMPT = _load_system_prompt()


@dataclass
class ClarifierResult:
    ready: bool
    summary: Optional[str] = None
    questions: Optional[list[str]] = None


class ClarifierAgent(BaseAgent):
    
    def __init__(self, verbose: bool = True):
        super().__init__(verbose=verbose)
        self.system_prompt = SYSTEM_PROMPT

    def analyze(self, task: str, context: str = "",
                prior_code: str = "", refinement_mode: bool = False) -> ClarifierResult:
        self._log("[CLARIFIER] Анализирую задачу...", "cyan")

        # Используем контракт для формирования полного промпта
        clarifier_in = ClarifierInput(
            task=task,
            context=context,
            prior_code=prior_code,
            refinement_mode=refinement_mode,
        )
        prompt = clarifier_in.full_prompt

        response = self.llm.chat(
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            clean = response.strip()
            # Правильное удаление markdown-обёртки (strip() удаляет символы, не подстроки!)
            for wrap in ["```json", "```"]:
                clean = clean.replace(wrap, "")
            clean = clean.strip()
            start = clean.find("{")
            end = clean.rfind("}") + 1
            if start >= 0 and end > start:
                clean = clean[start:end]
            data = json.loads(clean)
            result = ClarifierResult(
                ready=data.get("ready", True),
                summary=data.get("summary"),
                questions=data.get("questions"),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            self._log("[CLARIFIER] Не удалось распарсить JSON, считаю задачу понятной", "yellow")
            result = ClarifierResult(ready=True, summary=task)

        if result.ready:
            self._log(f"[CLARIFIER] ОК: {result.summary}", "green")
        else:
            self._log(f"[CLARIFIER] Нужны уточнения ({len(result.questions or [])} вопроса)", "yellow")

        return result