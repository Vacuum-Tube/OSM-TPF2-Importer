print("Load osm_importer.main")

osmdata = require"osm_importer.osmdata"
bulldoze =  require "osm_importer.bulldoze"
timer = require"osm_importer.timer"

osm_importer = {
	osmdata=osmdata,
	simpleproposal=require"osm_importer.simpleproposal",
	simpleproposalseq=require"osm_importer.simpleproposal_seq",
	models=require"osm_importer.models",
	towns=require"osm_importer.towns",
	areas=require"osm_importer.areas",
	reload=require"osm_importer.package".reload,
	-- options = {},
}
m = osm_importer


--------------------------------------------------------------------------------
-- Copy the following commands in the console step by step
-- Some commands go into the UG Console, some need to go in the CommonAPI Console (Script Thread)
-- Pause game !
--------------------------------------------------------------------------------
local function run()
	
	require"osm_importer.main"  -- Enter in UG Console and Script Thread
	
	-- (1) Town labels
	m.towns.createTownLabels(osmdata.towns)
	m.towns.setAllTownsDevActive(false)  -- disable town development  -- USE: Script thread
	bulldoze.delEdges() -- remove (ALL) built streets  -- USE: Script thread
	
	-- (2) Areas/forests  (before streets, so they remove trees)
	m.areas.buildAreas(osmdata.areas, osmdata.nodes)  -- USE: Script thread
	
	-- (3) Build edges (Streets/Tracks)
	options = {
		log_level = 1,
		build_streets = true,
		build_tracks = true,
		build_subwaytracks = true,  -- build subways and light rail as tracks
		build_tramtracks = false,  -- build tram tracks as tracks, set false if you build them manually on streets
		build_bridges = true,  -- the nodes within the bridge will not be in the air, but can be adjusted with node tool
		build_tunnels = false,  -- with tunnels the height is even more difficult
		build_signals = true,  -- build signals on tracks (only Germany)
		build_autobahn = true,  -- set false if you use melectro Autobahn to lay manually as twoway street (links are still built)
		build_edges_street_types = true,  -- build all osm types that are actual streets (motorways, city streets, residential streets)
		build_edges_footway_types = true,  -- build all osm types that are foot/bicycle ways
		build_edges_water = true,  -- use stream streets (with relozu water textures)
		build_edges_airport = true,  -- use airport streets (airport roads mod)
		skip_nodes_outofbounds = true,  -- avoids edges out of map bounds (but not forests)
		skip_tracks_shorter_than = 0,
		skip_tracks_radius_smaller_than = 10,
	}
	m.simpleproposalseq.SimpleProposalSeq(osmdata, options)  -- USE: UG Console
	
	-- (4) Build objects (single tree, fountain, bollards)  (after streets bec they can change terrain height) 
	m.models.buildObjects(osmdata.objects)  -- USE: UG Console
	
end

--------------------------------------------
local function tipps()
	-- Reload Lua Files:
	m.reload()
	
	-- Stop edges building:
	m.simpleproposalseq.stop=true
	
end
-------------------------------------------

-- return m