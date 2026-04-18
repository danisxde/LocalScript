-- TASK: initVariables начальные переменные схема запуск variables input входные параметры
-- Доступ к переменным запуска схемы (из variables при старте)
local userId   = wf.initVariables.userId
local planType = wf.initVariables.planType
if planType == "premium" then
    return userId .. ":premium"
else
    return userId .. ":basic"
end
-- JSON: {"userKey":"lua{local u=wf.initVariables.userId local p=wf.initVariables.planType if p==\"premium\" then return u..\":premium\" else return u..\":basic\" end}lua"}
