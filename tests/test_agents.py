"""
Тесты агентской системы — 12 тестов, LLM не требуется.
Запуск: python tests/test_agents.py  или  make test
"""
import sys, os, subprocess, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestSyntaxCheck:
    """Синтаксический анализ через luac -p (реальный компилятор Lua)."""

    def _luac(self, code):
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as f:
            f.write(code); tmp = f.name
        try:
            r = subprocess.run(["luac", "-p", tmp], capture_output=True, timeout=5)
            return r.returncode == 0, r.stderr.decode()
        except FileNotFoundError:
            return None, "luac not found"
        finally:
            os.unlink(tmp)

    def test_valid_function(self):
        ok, _ = self._luac("local function add(a,b) return a+b end\nprint(add(1,2))")
        if ok is None: print("SKIP: luac not installed"); return
        assert ok

    def test_syntax_error(self):
        ok, err = self._luac("local function broken(\n    return 1\nend")
        if ok is None: return
        assert not ok

    def test_metatables(self):
        ok, _ = self._luac("""
local MT = {}
MT.__index = MT
function MT.new() return setmetatable({}, MT) end
function MT:greet() return "hello" end
""")
        if ok is None: return
        assert ok


class TestSandboxExecution:
    """Реальное выполнение Lua-кода через subprocess."""

    def _run(self, code, timeout=3):
        with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as f:
            f.write(code); tmp = f.name
        try:
            r = subprocess.run(["lua", tmp], capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
        except FileNotFoundError:
            return None, "", "lua not found"
        except subprocess.TimeoutExpired:
            return False, "", "timeout"
        finally:
            os.unlink(tmp)

    def test_fibonacci(self):
        ok, out, _ = self._run("local function fib(n) if n<=1 then return n end return fib(n-1)+fib(n-2) end\nprint(fib(10))")
        if ok is None: return
        assert ok and out == "55"

    def test_table_sort(self):
        ok, out, _ = self._run("local t={5,3,1,4,2}\ntable.sort(t)\nprint(table.concat(t,','))")
        if ok is None: return
        assert ok and out == "1,2,3,4,5"

    def test_binary_search(self):
        ok, out, _ = self._run("""
local function bs(arr, t)
    local lo,hi = 1,#arr
    while lo<=hi do
        local mid=math.floor((lo+hi)/2)
        if arr[mid]==t then return mid
        elseif arr[mid]<t then lo=mid+1
        else hi=mid-1 end
    end
    return nil
end
print(bs({1,3,5,7,9},5))
print(tostring(bs({1,3,5,7,9},6)))
""")
        if ok is None: return
        assert ok
        lines = out.split("\n")
        assert lines[0] == "3"
        assert lines[1] == "nil"

    def test_timeout_detection(self):
        ok, _, err = self._run("while true do end", timeout=2)
        if ok is None: return
        assert not ok or err == "timeout"


class TestRAG:
    """Тесты локального TF-IDF поиска по сниппетам."""

    def _get_kb(self):
        from rag.knowledge_base import KnowledgeBase
        return KnowledgeBase()

    def test_snippets_loaded(self):
        from rag.knowledge_base import SNIPPETS
        assert len(SNIPPETS) >= 7, f"Ожидалось ≥7 сниппетов, получено {len(SNIPPETS)}"

    def test_snippets_have_code(self):
        from rag.knowledge_base import SNIPPETS
        for s in SNIPPETS:
            assert "code" in s and len(s["code"]) > 10, f"Сниппет {s.get('id')} без кода"
            assert "task" in s and len(s["task"]) > 3, f"Сниппет {s.get('id')} без описания"

    def test_search_sort(self):
        kb = self._get_kb()
        results = kb.search("sort table сортировка массив", top_k=2)
        assert len(results) > 0, "Поиск по 'sort' не дал результатов"

    def test_search_split(self):
        kb = self._get_kb()
        results = kb.search("split string разделить строку")
        assert len(results) > 0

    def test_search_oop(self):
        kb = self._get_kb()
        results = kb.search("class metatables ООП наследование")
        assert len(results) > 0

    def test_add_snippet(self):
        """Добавленный сниппет сразу доступен для поиска."""
        import uuid
        kb = self._get_kb()
        unique_word = f"xyztest{uuid.uuid4().hex[:6]}"
        kb.add_snippet(f"тест {unique_word}", "local x = 1")
        results = kb.search(unique_word)
        assert len(results) > 0, "Добавленный сниппет не найден при поиске"


class TestClarifierParsing:
    """Парсинг JSON-ответов агента кларификатора."""

    def _parse(self, response):
        clean = response.strip().strip("```json").strip("```").strip()
        return json.loads(clean)

    def test_ready_response(self):
        data = self._parse('{"ready": true, "summary": "Функция binary search"}')
        assert data["ready"] is True
        assert "summary" in data

    def test_not_ready_response(self):
        data = self._parse('{"ready": false, "questions": ["Тип?", "Направление?"]}')
        assert data["ready"] is False
        assert len(data["questions"]) == 2

    def test_markdown_wrapped_json(self):
        data = self._parse('```json\n{"ready": true, "summary": "test"}\n```')
        assert data["ready"] is True


if __name__ == "__main__":
    import traceback
    all_tests = [TestSyntaxCheck(), TestSandboxExecution(), TestRAG(), TestClarifierParsing()]
    passed = failed = 0
    for obj in all_tests:
        cls = type(obj).__name__
        for method in sorted(dir(obj)):
            if not method.startswith("test_"): continue
            try:
                getattr(obj, method)()
                print(f"  \033[92m✓\033[0m {cls}::{method}")
                passed += 1
            except Exception as e:
                print(f"  \033[91m✗\033[0m {cls}::{method}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
