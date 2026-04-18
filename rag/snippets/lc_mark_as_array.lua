-- TASK: markAsArray объявить массивом существующую переменную mark array
-- Объявить существующую переменную массивом
local arr = wf.vars.someList
_utils.array.markAsArray(arr)
return arr
-- JSON: {"result":"lua{local a=wf.vars.someList _utils.array.markAsArray(a) return a}lua"}
