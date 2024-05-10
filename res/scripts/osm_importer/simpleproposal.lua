local tools = require"osm_importer.tools"
local streettypes = require"osm_importer.types_street"
local tracktypes = require"osm_importer.types_track"
local bridgetypes = require"osm_importer.types_bridge"
local tunneltypes = require"osm_importer.types_tunnel"
local signaltypes = require"osm_importer.types_signal"

local default_cbLevel = 1

local s = { }

local function options()
	return osm_importer.options
end


function s.cmdcallback(cbLevel,cbFunc,retryWSmStreet)
	return function(res, success)
		local status, ret = xpcall(function()
			s.res = res
			if cbLevel>=1 then
				if cbLevel>=3 then
					print("Result:",res)
					if cbLevel>=5 then
						debugPrint(res)
					end
				end
				if success==false or cbLevel>=3 then
					print("Success:",success)
				end
			end
			if not success and (cbLevel>=2 and cbLevel<4) then
				print("errorState:",toString(res.resultProposalData.errorState))
			end
			if #res.resultProposalData.collisionInfo.collisionEntities>0 and ( (cbLevel>=2 or (cbLevel>=1 and not success)) and cbLevel<4) then
				print("Collision:",toString(res.resultProposalData.collisionInfo.collisionEntities))
			end
			
			if success==false and retryWSmStreet then
				local street
				for i,edge in pairs(res.proposal.proposal.addedSegments) do
					if edge.type == 0 then
						street = true
						local airportstreet  -- avoid airport streets, creating crash message
						-- for id,tn in pairs(res.resultProposalData.entity2tn) do  -- not exist when success false 
							-- for j,edg in pairs(tn.edges) do
							for j,edg in pairs(api.res.streetTypeRep.get(edge.streetEdge.streetType).laneConfigs) do
								if edg.transportModes[api.type.enum.TransportMode.AIRCRAFT+1]==1 or edg.transportModes[api.type.enum.TransportMode.SMALL_AIRCRAFT+1]==1 then
									airportstreet = true
								end
							end
						-- end
						if airportstreet then
							street = false
							break
						end
						edge.streetEdge.streetType = api.res.streetTypeRep.find(streettypes.small_type)
					end
				end
				if street then
					print("Retry with Small Street")
					api.cmd.sendCommand(res, s.cmdcallback(cbLevel, cbFunc, false))
					return
				end
			end
			if cbFunc then
				cbFunc(res, success)
			end
		end, 
		function(msg)
			-- print("Error Handler: ", msg, debug.traceback())
			return msg.."\n"..debug.traceback()
		end)
		if not status then
			print("Callback ERROR", ret)
		end
	end
end


function s.SimpleProposalCmd(data,context,ignoreErrors,cbLevel,cbFunc,retryWSmStreet)
	s.cbLevel = cbLevel
	local p = s.SimpleProposal(data.nodes, data.edges)
	s.p = p
	if (cbLevel or default_cbLevel)>=4 then
		print("SimpleProposal:",toString(p))
	end
	if #p.streetProposal.edgesToAdd==0 then
		if cbLevel>=2 then
			print("Empty Proposal")
		end
		if cbFunc then
			if cbLevel>=1 then
				print("Skip Proposal")
			end
			cbFunc(nil, true)  -- continue with next proposal
		end
		return
	end
	-- return 
	s.command(p,context,ignoreErrors,cbLevel,cbFunc,retryWSmStreet)
end

function s.command(proposal,context,ignoreErrors,cbLevel,cbFunc,retryWSmStreet)
	local cmd = api.cmd.make.buildProposal(proposal, context, ignoreErrors~=false)  -- ignoreErrors default true
	s.cmd = cmd
	api.cmd.sendCommand(cmd, s.cmdcallback(cbLevel or default_cbLevel, cbFunc, retryWSmStreet))
	return cmd
end

function s.SimpleProposal(nodes,edges)
	local p = api.type.SimpleProposal.new()
	local sp = p.streetProposal
	s.sp = sp
	
	local nodeindex = {}
	
	local function getNode(nodeId)
		return assert(nodes[nodeId], "Node not found: "..nodeId)
	end
	
	local function getNodeEntity(nodeId)
		local node = getNode(nodeId)
		if node.id then  -- existing
			return node.id
		else
			return sp.nodesToAdd[nodeindex[nodeId]].entity
		end
	end
	
	local function getNodePos(nodeId)
		local node = nodes[assert(nodeId, nodeId)]
		if node then
			if node.id then  -- node replaced in simpleproposal_seq
				return node.comp.position
			else
				return sp.nodesToAdd[nodeindex[nodeId]].comp.position
			end
		else  -- node not in proposal
			local pos = osmdata.nodes[nodeId].pos
			return api.type.Vec3f.new(pos[1], pos[2], pos[3])
		end
	end
	
	local function getNodeTan(nodeId,tangent,diff,etype)
		if not tangent then
			return
		end
		local n02 = getNode(nodeId)[string.format("path_%s",etype)]
		if not n02 then print( "Node no path_predecessor "..nodeId) return end
		local n0pos = getNodePos(n02[1][1])
		local pos = getNodePos(nodeId)
		local n2pos = getNodePos(n02[1][2])
		local length = tools.VecDist(diff)
		local tangZ = 0
		local tangZ01 = (pos.z-n0pos.z)/tools.VecDist(pos-n0pos)
		local tangZ12 = (n2pos.z-pos.z)/tools.VecDist(n2pos-pos)
		if tangZ12/tangZ01<0 then  -- rise and fall
			tangZ = 0
		else
			if math.abs(tangZ01)>math.abs(tangZ12) then  -- keep slopes low at the starts/ends
				tangZ = tangZ12*length
			else
				tangZ = tangZ01*length
			end
		end			
		local tang = api.type.Vec3f.new(
			tangent[1],
			tangent[2],
			tangZ 
		)
		if tang.z/diff.z<0 then
			print("WARNING: different sign tangZ"..toString(tang).." - diff".. toString(diff))
		end
		return tang
	end
	
	-- had to move nodes ids AFTER edges ONLY because of stupid assert when EdgeObjects are added: src/Game/scripting/util.cpp:131: struct construction_builder_util::Proposal __cdecl scripting::Convert(const struct street_util::StreetToolkit &,const struct scripting::Proposal &): Assertion `eo.edgeEntity.GetId() < 0 && eo.edgeEntity.GetId() >= -(int)result.proposal.addedSegments.size()' failed.
	
	for id,nodedata in pairs(nodes) do
		local idx = #sp.nodesToAdd
		if nodedata.id then  -- existing
		else
			local node = s.Node(-#edges -1-idx, nodedata)
			if node==false then
				return p  -- invalid node, return empty proposal
			end
			if node then
				sp.nodesToAdd:add(node)
				nodeindex[id] = idx+1
			end
		end
	end
	
	for id,edgedata in pairs(edges) do
		local idx = #sp.edgesToAdd
		local edge, edgeobjects = s.Edge(-1-idx, edgedata, getNodeEntity, getNodePos, getNodeTan)
		if edge then
			sp.edgesToAdd:add(edge)
			if edgedata.street and edgedata.street.type=="waterstream" then
				for jd,node in pairs(sp.nodesToAdd) do
					if node.entity==edge.comp.node0 or node.entity==edge.comp.node1 then
						node.comp.position.z = node.comp.position.z - ({
							stream = 1,
							river = 2.2,
						})[edgedata.street.waterwaytype]  -- lower streams into terrain. tangent?
					end
				end
			end
		end
		for _,edgeobject in pairs(edgeobjects or {}) do
			sp.edgeObjectsToAdd:add(edgeobject)
		end
	end
	
	return p
end

function s.Node(id,node)
	local n = api.type.NodeAndEntity.new()
	assert(id<0)
	n.entity = id or -1
	assert(n.entity<0)  -- int32 ?
	local position = node.pos
	n.comp.position = api.type.Vec3f.new(
		assert(position[1]), 
		assert(position[2]), 
		position[3] or tools.getTerrainZ(position[1], position[2])
	)
	if not tools.isValidCoordinate(position[1], position[2]) then
		print("Node "..id, "pos out of map: "..toString(position))
		if options().skip_nodes_outofbounds then
			return false
		end
	end
	n.comp.doubleSlipSwitch = node.switch==true  -- can create C:\GitLab-Runner\builds\1BJoMpBZ\0\ug\urban_games\train_fever\src\Lib\Geometry\Streets\track\Crossing.cpp:235: __cdecl StreetGeometry::track::Crossing::Crossing(const struct StreetGeometry::TransitionContext &,class std::vector<struct StreetGeometry::ConnectorContext,class std::allocator<struct StreetGeometry::ConnectorContext> >): Assertion `Angle(m_ctxs[0].curve[2], m_ctxs[1].curve[2]) >= ANGLE_MIN' failed.
	return n
end

function s.Edge(id,edge,getNodeEntity,getNodePos,getNodeTan)
	local e = api.type.SegmentAndEntity.new()
	assert(id<0)
	e.entity = id or -1
	assert(e.entity<0)
	
	local playerOwnedComponent = api.type.PlayerOwned.new()
	playerOwnedComponent.player = game.interface.getPlayer()
	e.playerOwned = playerOwnedComponent  -- lock streets to prevent automatic town development
	
	local etype = edge.track and "track" or "street"
	
	e.comp.node0 = getNodeEntity( assert(edge.node0, "No node0 for entity: "..id))
	e.comp.node1 = getNodeEntity( assert(edge.node1, "No node1 for entity: "..id))
	
	local tang_straight = getNodePos(edge.node1) - getNodePos(edge.node0)  -- straight edge
	local curved = true
	e.comp.tangent0 = curved and getNodeTan(edge.node0, edge.tangent0, tang_straight, etype) or tang_straight
	e.comp.tangent1 = curved and getNodeTan(edge.node1, edge.tangent1, tang_straight, etype) or tang_straight
	
	if edge.nodes_reversed then
		e.comp.node0, e.comp.node1 = e.comp.node1, e.comp.node0
		e.comp.tangent0, e.comp.tangent1 = tools.Vec3Mul(e.comp.tangent1, -1), tools.Vec3Mul(e.comp.tangent0, -1)
	end
	local edge_length = tools.hermiteLength(
		getNodePos(edge.node0),
		getNodePos(edge.node1),
		e.comp.tangent0,
		e.comp.tangent1
	)
	
	if edge.track then
		local track = edge.track
		e.type = 1   -- 0 = street; 1 = track
		local ttype = tracktypes.getType(track)
		if not ttype or ttype=="" then
			return
		end
		e.trackEdge.trackType = api.res.trackTypeRep.find(ttype)
		if e.trackEdge.trackType<0 then
			print("ERROR: Track Type not found: '"..ttype.."' track"..toString(track).." (Mod missing?)")
			assert(not options().crash_type_not_found)
		end
		e.trackEdge.catenary = not not track.electrified  -- bool()
		if track.reverse then  -- reverse added from certain track type
			e.comp.node0, e.comp.node1 = e.comp.node1, e.comp.node0
			e.comp.tangent0, e.comp.tangent1 = tools.Vec3Mul(e.comp.tangent1,-1), tools.Vec3Mul(e.comp.tangent0,-1)
		end
	elseif edge.street then
		local street = edge.street
		e.type = 0
		local stype = streettypes.getType(street,options())
		if not stype or stype=="" then
			return
		end
		e.streetEdge.streetType = api.res.streetTypeRep.find(stype)
		if e.streetEdge.streetType<0 then
			print("ERROR: Street Type not found: '"..stype.."' street"..toString(street).." (Mod missing?)")
			assert(not options().crash_type_not_found)
		end
		e.streetEdge.hasBus = street.buslane or false
		e.streetEdge.tramTrackType = (street.tram==true and 2) or (street.tram==false and 1) or 0
	else
		error(debugPrint(edge) or "Edge no street or track")
	end
	
	if edge.bridge then
		if not options().build_bridges then
			return
		end
		e.comp.type = 1
		local bridgeType = bridgetypes.getType(edge)
		if not bridgeType then
			return
		end
		e.comp.typeIndex = api.res.bridgeTypeRep.find(bridgeType)
		if e.comp.typeIndex<0 then
			print("ERROR: Bridge Type not found: '"..bridgeType.."' edge"..toString(edge).." (Mod missing?)")
			assert(not options().crash_type_not_found)
		end
	end
	
	if edge.tunnel then
		if not options().build_tunnels then
			return
		end
		e.comp.type = 2
		local tunnelType = tunneltypes.getType(edge)
		if not tunnelType then
			return
		end
		e.comp.typeIndex = api.res.tunnelTypeRep.find(tunnelType)
		if e.comp.typeIndex<0 then
			print("ERROR: Tunnel Type not found: '"..tunnelType.."' edge"..toString(edge).." (Mod missing?)")
			assert(not options().crash_type_not_found)
		end
	end
	
	local eos = {}
	local objects = {}
	if edge.objects then
		if edge.objects.signal and edge.track and options().build_signals then
			local signal = edge.objects.signal
			local types = signaltypes.getTypes(signal)
			if s.cbLevel>=2 and #types==0 then
				print("No mdl found for signal: "..toString(signal))
			end
			if s.cbLevel>=3 then
				print("Signal mdls: "..toString(types))
			end
			for _,sigmdl in pairs(types) do
				if api.res.modelRep.find(sigmdl)<0 then
					print("ERROR: Signal not found: '"..sigmdl.."' (Mod missing?)")
					assert(not options().crash_type_not_found)
					break
				end
				local offset = (signaltypes.isWaypoint(sigmdl) and 0 or 8) + 2  -- 2m before catenary pole; move signal 8m (Signal Distance)
				local distance = ((edge_length-offset) > 0 and (edge_length-offset) or 1) - (#eos)  -- multiple signals cannot be at the same place -> place 1m before each other
				if signal.direction_backward then
					distance = edge_length - distance
				end
				local eo = s.EdgeObject(e.entity, {
					model=sigmdl, 
					name=(signal.ref or "").." "..toString(signal), 
					left=signal.direction_backward, 
					distance=distance, 
					length=edge_length
				})
				table.insert(eos, eo)
				table.insert(objects, { -(#eos), 2 }) -- First value: negative idx in EdgeObject to add; Second value EdgeObjectType: 0 (STOP_LEFT), 1 (STOP_RIGHT), 2 (SIGNAL)
			end
		end
		e.comp.objects = objects
	end
	
	return e, eos
end

function s.EdgeObject(entity,object)
	local eo = api.type.SimpleStreetProposal.EdgeObject.new()
	eo.edgeEntity = entity
	eo.model = assert(object.model)
	eo.name = object.name or "" 
	eo.left = object.left or false  -- direction
	eo.oneWay = object.oneway or false
	eo.param = object.distance/object.length -- has to be 0<param<1
	eo.playerEntity = game.interface.getPlayer()
	return eo
end

return s