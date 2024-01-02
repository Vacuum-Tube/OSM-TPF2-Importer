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
			print("Error Handler: ", msg, debug.traceback())  -- not working?
			return msg..debug.traceback()
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
		end
		for _,edgeobject in pairs(edgeobjects or {}) do
			sp.edgeObjectsToAdd:add(edgeobject)
		end
	end
	
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

function s.Edge(entity,edge,getNodeEntity,getNodePos,getNodeTan)
	local e = api.type.SegmentAndEntity.new()
	assert(entity<0)
	e.entity = entity or -1
	assert(e.entity<0)  -- int32 ?
	--e.playerOwned
	
	e.comp.node0 = getNodeEntity( assert(edge.node0, "No node0 for entity: "..entity))
	e.comp.node1 = getNodeEntity( assert(edge.node1, "No node1 for entity: "..entity))
	
	local tang_straight = getNodePos(edge.node1) - getNodePos(edge.node0)  -- straight edge
	local tracks_curved = true --options().tracks_curved
	e.comp.tangent0 = edge.track and tracks_curved and getNodeTan(edge.node0,tang_straight) or tang_straight
	e.comp.tangent1 = edge.track and tracks_curved and getNodeTan(edge.node1,tang_straight) or tang_straight
	
	local skip_tracks_shorter_than = options().skip_tracks_shorter_than
	local tang_length = tools.VecDist(e.comp.tangent0)
	if edge.track and skip_tracks_shorter_than and tang_length<skip_tracks_shorter_than then
		print("Skip - Edge too short ",tang_length)
		return
	end
	
	local skip_tracks_radius_smaller_than = options().skip_tracks_radius_smaller_than
	local tang_radius = tools.calcRadius(
		getNodePos(edge.node0),
		getNodePos(edge.node1),
		e.comp.tangent0,
		e.comp.tangent1
	)
	if edge.track and skip_tracks_radius_smaller_than and tang_radius<skip_tracks_radius_smaller_than then
		print("Skip - Edge too narrow radius ",tang_radius)
		return
	end
	
	if edge.track then
		local track = edge.track
		e.type = 1   -- 0 = street; 1 = track
		local ttype = tracktypes.getType(track)
		if not ttype or ttype=="" then
			return
		end
		e.trackEdge.trackType = api.res.trackTypeRep.find(ttype)
		assert(e.trackEdge.trackType>=0 or debugPrint(track), "Track Type not found: '"..ttype.."'")
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
		assert(e.streetEdge.streetType>=0 or debugPrint(street), "Street Type not found: '"..stype.."'")
		e.streetEdge.hasBus = street.buslane or false
		e.streetEdge.tramTrackType = (street.tram==true and 2) or (street.tram==false and 1) or 0
	else
		error(debugPrint(edge) or "Edge no street or track")
	end
	
	if edge.bridge then
		if options().build_bridges then
			e.comp.type = 1
			local bridgeType = bridgetypes.getType(edge)
			if not bridgeType then
				return
			end
			e.comp.typeIndex = api.res.bridgeTypeRep.find(bridgeType)
			assert(e.comp.typeIndex>=0 or debugPrint(edge), "Bridge Type not found: '"..bridgeType.."'")
		else
			return
		end
	end
	
	if edge.tunnel then
		if options().build_tunnels then
			e.comp.type = 2
			local tunnelType = tunneltypes.getType(edge)
			e.comp.typeIndex = api.res.tunnelTypeRep.find(tunnelType)
			assert(e.comp.typeIndex>=0 or debugPrint(edge), "Tunnel Type not found: '"..tunnelType.."'")
		else
			return
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
				local offset = (signaltypes.isWaypoint(sigmdl) and 0 or 8) + 2  -- 2m before catenary pole; move signal 8m (Signal Distance)
				local distance = ((tang_length-offset) > 0 and (tang_length-offset) or 1) - (#eos)  -- multiple signals cannot be at the same place -> place 1m before each other
				if signal.direction_backward then
					distance = tang_length - distance
				end
				local eo = s.EdgeObject(e.entity, {
					model=sigmdl, 
					name=(signal.ref or "").." "..toString(signal), 
					left=signal.direction_backward, 
					distance=distance, 
					length=tang_length
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