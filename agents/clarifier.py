"""
CLARIFIER AGENT - использует глобальный LLM через BaseAgent.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Optional
from .base import BaseAgent

SYSTEM_PROMPT = """Analyze the Lua coding task. Reply ONLY with JSON (no markdown):
{"ready":true,"summary":"one sentence what to implement"}
OR if ambiguous (missing data type, unclear behavior):
{"ready":false,"questions":["question 1","question 2"]}
Max 2 questions. If task is clear → always ready:true."""


@dataclass
class ClarifierResult:
    ready: bool
    summary: Optional[str] = None
    questions: Optional[list[str]] = None


class ClarifierAgent(BaseAgent):
    
    def __init__(self, verbose: bool = True):
        super().__init__(verbose=verbose)
        self.system_prompt = SYSTEM_PROMPT

    def analyze(self, task: str, context: str = "") -> ClarifierResult:
        self._log("[CLARIFIER] Анализирую задачу...", "cyan")

        prompt = f"Task: {task}"
        if context:
            prompt += f"\nUser clarification: {context}"

        response = self.llm.chat(
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            clean = response.strip()
            for wrap in ["```json", "```"]:
                clean = clean.strip(wrap)
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