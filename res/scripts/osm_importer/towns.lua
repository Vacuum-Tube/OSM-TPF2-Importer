local tools = require "osm_importer.tools"

local t = {}
t.stop = false
local PER_STEP = 4

local function dryLand(x, y)
	local okValid, valid = pcall(tools.isValidCoordinate, x, y)
	if not okValid or not valid then
		return false, "oob"
	end
	local okDry, dry = pcall(tools.isOverWater, x, y)
	if not okDry then
		return false, "oob"
	end
	if not dry then
		return false, "water"
	end
	return true
end

function t.createTown(caps, pos, name)
	local town = api.type.TownInfo.new()
	town.name = tostring(name or "")
	town.position = api.type.Vec2f.new(pos[1], pos[2])
	town.initialLandUseCapacities = caps or { 0, 0, 10 }
	local ok = pcall(function()
		api.cmd.sendCommand(api.cmd.make.createTowns({ town }))
	end)
	return ok
end

function t.createTownLabel(pos, name)
	if type(pos) ~= "table" or not pos[1] or not pos[2] then
		return false, "oob"
	end
	if not name or name == "" then
		return false, "fail"
	end
	local ok, why = dryLand(pos[1], pos[2])
	if not ok then
		print("Town " .. tostring(name), why == "water" and "under water!" or ("pos out of map: " .. toString(pos)))
		return false, why
	end
	if not t.createTown({ 0, 0, 10 }, pos, name) then
		print("Create Town, no success !", name)
		return false, "fail"
	end
	return true
end

function t.setAllTownsDevActive(active)
	local towns = game.interface.getEntities({ radius = math.huge }, { type = "TOWN" })
	for _, id in pairs(towns) do
		pcall(game.interface.setTownDevelopmentActive, id, active)
	end
end

local function finish()
	t.setAllTownsDevActive(false)
	local extra = t.extra or {}
	if extra.delEdges or extra.delAssets then
		local ok, bulldoze = pcall(require, "osm_importer.bulldoze")
		if ok and bulldoze then
			if extra.delEdges then
				bulldoze.delEdges()
			end
			if extra.delAssets then
				bulldoze.delAssets()
			end
		end
	end
	print("Towns finished. Built:", t.built or 0, "skipped:", toString(t.skipped or {}))
end

function t.createTownLabels(towns, extra)
	t.stop = false
	t.extra = extra or {}
	t.seq = {}
	towns = towns or (osmdata and osmdata.towns) or {}
	if type(towns) ~= "table" then
		print("No towns in osmdata")
		finish()
		return
	end
	for _, data in pairs(towns) do
		if type(data) == "table" and data.pos and data.name then
			t.seq[#t.seq + 1] = data
		end
	end
	print("Create Town Labels", #t.seq)
	if #t.seq == 0 then
		finish()
		return
	end
	t.i = 1
	t.built = 0
	t.skipped = { oob = 0, water = 0, fail = 0 }
	t.step()
end

function t.step()
	if t.stop or not t.seq or t.i > #t.seq then
		finish()
		return
	end
	local n = 0
	while n < PER_STEP and t.seq and t.i <= #t.seq and not t.stop do
		local rec = t.seq[t.i]
		t.i = t.i + 1
		n = n + 1
		local ok, why = t.createTownLabel(rec.pos, rec.name)
		if ok then
			t.built = t.built + 1
		elseif why then
			t.skipped[why] = (t.skipped[why] or 0) + 1
		end
	end
	api.cmd.sendCommand(api.cmd.make.sendScriptEvent("osm_importer.lua", "osm_importer", "towns.step", {}))
end

return t
