local tt = {
	default_type_rail = "railroad_old.lua", -- Vanilla
	default_type_street = "street_old.lua", -- Vanilla
}

function tt.getType(data)
	if data.track then
		return tt.default_type_rail 
	else 
		return tt.default_type_street
	end
end

return tt