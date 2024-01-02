local st = {}


------------- Mods

-- unixroot_natural_environment_pro_tpf2_2
local nep = {
	hl1 = "railroad/grimes_hlsignal_hp1.mdl",
	hl10 = "railroad/grimes_hlsignal_hl10.mdl",
	form_hp1 = "railroad/grimes_signal_hp1b.mdl",  --form8m
	form_vr1 = "railroad/grimes_vorsignal_vr1.mdl",  --form
}

-- sebbe_hv69signale_basis_1, sebbe_hv69signale_erw1_1 + erw2 + erw3
local hv = {
	aus = "railroad/HV69-Signale/Basisset/HV69_Ausfahrt_Hp1.mdl",
	aus_hp2 = "railroad/HV69-Signale/Basisset/HV69_Ausfahrt_Hp2.mdl",
	bl = "railroad/HV69-Signale/Basisset/HV69_Block_Hp1.mdl",
	bl_left = "railroad/HV69-Signale/Basisset/HV69_Block_Hp1_links.mdl",
	ein = "railroad/HV69-Signale/Basisset/HV69_Einfahrt_Hp1.mdl",
	ein_left = "railroad/HV69-Signale/Basisset/HV69_Einfahrt_Hp1_links.mdl",
	ein_hp2 = "railroad/HV69-Signale/Basisset/HV69_Einfahrt_Hp2.mdl",
	ein_hp2_left = "railroad/HV69-Signale/Basisset/HV69_Einfahrt_Hp2_links.mdl",
	vr = "railroad/HV69-Signale/Basisset/HV69_Vorsignal_Vr1.mdl",
	vr_left = "railroad/HV69-Signale/Basisset/HV69_Vorsignal_Vr1_links.mdl",
	vr2 = "railroad/HV69-Signale/Basisset/HV69_Vorsignal_Vr2.mdl",
	vr2_left = "railroad/HV69-Signale/Basisset/HV69_Vorsignal_Vr2_links.mdl",
	vr_wdh = "railroad/HV69-Signale/Erweiterung I/HV69_VorsignalWdh_Vr1.mdl",
	vr_wdh_left = "railroad/HV69-Signale/Erweiterung I/HV69_VorsignalWdh_Vr1_links.mdl",
	vr2_wdh = "railroad/HV69-Signale/Erweiterung I/HV69_VorsignalWdh_Vr2.mdl",
	vr2_wdh_left = "railroad/HV69-Signale/Erweiterung I/HV69_VorsignalWdh_Vr2_links.mdl",
	aus_vr0 = "railroad/HV69-Signale/Erweiterung I/HV69_Ausfahrt_Hp1_Vr0.mdl",
	aus_hp2_vr0 = "railroad/HV69-Signale/Erweiterung I/HV69_Ausfahrt_Hp2_Vr0.mdl",
	bl_vr1 = "railroad/HV69-Signale/Erweiterung I/HV69_Block_Hp1_Vr1.mdl",
	bl_vr1_left = "railroad/HV69-Signale/Erweiterung I/HV69_Block_Hp1_Vr1_links.mdl",
	ein_vr0 = "railroad/HV69-Signale/Erweiterung I/HV69_Einfahrt_Hp1_Vr0.mdl",
	ein_vr0_left = "railroad/HV69-Signale/Erweiterung I/HV69_Einfahrt_Hp1_Vr0_links.mdl",
	ein_hp2_vr0 = "railroad/HV69-Signale/Erweiterung I/HV69_Einfahrt_Hp2_Vr0.mdl",
	ein_hp2_vr0_left = "railroad/HV69-Signale/Erweiterung I/HV69_Einfahrt_Hp2_Vr0_links.mdl",
}

-- 2770909719 Signalkomponenten
local sk = {
	zs2_F = "railroad/signals/zs2/ks_zs2_f.mdl",
	zs2v_F = "railroad/signals/zs2v/ks_zs2v_f.mdl",
	zp9 = "railroad/signals/zsa/ks_zp9.mdl",
	zs6 = "railroad/signals/zsa/ks_zs6.mdl",
	zs3_20 = "railroad/signals/zs3/ks_zs3_20.mdl",
	zs3_30 = "railroad/signals/zs3/ks_zs3_30.mdl",
	zs3_40 = "railroad/signals/zs3/ks_zs3_40.mdl",
	zs3_50 = "railroad/signals/zs3/ks_zs3_50.mdl",
	zs3_60 = "railroad/signals/zs3/ks_zs3_60.mdl",
	zs3_70 = "railroad/signals/zs3/ks_zs3_70.mdl",
	zs3_80 = "railroad/signals/zs3/ks_zs3_80.mdl",
	zs3_90 = "railroad/signals/zs3/ks_zs3_90.mdl",
	zs3_100 = "railroad/signals/zs3/ks_zs3_100.mdl",
	zs3_110 = "railroad/signals/zs3/ks_zs3_110.mdl",
	zs3_120 = "railroad/signals/zs3/ks_zs3_120.mdl",
	zs3_130 = "railroad/signals/zs3/ks_zs3_130.mdl",
	zs3_140 = "railroad/signals/zs3/ks_zs3_140.mdl",
	zs3_150 = "railroad/signals/zs3/ks_zs3_150.mdl",
	zs3_160 = "railroad/signals/zs3/ks_zs3_160.mdl",
	zs3v_20 = "railroad/signals/zs3v/ks_zs3v_20.mdl",
	zs3v_30 = "railroad/signals/zs3v/ks_zs3v_30.mdl",
	zs3v_40 = "railroad/signals/zs3v/ks_zs3v_40.mdl",
	zs3v_50 = "railroad/signals/zs3v/ks_zs3v_50.mdl",
	zs3v_60 = "railroad/signals/zs3v/ks_zs3v_60.mdl",
	zs3v_70 = "railroad/signals/zs3v/ks_zs3v_70.mdl",
	zs3v_80 = "railroad/signals/zs3v/ks_zs3v_80.mdl",
	zs3v_90 = "railroad/signals/zs3v/ks_zs3v_90.mdl",
	zs3v_100 = "railroad/signals/zs3v/ks_zs3v_100.mdl",
	zs3v_110 = "railroad/signals/zs3v/ks_zs3v_110.mdl",
	zs3v_120 = "railroad/signals/zs3v/ks_zs3v_120.mdl",
	zs3v_130 = "railroad/signals/zs3v/ks_zs3v_130.mdl",
	zs3v_140 = "railroad/signals/zs3v/ks_zs3v_140.mdl",
	zs3v_150 = "railroad/signals/zs3v/ks_zs3v_150.mdl",
	zs3v_160 = "railroad/signals/zs3v/ks_zs3v_160.mdl",
}

-- 2920749928 Ks-Signalsystem
local ks = {
	asig_ks1 = "railroad/ks_signale/asig/ks_fm_4_6_asig_hp0_ks1.mdl",
	msig_asig = "railroad/ks_signale/msig_als_asig/ks_fm_4_6_msig_asig_hp0_ks1.mdl",
	msig_asig_blink = "railroad/ks_signale/msig_als_asig/ks_fm_4_6_msig_asig_hp0_ks1_blink.mdl",
	asig_ks1_zs3_40 = "railroad/ks_signale/asig/ks_amnk_asig_hp0_ks1_zs3_40.mdl",
	asig_ks1_zs3_50 = "railroad/ks_signale/asig/ks_amnk_asig_hp0_ks1_zs3_50.mdl",
	asig_ks1_zs3_60 = "railroad/ks_signale/asig/ks_amnk_asig_hp0_ks1_zs3_60.mdl",
	asig_ks1_zs3_70 = "railroad/ks_signale/asig/ks_amnk_asig_hp0_ks1_zs3_70.mdl",
	asig_ks1_zs3_80 = "railroad/ks_signale/asig/ks_amnk_asig_hp0_ks1_zs3_80.mdl",
	asig_ks1_zs3_90 = "railroad/ks_signale/asig/ks_amnk_asig_hp0_ks1_zs3_90.mdl",
	asig_ks1_zs3_100 = "railroad/ks_signale/asig/ks_amnk_asig_hp0_ks1_zs3_100.mdl",
	asig_ks1_zs3_110 = "railroad/ks_signale/asig/ks_amnk_asig_hp0_ks1_zs3_110.mdl",
	asig_ks1_zs3_120 = "railroad/ks_signale/asig/ks_amnk_asig_hp0_ks1_zs3_120.mdl",
	asig_ks1_zs3_130 = "railroad/ks_signale/asig/ks_amnk_asig_hp0_ks1_zs3_130.mdl",
	asig_ks1_zs3_140 = "railroad/ks_signale/asig/ks_amnk_asig_hp0_ks1_zs3_140.mdl",
	bsig_ks1 = "railroad/ks_signale/bsig/ks_amhk_bsig_hp0_ks1.mdl",
	bsig_ks1_left = "railroad/ks_signale/bsig/ks_amhk_bsig_hp0_ks1_links.mdl",
	msig_ks1 = "railroad/ks_signale/msig/ks_amhk_msig_hp0_ks1.mdl",
	msig_ks1_left = "railroad/ks_signale/msig/ks_amhk_msig_hp0_ks1_links.mdl",
	msig_ks1_blink = "railroad/ks_signale/msig/ks_amhk_msig_hp0_ks1_blink.mdl",
	msig_ks1_blink_left = "railroad/ks_signale/msig/ks_amhk_msig_hp0_ks1_blink_links.mdl",
	msig_ks1_zs3_100 = "railroad/ks_signale/msig/ks_amhk_msig_hp0_ks1_zs3_100.mdl",
	msig_ks1_zs3_100_left = "railroad/ks_signale/msig/ks_amhk_msig_hp0_ks1_zs3_100_links.mdl",
	vsig = "railroad/ks_signale/vsig/ks_fm_4_6_vsig_ks2_ks1.mdl",
	vsig_left = "railroad/ks_signale/vsig/ks_fm_4_6_vsig_ks2_ks1_links.mdl",
	vsig_wdh = "railroad/ks_signale/vsig/ks_fm_4_6_vsig_ks2_ks1_w.mdl",
	vsig_wdh_left = "railroad/ks_signale/vsig/ks_fm_4_6_vsig_ks2_ks1_w_links.mdl",
	vsig_zs3v_80q_left = "railroad/ks_signale/vsig/ks_fm_4_6_vsig_ks2_ks1_zs3v_80_links.mdl",
	sh1_high = "railroad/ks_signale/ls/ks_ls_hoch_hp0_sh1.mdl",
	sh1_low = "railroad/ks_signale/ls/ks_ls_niedrig_hp0_sh1.mdl",
	sh1_low_left = "railroad/ks_signale/ls/ks_ls_niedrig_hp0_sh1_links.mdl",
}

-- 2770910636 Level crossing signals
local bue = {
	buesig = "railroad/BUe-Signale/buesig_modern.mdl",
	ptafel = "railroad/BUe-Signale/bue_mast_P_wp.mdl",
}


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
		add(bue.buesig)
	end

	if signal.crossingdistant then
		add(bue.buesig)
	end

	if signal.route then
		add(sk.zs2_F)
	end

	if signal.routedistant then
		add(sk.zs2v_F)
	end

	-- if signal.wrongtrack then
		-- add(sk.zs6)
	-- end

	if signal.departure then
		add(sk.zp9)
	end

	if signal.whistle then
		add(bue.ptafel)
	end

	-- if signal.stop=="DE-ESO:ne5"
	
	return sigtypes
end

function st.main(signal)
	-- not considering semaphores
	if signal.main=="DE-ESO:hp" then
		if signal.main_function=="exit" then
			return hv.aus_hp2
		elseif signal.main_function=="entry" then
			if signal.position_left then
				return hv.ein_left
			else
				return hv.ein
			end
		else -- make default if function missing; if signal.main_function=="block" or signal.main_function=="intermediate" then -- what's the difference?
			if signal.position_left then
				return hv.bl_left
			else
				return hv.bl
			end
		end
	elseif signal.main=="DE-ESO:ks" then
		if signal.main_function=="exit" then
			return ks.asig_ks1
		elseif signal.main_function=="entry" then
			if signal.position_left then
				return ks.msig_ks1_left
			else
				return ks.msig_ks1
			end
		else -- make default if function missing; if signal.main_function=="block" or signal.main_function=="intermediate" then
			if signal.position_left then
				return ks.bsig_ks1_left
			else
				return ks.bsig_ks1
			end
		end
	elseif signal.main=="DE-ESO:hl" then
		return nep.hl1
	end
end

function st.combined(signal)
	if signal.combined=="DE-ESO:ks" then  -- dont actually quite understand what "combined" is
		if signal.combined_function=="exit" then
			return ks.msig_asig_blink
		elseif signal.combined_function=="entry" then
			if signal.position_left then
				return ks.msig_ks1_blink_left
			else
				return ks.msig_ks1_blink
			end
		else --if signal.combined_function=="block" or signal.combined_function=="intermediate" then
			if signal.position_left then
				return ks.msig_ks1_left
			else
				return ks.msig_ks1
			end
		end
	-- elseif signal.combined=="DE-ESO:hl"
	end
end

function st.maindistant(signal)
	if signal.main=="DE-ESO:hp" and signal.distant=="DE-ESO:vr" then
		if signal.main_function=="exit" then
			return hv.aus_hp2_vr0
		elseif signal.main_function=="entry" then
			if signal.position_left then
				return hv.ein_hp2_vr0_left
			else
				return hv.ein_hp2_vr0
			end
		else --if signal.main_function=="block" or signal.main_function=="intermediate" then -- what's the difference?
			if signal.position_left then
				return hv.bl_vr1_left
			else
				return hv.bl_vr1
			end
		end
	end
end

function st.distant(signal)
	-- not considering semaphores
	if signal.distant=="DE-ESO:vr" then
		if signal.distant_repeated then --or signal.distant_shortened 
			if signal.position_left then
				return hv.vr_wdh_left
			else
				return hv.vr_wdh
			end
		else
			if signal.position_left then
				return hv.vr_left
			else
				return hv.vr
			end
		end
	elseif signal.distant=="DE-ESO:ks" then
		if signal.distant_repeated then --or signal.distant_shortened 
			if signal.position_left then
				return ks.vsig_wdh_left
			else
				return ks.vsig_wdh
			end
		else
			if signal.position_left then
				return ks.vsig_left
			else
				return ks.vsig
			end
		end
	-- elseif signal.distant=="DE-ESO:hl" then
	end
end

function st.minor(signal)
	if signal.minor:starts("DE-ESO:sh") then
		if signal.minor_dwarf then
			if signal.position_left then
				return ks.sh1_low_left
			else
				return ks.sh1_low
			end
		else
			return ks.sh1_high
		end
	end
end

function st.speedlimit(signal)
	if signal.speedlimit=="DE-ESO:zs3" then
		if signal.speedlimit_form=="sign" then
			
		else  -- light
			local res = sk["zs3_"..tostring(signal.speedlimit_speed_int or "")]
			if res then 
				return res
			else
				print("ERROR no signal DE-ESO:zs3 found for speed:",signal.speedlimit_speed_int)
			end
		end
	elseif signal.speedlimit=="DE-ESO:lf7" then  -- sign
		-- This mod 1966094307 has the signs, but as constructions not as signals...
	end
end
	
function st.speedlimitdistant(signal)
	if signal.speedlimitdistant=="DE-ESO:zs3v" then
		if signal.speedlimitdistant_form=="sign" then
			
		else  -- light
			local res = sk["zs3v_"..tostring(signal.speedlimitdistant_speed_int or "")]
			if res then 
				return res
			else
				print("ERROR no signal DE-ESO:zs3v found for speed:",signal.speedlimitdistant_speed_int)
			end
		end
	elseif signal.speedlimitdistant=="DE-ESO:lf6" then  -- sign
		-- This mod 1966094307 has the signs, but as constructions not as signals...
	end
end

function st.isWaypoint(mdl)
	local model = api.res.modelRep.get(api.res.modelRep.find(mdl))
	return model.metadata.signal.type==1
end

return st