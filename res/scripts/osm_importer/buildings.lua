local tools = require "osm_importer.tools"
local transf = require "transf"
local vec3 = require "vec3"
local constructionutil = require "constructionutil"

local b = {}
b.stop = false
b.CON = "osm_importer/footprint_building"

local PARCEL_M = 8
local PER_STEP = 8
local LAND = {
	residential = "RESIDENTIAL",
	commercial = "COMMERCIAL",
	industrial = "INDUSTRIAL",
}
local KIND = {
	res = "RESIDENTIAL",
	com = "COMMERCIAL",
	ind = "INDUSTRIAL",
}

local function options()
	return osm_importer.options or {}
end

local function landKey(raw)
	if raw == nil then
		return nil
	end
	if type(raw) == "number" then
		return ({ [0] = "RESIDENTIAL", [1] = "COMMERCIAL", [2] = "INDUSTRIAL" })[raw]
	end
	local s = string.upper(tostring(raw))
	if s:find("RESIDENT", 1, true) then
		return "RESIDENTIAL"
	end
	if s:find("COMMER", 1, true) then
		return "COMMERCIAL"
	end
	if s:find("INDUSTR", 1, true) then
		return "INDUSTRIAL"
	end
end

local function parcelWH(ps)
	if not ps then
		return nil
	end
	local w = tonumber(ps[1] or ps.x)
	local d = tonumber(ps[2] or ps.y)
	if w and d and w > 0 and d > 0 then
		return w, d
	end
end

local function parseResName(file)
	if type(file) ~= "string" then
		return
	end
	local era, kind, level, w, d = file:match("era_([abc])/([a-z]+)_([0-9]+)_([0-9]+)x([0-9]+)")
	if not kind then
		return
	end
	local land = KIND[kind]
	if land then
		return land, tonumber(w), tonumber(d), tonumber(level), era
	end
end

local function mdlFromCon(file)
	local base = file:gsub("%.con$", "")
	local padded = base:gsub("_(%d+)$", function(n)
		return string.format("_%02d", tonumber(n) or 0)
	end)
	local tries = {
		base .. ".mdl",
		padded .. ".mdl",
		base:gsub("^building/", "") .. ".mdl",
		padded:gsub("^building/", "") .. ".mdl",
	}
	for _, mdl in ipairs(tries) do
		if api.res.modelRep.find(mdl) >= 0 then
			return mdl
		end
	end
end

local function addCandidate(catalog, land, w, d, level, era, mdl)
	if not (catalog[land] and mdl) then
		return
	end
	catalog[land][#catalog[land] + 1] = {
		mdl = mdl,
		w = w,
		d = d,
		level = tonumber(level) or 1,
		era = era or "c",
	}
end

function b.postRunFnScript()
	local con = api.type.ConstructionDesc.new()
	con.type = api.type.enum.ConstructionType.ASSET_DEFAULT
	con.description.name = "OSM footprint building"
	con.description.description = "Placed from OSM house / shop / industry footprints"
	con.preProcessScript.fileName = "construction/osm_importer_buildings.updateFn"
	con.createTemplateScript.fileName = "construction/osm_importer_buildings.updateFn"
	con.upgradeScript.fileName = "construction/osm_importer_buildings.updateFn"
	con.updateScript.fileName = "construction/osm_importer_buildings.updateFn"
	con.updateScript.params = { kind = "building" }
	api.res.constructionRep.add(b.CON, con, false)
end

function b.updateFnScript(constrParams, scriptParams)
	local mdl = constrParams and constrParams.mdl
	local result = {
		models = {},
		terrainAlignmentLists = { { type = "EQUAL", faces = {} } },
	}
	if type(mdl) ~= "string" or mdl == "" then
		return result
	end
	if api.res.modelRep.find(mdl) < 0 then
		return result
	end
	result.models[1] = {
		id = mdl,
		transf = constructionutil.rotateTransf(constrParams, transf.scaleRotZYXTransl(
			vec3.new(1, 1, 1),
			vec3.new(0, 0, 0),
			vec3.new(0, 0, 0)
		)),
	}
	return result
end

function b.collectCatalog()
	local catalog = {
		RESIDENTIAL = {},
		COMMERCIAL = {},
		INDUSTRIAL = {},
	}
	local seenMdl = {}

	local function considerMdl(mdl, land, w, d, level, era)
		if type(mdl) ~= "string" or seenMdl[mdl] then
			return
		end
		if api.res.modelRep.find(mdl) < 0 then
			return
		end
		if not (land and w and d) then
			land, w, d, level, era = parseResName(mdl)
		end
		if land and w and d then
			seenMdl[mdl] = true
			addCandidate(catalog, land, w, d, level, era, mdl)
		end
	end

	local okModels, models = pcall(function()
		return api.res.modelRep.getAll()
	end)
	if okModels and type(models) == "table" then
		for _, file in pairs(models) do
			if type(file) == "string" and file:find("era_", 1, true) then
				considerMdl(file)
			end
		end
	end

	local okAll, all = pcall(function()
		return api.res.constructionRep.getAll()
	end)
	if okAll and type(all) == "table" then
		for _, file in pairs(all) do
			if type(file) == "string" then
				local land, w, d, level, era
				local idx = api.res.constructionRep.find(file)
				if idx >= 0 then
					local ok, desc = pcall(api.res.constructionRep.get, idx)
					if ok and desc and desc.type == api.type.enum.ConstructionType.TOWN_BUILDING and desc.townBuildingParams then
						local p = desc.townBuildingParams
						land = landKey(p.landUseType)
						w, d = parcelWH(p.parcelSize)
						level = tonumber(p.level)
					end
				end
				if not (land and w and d) then
					land, w, d, level, era = parseResName(file)
				elseif not era then
					local _, _, _, _, e = parseResName(file)
					era = e
				end
				if land and w and d then
					considerMdl(mdlFromCon(file), land, w, d, level, era)
				end
			end
		end
	end

	if #(catalog.RESIDENTIAL) + #(catalog.COMMERCIAL) + #(catalog.INDUSTRIAL) == 0 then
		for _, era in ipairs({ "c", "b", "a" }) do
			for prefix, land in pairs(KIND) do
				for level = 1, 3 do
					for w = 1, 5 do
						for d = 1, 5 do
							for _, suf in ipairs({ "01", "02", "03", "1", "2" }) do
								considerMdl(string.format("building/era_%s/%s_%d_%dx%d_%s.mdl", era, prefix, level, w, d, suf), land, w, d, level, era)
							end
						end
					end
				end
			end
		end
	end
	return catalog
end

local function tpfLevel(osmLevels)
	local n = tonumber(osmLevels)
	if not n then
		return nil
	end
	if n <= 2 then
		return 1
	end
	if n <= 5 then
		return 2
	end
	return 3
end

local function sizeError(pw, pd, width, depth)
	local e1 = math.abs(pw * PARCEL_M - width) + math.abs(pd * PARCEL_M - depth)
	local e2 = math.abs(pw * PARCEL_M - depth) + math.abs(pd * PARCEL_M - width)
	if e2 < e1 then
		return e2, true
	end
	return e1, false
end

function b.pickConstruction(catalog, bldg)
	local land = LAND[bldg.purpose]
	local list = land and catalog[land]
	if not list or #list == 0 then
		return
	end
	local wantLevel = tpfLevel(bldg.levels)
	local maxErr = math.max(8, 0.45 * math.min(bldg.width, bldg.depth))
	local best, bestScore
	for _, cand in ipairs(list) do
		local err, rotated = sizeError(cand.w, cand.d, bldg.width, bldg.depth)
		if err <= maxErr then
			local score = err
			if wantLevel and cand.level == wantLevel then
				score = score - 3
			elseif wantLevel then
				score = score + math.abs((cand.level or 1) - wantLevel)
			end
			if cand.era == "c" then
				score = score - 0.5
			elseif cand.era == "a" then
				score = score + 1
			end
			if not bestScore or score < bestScore then
				bestScore = score
				best = {
					mdl = cand.mdl,
					w = cand.w,
					d = cand.d,
					level = cand.level,
					era = cand.era,
					rotated = rotated,
				}
			end
		end
	end
	return best
end

local function headingTransf(x, y, z, heading, sx, sy)
	sx = sx or 1
	sy = sy or 1
	local c = math.cos(heading)
	local s = math.sin(heading)
	return {
		c * sx, s * sx, 0, 0,
		-s * sy, c * sy, 0, 0,
		0, 0, 1, 0,
		x, y, z, 1,
	}
end

function b.buildOne(bldg, cand)
	if not tools.isValidCoordinate(bldg.pos[1], bldg.pos[2]) then
		return false, "oob"
	end
	if not tools.isOverWater(bldg.pos[1], bldg.pos[2]) then
		return false, "water"
	end
	if type(cand.mdl) ~= "string" or api.res.modelRep.find(cand.mdl) < 0 then
		return false, "size"
	end
	local heading = bldg.heading or 0
	local osmW, osmD = bldg.width, bldg.depth
	if cand.rotated then
		heading = heading + math.pi * 0.5
		osmW, osmD = osmD, osmW
	end
	local nativeW = cand.w * PARCEL_M
	local nativeD = cand.d * PARCEL_M
	local sx = nativeW > 0.1 and math.max(0.7, math.min(1.35, osmW / nativeW)) or 1
	local sy = nativeD > 0.1 and math.max(0.7, math.min(1.35, osmD / nativeD)) or 1
	local z = tools.safeTerrainZ(bldg.pos[1], bldg.pos[2], 0)
	local tf = headingTransf(bldg.pos[1], bldg.pos[2], z, heading, sx, sy)
	local params = {
		mdl = cand.mdl,
		seed = math.floor(((bldg.pos[1] % 1000) * 17 + (bldg.pos[2] % 1000) * 31) % 100000),
		paramX = 0,
		paramY = 0,
	}
	local ok, err = pcall(function()
		game.interface.buildConstruction(b.CON, params, tf)
	end)
	if not ok then
		return false, "fail"
	end
	return true
end

function b.progressWindow()
	local pb = api.gui.comp.ProgressBar.new()
	local window = api.gui.comp.Window.new("Buildings (script continues if closed)", pb)
	window:addHideOnCloseHandler()
	pb:setMinimumSize(api.gui.util.Size.new(500, 10))
	return pb
end

function b.buildBuildings(buildings, opts)
	opts = opts or options()
	osm_importer.options = opts
	b.stop = false
	buildings = buildings or (osmdata and osmdata.buildings) or {}
	if type(buildings) ~= "table" or #buildings == 0 then
		print("No buildings in osmdata. Download OSM again (houses/shops/industry) and convert, then Install.")
		return
	end
	if api.res.constructionRep.find(b.CON) < 0 then
		print("OSM footprint construction missing. Restart the game after updating the OSM Importer mod.")
		return
	end
	local catalog = b.collectCatalog()
	print(string.format(
		"Building models: res %d / com %d / ind %d",
		#(catalog.RESIDENTIAL or {}),
		#(catalog.COMMERCIAL or {}),
		#(catalog.INDUSTRIAL or {})
	))
	if #(catalog.RESIDENTIAL) + #(catalog.COMMERCIAL) + #(catalog.INDUSTRIAL) == 0 then
		print("No matching TPF2 house/shop/industry models found; skip buildings.")
		return
	end
	local allowed = {
		residential = opts.build_buildings_residential ~= false,
		commercial = opts.build_buildings_commercial ~= false,
		industrial = opts.build_buildings_industrial ~= false,
	}
	local seq = {}
	local skippedPurpose = 0
	for _, rec in ipairs(buildings) do
		if rec and rec.purpose and allowed[rec.purpose] then
			seq[#seq + 1] = rec
		else
			skippedPurpose = skippedPurpose + 1
		end
	end
	print("Build Buildings", #seq, "skipped purpose/off", skippedPurpose)
	if #seq == 0 then
		return
	end
	b.seq = seq
	b.catalog = catalog
	b.i = 1
	b.built = { residential = 0, commercial = 0, industrial = 0 }
	b.skipped = { size = 0, fail = 0, oob = 0 }
	b.pb = b.progressWindow()
	b.step()
end

function b.step()
	if b.stop or not b.seq or b.i > #b.seq then
		if b.pb then
			pcall(function()
				b.pb:getParent():getParent():remove()
			end)
			b.pb = nil
		end
		print("Buildings finished. Built:", toString(b.built), "skipped:", toString(b.skipped))
		return
	end
	local n = 0
	while n < PER_STEP and b.seq and b.i <= #b.seq and not b.stop do
		local rec = b.seq[b.i]
		b.i = b.i + 1
		n = n + 1
		if b.pb then
			b.pb:setProgress((b.i - 1) / #b.seq)
			b.pb:setTask((rec.purpose or "?") .. " " .. (rec.name or ""))
		end
		local cand = b.pickConstruction(b.catalog, rec)
		if not cand then
			b.skipped.size = b.skipped.size + 1
		else
			local ok, why = b.buildOne(rec, cand)
			if ok then
				b.built[rec.purpose] = (b.built[rec.purpose] or 0) + 1
			elseif why == "oob" or why == "water" then
				b.skipped.oob = b.skipped.oob + 1
			elseif why == "size" then
				b.skipped.size = b.skipped.size + 1
			else
				b.skipped.fail = b.skipped.fail + 1
			end
		end
	end
	api.cmd.sendCommand(api.cmd.make.sendScriptEvent("osm_importer.lua", "osm_importer", "buildings.step", {}))
end

return b
