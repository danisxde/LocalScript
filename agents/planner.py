"""
PLANNER AGENT
Краткая декомпозиция задачи перед генерацией.
Промпт минимальный — укладывается в num_predict=256.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .base import BaseAgent 

SYSTEM_PROMPT = """List 2-4 implementation steps for the Lua task. Plain text only.
Format: 1. step one 2. step two
Be brief. No code, just steps."""


@dataclass
class PlanResult:
    plan_text: str
    steps: list[str]


class PlannerAgent(BaseAgent):
    """Планнер - использует глобальный LLM через BaseAgent."""
    
    def __init__(self, verbose: bool = True):
        super().__init__(verbose=verbose)  
        self.system_prompt = SYSTEM_PROMPT

    def plan(self, task_summary: str, context_snippets: Optional[list[str]] = None) -> PlanResult:
        self._log("[PLANNER] Составляю план...", "cyan")

        prompt = f"Task: {task_summary}"
        if context_snippets:
            first_line = context_snippets[0].split("\n")[0][:80]
            prompt += f"\nReference hint: {first_line}"

        response = self.llm.chat(
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )

        lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
        steps = [l for l in lines if l and (l[0].isdigit() or l.startswith("-"))]

        self._log(f"[PLANNER] {len(steps)} шагов: {' | '.join(steps[:3])}", "green")
        return PlanResult(plan_text=response, steps=steps)