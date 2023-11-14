local bt = {}

-- default_type = "cement.lua",  -- Vanilla

------------- Mods

  -- 2858595053 Straßen- und Schienenbaukasten
local pl_cement = "plo_cement.lua" -- vanilla beton, without pillar

  -- ritknat_fachwerke_1    ...??....ich werd hier noch wahnsinnig
local rit_t2v3n = "angier_bridge_t2_v3_n.lua"  -- small railing, low height, no pillar

-- ritknat_gitterbruecke_1
local greengitter = "gitterbruecke_o.lua"

-- Autobahn_Kreuz_1
local autobahn = "Autobahn_aq.lua"  -- 2 thin pillars, green railing

-- 2363493916
local ped_erac = "lollo_freestyle_train_station/pedestrian_basic_no_pillars_era_c.lua"

-- 1939805466
local ang_t1 = "angier_bridge_t1.lua"

-- 2187434173 TFMR2.0 Bridge (Transport Fever Modular Road)
local tfmr = "epbridge_thick.lua"


bt.streettypes = {
	motorway = autobahn,
	motorway_link = autobahn,
	trunk = autobahn,
	trunk_link = autobahn,
	primary = pl_cement,
	primary_link = pl_cement,
	secondary_link = ang_t1,
	secondary = ang_t1,
	tertiary = ang_t1,
	tertiary_link = ang_t1,
	residential = tfmr,
	living_street = tfmr,
	unclassified = ang_t1,
	service = ang_t1,
	construction = tfmr,
	pedestrian = ped_erac,
	track = ped_erac,
	footway = ped_erac,
	path = ped_erac,
	bridleway = ped_erac,
	cycleway = ang_t1,
}

function bt.getType(data)
	if data.track then
		-- return rit_t2v3n
		-- return ang_t1
		return greengitter
	else 
		local btype = bt.streettypes[data.street.type]
		if not btype then
			print("No Bridge Type for street type: "..data.street.type)
		end
		return btype  -- nil if type not in table
	end
end

return bt