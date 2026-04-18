"""
Локальное хранилище на ChromaDB с двумя коллекциями:
1. session_history - история диалогов текущей сессии
2. knowledge_base - Lua-коды и инструкции для RAG

Полностью офлайн, использует локальную embedding-функцию.
"""

from __future__ import annotations
import os
import re
import json
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
import numpy as np
from collections import Counter

# Директории
BASE_DIR = Path(__file__).parent
SNIPPETS_DIR = BASE_DIR / "snippets"
CHROMA_DIR = BASE_DIR / "chroma_db"

SNIPPETS_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)

class LocalTFIDFEmbedding(EmbeddingFunction):
    def __init__(self, fixed_dim: int = 512):
        self.fixed_dim = fixed_dim
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.corpus: List[str] = []
        self._is_fitted = False
    
    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        tokens = re.findall(r"[a-zа-яё0-9]+", text)
        return tokens
    
    def fit(self, documents: List[str]):
        self.corpus = documents
        all_tokens = []
        for doc in documents:
            tokens = self._tokenize(doc)
            all_tokens.extend(tokens)
        
        token_counts = Counter(all_tokens)
        most_common = token_counts.most_common(self.fixed_dim)
        
        self.vocab = {token: idx for idx, (token, _) in enumerate(most_common)}
        
        N = len(documents)
        for token, idx in self.vocab.items():
            df = sum(1 for doc in documents if token in self._tokenize(doc))
            self.idf[token] = np.log((N + 1) / (df + 1)) + 1.0
        
        self._is_fitted = True
        print(f"[Embedding] Словарь создан: {len(self.vocab)} токенов")

    def _compute_tfidf(self, text: str) -> np.ndarray:
        """Возвращает вектор фиксированной размерности."""
        if not self._is_fitted or not self.vocab:
            return np.zeros(self.fixed_dim)
        
        tokens = self._tokenize(text)
        if not tokens:
            return np.zeros(self.fixed_dim)
        
        tf = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        
        vec = np.zeros(self.fixed_dim)
        for token, count in tf.items():
            if token in self.vocab:
                idx = self.vocab[token]
                tfidf = (count / len(tokens)) * self.idf.get(token, 1.0)
                vec[idx] = tfidf
        
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        
        return vec

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for doc in input:
            vec = self._compute_tfidf(doc)
            embeddings.append(vec.tolist())
        return embeddings

# ── Загрузка сниппетов ───────────────────────────────────────────────────

def load_snippets_from_files() -> List[Dict[str, Any]]:
    """
    Загружает сниппеты из rag/snippets/*.lua.
    Формат файла:
    -- TASK: описание задачи
    -- TAGS: tag1, tag2, tag3
    код...
    """
    snippets = []
    if not SNIPPETS_DIR.exists():
        return []
    
    for lua_file in sorted(SNIPPETS_DIR.glob("*.lua")):
        content = lua_file.read_text(encoding="utf-8")
        lines = content.split("\n")
        
        # Парсим метаданные
        task = ""
        tags = []
        code_lines = []
        in_metadata = True
        
        for line in lines:
            if in_metadata and line.startswith("--"):
                if line.startswith("-- TASK:"):
                    task = line.replace("-- TASK:", "").strip()
                elif line.startswith("-- TAGS:"):
                    tags = [t.strip() for t in line.replace("-- TAGS:", "").split(",")]
                continue
            else:
                in_metadata = False
                code_lines.append(line)
        
        code = "\n".join(code_lines).strip()
        
        if not task:
            task = lua_file.stem.replace("_", " ")
        
        snippets.append({
            "id": lua_file.stem,
            "task": task,
            "tags": tags,
            "code": code,
            "file": str(lua_file),
            "timestamp": datetime.now().isoformat()
        })
    
    return snippets


# ── ChromaDB хранилище ──────────────────────────────────────────────────

class KnowledgeBase:
    """
    Локальное хранилище на ChromaDB с двумя коллекциями.
    Полностью офлайн, использует TF-IDF эмбеддинги.
    """
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.persist_directory = persist_directory
        
        # Инициализируем ChromaDB с локальным persist директорием
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            is_persistent=True
        ))
        
        # Создаём embedding функцию
        self.embedding_fn = LocalTFIDFEmbedding()
        
        # Инициализируем коллекции
        self._init_collections()
        
        # Загружаем сниппеты в knowledge base
        self._load_initial_snippets()
    
    def _init_collections(self):
        """Инициализирует или пересоздает коллекции с локальными эмбеддингами."""
        
        # Удаляем старые коллекции, если они есть (ВАЖНО!)
        try:
            self.client.delete_collection("session_history")
        except:
            pass
        try:
            self.client.delete_collection("knowledge_base")
        except:
            pass
        
        # Создаем заново с нашей embedding функцией
        self.session_collection = self.client.create_collection(
            name="session_history",
            embedding_function=self.embedding_fn,  # Явно указываем
            metadata={"description": "История диалогов текущей сессии", "hnsw:space": "cosine"}
        )
        
        self.kb_collection = self.client.create_collection(
            name="knowledge_base",
            embedding_function=self.embedding_fn,  # Явно указываем
            metadata={"description": "База знаний Lua-кодов и инструкций", "hnsw:space": "cosine"}
        )
    
    def _load_initial_snippets(self):
        snippets = load_snippets_from_files()
        
        if not snippets:
            print("[RAG] Нет сниппетов для загрузки")
            return
        
        existing = self.kb_collection.get()
        if existing['ids']:
            print(f"[RAG] База знаний уже содержит {len(existing['ids'])} документов")
            return
        
        ids = []
        documents = []
        metadatas = []
        
        for snippet in snippets:
            doc_text = f"{snippet['task']}\n{snippet['code']}"
            ids.append(snippet['id'])
            documents.append(doc_text)
            metadatas.append({
                "type": "lua_snippet",
                "task": snippet['task'],
                "tags": ",".join(snippet['tags']),
                "file": snippet['file'],
                "timestamp": snippet['timestamp']
            })
        
        self.embedding_fn.fit(documents)
        
        self.kb_collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        print(f"[RAG] Загружено {len(snippets)} сниппетов в knowledge base")
    
    # ── Методы для работы с историей диалога ───────────────────────────
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """
        Добавляет сообщение в историю диалога.
        role: 'user', 'assistant', 'system'
        """
        message_id = hashlib.md5(f"{datetime.now().isoformat()}{role}{content}".encode()).hexdigest()[:16]
        
        self.session_collection.add(
            ids=[message_id],
            documents=[content],
            metadatas=[{
                "role": role,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {})
            }]
        )
    
    def get_session_history(self, limit: int = 50) -> List[Dict]:
        """Получает историю диалога."""
        results = self.session_collection.get(
            limit=limit,
            include=["documents", "metadatas"]
        )
        
        history = []
        if results['ids']:
            for doc, meta in zip(results['documents'], results['metadatas']):
                history.append({
                    "role": meta.get('role', 'unknown'),
                    "content": doc,
                    "timestamp": meta.get('timestamp', ''),
                    **meta
                })
        
        return history
    
    def clear_session(self):
        """Очищает историю текущей сессии."""
        self.client.delete_collection("session_history")
        self._init_collections()
        print("[RAG] История диалога очищена")
    
    # ── Методы для работы с базой знаний ───────────────────────────────
    
    def search(self, query: str, top_k: int = 3, doc_type: Optional[str] = None) -> List[Dict]:
        """
        Поиск в базе знаний релевантных документов.
        
        Args:
            query: поисковый запрос
            top_k: количество результатов
            doc_type: фильтр по типу ('lua_snippet', 'instruction', etc.)
        """
        where_filter = None
        if doc_type:
            where_filter = {"type": doc_type}
        
        results = self.kb_collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        documents = []
        if results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                documents.append({
                    "id": doc_id,
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "relevance_score": 1 - results['distances'][0][i] if results['distances'] else 0
                })
        
        snippets = []
        for d in documents:
            # Результат search_knowledge возвращает поле 'content' 
            # в формате "task\ncode"
            content = d.get('content', '')
            
            # Разделяем task и code (первая строка - task, остальное - code)
            lines = content.split('\n', 1)
            if len(lines) == 2:
                # Возвращаем только код
                code = lines[1].strip()
                if code:
                    snippets.append(code)
            else:
                # Если формат неожиданный, возвращаем как есть
                snippets.append(content)
        
        return snippets
    
    def add_knowledge(self, 
                      content: str, 
                      doc_type: str, 
                      metadata: Optional[Dict] = None,
                      doc_id: Optional[str] = None):
        """
        Добавляет документ в базу знаний.
        
        Args:
            content: содержимое документа (Lua-код, инструкция и т.д.)
            doc_type: тип документа ('lua_snippet', 'instruction', 'example')
            metadata: дополнительные метаданные
            doc_id: уникальный ID (генерируется если не указан)
        """
        if not doc_id:
            doc_id = hashlib.md5(f"{doc_type}{content}{datetime.now()}".encode()).hexdigest()[:16]
        
        meta = {
            "type": doc_type,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {})
        }
        
        self.kb_collection.add(
            ids=[doc_id],
            documents=[content],
            metadatas=[meta]
        )
        
        # Обновляем embedding функцию новым документом
        all_docs = self.kb_collection.get()['documents']
        self.embedding_fn.fit(all_docs)
        
        print(f"[RAG] Добавлен документ {doc_id} типа '{doc_type}'")
        return doc_id
    
    def add_snippet(self, task: str, code: str, tags: Optional[List[str]] = None):
        """
        Добавляет Lua-сниппет в базу знаний и сохраняет в файл.
        """
        snippet_id = f"lua_{hashlib.md5(f'{task}{code}'.encode()).hexdigest()[:8]}"
        
        # Сохраняем в файл
        lua_file = SNIPPETS_DIR / f"{snippet_id}.lua"
        tags_str = ", ".join(tags) if tags else ""
        with open(lua_file, "w", encoding="utf-8") as f:
            f.write(f"-- TASK: {task}\n")
            if tags_str:
                f.write(f"-- TAGS: {tags_str}\n")
            f.write(code)
        
        # Добавляем в ChromaDB
        content = f"{task}\n{code}"
        self.add_knowledge(
            content=content,
            doc_type="lua_snippet",
            metadata={
                "task": task,
                "tags": tags_str,
                "file": str(lua_file),
                "snippet_id": snippet_id
            },
            doc_id=snippet_id
        )
        
        print(f"[RAG] Lua-сниппет сохранён: {snippet_id}")
        return snippet_id
    
    def delete_knowledge(self, doc_id: str):
        """Удаляет документ из базы знаний."""
        self.kb_collection.delete(ids=[doc_id])
        print(f"[RAG] Удалён документ {doc_id}")
    
    def get_statistics(self) -> Dict:
        """Возвращает статистику по хранилищу."""
        session_count = self.session_collection.count()
        kb_count = self.kb_collection.count()
        
        # Получаем типы документов в KB
        kb_docs = self.kb_collection.get()
        doc_types = {}
        if kb_docs['metadatas']:
            for meta in kb_docs['metadatas']:
                doc_type = meta.get('type', 'unknown')
                doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        
        return {
            "session_messages": session_count,
            "knowledge_documents": kb_count,
            "document_types": doc_types,
            "persist_directory": self.persist_directory
        }
