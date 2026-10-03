local simpleproposal = require"osm_importer.simpleproposal"
local nodesheights = require"osm_importer.nodesheights"
local tools = require"osm_importer.tools"
local timer = require"osm_importer.timer"

local s = {}


local function failpct(n, d)
	if not d or d == 0 then
		return 0
	end
	return 100 * n / d
end

local function persistRemaining()
	local keys = {}
	if s.seqlist and s.seqi and s.nseq then
		for i = s.seqi, s.nseq do
			local edge = s.seqlist[i]
			if edge and edge.__key then
				keys[#keys+1] = edge.__key
			end
		end
	end
	_G.osm_importer_seq_keys = keys
end

local function restoreRemaining(data)
	local keys = _G.osm_importer_seq_keys
	if type(keys) ~= "table" or #keys == 0 then
		return nil
	end
	local list = {}
	for _, key in ipairs(keys) do
		local edge = data.edges[key]
		if edge then
			edge.__key = key
			list[#list+1] = edge
		end
	end
	if #list == 0 then
		return nil
	end
	return list
end

function s.edgeAlreadyBuilt(edge)
	local n0 = s.data.nodes[edge.node0]
	local n1 = s.data.nodes[edge.node1]
	if not n0 or not n1 then
		return false
	end
	local id0 = s.getIdIfExist(edge.node0)
	local id1 = s.getIdIfExist(edge.node1)
	if not (id0 and id1) then
		return false
	end
	local p0, p1 = n0.pos, n1.pos
	local mid = { (p0[1]+p1[1])*0.5, (p0[2]+p1[2])*0.5 }
	local dx, dy = p0[1]-p1[1], p0[2]-p1[2]
	local radius = math.max(4, math.sqrt(dx*dx+dy*dy)*0.5 + 2)
	local ents = game.interface.getEntities({pos=mid, radius=radius}, {type="BASE_EDGE"})
	for _, eid in pairs(ents) do
		local comp = api.engine.getComponent(eid, api.type.ComponentType.BASE_EDGE)
		if comp and ((comp.node0==id0 and comp.node1==id1) or (comp.node0==id1 and comp.node1==id0)) then
			return true
		end
	end
	return false
end

function s.SimpleProposalSeq(data,options)
	osm_importer.options = assert(options, "Options not defined")
	s.data = data
	s.cbLevel = options.log_level or 1
	assert(type(s.cbLevel)=="number")

	local remaining = s.seqlist and s.nseq and s.seqi and s.seqi <= s.nseq
	if s.stop and remaining then
		print("Resume remaining edges:", (s.nseq - s.seqi + 1))
		s.stop = false
		s.pb = s.tryProgressWindow()
		s.SimpleProposalSeqE()
		return
	end

	local restored = restoreRemaining(data)
	if restored then
		print("Resume stored remaining edges:", #restored)
		s.stop = false
		s.called = true
		s.finished = false
		s.seqlist = restored
		s.nseq = #restored
		s.seqi = 1
		s.count = 0
		s.nedges = { STREET = 0, TRACK = 0 }
		s.nosuc = { STREET = 0, TRACK = 0 }
		s.nskipped = { STREET = 0, TRACK = 0 }
		s.pb = s.tryProgressWindow()
		s.SimpleProposalSeqE()
		return
	end

	s.stop = false
	s.called = true
	s.finished = false
	print("Start SimpleProposalCmdSeq")
	print(os.date())
	timer.start()
	print("Options: "..toString(options))

	local already_z
	for _, node in pairs(data.nodes) do
		already_z = node.pos and node.pos[3]
		break
	end
	if already_z then
		print("Node heights already set; skip.")
	else
		print("Set Nodes z height and tangents...")
		local okh, errh = pcall(nodesheights.setAllNodesHeight, data.nodes, data.paths or {}, data.edges)
		if not okh then
			print("WARNING nodesheights failed:", errh)
		end
	end

	local skipBuilt = s.hadRun == true
	s.seqlist = {}
	for key,edge in pairs(data.edges) do
		if (options.build_streets and edge.street)
		or (options.build_tracks and edge.track
			and (options.build_tramtracks or not edge.track.tram)
			and (options.build_subwaytracks or not edge.track.subway )) then
			edge.__key = key
			if skipBuilt and s.edgeAlreadyBuilt(edge) then
				-- already on the map from a previous Stage 3 run
			else
				table.insert(s.seqlist, edge)
			end
		end
	end
	s.hadRun = true
	s.nseq = #s.seqlist
	s.seqi = 1
	s.nedges = {
		STREET = 0,
		TRACK = 0,
	}
	s.nosuc = {
		STREET = 0,
		TRACK = 0,
	}
	s.nskipped = {
		STREET = 0,
		TRACK = 0,
	}
	s.count = 0
	print("Edges:  "..s.nseq)
	print(string.format("Estimated Time: %.0f min (%.2f h)", s.nseq/5/60, s.nseq/5/3600))
	s.pb = s.tryProgressWindow()
	s.SimpleProposalSeqE()
end

function s.countEdge(edge, skipped, failed)
	local etype = (edge and edge.track) and "TRACK" or "STREET"
	s.nedges[etype] = (s.nedges[etype] or 0) + 1
	if skipped then
		s.nskipped[etype] = (s.nskipped[etype] or 0) + 1
	elseif failed then
		s.nosuc[etype] = (s.nosuc[etype] or 0) + 1
	end
end

function s.finishSeq()
	print("-------------------------------------------------------------")
	if s.stop then
		print("Process aborted !")
		print(string.format("Remaining Edges: %d", math.max(0, s.nseq - s.seqi + 1)))
		persistRemaining()
		s.finished = false
	else
		print("Finished SimpleProposalCmdSeq")
		s.seqlist = {}
		s.nseq = 0
		s.seqi = 1
		s.called = false
		s.finished = true
		_G.osm_importer_seq_keys = nil
	end
	print(os.date())
	local timedur = timer.stop()
	print(string.format("Time: %.2f min (%.2f h)", timedur/60, timedur/3600))
	print(string.format("Streets build failed: %d / %d  (%.1f %%)  skipped: %d",
		s.nosuc.STREET or 0, s.nedges.STREET or 0, failpct(s.nosuc.STREET, s.nedges.STREET), s.nskipped.STREET or 0))
	print(string.format("Tracks build failed: %d / %d  (%.1f %%)  skipped: %d",
		s.nosuc.TRACK or 0, s.nedges.TRACK or 0, failpct(s.nosuc.TRACK, s.nedges.TRACK), s.nskipped.TRACK or 0))
	if s.pb then
		pcall(function()
			s.pb:getParent():getParent():remove()
		end)
		s.pb = nil
	end
end

function s.SimpleProposalSeqE()
	if s._running then
		s._again = true
		return
	end
	s._running = true
	while s.seqi <= s.nseq and not s.stop do
		local edge = s.seqlist[s.seqi]
		s.seqi = s.seqi + 1
		s.count = s.count + 1
		if s.pb then
			pcall(function()
				s.pb:setProgress(s.count/math.max(1, s.nseq))
				local label = "Edge"
				if edge and edge.track then
					label = "Track: "..tostring(edge.track.type)
				elseif edge and edge.street then
					label = "Street: "..tostring(edge.street.type)
				end
				s.pb:setTask(label)
			end)
		end
		s._waiting = true
		s._again = false
		local ok, err = pcall(s.SimpleProposalSeqEdgeCmd, edge, s.cbLevel, true)
		if not ok then
			print("Skip edge error", err)
			s.countEdge(edge, true, false)
			s._waiting = false
		elseif s._waiting then
			s._running = false
			return
		end
	end
	s._running = false
	s.finishSeq()
end

function s.SimpleProposalSeqEdgeCmd(edge,cbLevel,retryWSmStreet)
	if not edge or not edge.node0 or not edge.node1 then
		s.countEdge(edge, true, false)
		s._waiting = false
		return
	end
	s.edge = edge
	local d2 = {
		nodes = {
			[edge.node0] = s.data.nodes[edge.node0],
			[edge.node1] = s.data.nodes[edge.node1],
		},
		edges = {
			edge
		},
	}
	s.replaceNode(d2,edge.node0)
	s.replaceNode(d2,edge.node1)
	local n0 = d2.nodes[edge.node0]
	local n1 = d2.nodes[edge.node1]
	if not n0 or not n1 then
		s.countEdge(edge, true, false)
		s._waiting = false
		return
	end
	if type(n0.id)=="number" and n0.id == n1.id then
		print("Skip edge, node entity ids equal", n0.id, edge.__key or "")
		s.countEdge(edge, true, false)
		s._waiting = false
		return
	end

	if cbLevel>=1 then
		print("Cmd Edge #"..s.count.." - "..(edge.id or edge.__key or "").."  "..string.format("N0: %s (%s) - N1: %s (%s) - %s", edge.node0, n0.id or "", edge.node1, n1.id or "", edge.track and "TRACK" or edge.street and "highway="..tostring(edge.street.type)))
	end
	simpleproposal.SimpleProposalCmd(d2, nil, true, cbLevel, function(res, success)
		local etype = edge.track and "TRACK" or "STREET"
		s.nedges[etype] = (s.nedges[etype] or 0) + 1
		if res and res.skipped then
			s.nskipped[etype] = (s.nskipped[etype] or 0) + 1
		elseif not success then
			s.nosuc[etype] = (s.nosuc[etype] or 0) + 1
		end
		s._waiting = false
		s.SimpleProposalSeqE()
	end, retryWSmStreet)
end

function s.replaceNode(d,node)
	local id = s.getIdIfExist(node)
	if not id then
		return
	end
	if s.cbLevel>=2 then
		print("Node already exist",id,toString(s.data.nodes[node]))
	end
	local ok, basenode = pcall(api.engine.getComponent, id, api.type.ComponentType.BASE_NODE)
	if not ok or not basenode or not d.nodes[node] then
		return
	end
	d.nodes[node].id = id
	d.nodes[node].comp = basenode
end

function s.getIdIfExist(node)
	local n = s.data.nodes[node]
	if not n or not n.pos then
		return
	end
	local pos = n.pos
	local ok, ents = pcall(function()
		return game.interface.getEntities({pos=pos, radius=3}, {type="BASE_NODE"})
	end)
	if not ok or type(ents) ~= "table" then
		return
	end
	return tools.getNearestNode(pos, ents, 1e-3)
end

function s.tryProgressWindow()
	local pb
	pcall(function()
		pb = s.progressWindow()
	end)
	return pb
end

function s.progressWindow()
	local pb = api.gui.comp.ProgressBar.new()
	local window = api.gui.comp.Window.new("Progress (script will continue when closed)", pb)
	window:addHideOnCloseHandler()
	pb:setMinimumSize(api.gui.util.Size.new(500,10))
	return pb
end

return s
