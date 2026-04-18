"""
GENERATOR AGENT
Генерирует Lua-код на основе плана и контекста.
Поддерживает режим уточнения (refinement) — изменение существующего кода.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .base import BaseAgent


SYSTEM_PROMPT = """You are a Lua 5.5 code generator for a LowCode workflow platform.

STRICT PLATFORM RULES:
1. Variables ONLY via wf.vars.<field> or wf.initVariables.<field>
2. Arrays: _utils.array.new() to create new, _utils.array.markAsArray(x) to mark existing
3. Script MUST end with: return <value>
4. Forbidden: io, os, require, loadfile, dofile, coroutine, pcall, xpcall
5. No comments with -- (they break JSON wrapping)
6. local variables must be declared before use
7. for loops: for i = 1, #arr do ... end

Return ONLY a ```lua ... ``` block. Nothing else."""

SYSTEM_PROMPT_REFINE = """You are a Lua 5.5 code modifier for a LowCode workflow platform.

You will receive existing Lua code and a user request to modify it.
Apply ONLY the requested changes. Keep everything else intact.

PLATFORM RULES (same as always):
1. wf.vars.<field> and wf.initVariables.<field> only
2. _utils.array.new() for new arrays
3. Must end with: return <value>
4. Forbidden: io, os, require, coroutine, pcall, xpcall
5. No -- comments

Return ONLY the modified ```lua ... ``` block. No explanation."""

SYSTEM_PROMPT_REPAIR = """You are a Lua 5.5 bug fixer for a LowCode workflow platform.

Fix ONLY the reported issue. Do not rewrite unrelated parts.

PLATFORM RULES:
1. wf.vars.<field> / wf.initVariables.<field> only
2. _utils.array.new() for new arrays
3. Must end with: return <value>
4. Forbidden: io, os, require, coroutine, pcall, xpcall

Return ONLY the fixed ```lua ... ``` block."""


@dataclass
class GeneratorResult:
    code: str
    raw_response: str
    iteration: int = 1


class GeneratorAgent(BaseAgent):

    def __init__(self, verbose: bool = True):
        super().__init__(verbose=verbose)
        self.system_prompt = SYSTEM_PROMPT

    def generate(
        self,
        task_summary: str,
        plan: Optional[str] = None,
        context_snippets: Optional[list[str]] = None,
        iteration: int = 1,
        previous_error: Optional[str] = None,
        prior_code: str = "",
        refinement_request: str = "",
        lang: str = "ru",
    ) -> GeneratorResult:

        # Выбираем режим: refinement / repair / генерация с нуля
        is_refinement = bool(refinement_request) and bool(prior_code)
        is_repair = bool(previous_error) and iteration > 1

        if is_refinement and not is_repair:
            return self._refine(task_summary, prior_code, refinement_request, iteration)
        elif is_repair:
            return self._repair(task_summary, prior_code, previous_error, iteration)
        else:
            return self._generate_fresh(task_summary, plan, context_snippets, iteration)

    def _generate_fresh(self, task_summary: str, plan: Optional[str],
                        context_snippets: Optional[list[str]], iteration: int) -> GeneratorResult:
        self._log(f"[GENERATOR] Генерирую код (итерация {iteration})...", "cyan")

        parts = [f"Task: {task_summary}"]
        if context_snippets:
            best = context_snippets[0][:300]
            parts.append(f"Reference:\n```lua\n{best}\n```")
        if plan:
            plan_lines = [l for l in plan.split("\n") if l.strip()][:3]
            parts.append("Steps: " + " | ".join(plan_lines))

        prompt = "\n".join(parts)
        raw = self.llm.chat(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        code = self._extract_lua(raw)
        self._log(f"[GENERATOR] Сгенерировано {len(code.splitlines())} строк", "green")
        return GeneratorResult(code=code, raw_response=raw, iteration=iteration)

    def _refine(self, task_summary: str, prior_code: str,
                refinement_request: str, iteration: int) -> GeneratorResult:
        self._log(f"[GENERATOR] Уточняю код: \"{refinement_request[:50]}\"...", "cyan")

        prompt = (
            f"Original task: {task_summary}\n"
            f"Current code:\n```lua\n{prior_code}\n```\n"
            f"User request: {refinement_request}"
        )
        raw = self.llm.chat(
            system=SYSTEM_PROMPT_REFINE,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        code = self._extract_lua(raw)
        self._log(f"[GENERATOR] Уточнённый код: {len(code.splitlines())} строк", "green")
        return GeneratorResult(code=code, raw_response=raw, iteration=iteration)

    def _repair(self, task_summary: str, broken_code: str,
                error: str, iteration: int) -> GeneratorResult:
        self._log(f"[GENERATOR] Исправляю ошибку (попытка {iteration})...", "cyan")

        prompt = (
            f"Task: {task_summary}\n"
            f"Broken code:\n```lua\n{broken_code}\n```\n"
            f"Error: {error[:300]}"
        )
        raw = self.llm.chat(
            system=SYSTEM_PROMPT_REPAIR,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        code = self._extract_lua(raw)
        self._log(f"[GENERATOR] Исправлено: {len(code.splitlines())} строк", "green")
        return GeneratorResult(code=code, raw_response=raw, iteration=iteration)
