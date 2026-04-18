-- TASK: сумма sum поле field массив total итого суммировать числа
-- Суммировать поле объектов в массиве
local total = 0
for i = 1, #wf.vars.items do
    total = total + wf.vars.items[i].price
end
return total
-- JSON: {"totalPrice":"lua{local t=0 for i=1,#wf.vars.items do t=t+wf.vars.items[i].price end return t}lua"}
