local forester = require "osm_importer.forester"
local timer = require"osm_importer.timer"

local a = {}

function a.buildAreas(areas, nodes)
	timer.start()
	print("Build Forests",#areas.forests)
	a.buildForests(areas.forests, nodes)
	print("Build Shrubs",#areas.shrubs)
	a.buildShrubs(areas.shrubs, nodes)
	print(string.format("Time: %.1f s", timer.stop()))
end

function a.buildForests(data, nodes)
	for i,forest in pairs(data) do
		if forest.polygon then
			forester.plantPolygon(nodes, forest.polygon, forest.leaf_type or "mixed")
		elseif forest.multipolygon then
			forester.plantMultiPolygon(nodes, forest.multipolygon, forest.leaf_type or "mixed")
		end
	end
end

function a.buildShrubs(data, nodes)
	for i,shrub in pairs(data) do
		if shrub.polygon then
			forester.plantPolygon(nodes, shrub.polygon, "shrubs")
		elseif shrub.multipolygon then
			forester.plantMultiPolygon(nodes, shrub.multipolygon, "shrubs")
		end
	end
end

return a