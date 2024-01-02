local simpleproposal = require"osm_importer.simpleproposal"
local tools = require"osm_importer.tools"
local timer = require"osm_importer.timer"

local s = {}

function s.fixNodesTerrainHeight(nodes)
	for id,node in pairs(nodes) do
		node.pos[3] = tools.getTerrainZ(node.pos[1], node.pos[2])
	end
end

function s.SimpleProposalSeq(data,options) 
	osm_importer.options = assert(options, "Options not defined")
	s.stop = false
	s.data = data
	s.cbLevel = options.log_level or 1
	assert(type(s.cbLevel)=="number")
	
	print("Start SimpleProposalCmdSeq")
	print(os.date())
	timer.start()
	print("Options: "..toString(options))
	
	print("Add nodes z height")
	s.fixNodesTerrainHeight(data.nodes)
	
	s.seqlist = {}  -- List of individual build Cmds
	for i,edge in pairs(data.edges) do
		if (options.build_streets and edge.street)
		or (options.build_tracks and edge.track 
			and (options.build_tramtracks or not edge.track.tram  )
			and (options.build_subwaytracks or not edge.track.subway )) then
				table.insert(s.seqlist, edge)
		end
	end
	s.nseq = #s.seqlist
	s.edges = {
		STREET = 0,
		TRACK = 0,
	}
	s.nosuc = {
		STREET = 0,
		TRACK = 0,
	}
	s.count = 0
	print("Edges:  "..s.nseq)
	print(string.format("Estimated Time: %.0f min (%.2f h)", s.nseq/5/60, s.nseq/5/3600))
	s.SimpleProposalSeqE()
end

function s.SimpleProposalSeqE()
	if #s.seqlist>0 and not s.stop then
		s.SimpleProposalSeqEdgeCmd(table.remove(s.seqlist,1), s.cbLevel, true)
	else
		local nosuc = s.nosuc.STREET+s.nosuc.TRACK
		print("-------------------------------------------------------------")
		if #s.seqlist~=0 then
			print("Process aborted !")
			print(string.format("Remaining Edges: %d", #s.seqlist))
		else
			print("Finished SimpleProposalCmdSeq")
		end
		print(os.date())
		local timedur = timer.stop()
		print(string.format("Time: %.2f min (%.2f h)", timedur/60, timedur/3600))
		-- print(string.format("Edges build failed: %d / %d  (%.1f %%)", nosuc, s.nseq, 100*nosuc/s.nseq))
		print(string.format("Streets build failed: %d / %d  (%.1f %%)", s.nosuc.STREET, s.edges.STREET, 100*s.nosuc.STREET/s.edges.STREET))
		print(string.format("Tracks build failed: %d / %d  (%.1f %%)", s.nosuc.TRACK, s.edges.TRACK, 100*s.nosuc.TRACK/s.edges.TRACK))
	end
end

function s.SimpleProposalSeqEdgeCmd(edge,cbLevel,retryWSmStreet)
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
	if type(d2.nodes[edge.node0].id)=="number" and d2.nodes[edge.node0].id == d2.nodes[edge.node1].id then
		print("Node entity Id equal!", d2.nodes[edge.node1].id, toString(d2), toString(s.data.nodes[edge.node0]), toString(s.data.nodes[edge.node1]))
		error("")
	end
	
	s.count = s.count +1
	if cbLevel>=1 then
		print("Cmd Edge #"..s.count.." - "..(edge.id or "").."  "..(cbLevel>=1 and string.format("N0: %s (%s) - N1: %s (%s) - %s", edge.node0, d2.nodes[edge.node0].id or "", edge.node1, d2.nodes[edge.node1].id or"", edge.track and "TRACK" or edge.street and "highway="..edge.street.type)) .. (cbLevel>=3 and toString(d2) or ""))
	end
	simpleproposal.SimpleProposalCmd(d2,context,ignoreErrors,cbLevel, function(res, success)
		local etype = edge.track and "TRACK" or edge.street and "STREET"
		s.edges[etype] = s.edges[etype] + 1
		if not success then
			s.nosuc[etype] = s.nosuc[etype] + 1
		end
		s.SimpleProposalSeqE()
	end, retryWSmStreet)
end

function s.replaceNode(d,node)
	local id = s.getIdIfExist(node)
	if id then
		if s.cbLevel>=2 then
			print("Node already exist",id,toString(s.data.nodes[node]))
		end
		local basenode = api.engine.getComponent(id,api.type.ComponentType.BASE_NODE)
		d.nodes[node].id = id
		d.nodes[node].comp = basenode
	end
end

function s.getIdIfExist(node)
	local pos = assert(s.data.nodes[node].pos)
	local ents = game.interface.getEntities({pos=pos, radius=3}, {type="BASE_NODE"})  -- in most cases radius=0 is sufficient, but for sharp angles the node position is not in bounding box
	return tools.getNearestNode(pos,ents,1e-3)  -- choose  existing node only if very close 
end

return s