-- TASK: подсчёт count filter фильтр элементов массива по условию количество
-- Подсчёт элементов по условию
local count = 0
for i = 1, #wf.vars.orders do
    if wf.vars.orders[i].status == "active" then
        count = count + 1
    end
end
return count
-- JSON: {"activeCount":"lua{local c=0 for i=1,#wf.vars.orders do if wf.vars.orders[i].status==\"active\" then c=c+1 end end return c}lua"}
