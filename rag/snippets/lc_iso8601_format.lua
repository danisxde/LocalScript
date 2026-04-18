-- TASK: преобразовать дату время из формата YYYYMMDD HHMMSS в ISO 8601 format datetime convert date string
-- TAGS: date, time, ISO8601, string.format, string.sub, wf.vars, datetime, format, convert

DATUM = wf.vars.json.IDOC.ZCDF_HEAD.DATUM
TIME = wf.vars.json.IDOC.ZCDF_HEAD.TIME

local function safe_sub(str, start, finish)
    local s = string.sub(str, start, math.min(finish, #str))
    return s ~= "" and s or "00"
end

year   = safe_sub(DATUM, 1, 4)
month  = safe_sub(DATUM, 5, 6)
day    = safe_sub(DATUM, 7, 8)
hour   = safe_sub(TIME, 1, 2)
minute = safe_sub(TIME, 3, 4)
second = safe_sub(TIME, 5, 6)

iso_date = string.format(
    '%s-%s-%sT%s:%s:%s.00000Z',
    year, month, day,
    hour, minute, second
)
return iso_date

-- Шаблон: DATUM содержит "YYYYMMDD", TIME содержит "HHMMSS"
-- Результат: "2023-10-15T15:30:00.00000Z"
-- JSON: {"time":"lua{DATUM = wf.vars.json.IDOC.ZCDF_HEAD.DATUM\nTIME = wf.vars.json.IDOC.ZCDF_HEAD.TIME\nlocal function safe_sub(str, start, finish)\n\tlocal s = string.sub(str, start, math.min(finish, #str))\n\treturn s ~= \"\" and s or \"00\"\nend\nyear = safe_sub(DATUM, 1, 4)\nmonth = safe_sub(DATUM, 5, 6)\nday = safe_sub(DATUM, 7, 8)\nhour = safe_sub(TIME, 1, 2)\nminute = safe_sub(TIME, 3, 4)\nsecond = safe_sub(TIME, 5, 6)\niso_date = string.format('%s-%s-%sT%s:%s:%s.00000Z', year, month, day, hour, minute, second)\nreturn iso_date\n}lua"}
