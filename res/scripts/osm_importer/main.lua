
osmdata = require"osm_importer.osmdata"
do
	local existing = osmdata.buildings
	local n = type(existing) == "table" and #existing or 0
	if n == 0 then
		local ok, extra = pcall(require, "osm_importer.osmdata_buildings")
		if ok and type(extra) == "table" and #extra > 0 then
			rawset(osmdata, "buildings", extra)
		end
	end
end
bulldoze =  require "osm_importer.bulldoze"

osm_importer = {
	simpleproposal=require"osm_importer.simpleproposal",
	simpleproposalseq=require"osm_importer.simpleproposal_seq",
	models=require"osm_importer.models",
	towns=require"osm_importer.towns",
	areas=require"osm_importer.areas",
	buildings=require"osm_importer.buildings",
	scriptevent=require"osm_importer.script_event",
	reload=require"osm_importer.package".reload,
	-- options = {},
}
m = osm_importer

print("Loaded osm_importer.main")

local function defaultOptions()
	return {
		build_streets = true,
		build_tracks = true,
		build_subwaytracks = true,
		build_tramtracks = false,
		build_bridges = true,
		build_tunnels = false,
		build_signals = true,
		build_autobahn = true,
		build_streets_street_types = true,
		build_streets_footway_types = false,
		build_streets_water = true,
		build_streets_airport = true,
		build_buildings_residential = true,
		build_buildings_commercial = true,
		build_buildings_industrial = true,
		skip_nodes_outofbounds = true,
		crash_type_not_found = false,
		log_level = 1,
	}
end

function osm_importer.loadOptions()
	local opts = defaultOptions()
	package.loaded["osm_importer.user_options"] = nil
	local ok, user = pcall(require, "osm_importer.user_options")
	if ok and type(user) == "table" then
		for k, v in pairs(user) do
			opts[k] = v
		end
	end
	return opts
end


--------------------------------------------------------------------------------
-- Copy the following commands in the console step by step
-- Some commands go into the UG Console, some need to be executed in the Script Thread. Either use CommonAPI Console for that or use the Workaround below.
-- Pause game !
--------------------------------------------------------------------------------
local function run()
	
	require"osm_importer.main"  -- Enter in UG Console AND Script Thread
	
	-- (1) Town labels
	m.towns.createTownLabels(osmdata.towns)
	m.towns.setAllTownsDevActive(false)  -- disable town development  -- USE: Script thread
	-- bulldoze.delEdges() -- removes ALL streets; tick the in-game checkbox if dummy-town streets must go
	-- bulldoze.delAssets() -- removes trees
	
	-- (2) Areas: forests/shrubs + ground surfaces  (before streets, so they remove trees)
	m.areas.buildAreas(osmdata.areas, osmdata.nodes)  -- USE: Script thread
	-- m.areas.paveGroundSurfaces(osmdata.areas.grounds, osmdata.nodes, {skipMultiPolygons=false})  -- only Paver surfaces when forests already on the map
	
	-- (3) Build edges (Streets/Tracks)
	options = {
		build_streets = true,
		build_tracks = true,
		build_subwaytracks = true,  -- build subways and light rail as tracks
		build_tramtracks = false,  -- build tram tracks as tracks
		build_bridges = true,
		build_tunnels = false,  -- with tunnels the height is more difficult
		build_signals = true,  -- OSM country tags pick regional signals if subscribed, else vanilla
		build_autobahn = true,  -- motorways as vanilla country/highway streets
		build_streets_street_types = true,  -- build all osm types that are actual streets (motorways, city streets, residential streets)
		build_streets_footway_types = true,  -- build all osm types that are foot/bicycle ways
		build_streets_water = true,  -- use stream streets when a water-street mod is loaded
		build_streets_airport = true,  -- airport roads mod, else vanilla airport streets
		build_buildings_residential = true,
		build_buildings_commercial = true,
		build_buildings_industrial = true,
		skip_nodes_outofbounds = true,  -- avoids edges outside the map bounds (but not forests)
		crash_type_not_found = false,  -- missing workshop types fall back to vanilla
		log_level = 1,
	}
	m.simpleproposalseq.SimpleProposalSeq(osmdata, options)  -- USE: UG Console
	
	-- (4) Town buildings from OSM footprints (houses / shops / industry). Skip if no matching TPF2 size.
	m.buildings.buildBuildings(osmdata.buildings, options)
	
	-- (5) Build objects (single tree, fountain, bollards)  (after streets bec they can change terrain height) 
	m.models.buildObjects(osmdata.objects)  -- USE: UG Console
	
end

--------------------------------------------
local function execute_commands_in_Script_Thread()
	-- Workaround without CommonAPI
	m.scriptevent.ScriptEvent("require-osm_importer.main")
	m.scriptevent.ScriptEvent("setAllTownsDevActive-false")
	m.scriptevent.ScriptEvent("bulldoze.delEdges")
	m.scriptevent.ScriptEvent("areas.buildAreas")  -- wait some time for the result
	m.scriptevent.ScriptEvent("m.reload")
end
--------------------------------------------
local function Tips()
	-- Reload Lua Files:
	m.reload()
	
	-- Stop towns / edges / buildings:
	m.simpleproposalseq.stop=true
	m.buildings.stop=true
	m.towns.stop=true
	
end
-------------------------------------------
