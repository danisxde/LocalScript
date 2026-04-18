-- TASK: получить последний элемент массива last element get last item from list emails
-- TAGS: array, last, index, wf.vars, list

return wf.vars.emails[#wf.vars.emails]

-- JSON: {"lastEmail":"lua{return wf.vars.emails[#wf.vars.emails]}lua"}
