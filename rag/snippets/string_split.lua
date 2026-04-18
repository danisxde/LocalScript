-- TASK: split string разделить строку на части разбить
local function split(str, sep)
    if str == nil or str == "" then return {} end
    local result = {}
    for part in str:gmatch("([^" .. sep .. "]+)") do
        result[#result + 1] = part:match("^%s*(.-)%s*$")
    end
    return result
end

-- Пример:
-- local parts = split("alpha, beta, gamma", ",")
-- for i, v in ipairs(parts) do print(i, v) end
-- --> 1  alpha  2  beta  3  gamma
