-- TASK: while цикл repeat until повторять пока условие loop while
-- Цикл while и repeat..until (for запрещён для while-семантики)
local i = 1
local result = _utils.array.new()
while i <= #wf.vars.data do
    if wf.vars.data[i] ~= nil then
        result[#result + 1] = wf.vars.data[i]
    end
    i = i + 1
end
return result
-- JSON: {"filtered":"lua{local i=1 local r=_utils.array.new() while i<=#wf.vars.data do if wf.vars.data[i]~=nil then r[#r+1]=wf.vars.data[i] end i=i+1 end return r}lua"}
