-- TASK: сортировка таблицы массива sort table
-- Сортировка массива чисел/строк (по возрастанию)
table.sort(arr)

-- Сортировка таблицы объектов по полю
table.sort(items, function(a, b) return a.value < b.value end)

-- Стабильная сортировка (сохраняет порядок равных элементов)
local function stable_sort(arr, cmp)
    local indexed = {}
    for i, v in ipairs(arr) do indexed[i] = {v, i} end
    table.sort(indexed, function(a, b)
        if cmp(a[1], b[1]) then return true end
        if cmp(b[1], a[1]) then return false end
        return a[2] < b[2]
    end)
    for i, v in ipairs(indexed) do arr[i] = v[1] end
end

-- Пример:
-- local t = {5, 3, 1, 4, 2}
-- table.sort(t)
-- print(table.concat(t, ","))  --> 1,2,3,4,5
