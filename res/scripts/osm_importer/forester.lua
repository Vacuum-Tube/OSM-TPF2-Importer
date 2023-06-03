local forester = require "snowball/forester/forester"
local Polygon = require "snowball/common/polygon_1"
local MultiPolygon = require "snowball/common/multipolygon_1"

local f = {}

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
		-- spacky.tanne2,  -- careful with performance
		-- spacky.tanne4,
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
-- f.density = {  -- test
	-- mixed = 40,
	-- broadleaved = 40,
	-- shrubs = 70,
	-- __default = 150,
-- }

function f.getModels(config)
	local models = f.models[config]
	if not models then
		print("ERROR undefined forest leaf_type: "..config)
		models = f.models.mixed
	end
	return models
end

function f.polygonPositions(nodes,polygon)
	local points = {}
	for i,nodeId in pairs(polygon) do
		table.insert(points, assert(assert(nodes[nodeId] or print(nodeId)).pos or print(nodeId)) )
	end
	return points
end

function f.plantPolygon(nodes,polygon,config)
	forester.plant2(Polygon:Create(f.polygonPositions(nodes,polygon)), f.density[config] or f.density.__default, f.getModels(config), 0.3)
end

function f.plantMultiPolygon(nodes,mp,config)
	local outer,inner = {},{}
	for i,polygon in pairs(mp.outer) do
		outer[i] = f.polygonPositions(nodes,polygon)
	end
	for i,polygon in pairs(mp.inner) do
		inner[i] = f.polygonPositions(nodes,polygon)
	end
	forester.plant2(MultiPolygon:Create(outer, inner), f.density[config] or f.density.__default, f.getModels(config), 0.3)
end

return f