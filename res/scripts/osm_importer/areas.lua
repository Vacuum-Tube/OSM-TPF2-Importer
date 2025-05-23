local forester = require "osm_importer.forester"
local paver = require "osm_importer.paver"
local timer = require"osm_importer.timer"

local a = {}

function a.buildAreas(areas, nodes, options)
	options = options or {}
	timer.start()
	math.randomseed(os.time())  -- so that multiple executions do not create the exact same result
	forester.modelrestest()
	print("Build Forests",#areas.forests)
	a.buildForests(areas.forests, nodes, options)
	print("Build Shrubs",#areas.shrubs)
	a.buildShrubs(areas.shrubs, nodes, options)
	print("Pave Ground Surfaces",#areas.grounds)
	a.paveGroundSurfaces(areas.grounds, nodes, options)
	print(string.format("Time: %.1f s", timer.stop()))
end

function a.buildForests(data, nodes, options)
	for i,forest in pairs(data) do
		if forest.polygon then
			forester.plantPolygon(nodes, forest.polygon, forest.leaf_type or "mixed")
		elseif forest.multipolygon then
			forester.plantMultiPolygon(nodes, forest.multipolygon, forest.leaf_type or "mixed")
		end
	end
end

function a.buildShrubs(data, nodes, options)
	for i,shrub in pairs(data) do
		if shrub.polygon then
			forester.plantPolygon(nodes, shrub.polygon, "shrubs")
		elseif shrub.multipolygon then
			forester.plantMultiPolygon(nodes, shrub.multipolygon, "shrubs")
		end
	end
end

function a.paveGroundSurfaces(data, nodes, options)
	for i,ground in pairs(data) do
		if ground.polygon then
			paver.pavePolygon(nodes, ground.polygon, assert(ground.surface))
		elseif ground.multipolygon and not options.skipMultiPolygons then
			paver.paveMultiPolygon(nodes, ground.multipolygon, assert(ground.surface))
		end
	end
end

return a