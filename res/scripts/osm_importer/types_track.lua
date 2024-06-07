local tt = {}

tt.fallback_type = "ETH_Schotterbett.lua" -- < choose this to better detect unknown types
-- tt.fallback_type = "standard.lua" -- < choose this for visual appearance


------------- Mods
-- unixroot_natural_environment_pro_tpf2_1
-- vt_natural_environment_pro_addon_1
-- ETH_Schotterbett_1
-- eis_os_trackpackage_1
-- yoshi_feldbahn_infra_1
-- 2060012969 vienna_fever_infrastruktur
-- 2258619623 Eeasy Stadtbahn Construction - Basic Segmets
-- 1983390040 Old Track


function tt.getType(track)
	if track.tram or track.subway then
		if track.gauge then
			if track.gauge<700 then
				return "600mm_holz_08.lua"
			elseif track.gauge<900 then
				return
			elseif track.gauge<1200 then  -- 1000
				return
			elseif track.gauge<1500 then  -- 1435
				track.reverse = true
				return "vienna_fever_stadtbahngleis.lua"  -- mast on the left side
			else
				return
			end
		else
			print("WARNING track no gauge ")
			return
		end
	end
	
	if track.electrified=="rail" then  --Stromschiene
		return "ice_berlin_stromschiene_rechts_neu.lua"
	end
	
	if track.electrified=="4th_rail" then
		return
	end
	
	if track.type=="construction" then
		return "ETH_Schotterbett_300.lua"
		--"alternativ/high_speed_120.lua"
	end
	
	if track.type=="disused" then
		-- if track.tram then
		if track.gauge and track.gauge<850 then
			return "600mm_stahl_12_schotter.lua"
		else
			return "old_track_standard.lua"
		end
	end
	
	-- if track.type=="miniature" then
		-- return
	-- end
	
	-- if track.type=="preserved" then
		-- return
	-- end
	
	if track.gauge then
		if track.gauge<700 then
			return "600mm_stahl_12_schotter.lua"
		elseif track.gauge<900 then
			return "eis_os_750mm.lua"
		elseif track.gauge<1200 then  -- 1000
			return "eis_os_1000mm_5_5m.lua"
		elseif track.gauge<1500 then  -- 1435
			if track.speed then
				return tt.normalSpeeds(track)
			else
				-- print("ERROR track no speed")
				return tt.fallback_type
				-- return "standard.lua"
			end
		else
			return
		end
	else
		-- print("ERROR track no gauge ")
		return
	end
	
	error(debugPrint(track) or "not return")
end

tt.normalSpeeds = function(track)
	local speeds = {
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
		[140] = "high_speed_140.lua",--low_speed.lua
		[150] = "high_speed_150.lua",
		[160] = "high_speed.lua",
		[180] = "high_speed_lzb_180.lua",
		[200] = "high_speed_lzb_200.lua",
		[220] = "alternativ/high_speed_lzb_220.lua",  -- alternativ: new
		[250] = "alternativ/high_speed_lzb_250.lua",
		[300] = "alternativ/high_speed_block_lzb_300.lua",  -- feste Fahrbahn
	}
	local speedsLZB = {
		[10] = "high_speed_lzb_10.lua",
		[20] = "high_speed_lzb_20.lua",
		[30] = "high_speed_lzb_30.lua",
		[40] = "high_speed_lzb_40.lua",
		[50] = "high_speed_lzb_50.lua",
		[60] = "high_speed_lzb_60.lua",
		[70] = "high_speed_lzb_70.lua",
		[80] = "high_speed_lzb_80.lua",
		[90] = "high_speed_lzb_90.lua",
		[100] = "high_speed_lzb_100.lua",
		[110] = "high_speed_lzb_110.lua",
		[120] = "high_speed_lzb_120.lua",
		[130] = "high_speed_lzb_130.lua",
		[140] = "high_speed_lzb_140.lua",
		[150] = "high_speed_lzb_150.lua",
		[160] = "high_speed_lzb_160.lua",
	}
	local speedtype
	if track.lzb then
		speedtype = speedsLZB[track.speed]
	end
	if not speedtype then
		speedtype = speeds[track.speed]
	end
	if speedtype then
		return speedtype
	else
		print("WARNING normal gauge - speed not found "..track.speed)
		return tt.fallback_type
	end
end

return tt