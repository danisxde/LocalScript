-- TASK: построить объект table build object создать структуру собрать объект result
-- Построить результирующий объект из нескольких переменных
local result = {
    id      = wf.vars.userId,
    name    = wf.vars.firstName .. " " .. wf.vars.lastName,
    score   = wf.vars.score,
    active  = wf.vars.score > 0
}
return result
-- JSON: {"profile":"lua{return {id=wf.vars.userId,name=wf.vars.firstName..\" \"..wf.vars.lastName,score=wf.vars.score,active=wf.vars.score>0}}lua"}
