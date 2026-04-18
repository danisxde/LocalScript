-- TASK: создать новый массив array new push добавить элемент collect собрать
-- Создание нового массива и добавление элементов
local result = _utils.array.new()
for i = 1, #wf.vars.items do
    if wf.vars.items[i].active == true then
        result[#result + 1] = wf.vars.items[i].name
    end
end
return result
-- JSON: {"activeNames":"lua{local r=_utils.array.new() for i=1,#wf.vars.items do if wf.vars.items[i].active==true then r[#r+1]=wf.vars.items[i].name end end return r}lua"}
