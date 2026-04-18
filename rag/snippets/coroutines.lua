-- TASK: корутины coroutine generator iterator асинхронность
-- Генератор через coroutine.wrap
local function range(from, to, step)
    step = step or 1
    return coroutine.wrap(function()
        for i = from, to, step do coroutine.yield(i) end
    end)
end

-- Пример:
-- for i in range(1, 10, 2) do print(i) end  --> 1 3 5 7 9

-- Продюсер-потребитель
local function producer(items)
    return coroutine.create(function()
        for _, item in ipairs(items) do coroutine.yield(item) end
    end)
end

local p = producer({"a", "b", "c"})
while true do
    local ok, val = coroutine.resume(p)
    if not ok or val == nil then break end
    print(val)
end
