-- TASK: условие if else condition проверка статус выбор значения
-- Условная логика с wf.vars
local status = wf.vars.orderStatus
if status == "done" then
    return "Завершён"
elseif status == "pending" then
    return "В ожидании"
else
    return "Неизвестно"
end
-- JSON: {"label":"lua{local s=wf.vars.orderStatus if s==\"done\" then return \"Завершён\" elseif s==\"pending\" then return \"В ожидании\" else return \"Неизвестно\" end}lua"}
