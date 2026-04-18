-- TASK: найти элемент по полю find by field search lookup поиск в массиве по значению
-- Найти первый элемент массива по значению поля
local target = wf.vars.targetId
local found = nil
for i = 1, #wf.vars.users do
    if wf.vars.users[i].id == target then
        found = wf.vars.users[i]
        break
    end
end
return found
-- JSON: {"user":"lua{local t=wf.vars.targetId local f=nil for i=1,#wf.vars.users do if wf.vars.users[i].id==t then f=wf.vars.users[i] break end end return f}lua"}
