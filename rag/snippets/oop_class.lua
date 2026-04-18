-- TASK: класс ООП object oriented class metatables inheritance наследование
local Animal = {}
Animal.__index = Animal

function Animal.new(name, sound)
    local self = setmetatable({}, Animal)
    self.name  = name
    self.sound = sound
    return self
end

function Animal:speak()
    return self.name .. " says " .. self.sound
end

-- Наследование
local Dog = setmetatable({}, {__index = Animal})
Dog.__index = Dog

function Dog.new(name)
    local self = Animal.new(name, "Woof")
    return setmetatable(self, Dog)
end

function Dog:fetch(item)
    return self.name .. " fetches " .. item
end

-- Пример:
-- local d = Dog.new("Rex")
-- print(d:speak())       --> Rex says Woof
-- print(d:fetch("ball")) --> Rex fetches ball
