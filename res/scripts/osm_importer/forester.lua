local okPoly, Polygon = pcall(require, "snowball/common/polygon_1")
local okMulti, MultiPolygon = pcall(require, "snowball/common/multipolygon_1")
local okFor, snowForester = pcall(require, "snowball/forester/forester")

local f = {}
f.available = okPoly and okMulti and okFor and Polygon and MultiPolygon and snowForester
if not f.available then
	print("WARNING: Could not load snowball/forester (Is Forester mod activated?). Forests will be skipped.")
end


-- 2247194383 Spacky_Trees conifers
local spacky = {
	birke_big = "tree/european_birken.mdl",  -- reused ug msh
	birke_small = "tree/european_birken_1.mdl",  -- reused ug msh
	alaska1 = "tree/AlaskaCedar_RT_1.mdl",
	alaska2 = "tree/AlaskaCedar_RT_2.mdl",
	tanne1 = "tree/Spacky_Tanne_pine.mdl",--small
	tanne2 = "tree/Spacky_Tanne_pine2.mdl",--unten dicht
	tanne3 = "tree/Spacky_Tanne_pine3.mdl",--unten dicht
	tanne4 = "tree/Spacky_Tanne_pine4.mdl",
	tanne5 = "tree/Spacky_Tanne_pine5.mdl",
	tanne6 = "tree/Spacky_Tanne_pine6.mdl", --small
}


f.models = {
	mixed = {
		"tree/azalea.mdl",
		"tree/common_hazel.mdl",
		"tree/european_linden.mdl",
		"tree/shingle_oak.mdl",
		"tree/sugar_maple.mdl",
		spacky.birke_big,
		spacky.birke_small,
		"tree/scots_pine.mdl",
	},
	broadleaved = {
		"tree/common_hazel.mdl",
		"tree/european_linden.mdl",
		"tree/shingle_oak.mdl",
		"tree/sugar_maple.mdl",
		spacky.birke_big,
		spacky.birke_small,
	},
	needleleaved = {
		"tree/scots_pine.mdl",
		spacky.tanne1,
		spacky.tanne2,
		spacky.tanne3,
		spacky.tanne4,
		spacky.tanne5,
	},
	shrubs = {
		"tree/azalea.mdl",
		"tree/common_hazel.mdl",
		"tree/elderberry.mdl",
	},
}

f.density = {
	mixed = 150,
	broadleaved = 120,
	needleleaved = 100,
	shrubs = 300,
	__default = 150,
}

function f.getModels(config)
	local models = f.models[config]
	if not models then
		print("ERROR undefined forest leaf_type: "..config)
		models = f.models.mixed
	end
	return models
end

function f.polygonPositions(nodes, polygon)
	local points = {}
	if type(nodes) ~= "table" or type(polygon) ~= "table" then
		return points
	end
	for _, nodeId in pairs(polygon) do
		local node = nodes[nodeId]
		if node and node.pos then
			points[#points + 1] = node.pos
		end
	end
	return points
end

function f.plantPolygon(nodes, polygon, config)
	if not f.available then
		return false
	end
	local models = f.getModels(config)
	if not models or #models == 0 then
		return false
	end
	local points = f.polygonPositions(nodes, polygon)
	if #points < 3 then
		return false
	end
	local ok = pcall(function()
		snowForester.plant2(Polygon:Create(points), f.density[config] or f.density.__default, models, 0.3)
	end)
	return ok
end

function f.plantMultiPolygon(nodes, mp, config)
	if not f.available or type(mp) ~= "table" then
		return false
	end
	local models = f.getModels(config)
	if not models or #models == 0 then
		return false
	end
	local outer, inner = {}, {}
	for i, polygon in pairs(mp.outer or {}) do
		local pts = f.polygonPositions(nodes, polygon)
		if #pts >= 3 then
			outer[#outer + 1] = pts
		end
	end
	for i, polygon in pairs(mp.inner or {}) do
		local pts = f.polygonPositions(nodes, polygon)
		if #pts >= 3 then
			inner[#inner + 1] = pts
		end
	end
	if #outer == 0 then
		return false
	end
	local ok = pcall(function()
		snowForester.plant2(MultiPolygon:Create(outer, inner), f.density[config] or f.density.__default, models, 0.3)
	end)
	return ok
end

function f.modelrestest()
	if not f.available then
		return
	end
	for catg, mdls in pairs(f.models) do
		local keep = {}
		for i, mdl in pairs(mdls) do
			if api.res.modelRep.find(mdl)<0 then
				print("WARNING: tree model missing, skip: '"..mdl.."'")
			else
				table.insert(keep, mdl)
			end
		end
		if #keep == 0 then
			print("WARNING: no tree models left for "..catg)
		end
		f.models[catg] = keep
	end
end

return f
