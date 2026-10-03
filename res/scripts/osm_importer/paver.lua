local okPoly, Polygon = pcall(require, "paver.polygon")
local okPaver, paverMod = pcall(require, "paver.main")

local p = {}
p.available = okPoly and okPaver and Polygon and paverMod
if not p.available then
	print("WARNING: Could not load Paver (Is Paver mod activated?). Ground surfaces will be skipped.")
end

-- https://wiki.openstreetmap.org/wiki/DE:Key:landuse
-- https://wiki.openstreetmap.org/wiki/DE:Key:natural
-- https://wiki.openstreetmap.org/wiki/DE:Key:surface

p.groundTextures = {
	paved = "asphalt1",
	asphalt = "asphalt4",
	concrete = "asphalt5",
	ground = "dirt",
	dirt = "dirt",
	earth = "dirt",
	mud = "soil",
	unpaved = "gravel4",
	compacted = "gravel2",
	fine_gravel = "gravel2",
	gravel = "gravel2",
	rock = "rock",
	pebblestone = "scree",
	shingle = "scree",  -- Geröll
	sand = "mt_strand2",  -- mod: Mariotator Ground Tex 4
	beach = "mt_strand1",  -- mod: Mariotator Ground Tex 4
	sett = "ingo_kopfstein",  -- mod: ingo pavement
	cobblestone = "ingo_kopfstein",  -- mod: ingo pavement
	unhewn_cobblestone = "ingo_naturstein",  -- mod: ingo pavement
	paving_stones = "ingo_pflaster",  -- mod: ingo pavement
 	bricks = "ingo_pflaster",  -- mod: ingo pavement
	grass_paver = "mt_pflaster3",  -- mod: Mariotator Ground Tex 1
	grass = "grass_cutted1",
	flowerbed = "sunflower",
	animal_keeping = "grass_dirt",
	brownfield = "grass_brown",
	farmyard = "dirt",
	farmland = {  -- one of these is used by random each time
		"soil", 
		"wheat", 
		"corn", 
		"barley", 
		"corn2",  -- mod: NEP
		"barley2", 
		"oat", 
		"potato", 
		"rape", 
		"mt_spargel1",  -- mod: Mariotator Ground Tex 1
		-- "mt_acker_trocken1", -- mod: Mariotator Ground Tex 4
		-- "wheatfeild", -- mod: Farm land textures (JamesT85Gaming)
		-- "plowedfeidl", -- mod: Farm land textures (JamesT85Gaming)
		"ingo_trockenes_gras", -- mod: Ingo Vegetation Extended
	},
	-- orchard
	-- allotments
	-- vineyard
	-- meadow = "",  -- high grass -> default
	-- heath 
	railway = "ballast",
	quarry = "dirt",
	construction = "dirt",
	-- residential
	retail = "ingo_pflaster",  -- mod: ingo pavement
	education = "asphalt1",
	commercial = "asphalt1",
	industrial = "asphalt2",
	golf_fairway = "grass_cutted1",
	golf_green = "grass_cutted2",
	golf_bunker = "mt_strand1",  -- mod: Mariotator Ground Tex 4
	water = "water_dirty",
}

function p.polygonPositions(nodes, polygon)
	local points = {}
	if type(nodes) ~= "table" or type(polygon) ~= "table" then
		return points
	end
	local last = #polygon
	for i, nodeId in pairs(polygon) do
		if i ~= last then
			local node = nodes[nodeId]
			if node and node.pos then
				points[#points + 1] = node.pos
			end
		end
	end
	return points
end

function p.getTexType(surface)
	local groundTex = p.groundTextures[surface]
	if type(groundTex)=="table" then
		groundTex = groundTex[math.random(#groundTex)]
	end
	return groundTex
end


function p.pavePolygon(nodes, polygon, surface)
	if not p.available then
		return
	end
	local groundTex = p.getTexType(surface)
	if not groundTex then
		return
	end
	local points = p.polygonPositions(nodes, polygon)
	if #points < 3 then
		return false
	end
	local id
	local ok = pcall(function()
		id = paverMod.pave(Polygon:Create(points), groundTex)
	end)
	if not ok then
		return false
	end
	if id then
		pcall(game.interface.setName, id, "OSM surface=" .. tostring(surface))
		return id
	end
	return false
end

function p.paveMultiPolygon(nodes, mp, surface)
	if not p.available or type(mp) ~= "table" then
		return
	end
	for _, polygon in pairs(mp.outer or {}) do
		p.pavePolygon(nodes, polygon, surface)
	end
end

-- function p.res_test()  -- can only check the ground_texture file (in paver) but not the actual terrain texture from mod
	-- for key, gtexs in pairs(p.groundTextures) do
		-- for _,gtex in pairs(type(gtexs)=="string" and {gtexs} or gtexs) do
			-- if api.res.groundTextureRep.find(gtex)<0 then
				-- error("GroundTexture not found: '"..gtex.."' (Mod missing?)")
			-- end
		-- end
	-- end
-- end

return p