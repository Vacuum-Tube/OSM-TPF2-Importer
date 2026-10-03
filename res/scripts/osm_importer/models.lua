local transf = require "transf"
local vec3 = require "vec3"
local constructionutil = require "constructionutil"
local t = require"osm_importer.tools"

local m = {}

m.candidates = {
	tree = { "tree/shingle_oak.mdl" },
	fountain = { "asset/ground/fountain_1.mdl" },
	bollard = {
		"asset/ground/bollard.mdl",
		"asset/industry/industry_barrier.mdl",
		"street/street_barrier.mdl",
		"asset/industry/industry_lamp_old.mdl",
	},
	litfass = {
		"asset/ground/advertising_column.mdl",
		"asset/industry/industry_advertising_column.mdl",
		"asset/ground/column.mdl",
		"asset/industry/industry_chimney_small.mdl",
	},
}

m.models = {
	tree = "tree/shingle_oak.mdl",
	fountain = "asset/ground/fountain_1.mdl",
}

m.postRunFnScript = function()
	for typ, list in pairs(m.candidates) do
		if not m.models[typ] then
			for _, mdl in ipairs(list) do
				if api.res.modelRep.find(mdl)>=0 then
					m.models[typ] = mdl
					break
				end
			end
		end
	end
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
	result.terrainAlignmentLists = { {
		type = "EQUAL",
		faces = {},
	} }
	return result
end

function m.buildObjects(objects)
	m.modelrestest()
	objects = objects or {}
	local n = 0
	for _ in pairs(objects) do
		n = n + 1
	end
	print("Build Objects", n)
	local built = {}
	local skipped = { model = {}, oob = 0, con = 0, fail = 0 }
	for _, data in pairs(objects) do
		if type(data) ~= "table" or not data.pos then
			skipped.fail = skipped.fail + 1
		elseif not m.models[data.type] then
			skipped.model[data.type] = (skipped.model[data.type] or 0) + 1
		elseif not t.isValidCoordinate(data.pos[1], data.pos[2]) then
			skipped.oob = skipped.oob + 1
		else
			local ok = m.buildModel(data.pos, data.type)
			if ok then
				built[data.type] = (built[data.type] or 0) + 1
			else
				skipped.con = skipped.con + 1
			end
		end
	end
	print("Built: "..toString(built))
	if next(skipped.model) or skipped.oob > 0 or skipped.con > 0 or skipped.fail > 0 then
		print("Skipped objects: "..toString(skipped))
	end
end

function m.buildModel(pos, model)
	return m.buildCon(pos, "osm_importer/models/"..model)
end

function m.buildCon(pos, con)
	if type(con) ~= "string" or api.res.constructionRep.find(con) < 0 then
		print("Skip object, construction missing: "..tostring(con))
		return false
	end
	local c = api.type.SimpleProposal.ConstructionEntity.new()
	c.fileName = con
	c.params = {
		seed=0,
		paramX = 0,
		paramY = 0,
	}
	local z = t.safeTerrainZ(pos[1], pos[2], 0)
	local transf = { 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, pos[1], pos[2], z, 1 }
	for i = 1, 16 do
		c.transf[i] = transf[i]
	end
	local p = api.type.SimpleProposal.new()
	p.constructionsToAdd[1] = c
	local ok = pcall(function()
		api.cmd.sendCommand(api.cmd.make.buildProposal(p, nil, true))
	end)
	return ok
end

function m.modelrestest()
	for typ, list in pairs(m.candidates) do
		local found
		for _, mdl in ipairs(list) do
			if api.res.modelRep.find(mdl)>=0 then
				found = mdl
				break
			end
		end
		if found then
			m.models[typ] = found
		else
			print("WARNING Model not found, skip objects of type '"..typ.."'")
			m.models[typ] = nil
		end
	end
end

return m
