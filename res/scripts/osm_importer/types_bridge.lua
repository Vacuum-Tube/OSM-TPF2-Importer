local tools = require "osm_importer.tools"

local bt = {}

local vanilla = {
	street = "cement.lua",
	track = "iron.lua",
	ped = "stone.lua",
}

bt.streettypes = {
	motorway = { "epbridge_thick.lua", "angier_bridge_t1.lua", vanilla.street },
	trunk = { "epbridge_thick.lua", "angier_bridge_t1.lua", vanilla.street },
	motorway_link = { "epbridge_thin.lua", vanilla.street },
	trunk_link = { "epbridge_thin.lua", vanilla.street },
	primary = { "angier_bridge_t1.lua", "epbridge_thick.lua", vanilla.street },
	secondary = { "angier_bridge_t1.lua", "epbridge_thick.lua", vanilla.street },
	tertiary = { "angier_bridge_t1.lua", vanilla.street },
	primary_link = { "epbridge_thin.lua", vanilla.street },
	secondary_link = { "epbridge_thin.lua", vanilla.street },
	tertiary_link = { "epbridge_thin.lua", vanilla.street },
	residential = { "epbridge_thick.lua", vanilla.street },
	living_street = { "epbridge_thick.lua", vanilla.street },
	unclassified = { "angier_bridge_t1.lua", vanilla.street },
	service = { "angier_bridge_t1.lua", vanilla.street },
	construction = { "epbridge_thick.lua", vanilla.street },
	pedestrian = { "lollo_freestyle_train_station/pedestrian_basic_no_pillars_era_c.lua", vanilla.ped },
	track = { "lollo_freestyle_train_station/pedestrian_basic_no_pillars_era_c.lua", vanilla.ped },
	footway = { "lollo_freestyle_train_station/pedestrian_basic_no_pillars_era_c.lua", vanilla.ped },
	path = { "lollo_freestyle_train_station/pedestrian_basic_no_pillars_era_c.lua", vanilla.ped },
	bridleway = { vanilla.ped },
	cycleway = { "angier_bridge_t1.lua", vanilla.street },
}

function bt.getType(data)
	if data.track then
		return tools.pick("bridge",
			"vienna_fever_infra_leere_bruecke.lua",
			"iron.lua",
			vanilla.track
		)
	end
	local street = data.street or {}
	local cands = bt.streettypes[street.type]
	if type(cands) == "table" then
		return tools.pick("bridge", table.unpack(cands))
	end
	return tools.pick("bridge", vanilla.street)
end

return bt
