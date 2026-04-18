-- TASK: обработка ошибок error handling pcall xpcall защита
-- Безопасный вызов через pcall
local ok, result = pcall(function()
    return risky_operation()
end)
if not ok then
    print("Ошибка: " .. tostring(result))
end

-- xpcall с трассировкой стека
local function traceback(err)
    return debug.traceback(err, 2)
end
local ok2, result2 = xpcall(risky_fn, traceback, arg1, arg2)

-- Паттерн возврата (nil, err_string)
local function safe_divide(a, b)
    if b == 0 then return nil, "division by zero" end
    return a / b, nil
end
local val, err = safe_divide(10, 0)
if err then print("Ошибка: " .. err) end
