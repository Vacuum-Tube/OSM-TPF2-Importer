local tools = require "osm_importer.tools"

local tt = {}

tt.fallback_type = "standard.lua"

local function pickTrack(...)
	return tools.pick("track", ...) or tt.fallback_type
end

function tt.getType(track)
	if track.tram or track.subway then
		if track.gauge then
			if track.gauge < 700 then
				return pickTrack("600mm_holz_08.lua", "standard.lua")
			elseif track.gauge < 1200 then
				return pickTrack("eis_os_1000mm_5_5m.lua", "eis_os_750mm.lua", "standard.lua")
			elseif track.gauge < 1500 then
				track.reverse = true
				return pickTrack("vienna_fever_stadtbahngleis.lua", "standard.lua")
			else
				return pickTrack("standard.lua")
			end
		end
		return pickTrack("standard.lua")
	end

	if not track.gauge then
		track.gauge = 1435
	end

	if track.electrified == "rail" then
		return pickTrack("ice_berlin_stromschiene_rechts_neu.lua", "standard.lua")
	end

	if track.electrified == "4th_rail" then
		return pickTrack("standard.lua")
	end

	if track.type == "construction" then
		return pickTrack("ETH_Schotterbett_300.lua", "standard.lua")
	end

	if track.type == "disused" then
		if track.gauge and track.gauge < 850 then
			return pickTrack("600mm_stahl_12_schotter.lua", "standard.lua")
		end
		return pickTrack("old_track_standard.lua", "standard.lua")
	end

	if track.gauge then
		if track.gauge < 700 then
			return pickTrack("600mm_stahl_12_schotter.lua", "standard.lua")
		elseif track.gauge < 900 then
			return pickTrack("eis_os_750mm.lua", "standard.lua")
		elseif track.gauge < 1200 then
			return pickTrack("eis_os_1000mm_5_5m.lua", "standard.lua")
		elseif track.gauge < 1500 then
			if track.speed then
				return tt.normalSpeeds(track)
			end
			return pickTrack("standard.lua")
		else
			return pickTrack("standard.lua")
		end
	end
	return pickTrack("standard.lua")
end

function tt.normalSpeeds(track)
	local speed = tonumber(track.speed) or 80
	if speed >= 160 then
		return pickTrack(
			"high_speed.lua",
			"high_speed_lzb_200.lua",
			"standard.lua"
		)
	end
	local named = {
		[5] = "standard_10.lua",
		[10] = "standard_10.lua",
		[15] = "standard_20.lua",
		[20] = "standard_20.lua",
		[25] = "standard_30.lua",
		[30] = "standard_30.lua",
		[40] = "standard_40.lua",
		[50] = "low_speed_50.lua",
		[60] = "low_speed_60.lua",
		[70] = "low_speed_70.lua",
		[80] = "low_speed_80.lua",
		[90] = "low_speed_90.lua",
		[100] = "low_speed_100.lua",
		[110] = "low_speed_110.lua",
		[120] = "low_speed_120.lua",
		[130] = "low_speed_130.lua",
		[140] = "high_speed_140.lua",
		[150] = "high_speed_150.lua",
	}
	local preferred = named[speed]
	if speed >= 140 then
		return pickTrack(preferred, "high_speed.lua", "standard.lua")
	end
	return pickTrack(preferred, "standard.lua")
end

return tt
