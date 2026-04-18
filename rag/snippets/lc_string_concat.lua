-- TASK: конкатенация строк string concat соединить строки fullname имя фамилия
-- Склейка строк из wf.vars
local firstName = wf.vars.firstName
local lastName  = wf.vars.lastName
return firstName .. " " .. lastName
-- JSON: {"fullName":"lua{return wf.vars.firstName .. \" \" .. wf.vars.lastName}lua"}
