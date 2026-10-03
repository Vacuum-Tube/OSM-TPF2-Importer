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
		local invoked
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
			local rpd = res and res.resultProposalData
			if not success and (cbLevel>=2 and cbLevel<4) and rpd then
				print("errorState:",toString(rpd.errorState))
			end
			local collisions = rpd and rpd.collisionInfo and rpd.collisionInfo.collisionEntities
			if collisions and #collisions>0 and ( (cbLevel>=2 or (cbLevel>=1 and not success)) and cbLevel<4) then
				print("Collision:",toString(collisions))
			end
			
			if success==false and retryWSmStreet then
				local street
				local added = res and res.proposal and res.proposal.proposal and res.proposal.proposal.addedSegments
				for i,edge in pairs(added or {}) do
					if edge.type == 0 then
						street = true
						local airportstreet  -- avoid airport streets, creating crash message
						local stRep = edge.streetEdge and api.res.streetTypeRep.get(edge.streetEdge.streetType)
						for j,edg in pairs((stRep and stRep.laneConfigs) or {}) do
							if edg.transportModes[api.type.enum.TransportMode.AIRCRAFT+1]==1 or edg.transportModes[api.type.enum.TransportMode.SMALL_AIRCRAFT+1]==1 then
								airportstreet = true
							end
						end
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
				invoked = true
				cbFunc(res, success)
			end
		end, 
		function(msg)
			return msg.."\n"..debug.traceback()
		end)
		if not status then
			print("Callback ERROR", ret)
			if cbFunc and not invoked then
				pcall(cbFunc, res or {skipped=true}, false)
			end
		end
	end
end


function s.SimpleProposalCmd(data,context,ignoreErrors,cbLevel,cbFunc,retryWSmStreet)
	s.cbLevel = cbLevel
	local ok, p = pcall(s.SimpleProposal, data.nodes, data.edges)
	if not ok or not p or not p.streetProposal then
		print("SimpleProposal failed:", tostring(p))
		if cbFunc then
			cbFunc({skipped=true}, true)
		end
		return
	end
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
			cbFunc({skipped=true}, true)  -- empty proposal: skip, do not count as built
		end
		return
	end
	s.command(p,context,ignoreErrors,cbLevel,cbFunc,retryWSmStreet)
end

function s.command(proposal,context,ignoreErrors,cbLevel,cbFunc,retryWSmStreet)
	local ok, cmd = pcall(function()
		local c = api.cmd.make.buildProposal(proposal, context, ignoreErrors~=false)
		api.cmd.sendCommand(c, s.cmdcallback(cbLevel or default_cbLevel, cbFunc, retryWSmStreet))
		return c
	end)
	if not ok then
		print("buildProposal failed:", tostring(cmd))
		if cbFunc then
			cbFunc({skipped=true}, false)
		end
		return
	end
	s.cmd = cmd
	return cmd
end

function s.SimpleProposal(nodes,edges)
	local p = api.type.SimpleProposal.new()
	local sp = p.streetProposal
	s.sp = sp
	
	local nodeindex = {}
	
	local function getNode(nodeId)
		return nodes and nodes[nodeId]
	end
	
	local function getNodeEntity(nodeId)
		local node = getNode(nodeId)
		if not node then
			return
		end
		if node.id then  -- existing
			return node.id
		else
			local idx = nodeindex[nodeId]
			local added = idx and sp.nodesToAdd[idx]
			return added and added.entity
		end
	end
	
	local function getNodePos(nodeId)
		local node = nodeId and nodes[nodeId]
		if node then
			if node.id and node.comp and node.comp.position then  -- node replaced in simpleproposal_seq
				return node.comp.position
			else
				local idx = nodeindex[nodeId]
				local added = idx and sp.nodesToAdd[idx]
				if added and added.comp then
					return added.comp.position
				end
			end
		end
		local src = osmdata and osmdata.nodes and osmdata.nodes[nodeId]
		local pos = src and src.pos
		if pos then
			return api.type.Vec3f.new(pos[1], pos[2], pos[3] or 0)
		end
		return api.type.Vec3f.new(0, 0, 0)
	end
	
	-- had to move nodes ids AFTER edges ONLY because of stupid assert when EdgeObjects are added: src/Game/scripting/util.cpp:131: struct construction_builder_util::Proposal __cdecl scripting::Convert(const struct street_util::StreetToolkit &,const struct scripting::Proposal &): Assertion `eo.edgeEntity.GetId() < 0 && eo.edgeEntity.GetId() >= -(int)result.proposal.addedSegments.size()' failed.
	
	for id,nodedata in pairs(nodes) do
		local idx = #sp.nodesToAdd
		if nodedata.id then  -- existing
		else
			local okNode, node = pcall(s.Node, -#edges -1-idx, nodedata)
			if not okNode then
				print("Skip node error", id, tostring(node))
				return p
			end
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
		local okEdge, edge, edgeobjects = pcall(s.Edge, -1-idx, edgedata, getNodeEntity, getNodePos)
		if not okEdge then
			print("Skip edge error", id, tostring(edge))
			edge, edgeobjects = nil, nil
		end
		if edge then
			sp.edgesToAdd:add(edge)
			if edgedata.street and edgedata.street.type=="waterstream" then
				local drop = ({
					stream = 1,
					river = 2.2,
				})[edgedata.street.waterwaytype] or 1
				for jd,node in pairs(sp.nodesToAdd) do
					if node.entity==edge.comp.node0 or node.entity==edge.comp.node1 then
						node.comp.position.z = node.comp.position.z - drop
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
	if not node or not node.pos or not node.pos[1] or not node.pos[2] then
		return false
	end
	local n = api.type.NodeAndEntity.new()
	if not id or id >= 0 then
		return false
	end
	n.entity = id
	local position = node.pos
	n.comp.position = api.type.Vec3f.new(
		assert(position[1]), 
		assert(position[2]), 
		position[3] or tools.safeTerrainZ(position[1], position[2], 0)
	)
	local okValid, valid = pcall(tools.isValidCoordinate, position[1], position[2])
	if not okValid or not valid then
		print("Node "..id, "pos out of map: "..toString(position))
		if options().skip_nodes_outofbounds then
			return false
		end
	end
	n.comp.doubleSlipSwitch = node.switch==true  -- can create C:\GitLab-Runner\builds\1BJoMpBZ\0\ug\urban_games\train_fever\src\Lib\Geometry\Streets\track\Crossing.cpp:235: __cdecl StreetGeometry::track::Crossing::Crossing(const struct StreetGeometry::TransitionContext &,class std::vector<struct StreetGeometry::ConnectorContext,class std::allocator<struct StreetGeometry::ConnectorContext> >): Assertion `Angle(m_ctxs[0].curve[2], m_ctxs[1].curve[2]) >= ANGLE_MIN' failed.
	return n
end

function s.Edge(id,edge,getNodeEntity,getNodePos)
	local e = api.type.SegmentAndEntity.new()
	assert(id<0)
	e.entity = id or -1
	assert(e.entity<0)
	
	local playerOwnedComponent = api.type.PlayerOwned.new()
	playerOwnedComponent.player = game.interface.getPlayer()
	e.playerOwned = playerOwnedComponent  -- lock streets to prevent automatic town development
	
	local n0 = getNodeEntity(edge.node0)
	local n1 = getNodeEntity(edge.node1)
	if not n0 or not n1 then
		return
	end
	e.comp.node0 = n0
	e.comp.node1 = n1
	
	local tang_straight = getNodePos(edge.node1) - getNodePos(edge.node0)  -- straight edge
	e.comp.tangent0 = edge.tangent0 and api.type.Vec3f.new(
		edge.tangent0[1] or tang_straight.x, 
		edge.tangent0[2] or tang_straight.y, 
		edge.tangent0[3] or tang_straight.z
	) or tang_straight
	e.comp.tangent1 = edge.tangent1 and api.type.Vec3f.new(
		edge.tangent1[1] or tang_straight.x, 
		edge.tangent1[2] or tang_straight.y, 
		edge.tangent1[3] or tang_straight.z
	) or tang_straight
	
	if edge.nodes_reversed then  -- reverse edge direction again to recover original direction (oneway)
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
			local fb = tracktypes.fallback_type or "standard.lua"
			print("WARNING: Track type missing '"..ttype.."', using vanilla '"..fb.."'")
			e.trackEdge.trackType = api.res.trackTypeRep.find(fb)
			if e.trackEdge.trackType<0 then
				print("ERROR: Vanilla track type also missing: '"..fb.."'")
				assert(not options().crash_type_not_found)
				return
			end
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
			local fb = streettypes.vanillaFor and streettypes.vanillaFor(street) or streettypes.fallback_type
			print("WARNING: Street type missing '"..stype.."', using vanilla '"..tostring(fb).."'")
			e.streetEdge.streetType = api.res.streetTypeRep.find(fb)
			if e.streetEdge.streetType<0 then
				print("ERROR: Vanilla street type also missing: '"..tostring(fb).."'")
				assert(not options().crash_type_not_found)
				return
			end
		end
		e.streetEdge.hasBus = street.buslane or false
		e.streetEdge.tramTrackType = (street.tram==true and 2) or (street.tram==false and 1) or 0
	else
		print("Skip edge, neither street nor track", id)
		return
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
			local fb = "cement.lua"
			print("WARNING: Bridge type missing '"..bridgeType.."', using vanilla '"..fb.."'")
			e.comp.typeIndex = api.res.bridgeTypeRep.find(fb)
			if e.comp.typeIndex<0 then
				print("ERROR: Vanilla bridge type also missing: '"..fb.."'")
				assert(not options().crash_type_not_found)
				return
			end
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
			local fb = edge.track and "railroad_old.lua" or "street_old.lua"
			print("WARNING: Tunnel type missing '"..tunnelType.."', using vanilla '"..fb.."'")
			e.comp.typeIndex = api.res.tunnelTypeRep.find(fb)
			if e.comp.typeIndex<0 then
				print("ERROR: Vanilla tunnel type also missing: '"..fb.."'")
				assert(not options().crash_type_not_found)
				return
			end
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
					print("WARNING: Signal not found, skip: '"..sigmdl.."'")
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
	local length = object.length or 0
	local param = (length ~= 0) and (object.distance / length) or 0.5
	if param <= 0 then param = 0.01 end
	if param >= 1 then param = 0.99 end
	eo.param = param -- has to be 0<param<1
	eo.playerEntity = game.interface.getPlayer()
	return eo
end

return s