-- TASK: фильтровать элементы массива у которых есть значение в поле Discount или Markdown filter array by nonempty field value presence
-- TAGS: filter, array, ipairs, _utils.array.new, nonempty, nil, empty string, condition

local result = _utils.array.new()
local items = wf.vars.parsedCsv

for _, item in ipairs(items) do
    if (item.Discount ~= "" and item.Discount ~= nil) or (item.Markdown ~= "" and item.Markdown ~= nil) then
        table.insert(result, item)
    end
end
return result

-- Шаблон: фильтрует массив, оставляя только элементы где хотя бы одно
-- из указанных полей заполнено (не пусто и не nil).
-- Замените wf.vars.parsedCsv на нужный массив, поля Discount/Markdown — на нужные.
-- JSON: {"result":"lua{local result = _utils.array.new()\nlocal items = wf.vars.parsedCsv\nfor _, item in ipairs(items) do\nif (item.Discount ~= \"\" and item.Discount ~= nil) or (item.Markdown ~= \"\" and item.Markdown ~= nil) then\ntable.insert(result, item)\nend\nend\nreturn result\n}lua"}
