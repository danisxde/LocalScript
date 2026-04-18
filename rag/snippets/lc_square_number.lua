-- TASK: вычислить квадрат числа дополнить код добавить переменную square squared number math
-- TAGS: math, number, square, tonumber, variable, arithmetic

local n = tonumber(wf.vars.num)
return n * n

-- Шаблон: вычисление квадрата числа из wf.vars.num.
-- Если число задано строкой — tonumber() конвертирует.
-- Пример дополнения кода когда уже есть базовая переменная:
-- JSON: {"num":"lua{return tonumber('5')}lua","squared":"lua{local n = tonumber('5')\nreturn n * n}lua"}
