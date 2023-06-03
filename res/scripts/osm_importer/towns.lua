local t = {}

function t.createTown(caps,pos,name,devactive)
	local town = api.type.TownInfo.new()
	town.name = name
	town.position = api.type.Vec2f.new(pos[1],pos[2])
	assert(#caps==3)
	town.initialLandUseCapacities = caps
	api.cmd.sendCommand(
		api.cmd.make.createTowns({town}),
		function(res, success)
			if success then
				-- d(res)  --id???
				if devactive==false then
					-- game.interface.setTownDevelopmentActive(id, false)
				end
			else
				print("Create Town, no success !",name)
			end
		end
	)
end

function t.createTownLabel(pos,name)
	t.createTown({0,0,0},pos,name,false)
end

function t.createTownLabels(towns)
	print("Start Create Town Labels",#towns)
	for i,data in pairs(towns) do
		t.createTownLabel(data.pos,data.name)
	end
end

function t.setAllTownsDevActive(active)
	-- local towns = game.interface.getTowns()  -- not working for newly created towns??
	local towns = game.interface.getEntities({radius=math.huge},{type="TOWN"})
	for _,id in pairs(towns) do
		game.interface.setTownDevelopmentActive(id, active)
	end
end

return t