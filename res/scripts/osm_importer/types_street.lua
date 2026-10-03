local tools = require"osm_importer.tools"

local st = {}

st.fallback_type = "standard/town_small_new.lua"
st.small_type = "standard/town_small_new.lua"

local vanilla = {
	town_small = "standard/town_small_new.lua",
	town_medium = "standard/town_medium_new.lua",
	town_large = "standard/town_large_new.lua",
	town_xlarge = "standard/town_x_large_new.lua",
	town_small_ow = "standard/town_small_one_way_new.lua",
	town_medium_ow = "standard/town_medium_one_way_new.lua",
	town_large_ow = "standard/town_large_one_way_new.lua",
	town_small_old = "standard/town_small_old.lua",
	town_medium_old = "standard/town_medium_old.lua",
	country_small = "standard/country_small_new.lua",
	country_medium = "standard/country_medium_new.lua",
	country_large = "standard/country_large_new.lua",
	country_xlarge = "standard/country_x_large_new.lua",
	country_small_ow = "standard/country_small_one_way_new.lua",
	country_medium_ow = "standard/country_medium_one_way_new.lua",
	country_large_ow = "standard/country_large_one_way_new.lua",
	runway = "airport/airport_runway_medium.lua",
	taxi = "airport/airport_taxiway_medium.lua",
}

function st.vanillaFor(street)
	local typ = street and street.type
	local ow = street and street.oneway
	if typ == "motorway" or typ == "trunk" then
		return ow and vanilla.country_large_ow or vanilla.country_xlarge
	elseif typ == "motorway_link" or typ == "trunk_link" then
		return ow and vanilla.country_medium_ow or vanilla.country_large
	elseif typ == "primary" or typ == "secondary" or typ == "primary_link" or typ == "secondary_link" then
		if street.country ~= false then
			return ow and vanilla.country_medium_ow or vanilla.country_medium
		end
		return ow and vanilla.town_medium_ow or vanilla.town_large
	elseif typ == "tertiary" or typ == "tertiary_link" then
		return ow and vanilla.town_small_ow or vanilla.town_medium
	elseif typ == "residential" or typ == "living_street" or typ == "service" then
		if street.surface == "cobblestone" or street.surface == "sett" then
			return vanilla.town_small_old
		end
		return ow and vanilla.town_small_ow or vanilla.town_small
	elseif typ == "unclassified" or typ == "track" then
		return vanilla.country_small
	elseif typ == "path" or typ == "footway" or typ == "cycleway" or typ == "bridleway" or typ == "pedestrian" or typ == "steps" or typ == "platform" then
		return vanilla.town_small
	elseif typ == "construction" then
		return vanilla.town_small
	elseif typ == "raceway" then
		return vanilla.country_small_ow
	elseif typ == "aeroway" then
		return (street.subtype == "runway") and vanilla.runway or vanilla.taxi
	elseif typ == "waterstream" then
		return vanilla.country_small
	end
	return st.fallback_type
end

function st.resolve(name, street)
	if not name or name == "" then
		return name
	end
	if tools.resOk("street", name) then
		return name
	end
	local fb = st.vanillaFor(street or {})
	if fb and tools.resOk("street", fb) then
		print("WARNING street type missing '" .. name .. "', using vanilla '" .. fb .. "'")
		return fb
	end
	if tools.resOk("street", st.fallback_type) then
		print("WARNING street type missing '" .. name .. "', using fallback '" .. st.fallback_type .. "'")
		return st.fallback_type
	end
end

function st.pickOk(list, idx, street)
	if type(list) ~= "table" then
		return st.resolve(list, street)
	end
	idx = math.max(1, math.min(#list, idx or 1))
	for i = idx, #list do
		if list[i] and list[i] ~= "" and tools.resOk("street", list[i]) then
			return list[i]
		end
	end
	for i = 1, idx - 1 do
		if list[i] and list[i] ~= "" and tools.resOk("street", list[i]) then
			return list[i]
		end
	end
	return st.resolve(list[idx] or list[1], street)
end

function st.getType(street,options)
	-- if true then return st.fallback_type end
	if options.build_autobahn==false and (street.type=="motorway" or street.type=="trunk") and street.oneway then
		return
	end
	if options.build_streets_street_types==false and st.osmtypes_street[street.type] then
		return
	end
	if options.build_streets_footway_types==false and st.osmtypes_footways[street.type] then
		return
	end
	if options.build_streets_water==false and st.osmtypes_water[street.type] then
		return
	end
	if options.build_streets_airport==false and st.osmtypes_airport[street.type] then
		return
	end
	local chosen
	local type_data = st.types[street.type]
	if type(type_data)=="table" then
		if street.lanes==3 and not street.oneway then
			local lane3 = type_data["lane3"]
			if type(lane3)=="string" then
				chosen = lane3
			elseif type(lane3)=="function" then
				chosen = lane3(street)
			end
		end
		if not chosen then
			local lane_data = type_data[street.oneway and "ow" or "tw"]
			if type(lane_data)=="function" then
				lane_data = lane_data(street)
			end
			if type(lane_data)=="string" then
				chosen = lane_data
			elseif type(lane_data)=="table" then
				local lanes = street.lanes
				if not street.oneway then
					lanes = math.ceil( (lanes or 2) / 2 )
				end
				return st.pickOk(lane_data, math.min(#lane_data, lanes or 1), street)
			end
		end
	elseif type(type_data)=="function" then
		chosen = type_data(street)
	elseif type(type_data)=="string" then
		chosen = type_data
	elseif type_data == false then
		return
	else
		print("WARNING osm highway type unmapped: "..tostring(street.type))
	end
	return st.resolve(chosen or st.fallback_type, street)
end

--Die Vorabdefinition der Straßen hat Vorteile, da 1. umständliche Namen abgekürzt und leicht mehrfach verwendet werden können, 2. der Überblick über die abhängigen Mods ist besser, 3. teilweise unfassbar uneindeutige Dateinamen der Modder
local ug = {
	town_medium = "standard/town_medium_new.lua",
	town_small = "standard/town_small_new.lua", --lantern
}
-------------  Mods
local easybr_rtp = {  -- RTP-Roads_V2_1
	fus_asphalt = "01_fusswege/01_fussweg_asphalt.lua",  --4m
	fus_schotter = "01_fusswege/01_fussweg_schotter.lua",
	fus_schotterrot = "01_fusswege/01_fussweg_roter_schotter.lua",
	fus_erde = "01_fusswege/01_fussweg_erde.lua",  -- smaller than the others
	fus_schottererde = "01_fusswege/01_fussweg_unsichtbar.lua",
	feld_erde = "02_feldwege/02_feldweg_erde_zweispurig.lua",
	feld_unsichtb = "02_feldwege/02_feldweg_unsichtbar_zweispurig.lua",
	land_tw2 = "03_landstrassen/03_landstrasse_asphalt_zweispurig_standard.lua",
	land_tw4 = "03_landstrassen/03_landstrasse_asphalt_vierspurig.lua",
	land_ow1 = "03_landstrassen/03_landstrasse_asphalt_einspurig_einweg.lua",
	land_ow2 = "03_landstrassen/03_landstrasse_asphalt_zweispurig_einweg.lua",
	stadt_asphalt_nomark = "04_stadtstrassen/04_stadtstrasse_asphalt_zweispurig_klein.lua",--laterne, no sw
	stadt_asphalt_ow2 = "04_stadtstrassen/04_stadtstrasse_asphalt_zweispurig_einweg.lua",--laterne, no sw
	stadt_asphalt_ow1 = "04_stadtstrassen/04_stadtstrasse_asphalt_einspurig_einweg.lua",--laterne, no sw
	stadt_asphalt_tw2 = "04_stadtstrassen/04_stadtstrasse_asphalt_zweispurig_standard.lua",--laterne, no sw
	stadt_asphalt_tw4 = "04_stadtstrassen/04_stadtstrasse_asphalt_vierspurig.lua",--laterne, no sw
}
local av_extroads = {  -- 1968514713 ext.roads - footpaths standalone
	asphalt3m = "extended ROADS/footpath  with buildings 2 asphalt_03 3m.lua",
	hexagon3m = "extended ROADS/footpath  with buildings 3 hexagon 3m.lua",
	dirt3m = "extended ROADS/footpath  with buildings 1 dirt 3m.lua",  -- dirt/gravel
}
local lollo_sft = {  -- 2021038808 Street fine tuning; 2363493916 Freestyle station
	asphalt1m = "lollo_1m_path_concrete.lua",
	sett1m = "lollo_1m_path.lua",
	cobble1m = "lollo_1m_path_cobbles.lua",
	cobblelarge1m = "lollo_1m_path_cobbles_large.lua",
	ultrathin = "lollo_ultrathin_path.lua",
	asphalt1way = "lollo_medium_1_way_1_lane_street_narrow_sidewalk.lua", -- laterne, no sidewalk, 2m
	country_1way3lane = "lollo_medium_1_way_3_lane_country_road.lua",
}
local marc26_tramstreet = {  -- marc_strassetram_1
	s1lane_nosw = "standard/town_verysmall_new_tram.lua",  -- no lantern
	s1lane_nosw_bigger = "standard/town_small_new_tram.lua",  -- no lantern
	s1lane_smsw = "standard/town_mediumsmall_new_tram.lua",
	s2lane = "standard/town_large_new_tram.lua",
	s3lane = "standard/town_x_large_new_tram.lua",
	s1lane_ow_nosw = "standard/town_small_one_way_new_tram.lua",
	s1lane_ow = "standard/town_medium_one_way_new_tram.lua",
	s2lane_ow = "standard/town_large_one_way_new_tram.lua",
	s3lane_ow = "standard/town_x_large_one_way_new_tram.lua",
	grass_small = "standard/country_verysmall_new_tramgras.lua",  --6m
	grass_verysmall = "standard/country_verysmall_one_way_new_tramgras.lua",  --2m
}
local majuen_smp = {  -- majuen_smp_1
	bikelane = "standard/town_middle_bikelane.lua",
	fgzone_7m = "standard/town_middle_sidewalk.lua",  -- pavedstones
	fgzone_3m = "standard/town_smaller_sidewalk.lua", --oneway, pavedstones
	fgzone_bus_small = "standard/town_smaller_pedestrian_bus_tram_street.lua", -- pavedstones
	streetbike = "special/town_large_bike_new.lua",  -- bikelane on street
	town3lane = "special/town_new_large_three_lane.lua",
	country3lane = "special/country_new_large_three_lane.lua",
}
local jf_roads = {  -- joefried_roadstrassen_em_2
	fusspflaster = "xjfschmalweg/xstr_jf13_w1pflastercc.lua",  -- cobble, 6m
	stadtY = "xjfschmalstr1/xstr_jf15_kupplungy.lua",
	stadtN = "xjfschmalstr3/xstr_jf49_teeplatthelln.lua",
	stadtO = "xjfschmalstr1/xstr_jf50_teerweiso.lua",
	stadtC_ml = "xjfschmalstr3/xstr_jf21_pflasterc.lua",
	stadtC = "xjfschmalstr3/xstr_jf21_pflasterc_ol.lua",
	ug_old_small = "xjfspezial_ug1/xjfstrold_small.lua",
	ug_old_medium = "xjfspezial_ug1/xjfstrold_medium.lua",
	feldweg  = "xjfschmalweg/xstr_jf07_feld1kfz.lua", --1lane both ways
	pflasterweg = "xjfschmalweg/xstr_jf09_pflaster1.lua", --1lane both ways, cobble, 2.5m
	teerweg = "xjfschmalweg/xstr_jf10_teer1kfz.lua",  --1lane both ways, 2.5m
	landsand_marker = "xjflandstr1/xstr_jf601_altelandstr1.lua",  -- stone marker on sides
	landcobbl_marker = "xjflandstr1/xstr_jf619_pflasterb.lua",  --40kmh
	landcobbl = "xjflandstr1/xstr_jf619_pflasterb_is.lua",  --30kmh
	landcobbl2_marker = "xjflandstr1/xstr_jf622_pflasterd.lua", --70kmh
	landcobbl2 = "xjflandstr1/xstr_jf622_pflasterd_is.lua", --30kmh
	landasphalt_marker = "xjflandstr1/xstr_jf641_teerflachi.lua",  --60kmh
	landasphalt = "xjflandstr1/xstr_jf641_teerflachi_is.lua",  -- 30kmh
	landasphalt_marking = "xjflandstr1/xstr_jf645_teergelbk_is.lua", -- 30kmh, line marking (weiß)
	landschotter_ow = "xjflandstr1/xstr_jf514_518ohnespur2_eb.lua",
	landcobbl_ow = "xjflandstr1/xstr_jf619_pflasterb_is_eb.lua",
	landcobbl2_ow = "xjflandstr1/xstr_jf622_pflasterd_is_eb.lua",
	landasphalt_ow = "xjflandstr1/xstr_jf645_teergelbk_is_eb.lua", -- 30kmh, no markings
}
-- local rutel_bach = {  -- Rutel_Brook_1
	-- brook1m = "brook_slow_tiny.lua",
	-- brook2m = "brook_slow_small.lua",
	-- brook3m = "brook_slow_narrow.lua",
	-- brook4m = "brook_slow_normal.lua",
	-- brook5m = "brook_slow_wide.lua",
	-- brook7m = "brook_slow_large.lua",
	-- brook10m = "brook_slow_huge.lua",
-- }
local relozu_wattex = {  -- relozu_terrain_material_water_1
	gray4m = "zzwk_waterways/relozu_wk_water_03_country_small.lua",
	gray8m = "zzwk_waterways/relozu_wk_water_03_country_medium.lua",
	gray16m = "zzwk_waterways/relozu_wk_water_03_country_large.lua",
	blue4m = "zzwk_waterways/relozu_wk_water_04_country_small.lua",
	blue8m = "zzwk_waterways/relozu_wk_water_04_country_medium.lua",
	blue16m = "zzwk_waterways/relozu_wk_water_04_country_large.lua",
}
local mkh_airportroads = {  -- 2232249704 Airport Roads (EXPERIMENTAL)
	runway = "standard/ar_runway_wide.lua",
	taxiway = "standard/ar_taxi_standard_altl.lua",
}


st.types = {  -- tag "highway"
	steps = "standard/town_small_new.lua",
	platform = "standard/town_small_new.lua",
	motorway = {
		tw = {
			"standard/country_large_new.lua",
			"standard/country_x_large_new.lua",
		},
		ow = {
			"standard/country_medium_one_way_new.lua",
			"standard/country_large_one_way_new.lua",
			lollo_sft.country_1way3lane,
		}
	},
	motorway_link = {
		tw = {
			"standard/country_medium_new.lua",
			"standard/country_large_new.lua",
		},
		ow = {
			"standard/country_small_one_way_new.lua",
			"standard/country_medium_one_way_new.lua",
			lollo_sft.country_1way3lane,
		}
	},
	secondary = {
		tw = function(street)
			if street.country~=false then
				return {
					"standard/country_medium_new.lua",
					"standard/country_large_new.lua",
					easybr_rtp.land_tw2,
					easybr_rtp.land_tw4,
				}
			else  -- urban
				return st.types.tertiary.tw(street)
			end
		end,
		ow = function(street)
			if street.country~=false then
				return {
					"standard/country_small_one_way_new.lua",
					"standard/country_medium_one_way_new.lua",
				}
			else  -- urban
				return st.types.tertiary.ow(street)
			end
		end,
		lane3 = function(street)
			if street.country~=false then
				return majuen_smp.country3lane
			else  -- urban
				return majuen_smp.town3lane
			end
		end,
	},
	tertiary = {
		-- if cycleway
		tw = function(street)
			if street.country~=false then
				return st.types.secondary.tw(street)
			else  -- urban
				if street.sidewalk~=false then
					return {
						marc26_tramstreet.s1lane_smsw,
						marc26_tramstreet.s2lane,
						marc26_tramstreet.s3lane,
					}
				else  -- no sidewalk
					return {
						"standard/town_small_new.lua",
						"standard/town_medium_new.lua",
						easybr_rtp.stadt_asphalt_tw2,
						easybr_rtp.stadt_asphalt_tw4,
					}
				end
			end
		end,
		ow = function(street)
			if street.country~=false then
				return st.types.secondary.ow(street)
			else  -- urban
				if street.sidewalk~=false then
					return {
						marc26_tramstreet.s1lane_ow,
						marc26_tramstreet.s2lane_ow,
						marc26_tramstreet.s3lane_ow,
					}
				else  -- no sidewalk
					return {
						marc26_tramstreet.s1lane_ow_nosw,
						easybr_rtp.stadt_asphalt_ow2,
					}
				end
			end
		end,
		lane3 = function(street)
			if street.country~=false then
				return majuen_smp.country3lane
			else  -- urban
				return majuen_smp.town3lane
			end
		end,
	},
	residential = {
		tw = function(street)
			if street.sidewalk~=false then
				if street.surface then
					if street.surface=="cobblestone" then	
						return jf_roads.ug_old_small
					else
						return ug.town_medium
					end
				else
					return ug.town_medium
				end
			else  -- no sidewalk
				-- return marc26_tramstreet.s1lane_nosw
				return ug.town_small
			end
		end,
		ow = function(street)
			if street.sidewalk~=false then
				street.country = false
				return st.types.tertiary.ow(street)
			else
				return marc26_tramstreet.s1lane_ow_nosw
			end
		end,
		lane3 = majuen_smp.town3lane,
	},
	living_street = {
		tw = function(street)
			if street.surface=="paving_stones" then
				return majuen_smp.fgzone_bus_small
			else
				return marc26_tramstreet.s1lane_nosw
			end
		end,
		ow = function(street)
			if street.sidewalk then
				return marc26_tramstreet.s1lane_ow
			else
				return marc26_tramstreet.s1lane_ow_nosw
			end
		end,
		lane3 = majuen_smp.town3lane,
	},
	unclassified = {
		tw = "standard/country_small_new.lua",
		ow = "standard/country_small_one_way_new.lua",
		lane3 = function(street)
			if street.country~=false then
				return majuen_smp.country3lane
			else  -- urban
				return majuen_smp.town3lane
			end
		end,
	},
	service = {
		tw = {
			"standard/town_small_new.lua",
			easybr_rtp.stadt_asphalt_nomark,
		},
		ow = {
			"standard/town_small_one_way_new.lua",
			easybr_rtp.stadt_asphalt_ow1,
		},
	},
	construction = "standard/town_small_new.lua",
	_pedestrian_surface = {
		sett = jf_roads.stadtC,
		cobblestone = jf_roads.stadtC,
		unhewn_cobblestone = jf_roads.ug_old_small,
		paving_stones =majuen_smp.fgzone_7m,
	},
	pedestrian = function(street)
		local r
		if street.surface then
			r = st.types._pedestrian_surface[street.surface]
			if not r then
				return st.types.footway(street)
			end
		else
			r = st.types._pedestrian_surface.paving_stones
		end
		return r
	end,
	_track_grade = {
		grade1 = easybr_rtp.fus_asphalt,
		grade2 = easybr_rtp.fus_schotter,
		grade3 = easybr_rtp.fus_schottererde,
		grade4 = easybr_rtp.fus_erde,
		grade5 = easybr_rtp.fus_erde,
	},
	_track_surface = {
		asphalt = easybr_rtp.fus_asphalt,
		concrete = easybr_rtp.fus_asphalt,
		paved = easybr_rtp.fus_asphalt,
		paving_stones = av_extroads.hexagon3m,
		["paving_stones:30"] = av_extroads.hexagon3m,
		["paving_stones:double_t"] = av_extroads.hexagon3m,
		sett = jf_roads.pflasterweg,
		cobblestone = jf_roads.pflasterweg,
		unhewn_cobblestone = jf_roads.pflasterweg,
		["cobblestone:flattened"] = jf_roads.pflasterweg,
		compacted = easybr_rtp.feld_unsichtb,
		unpaved = easybr_rtp.feld_unsichtb,
		gravel = easybr_rtp.fus_schotter,
		fine_gravel = easybr_rtp.fus_schotter,
		pebblestone = easybr_rtp.fus_schotter,
		ground = easybr_rtp.fus_erde,
		earth = easybr_rtp.fus_erde,
		mud = easybr_rtp.fus_erde,
		dirt = easybr_rtp.fus_erde,
		wood = easybr_rtp.fus_erde,
		grass = jf_roads.feldweg,  --marc26_tramstreet.grass_verysmall,
		["grass;ground"] = jf_roads.feldweg,
		sand = jf_roads.feldweg,
		-- grass_paver = ,
		woodchips = easybr_rtp.fus_erde,
		metal = st.fallback_type,
		["concrete:plates"] = easybr_rtp.fus_asphalt,
	},
	track = function(street)
		local r
		if street.surface then
			r = st.types._track_surface[street.surface]
			if not r then
				print("ERROR: surface NOT DEFINED _track_surface: ".. street.surface)
				r = st.fallback_type
			end
		elseif street.tracktype then
			r = st.types._track_grade[street.tracktype]
			if not r then
				print("ERROR: tracktype NOT DEFINED: "..street.tracktype)
				r = st.fallback_type
			end
		else
			r = easybr_rtp.fus_schottererde
		end
		return r
	end,
	_foot_surface_3m = {
		asphalt = av_extroads.asphalt3m,
		concrete = av_extroads.asphalt3m,
		paved = av_extroads.asphalt3m,
		paving_stones = av_extroads.hexagon3m,
		compacted = av_extroads.dirt3m,
		gravel = av_extroads.dirt3m,
		fine_gravel = av_extroads.dirt3m,
		pebblestone = av_extroads.dirt3m,
		ground = av_extroads.dirt3m,
		earth = av_extroads.dirt3m,
		dirt = av_extroads.dirt3m,
		wood = av_extroads.dirt3m,
		unpaved = av_extroads.dirt3m,
	},
	_foot_surface_1m = {
		asphalt = lollo_sft.asphalt1m,
		sett = lollo_sft.sett1m,
		paving_stones = lollo_sft.cobblelarge1m,
		cobblestone = lollo_sft.cobble1m,
	},
	footway = function(street)
		local r
		if street.width and street.width<0.5 then
			return lollo_sft.ultrathin
		end
		if street.width and street.width<1.5 then
			if street.surface then
				r = st.types._foot_surface_1m[street.surface]
				if not r then
					-- print("ERROR:  Surface NOT DEFINED _foot_surface_1m: ".. street.surface)
					-- r = st.fallback_type
					--continue
				else 
					return r
				end
			else
				return lollo_sft.asphalt1m
			end
		end
		if street.surface then
			r = st.types._foot_surface_3m[street.surface]
			if not r then
				return st.types.track(street)
			end
		else
			-- r = lollo_sft.asphalt1way
			-- r = majuen_smp.fgzone_3m
			r = "standard/town_small_new.lua"
		end
		return r
	end,
	path = {
		tw = function(street)
			if street.segregated then
				return majuen_smp.bikelane
			else
			-- if street.bicycle then
				if street.surface then
					return st.types.footway(street)
				else
					return av_extroads.dirt3m
				end
			end
		end,
		ow = function(street)
			-- return lollo_sft.asphalt1way
			if street.surface then
				return st.types.footway(street)
			else
				return av_extroads.dirt3m
			end
		end,
	},
	cycleway = {
		tw = function(street)
			if street.segregated then
				return majuen_smp.bikelane
			else
				return "standard/town_small_new.lua"
			end
		end,
		ow = function(street)
			return "standard/town_small_one_way_new.lua"
		end,
	},
	waterstream = function(data)
		local width
		if data.waterwaytype=="stream" then
			width = data.width or 3
		elseif data.waterwaytype=="river" then
			width = data.width or (data.boat and 30 or 15)
		else
			width = data.width or 4
		end
		width = tonumber(width) or 4
		-- if width<2 then
			-- return rutel_bach.brook1m
		-- elseif width<3 then
			-- return rutel_bach.brook2m
		-- elseif width<4 then
			-- return rutel_bach.brook3m
		-- elseif width<5 then
			-- return rutel_bach.brook4m
		-- elseif width<6 then
			-- return rutel_bach.brook5m
		-- else
			-- return rutel_bach.brook7m
		-- end
		if width<6 then
			return relozu_wattex.blue4m
		elseif width<12 then
			return relozu_wattex.gray8m
		elseif width<20 then
			return relozu_wattex.gray16m  -- looks a bit more natural
		end
		return relozu_wattex.gray16m
	end,
	aeroway = function(data)
		if data.subtype=="runway" then
			return mkh_airportroads.runway
		end
		return mkh_airportroads.taxiway
	end,
	raceway = "standard/country_small_one_way_new.lua",
}

local types = st.types
types.trunk = types.motorway
types.trunk_link = types.motorway_link
types.secondary_link = types.secondary
types.primary = types.secondary
types.primary_link = types.secondary_link
types.tertiary_link = types.tertiary
types.bridleway = types.path

st.osmtypes_street = tools.list2dict{
	"raceway",
	"motorway",
	"motorway_link",
	"trunk",
	"trunk_link",
	"primary",
	"primary_link",
	"secondary",
	"secondary_link",
	"tertiary",
	"tertiary_link",
	"residential",
	"living_street",
	"unclassified",
	"service",
	"construction",
}
st.osmtypes_footways = tools.list2dict{
	"pedestrian",
	"footway",
	"cycleway",
	"path",
	"track",
	"bridleway",
	"steps",
	"platform",
}
st.osmtypes_water = tools.list2dict{"waterstream"}
st.osmtypes_airport = tools.list2dict{"aeroway"}

return st