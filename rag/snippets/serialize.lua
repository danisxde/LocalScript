-- TASK: сериализация таблицы serialize table string json строка
local function serialize(val, indent)
    indent = indent or ""
    local t = type(val)
    if t == "number" or t == "boolean" then return tostring(val)
    elseif t == "string" then return string.format("%q", val)
    elseif t == "table" then
        local items = {}
        if #val > 0 then
            for _, v in ipairs(val) do
                items[#items+1] = serialize(v)
            end
            return "{" .. table.concat(items, ", ") .. "}"
        else
            for k, v in pairs(val) do
                items[#items+1] = tostring(k) .. " = " .. serialize(v)
            end
            return "{\n  " .. table.concat(items, ",\n  ") .. "\n}"
        end
    end
    return "nil"
end

-- Пример:
-- print(serialize({1, 2, 3}))          --> {1, 2, 3}
-- print(serialize({name="lua", v=5}))  --> {name = "lua", v = 5}
