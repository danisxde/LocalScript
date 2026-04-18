"""
LLM Client — обёртка над Ollama API.
Одиночка (Singleton) для всего приложения.
"""
from __future__ import annotations
import json
import re
import requests
from dataclasses import dataclass
from typing import Optional, Dict, Any


_global_llm_client = None
_global_llm_config = None


@dataclass
class LLMConfig:
    host: str
    port: int
    model: str
    temperature: float
    num_ctx: int
    num_predict: int
    num_batch: int
    num_parallel: int
    num_gpu: int
    top_p: float
    repeat_penalty: float

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMConfig":
        return cls(
            host=data.get("host"),
            port=data.get("port"),
            model=data.get("name", data.get("model")), 
            temperature=data.get("temperature"),
            num_ctx=data.get("num_ctx"),
            num_predict=data.get("num_predict"),
            num_batch=data.get("num_batch"),
            num_parallel=data.get("num_parallel"),
            num_gpu=data.get("num_gpu"),
            top_p=data.get("top_p"),
            repeat_penalty=data.get("repeat_penalty"),
        )


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self._session = requests.Session()
        self._check_ollama()

    def _check_ollama(self):
        print(f"[LLM] Проверка Ollama на {self.config.base_url}...")
        try:
            resp = self._session.get(f"{self.config.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]
            
            if self.config.model not in model_names:
                print(f"[LLM] Модель {self.config.model} не найдена. Загружаем...")
                pull_resp = self._session.post(
                    f"{self.config.base_url}/api/pull",
                    json={"name": self.config.model},
                    timeout=300
                )
                if pull_resp.status_code != 200:
                    raise RuntimeError(f"Не удалось загрузить модель: {pull_resp.text}")
                print(f"[LLM] Модель {self.config.model} загружена")
            else:
                print(f"[LLM] Модель {self.config.model} найдена")
                
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Ollama недоступна на {self.config.base_url}\n"
                "Запустите: ollama serve"
            )

    def chat(self, system: str, messages: list[dict], 
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None) -> str:
        full_messages = [{"role": "system", "content": system}] + messages
        predict = max_tokens if max_tokens else self.config.num_predict

        payload = {
            "model": self.config.model,
            "messages": full_messages,
            "stream": False,
            "options": {
                "temperature": temperature or self.config.temperature,
                "num_ctx": self.config.num_ctx,
                "num_predict": predict,
                "num_batch": self.config.num_batch,
                "num_parallel": self.config.num_parallel,
                "num_gpu": self.config.num_gpu,
                "top_p": self.config.top_p,
                "repeat_penalty": self.config.repeat_penalty,
            },
        }

        resp = self._session.post(
            f"{self.config.base_url}/api/chat",
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"].strip()

    def is_available(self) -> bool:
        try:
            resp = self._session.get(f"{self.config.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            resp = self._session.get(f"{self.config.base_url}/api/tags", timeout=5)
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []


def init_llm(config: LLMConfig) -> LLMClient:
    global _global_llm_client, _global_llm_config
    
    if _global_llm_client is None:
        print("[INIT] Инициализация LLM клиента...")
        _global_llm_config = config
        _global_llm_client = LLMClient(config)
        print(f"[INIT] LLM клиент готов: {config.model}")
    else:
        print("[INIT] LLM клиент уже инициализирован")
    
    return _global_llm_client


def get_llm() -> LLMClient:
    if _global_llm_client is None:
        raise RuntimeError("LLM не инициализирован! Вызовите init_llm() сначала")
    return _global_llm_client


def get_llm_config() -> LLMConfig:
    if _global_llm_config is None:
        raise RuntimeError("LLM не инициализирован!")
    return _global_llm_config


class BaseAgent:
    
    def __init__(self, verbose: bool = True):
        self.llm = get_llm()  
        self.verbose = verbose
        self.system_prompt = ""

    def _log(self, msg: str, color: str = "cyan"):
        if self.verbose:
            colors = {"cyan": "\033[96m", "green": "\033[92m",
                      "yellow": "\033[93m", "red": "\033[91m", "reset": "\033[0m"}
            print(f"{colors.get(color, '')}{msg}{colors['reset']}")

    def _extract_lua(self, text: str) -> str:
        m = re.search(r"```(?:lua)?\s*\n(.*?)```", text, re.DOTALL)
        if m:
            return m.group(1).strip()
        lines = text.strip().split("\n")
        code_lines = [l for l in lines if not l.startswith("--#") and
                      not l.startswith("Объяснение:") and not l.startswith("Explanation:")]
        return "\n".join(code_lines).strip()