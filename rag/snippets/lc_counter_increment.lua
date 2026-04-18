-- TASK: счётчик попыток увеличить переменную на единицу increment counter try_count iteration counter
-- TAGS: counter, increment, number, wf.vars, iteration, retry

return wf.vars.try_count_n + 1

-- JSON: {"try_count_n":"lua{return wf.vars.try_count_n + 1}lua"}
