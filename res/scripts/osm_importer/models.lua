local transf = require "transf"
local vec3 = require "vec3"
local constructionutil = require "constructionutil"
local t = require"osm_importer.tools"

local m = {}

m.models = {
	tree = "tree/shingle_oak.mdl",
	fountain = "asset/ground/fountain_1.mdl",
	bollard = "asset/connum_poller_gehweg_rund_1.mdl",  -- 1963592311 Connum's German Traffic Assets
	litfass = "asset/sab_LitV2_3.mdl",  -- sabon_litfass_era_c_1
}

m.postRunFnScript = function()
	for model,mdlfile in pairs(m.models) do
		local con = api.type.ConstructionDesc.new()
		con.type = api.type.enum.ConstructionType.ASSET_DEFAULT
		con.description.name = model
		con.description.description = _("Build your construction")
		con.preProcessScript.fileName = "construction/osm_importer_models.updateFn"
		con.createTemplateScript.fileName = "construction/osm_importer_models.updateFn"
		con.upgradeScript.fileName = "construction/osm_importer_models.updateFn"
		con.updateScript.fileName = "construction/osm_importer_models.updateFn"
		con.updateScript.params = {
			model = model,
			mdl = mdlfile,
		}
		api.res.constructionRep.add("osm_importer/models/"..model, con, false)
	end
end

m.updateFnScript = function(constrParams,scriptParams)
	local result = { }
	result.models = { {
		id = scriptParams.mdl,
		transf = constructionutil.rotateTransf(constrParams, transf.scaleRotZYXTransl(
			vec3.new(1, 1, 1),
			vec3.new(math.rad(0), math.atan(0/1000), 0),
			vec3.new(0, 0, 0) 
		))
	} }
	result.terrainAlignmentLists = { {  -- otherwise BoundingBox is used
		type = "EQUAL",
		faces = {},
	} }
	-- result.groundFaces = { {  -- asset clickable
		-- face = { { 0, 0 }, { 0, 0.01 }, { 0.01, 0 } },
		-- modes = { { type = "FILL", key = "none.lua" } },
	-- } }
	return result
end

function m.buildObjects(objects)
	m.modelrestest()
	print("Build Objects", #objects)
	local built = {}
	for i,data in pairs(objects) do
		assert(m.models[data.type], "No mdl for type: "..data.type)
		m.buildModel(data.pos, data.type)
		built[data.type] = (built[data.type] or 0) + 1
	end
	print("Built: "..toString(built))
end

function m.buildModel(pos, model)
	m.buildCon(pos, "osm_importer/models/"..model)
end

function m.buildCon(pos, con)
	assert(api.res.constructionRep.find(con)>=0, "con not found: "..con)
	local c = api.type.SimpleProposal.ConstructionEntity.new()
	c.fileName = con
	-- c.playerEntity=api.engine.util.getPlayer()
	c.params = {
		seed=0,
		paramX = 0,
		paramY = 0,
	}
	local transf = { 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, pos[1], pos[2], t.getTerrainZ(pos[1], pos[2]), 1 }
	for i = 1, 16 do
		c.transf[i] = transf[i]
	end
	local p = api.type.SimpleProposal.new()
	p.constructionsToAdd[1] = c
	api.cmd.sendCommand(api.cmd.make.buildProposal(p, context, ignoreErrors~=false))
end

function m.modelrestest()
	for i, mdl in pairs(m.models) do
		if api.res.modelRep.find(mdl)<0 then
			error("Model not found: '"..mdl.."' (Mod missing?)")
		end
	end
end

return m