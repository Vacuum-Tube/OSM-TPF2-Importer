local forester = require "osm_importer.forester"
local paver = require "osm_importer.paver"
local timer = require "osm_importer.timer"

local a = {}
a.stop = false
local PER_STEP = 6

local function count(list)
	if type(list) ~= "table" then
		return 0
	end
	return #list
end

local function enqueue(seq, kind, list)
	if type(list) ~= "table" then
		return
	end
	for _, rec in pairs(list) do
		if type(rec) == "table" then
			seq[#seq + 1] = { kind = kind, rec = rec }
		end
	end
end

function a.buildOne(kind, rec, nodes, options)
	if kind == "forest" then
		if rec.polygon then
			return forester.plantPolygon(nodes, rec.polygon, rec.leaf_type or "mixed")
		elseif rec.multipolygon then
			return forester.plantMultiPolygon(nodes, rec.multipolygon, rec.leaf_type or "mixed")
		end
	elseif kind == "shrub" then
		if rec.polygon then
			return forester.plantPolygon(nodes, rec.polygon, "shrubs")
		elseif rec.multipolygon then
			return forester.plantMultiPolygon(nodes, rec.multipolygon, "shrubs")
		end
	elseif kind == "ground" then
		if not rec.surface then
			return false, "surface"
		end
		if rec.polygon then
			local id = paver.pavePolygon(nodes, rec.polygon, rec.surface)
			if id == false then
				return false, "fail"
			end
			return id and true or false, "node"
		elseif rec.multipolygon and not (options and options.skipMultiPolygons) then
			paver.paveMultiPolygon(nodes, rec.multipolygon, rec.surface)
			return true
		end
	end
	return false, "fail"
end

function a.buildForests(data, nodes, options)
	for _, forest in pairs(data or {}) do
		a.buildOne("forest", forest, nodes, options)
	end
end

function a.buildShrubs(data, nodes, options)
	for _, shrub in pairs(data or {}) do
		a.buildOne("shrub", shrub, nodes, options)
	end
end

function a.paveGroundSurfaces(data, nodes, options)
	for _, ground in pairs(data or {}) do
		a.buildOne("ground", ground, nodes, options)
	end
end

function a.buildAreas(areas, nodes, options)
	options = options or {}
	a.stop = false
	a.options = options
	a.nodes = nodes or (osmdata and osmdata.nodes) or {}
	areas = areas or (osmdata and osmdata.areas) or {}
	timer.start()
	math.randomseed(os.time())
	if not forester.available then
		print("WARNING: Forester not loaded; skip forests/shrubs")
	else
		forester.modelrestest()
	end
	if not paver.available then
		print("WARNING: Paver not loaded; skip ground surfaces")
	end
	print("Build Forests", count(areas.forests))
	print("Build Shrubs", count(areas.shrubs))
	print("Pave Ground Surfaces", count(areas.grounds))
	a.seq = {}
	if forester.available then
		enqueue(a.seq, "forest", areas.forests)
		enqueue(a.seq, "shrub", areas.shrubs)
	end
	if paver.available then
		enqueue(a.seq, "ground", areas.grounds)
	end
	a.i = 1
	a.built = { forest = 0, shrub = 0, ground = 0 }
	a.skipped = { node = 0, surface = 0, fail = 0 }
	if #a.seq == 0 then
		print("No area polygons to build.")
		print(string.format("Time: %.1f s", timer.stop()))
		return
	end
	a.step()
end

function a.step()
	if a.stop or not a.seq or a.i > #a.seq then
		print("Areas finished. Built:", toString(a.built), "skipped:", toString(a.skipped))
		print(string.format("Time: %.1f s", timer.stop()))
		return
	end
	local n = 0
	while n < PER_STEP and a.seq and a.i <= #a.seq and not a.stop do
		local item = a.seq[a.i]
		a.i = a.i + 1
		n = n + 1
		local ok, why = a.buildOne(item.kind, item.rec, a.nodes, a.options)
		if ok then
			a.built[item.kind] = (a.built[item.kind] or 0) + 1
		else
			local key = why or "fail"
			a.skipped[key] = (a.skipped[key] or 0) + 1
		end
	end
	api.cmd.sendCommand(api.cmd.make.sendScriptEvent("osm_importer.lua", "osm_importer", "areas.step", {}))
end

return a
