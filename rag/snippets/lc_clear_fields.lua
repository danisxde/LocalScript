-- TASK: очистить значения полей в объектах массива оставить только нужные ключи удалить лишние поля clear fields keep only specific keys filter object properties
-- TAGS: table, filter, keys, pairs, nil, clear, REST, result, wf.vars

result = wf.vars.RESTbody.result
for _, filteredEntry in pairs(result) do
    for key, value in pairs(filteredEntry) do
        if key ~= "ID" and key ~= "ENTITY_ID" and key ~= "CALL" then
            filteredEntry[key] = nil
        end
    end
end
return result

-- Шаблон: оставить только перечисленные ключи, остальные установить в nil.
-- Для другого набора ключей замените условие: key ~= "FIELD1" and key ~= "FIELD2"
-- JSON: {"result":"lua{result = wf.vars.RESTbody.result\nfor _, filteredEntry in pairs(result) do\n\tfor key, value in pairs(filteredEntry) do\n\t\tif key ~= \"ID\" and key ~= \"ENTITY_ID\" and key ~= \"CALL\" then\n\t\t\tfilteredEntry[key] = nil\n\t\tend\n\tend\nend\nreturn result\n}lua"}
