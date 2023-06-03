local tools = require"osm_importer.tools"
local streettypes = require"osm_importer.types_street"
local tracktypes = require"osm_importer.types_track"
local bridgetypes = require"osm_importer.types_bridge"
local tunneltypes = require"osm_importer.types_tunnel"

local default_cbLevel = 1

local s = {
	streettypes = streettypes,
	tracktypes = tracktypes,
}

local function options()
	return osm_importer.options
end


function s.cmdcallback(cbLevel,cbFunc,retryWSmStreet)
	return function(res, success)
		local status, ret = pcall(function()
			s.res = res
			if cbLevel>=1 then
				if cbLevel>=3 then
					print("Result:",res)
					if cbLevel>=4 then
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
		end)
		if not status then
			print("Callback ERROR",ret)
		end
	end
end


function s.SimpleProposalCmd(data,context,ignoreErrors,cbLevel,cbFunc,retryWSmStreet)
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

function s.SimpleProposal(nodes,edges,edgeObjects,constructions)
	local p = api.type.SimpleProposal.new()
	local sp = p.streetProposal
	s.sp = sp
	
	local nodeindex = {}
	for id,node in pairs(nodes) do
		local idx = #sp.nodesToAdd
		if node.id then  -- existing
		else
			local n = s.Node(-1-idx, node)
			if n==false then
				return p  -- invalid node, return empty proposal
			end
			if n then
				sp.nodesToAdd[idx+1] = n
				nodeindex[id] = idx+1
			end
		end
	end
	local nnodes = #sp.nodesToAdd
	
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
		local node = nodes[nodeId]
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
	
	local function getNodeTan(nodeId,diff,mirror)
		local node = getNode(nodeId)
		if not node.tangent then
			return
		end
		local n0 = node.path_predecessor
		local n2 = node.path_successor
		local n0pos = getNodePos(n0)
		local pos = getNodePos(nodeId)
		local n2pos = getNodePos(n2)
		local length = tools.VecDist(diff)
		local v = api.type.Vec3f.new(  -- assuming node.tangent vector has length 1
			node.tangent[1]*length*(mirror and -1 or 1),
			node.tangent[2]*length*(mirror and -1 or 1),
			-- diff.z
			((n2pos.z-pos.z)/tools.VecDist(n2pos-pos)/2 + (pos.z-n0pos.z)/tools.VecDist(pos-n0pos)/2)*length*(mirror and -1 or 1)
		)
		local ang = tools.VecAngleCos(v,diff)
		if ang<0 and not mirror then  -- vector other direction
			return getNodeTan(nodeId,diff,true)
		else
			if ang<0.8 then	
				print("WARNING Angle<0.8: "..ang.." for node "..nodeId)
			end
			return v
		end
	end
	
	for id,edge in pairs(edges) do
		local idx = #sp.edgesToAdd
		local e = s.Edge(-nnodes-1-idx, edge, getNodeEntity, getNodePos, getNodeTan)
		if e then
			sp.edgesToAdd[idx+1] = e
		end
	end
	--sp.edgeObjectsToAdd
	--p.constructionsToAdd
	return p
end

function s.Node(entity,node)
	local n = api.type.NodeAndEntity.new()
	assert(entity<0)
	n.entity = entity or -1
	assert(n.entity<0)  -- int32 ?
	local position = node.pos
	n.comp.position = api.type.Vec3f.new(
		assert(position[1]), 
		assert(position[2]), 
		position[3] or tools.getTerrainZ(position[1], position[2])
	)
	if not tools.isValidCoordinate(position[1], position[2]) then
		print("Node "..entity, "pos out of map: "..toString(position))
		if options().skip_nodes_outofbounds then
			return false
		end
	end
	n.comp.doubleSlipSwitch = node.switch==true  -- can create C:\GitLab-Runner\builds\1BJoMpBZ\0\ug\urban_games\train_fever\src\Lib\Geometry\Streets\track\Crossing.cpp:235: __cdecl StreetGeometry::track::Crossing::Crossing(const struct StreetGeometry::TransitionContext &,class std::vector<struct StreetGeometry::ConnectorContext,class std::allocator<struct StreetGeometry::ConnectorContext> >): Assertion `Angle(m_ctxs[0].curve[2], m_ctxs[1].curve[2]) >= ANGLE_MIN' failed.
	return n
end

function s.Edge(entity,data,getNodeEntity,getNodePos,getNodeTan)
	local e = api.type.SegmentAndEntity.new()
	assert(entity<0)
	e.entity = entity or -1
	assert(e.entity<0)  -- int32 ?
	--e.playerOwned
	
	e.comp.node0 = getNodeEntity( assert(data.node0, "No node0 for entity: "..entity))
	e.comp.node1 = getNodeEntity( assert(data.node1, "No node1 for entity: "..entity))
	
	local tang_straight = getNodePos(data.node1) - getNodePos(data.node0)  -- straight edge
	local tracks_curved = options().tracks_curved
	e.comp.tangent0 = data.track and tracks_curved and getNodeTan(data.node0,tang_straight) or tang_straight
	e.comp.tangent1 = data.track and tracks_curved and getNodeTan(data.node1,tang_straight) or tang_straight
	
	local skip_tracks_shorter_than = options().skip_tracks_shorter_than
	local tang_length = tools.VecDist(tang_straight)
	if data.track and skip_tracks_shorter_than and tang_length<skip_tracks_shorter_than then
		print("Skip - Edge too short ",tang_length)
		return
	end
	
	local skip_tracks_radius_smaller_than = options().skip_tracks_radius_smaller_than
	local tang_radius = tools.calcRadius(
		getNodePos(data.node0),
		getNodePos(data.node1),
		e.comp.tangent0,
		e.comp.tangent1
	)
	if data.track and skip_tracks_radius_smaller_than and tang_radius<skip_tracks_radius_smaller_than then
		print("Skip - Edge too narrow radius ",tang_radius)
		return
	end
	
	if data.track then
		local track = data.track
		e.type = 1   -- 0 = street; 1 = track
		local ttype = tracktypes.getType(track)
		if not ttype or ttype=="" then
			return
		end
		e.trackEdge.trackType = api.res.trackTypeRep.find(ttype)
		assert(e.trackEdge.trackType>=0 or debugPrint(track), "Track Type not found: '"..ttype.."'")
		e.trackEdge.catenary = not not track.electrified
		if track.reverse then  -- reverse added from certain track type
			e.comp.node0, e.comp.node1 = e.comp.node1, e.comp.node0
			e.comp.tangent0, e.comp.tangent1 = tools.Vec3Mul(e.comp.tangent1,-1), tools.Vec3Mul(e.comp.tangent0,-1)
		end
	elseif data.street then
		local street = data.street
		e.type = 0
		local stype = streettypes.getType(street,options())
		if not stype or stype=="" then
			return
		end
		e.streetEdge.streetType = api.res.streetTypeRep.find(stype)
		assert(e.streetEdge.streetType>=0 or debugPrint(street), "Street Type not found: '"..stype.."'")
		e.streetEdge.hasBus = street.buslane or false
		e.streetEdge.tramTrackType = (street.tram==true and 2) or (street.tram==false and 1) or 0
	else
		error(debugPrint(data) or "Edge no street or track")
	end
	
	if data.bridge then
		if options().build_bridges then
			e.comp.type = 1
			local bridgeType = bridgetypes.getType(data)
			if not bridgeType then
				return
			end
			e.comp.typeIndex = api.res.bridgeTypeRep.find(bridgeType)
			assert(e.comp.typeIndex>=0 or debugPrint(data), "Bridge Type not found: '"..bridgeType.."'")
		else
			return
		end
	end
	
	if data.tunnel then
		if options().build_tunnels then
			e.comp.type = 2
			local tunnelType = tunneltypes.getType(data)
			e.comp.typeIndex = api.res.tunnelTypeRep.find(tunnelType)
			assert(e.comp.typeIndex>=0 or debugPrint(data), "Tunnel Type not found: '"..tunnelType.."'")
		else
			return
		end
	end
	
	return e
end

function s.Context()
	local c = api.type.Context.new()
	--c.checkTerrainAlignment = false
	--c.cleanupStreetGraph = false
	-- gatherBuildings = false
	--gatherFields = true
	return c
end

-- causing weird self calls ???
-- for fname,desc in pairs(doc) do
	-- local func = s[fname]
	-- s[fname] = {
		-- __doc__ = desc,
	-- }
	-- setmetatable(s[fname], {
		-- __call = func,
	-- })
-- end

return s