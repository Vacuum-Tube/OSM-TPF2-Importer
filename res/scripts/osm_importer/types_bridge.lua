local bt = {}

-- default_type = "cement.lua",  -- Vanilla

------------- Mods

-- Autobahn_Kreuz_1
local autobahn = "Autobahn_aq.lua"  -- 2 thin pillars, green railing

-- 2187434173 TFMR2.0 Bridge (Transport Fever Modular Road)
local tfmr = {
	thick = "epbridge_thick.lua",
	thin = "epbridge_thin.lua",
	nopillar = "epbridge_no_pillar.lua",
}

-- 2363493916
local ped_erac = "lollo_freestyle_train_station/pedestrian_basic_no_pillars_era_c.lua"  -- flat

-- 1939805466
local ang_t1 = "angier_bridge_t1.lua"  -- grey concrete, pillar

-- ritknat_gitterbruecke_1
local greengitter = "gitterbruecke_o.lua"  -- no pillar, medium flat

-- ritknat_fachwerke_1
-- local rit_t2v3n = "angier_bridge_t2_v3_n.lua"  -- no railing, no pillar

-- 2858595053 Straßen- und Schienenbaukasten
-- local pl_cement = "plo_cement.lua" -- vanilla beton, without pillar


bt.streettypes = {
	motorway = autobahn,
	trunk = autobahn,
	motorway_link = tfmr.thin,
	trunk_link = tfmr.thin,
	primary = ang_t1,
	secondary = ang_t1,
	tertiary = ang_t1,
	primary_link = tfmr.thin,
	secondary_link = tfmr.thin,
	tertiary_link = tfmr.thin,
	residential = tfmr.thick,
	living_street = tfmr.thick,
	unclassified = ang_t1,
	service = ang_t1,
	construction = tfmr.thick,
	pedestrian = ped_erac,
	track = ped_erac,
	footway = ped_erac,
	path = ped_erac,
	bridleway = ped_erac,
	cycleway = ang_t1,
}

function bt.getType(data)
	if data.track then
		if data.track.speed and data.track.speed>120 then
			return ang_t1
		else
			return greengitter
		end
	else 
		local btype = bt.streettypes[data.street.type]
		if not btype then
			print("No Bridge Type for street type: "..data.street.type)
		end
		return btype  -- nil if type not in table
	end
end

return bt