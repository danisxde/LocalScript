-- TASK: строковые операции string length upper lower sub find содержит проверка строки
-- Строковые операции над wf.vars (стандартные Lua string.*)
local s = wf.vars.inputText
local length  = #s
local upper   = string.upper(s)
local lower   = string.lower(s)
local trimmed = string.match(s, "^%s*(.-)%s*$")
local has_at  = string.find(s, "@") ~= nil
return has_at
-- JSON: {"hasAt":"lua{return string.find(wf.vars.inputText,\"@\")~=nil}lua"}
