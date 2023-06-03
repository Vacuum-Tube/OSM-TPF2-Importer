local b = {}

function b.deleteAll()  -- produces crashes bec happens in the same step
	b.delVehicles()
	b.delLines()
	b.delAssets()
	b.delAnimals()
	b.delSimBds()
	b.delTownBds()
	-- b.delCons()
	-- b.delStationsGroup()
	b.delEdges()
	b.delTowns()
end


function b.delVehicles()
	for i,k in pairs(game.interface.getVehicles()) do 
		api.cmd.sendCommand(api.cmd.make.sellVehicle(k))
	end
	print("Removed all Vehicles")
end

function b.delLines()
	for i,k in pairs(game.interface.getLines()) do
		api.cmd.sendCommand(api.cmd.make.deleteLine(k))
	end
	print("Removed all Lines")
end

function b.delTowns()
	for i,k in pairs(game.interface.getEntities({ radius = math.huge }, { type = "TOWN" })) do 
		api.cmd.sendCommand(api.cmd.make.removeTown(k))
	end
	print("Removed all Towns")
end


function b.delCons(cons)
	if cons==nil then
		b.delCons(game.interface.getEntities({ radius = math.huge }, { type = "CONSTRUCTION" }))
		print("Removed all Constructions")
		return
	end
	-- local p = api.type.SimpleProposal.new()
	-- p.constructionsToRemove = cons
	-- api.cmd.sendCommand(api.cmd.make.buildProposal(p, nil, false))  -- stations game crashes...
	for i,k in pairs(cons) do
		game.interface.bulldoze(k)
	end
end

function b.delTownBds()
	local townbuildings = game.interface.getEntities({ radius = math.huge }, { type = "TOWN_BUILDING" })
	local townCons = {}
	for i,k in pairs(townbuildings) do 
		townCons[i] = game.interface.getEntity(k).personCapacity
	end
	b.delCons(townCons)
	print("Removed all TownBuildings")
end

function b.delSimBds()
	local simbuildings = game.interface.getEntities({ radius = math.huge }, { type = "SIM_BUILDING" })
	local simCons = {}
	for i,k in pairs(simbuildings) do 
		simCons[i] = game.interface.getEntity(k).stockList
	end
	b.delCons(simCons)
	print("Removed all Industries")
end


function b.remFld(id)
	api.cmd.sendCommand(api.cmd.make.removeField(id))
end

function b.remType(entitytype,bulldoze)
	for i,k in pairs(game.interface.getEntities({ radius = math.huge }, { type = entitytype })) do 
		if bulldoze then
			if game.interface.bulldoze then
				game.interface.bulldoze(k)
			else
				print("No bulldoze")
			end
		else
			b.remFld(k)
		end
	end
end

function b.delAssets()
	b.remType("ASSET_GROUP")
	print("Removed all Assets")
end

function b.delStationsGroup()
	b.remType("STATION_GROUP")
	print("Removed all Stations")
end

function b.delAnimals()
	b.remType("ANIMAL")
	print("Removed all Animals")
end

function b.delEdges()
	if not game.interface.bulldoze then
		print("Not game.interface.bulldoze - Switch to Script Thread")
		return
	end
	local ents = game.interface.getEntities({ radius = math.huge }, { type = "BASE_EDGE" })
	for i,k in pairs(ents) do 
		if api.engine.entityExists(k) then
			local stat, ret = pcall(function()
				game.interface.bulldoze(k)
				--b.remFld(k)  -- c:\build\tpf2_steam\src\game\ecs\tpnetlinksystem.cpp:60: auto __cdecl ecs::TpNetLinkSystem::{ctor}::<lambda_1bbffd24a3104f63adb0507ef0a7aecb>::operator ()(class ecs::Engine *,const class ecs::Entity &) const: Assertion `m_tnEntity2linkEntities.find(entity) == m_tnEntity2linkEntities.end()' failed.
			end)
			if not stat then
				print("Error:",ret)
			end
		end
	end
	local ents2 = game.interface.getEntities({ radius = math.huge }, { type = "BASE_EDGE" })
	if #ents2==0 then
		print("Removed all Edges")
	else
		print("Not all edges gone",#ents2)
		if #ents2<#ents then
			print("Try again ...")
			b.delEdges()
		else  -- stuck
			print("Stop trying")
		end
	end
end


function b.removePlaceholders()
	for id,asset in pairs( game.interface.getEntities({radius=1e46},{type="ASSET_GROUP", includeData = true})) do if asset.models["placeholders/missing_generic.mdl"] then api.cmd.sendCommand(api.cmd.make.removeField(id)) end   end
end


return b