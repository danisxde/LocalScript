-- TASK: число математика math round floor ceil abs min max number arithmetic
-- Математические операции
local val  = wf.vars.amount
local rounded  = math.floor(val + 0.5)
local clamped  = math.max(0, math.min(val, 100))
local absolute = math.abs(val)
return rounded
-- JSON: {"rounded":"lua{return math.floor(wf.vars.amount+0.5)}lua"}
