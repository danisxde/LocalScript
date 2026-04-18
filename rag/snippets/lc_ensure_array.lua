-- TASK: проверить тип данных и убедиться что items является массивом ensure array type check markAsArray nested objects
-- TAGS: array, type, table, ensureArray, markAsArray, _utils, ipairs, items, type check

function ensureArray(t)
    if type(t) ~= "table" then
        return {t}
    end
    local isArray = true
    for k, v in pairs(t) do
        if type(k) ~= "number" or math.floor(k) ~= k then
            isArray = false
            break
        end
    end
    return isArray and t or {t}
end

function ensureAllItemsAreArrays(objectsArray)
    if type(objectsArray) ~= "table" then
        return objectsArray
    end
    for _, obj in ipairs(objectsArray) do
        if type(obj) == "table" and obj.items then
            obj.items = ensureArray(obj.items)
        end
    end
    return objectsArray
end

return ensureAllItemsAreArrays(wf.vars.json.IDOC.ZCDF_HEAD.ZCDF_PACKAGES)

-- Шаблон: гарантирует что вложенное поле items всегда массив,
-- даже если в данных пришёл одиночный объект вместо массива.
-- JSON: {"packages":"lua{function ensureArray(t)\nif type(t) ~= \"table\" then return {t} end\nlocal isArray = true\nfor k, v in pairs(t) do\nif type(k) ~= \"number\" or math.floor(k) ~= k then isArray = false break end\nend\nreturn isArray and t or {t}\nend\nfunction ensureAllItemsAreArrays(objectsArray)\nif type(objectsArray) ~= \"table\" then return objectsArray end\nfor _, obj in ipairs(objectsArray) do\nif type(obj) == \"table\" and obj.items then obj.items = ensureArray(obj.items) end\nend\nreturn objectsArray\nend\nreturn ensureAllItemsAreArrays(wf.vars.json.IDOC.ZCDF_HEAD.ZCDF_PACKAGES)}lua"}
