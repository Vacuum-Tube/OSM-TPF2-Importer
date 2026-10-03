local tools = require "osm_importer.tools"

local st = {}

-- Match OSM railway:signal:* country prefixes when a pack is installed.
-- Untagged signals use vanilla TPF2 types. Regional models are a fallback.

local vanilla = {
	main = "railroad/signal_new_block.mdl",
	path = "railroad/signal_new_path.mdl",
	old = "railroad/signal_old_block.mdl",
}

local sms = {
	main_2_left = "railroad/left_011_hsi_2_80.mdl",
	main_3_left = "railroad/left_012_hsi_3_40.mdl",
	main_4_left = "railroad/left_013_hsi_4.mdl",
	main_5_left = "railroad/left_014_hsi_5.mdl",
	main_2_right = "railroad/right_011_hsi_2_80.mdl",
	main_3_right = "railroad/right_012_hsi_3_40.mdl",
	main_4_right = "railroad/right_013_hsi_4.mdl",
	main_5_right = "railroad/right_014_hsi_5.mdl",
	block_2_left = "railroad/left_001_blsi_2_80.mdl",
	block_4_left = "railroad/left_002_blsi_4_80_nxt_80.mdl",
	block_5_left = "railroad/left_003_blsi_5_80_nxt_80.mdl",
	block_2_right = "railroad/right_001_blsi_2_80.mdl",
	block_4_right = "railroad/right_002_blsi_4_80_nxt_80.mdl",
	block_5_right = "railroad/right_003_blsi_5_80_nxt_80.mdl",
	maindist_2_left = "railroad/left_021_vdvsi_hsi_2_80.mdl",
	maindist_3_left = "railroad/left_022_vdvsi_hsi_3_40.mdl",
	maindist_4_left = "railroad/left_023_vdvsi_hsi_4.mdl",
	maindist_5_left = "railroad/left_024_vdvsi_hsi_5.mdl",
	maindist_2_right = "railroad/right_021_vdvsi_hsi_2_80.mdl",
	maindist_3_right = "railroad/right_022_vdvsi_hsi_3_40.mdl",
	maindist_4_right = "railroad/right_023_vdvsi_hsi_4.mdl",
	maindist_5_right = "railroad/right_024_vdvsi_hsi_5.mdl",
	distant_vdvsi_left = "railroad/left_031_vdvsi.mdl",
	distant_vsi_left = "railroad/left_051_vsi.mdl",
	distant_vsi2_left = "railroad/left_052_vsi.mdl",
	distant_vdvsi_right = "railroad/right_031_vdvsi.mdl",
	distant_vsi_right = "railroad/right_051_vsi.mdl",
	distant_vsi2_right = "railroad/right_052_vsi.mdl",
	dwarf_2_left = "railroad/left_041_fsi_2.mdl",
	dwarf_3_left = "railroad/left_042_fsi_3.mdl",
	dwarf_2_right = "railroad/right_041_fsi_2.mdl",
	dwarf_3_right = "railroad/right_042_fsi_3.mdl",
	crossing = "railroad/left_051_vsi.mdl",
	crossing_right = "railroad/right_051_vsi.mdl",
	crossing_distant = "railroad/left_053_vfsi.mdl",
	crossing_distant_right = "railroad/right_053_vfsi.mdl",
	whistle = "railroad/left_203_sign_horn_levelcrossing_wp.mdl",
	whistle_right = "railroad/right_203_sign_horn_levelcrossing_wp.mdl",
}

local nep = {
	hl1 = "railroad/grimes_hlsignal_hp1.mdl",
}

local hv = {
	aus_hp2 = "railroad/HV69-Signale/Basisset/HV69_Ausfahrt_Hp2.mdl",
	bl = "railroad/HV69-Signale/Basisset/HV69_Block_Hp1.mdl",
	bl_left = "railroad/HV69-Signale/Basisset/HV69_Block_Hp1_links.mdl",
	ein = "railroad/HV69-Signale/Basisset/HV69_Einfahrt_Hp1.mdl",
	ein_left = "railroad/HV69-Signale/Basisset/HV69_Einfahrt_Hp1_links.mdl",
	vr = "railroad/HV69-Signale/Basisset/HV69_Vorsignal_Vr1.mdl",
	vr_left = "railroad/HV69-Signale/Basisset/HV69_Vorsignal_Vr1_links.mdl",
	vr_wdh = "railroad/HV69-Signale/Erweiterung I/HV69_VorsignalWdh_Vr1.mdl",
	vr_wdh_left = "railroad/HV69-Signale/Erweiterung I/HV69_VorsignalWdh_Vr1_links.mdl",
	aus_hp2_vr0 = "railroad/HV69-Signale/Erweiterung I/HV69_Ausfahrt_Hp2_Vr0.mdl",
	bl_vr1 = "railroad/HV69-Signale/Erweiterung I/HV69_Block_Hp1_Vr1.mdl",
	bl_vr1_left = "railroad/HV69-Signale/Erweiterung I/HV69_Block_Hp1_Vr1_links.mdl",
	ein_hp2_vr0 = "railroad/HV69-Signale/Erweiterung I/HV69_Einfahrt_Hp2_Vr0.mdl",
	ein_hp2_vr0_left = "railroad/HV69-Signale/Erweiterung I/HV69_Einfahrt_Hp2_Vr0_links.mdl",
}

local ks = {
	asig_ks1 = "railroad/ks_signale/asig/ks_fm_4_6_asig_hp0_ks1.mdl",
	msig_ks1 = "railroad/ks_signale/msig/ks_amhk_msig_hp0_ks1.mdl",
	msig_ks1_left = "railroad/ks_signale/msig/ks_amhk_msig_hp0_ks1_links.mdl",
	bsig_ks1 = "railroad/ks_signale/bsig/ks_amhk_bsig_hp0_ks1.mdl",
	bsig_ks1_left = "railroad/ks_signale/bsig/ks_amhk_bsig_hp0_ks1_links.mdl",
	msig_asig_blink = "railroad/ks_signale/msig_als_asig/ks_fm_4_6_msig_asig_hp0_ks1_blink.mdl",
	msig_ks1_blink = "railroad/ks_signale/msig/ks_amhk_msig_hp0_ks1_blink.mdl",
	msig_ks1_blink_left = "railroad/ks_signale/msig/ks_amhk_msig_hp0_ks1_blink_links.mdl",
	vsig = "railroad/ks_signale/vsig/ks_fm_4_6_vsig_ks2_ks1.mdl",
	vsig_left = "railroad/ks_signale/vsig/ks_fm_4_6_vsig_ks2_ks1_links.mdl",
	vsig_wdh = "railroad/ks_signale/vsig/ks_fm_4_6_vsig_ks2_ks1_w.mdl",
	vsig_wdh_left = "railroad/ks_signale/vsig/ks_fm_4_6_vsig_ks2_ks2_w_links.mdl",
	sh1_high = "railroad/ks_signale/ls/ks_ls_hoch_hp0_sh1.mdl",
	sh1_low = "railroad/ks_signale/ls/ks_ls_niedrig_hp0_sh1.mdl",
	sh1_low_left = "railroad/ks_signale/ls/ks_ls_niedrig_hp0_sh1_links.mdl",
}

local function M(...)
	return tools.pick("model", ...)
end

local function side(signal, leftName, rightName)
	if signal.position_left then
		return M(leftName, rightName)
	end
	return M(rightName, leftName)
end

function st.swedish_main(signal)
	if signal.main_function == "exit" then
		return side(signal, sms.maindist_3_left, sms.maindist_3_right) or M(vanilla.main)
	elseif signal.main_function == "entry" then
		return side(signal, sms.main_3_left, sms.main_3_right) or M(vanilla.main)
	end
	return side(signal, sms.block_5_left, sms.block_5_right)
		or side(signal, sms.block_4_left, sms.block_4_right)
		or M(vanilla.main)
end

function st.swedish_distant(signal)
	if signal.distant_repeated then
		return side(signal, sms.distant_vdvsi_left, sms.distant_vdvsi_right) or M(vanilla.path)
	end
	return side(signal, sms.distant_vsi_left, sms.distant_vsi_right) or M(vanilla.path)
end

function st.swedish_minor(signal)
	if signal.minor_dwarf then
		return side(signal, sms.dwarf_2_left, sms.dwarf_2_right) or M(vanilla.old)
	end
	return side(signal, sms.dwarf_3_left, sms.dwarf_3_right) or M(vanilla.old)
end

local function swedish_speed(signal)
	local spd = tonumber(signal.speedlimit_speed_int or signal.speedlimitdistant_speed_int)
	if not spd then
		return
	end
	local n = string.format("%03d", math.floor(spd / 5) * 5)
	return M(
		"railroad/sign_speed_" .. n .. ".mdl",
		"railroad/sign_speed_" .. n .. "_no_pole.mdl"
	)
end

function st.getTypes(signal)
	local sigtypes = {}
	local function add(o)
		if o then
			table.insert(sigtypes, o)
			return o
		end
	end

	if signal.main and signal.distant and add(st.maindistant(signal))
	or signal.combined and add(st.combined(signal))
	or signal.main and add(st.main(signal))
	or signal.distant and add(st.distant(signal))
	or signal.minor and add(st.minor(signal))
	then end

	if signal.speedlimit then
		add(st.speedlimit(signal))
	end
	if signal.speedlimitdistant then
		add(st.speedlimitdistant(signal))
	end
	if signal.crossing then
		add(side(signal, sms.crossing, sms.crossing_right) or M(vanilla.path))
	end
	if signal.crossingdistant then
		add(side(signal, sms.crossing_distant, sms.crossing_distant_right))
	end
	if signal.whistle then
		add(side(signal, sms.whistle, sms.whistle_right))
	end
	return sigtypes
end

function st.main(signal)
	local tag = signal.main or ""
	if tag:starts("SE-SJ") then
		return st.swedish_main(signal)
	elseif tag == "DE-ESO:hp" then
		if signal.main_function == "exit" then
			return M(hv.aus_hp2) or M(vanilla.main)
		elseif signal.main_function == "entry" then
			return M(signal.position_left and hv.ein_left or hv.ein) or M(vanilla.main)
		end
		return M(signal.position_left and hv.bl_left or hv.bl) or M(vanilla.main)
	elseif tag == "DE-ESO:ks" then
		if signal.main_function == "exit" then
			return M(ks.asig_ks1) or M(vanilla.main)
		elseif signal.main_function == "entry" then
			return M(signal.position_left and ks.msig_ks1_left or ks.msig_ks1) or M(vanilla.main)
		end
		return M(signal.position_left and ks.bsig_ks1_left or ks.bsig_ks1) or M(vanilla.main)
	elseif tag == "DE-ESO:hl" then
		return M(nep.hl1) or M(vanilla.main)
	end
	return M(vanilla.main) or st.swedish_main(signal)
end

function st.combined(signal)
	if signal.combined == "DE-ESO:ks" then
		if signal.combined_function == "exit" then
			return M(ks.msig_asig_blink) or M(vanilla.main)
		end
		return M(signal.position_left and ks.msig_ks1_blink_left or ks.msig_ks1_blink) or M(vanilla.main)
	end
	return M(vanilla.main) or st.swedish_main(signal)
end

function st.maindistant(signal)
	local main = signal.main or ""
	local dist = signal.distant or ""
	if main:starts("SE-SJ") or dist:starts("SE-SJ") then
		return side(signal, sms.maindist_3_left, sms.maindist_3_right) or st.swedish_main(signal)
	end
	if main == "DE-ESO:hp" and dist == "DE-ESO:vr" then
		if signal.main_function == "exit" then
			return M(hv.aus_hp2_vr0) or M(vanilla.main)
		elseif signal.main_function == "entry" then
			return M(signal.position_left and hv.ein_hp2_vr0_left or hv.ein_hp2_vr0) or M(vanilla.main)
		end
		return M(signal.position_left and hv.bl_vr1_left or hv.bl_vr1) or M(vanilla.main)
	end
	return M(vanilla.main) or side(signal, sms.maindist_3_left, sms.maindist_3_right) or st.swedish_main(signal)
end

function st.distant(signal)
	local tag = signal.distant or ""
	if tag:starts("SE-SJ") then
		return st.swedish_distant(signal)
	elseif tag == "DE-ESO:vr" then
		if signal.distant_repeated then
			return M(signal.position_left and hv.vr_wdh_left or hv.vr_wdh) or M(vanilla.path)
		end
		return M(signal.position_left and hv.vr_left or hv.vr) or M(vanilla.path)
	elseif tag == "DE-ESO:ks" then
		if signal.distant_repeated then
			return M(signal.position_left and ks.vsig_wdh_left or ks.vsig_wdh) or M(vanilla.path)
		end
		return M(signal.position_left and ks.vsig_left or ks.vsig) or M(vanilla.path)
	end
	return M(vanilla.path) or st.swedish_distant(signal)
end

function st.minor(signal)
	local tag = tostring(signal.minor or "")
	if tag:starts("SE-SJ") then
		return st.swedish_minor(signal)
	elseif tag:starts("DE-ESO:sh") then
		if signal.minor_dwarf then
			return M(signal.position_left and ks.sh1_low_left or ks.sh1_low) or M(vanilla.old)
		end
		return M(ks.sh1_high) or M(vanilla.old)
	end
	return M(vanilla.old) or st.swedish_minor(signal)
end

function st.speedlimit(signal)
	return swedish_speed(signal)
end

function st.speedlimitdistant(signal)
	return swedish_speed(signal)
end

function st.isWaypoint(mdl)
	local id = api.res.modelRep.find(mdl)
	if id < 0 then
		return false
	end
	local model = api.res.modelRep.get(id)
	return model.metadata.signal and model.metadata.signal.type == 1
end

return st
