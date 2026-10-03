-- provide an interface for running some commands in the script thread

local function ensureMain()
	if not rawget(_G, "osm_importer") then
		require "osm_importer.main"
	end
end

local events = {
	["require-osm_importer.main"] = function(param)
		require "osm_importer.main"
	end,
	["setAllTownsDevActive-false"] = function(param)
		ensureMain()
		m.towns.setAllTownsDevActive(false)
	end,
	["bulldoze.delEdges"] = function(param)
		ensureMain()
		bulldoze.delEdges()
	end,
	["bulldoze.delAssets"] = function(param)
		ensureMain()
		bulldoze.delAssets()
	end,
	["areas.buildAreas"] = function(param)
		ensureMain()
		m.areas.buildAreas(osmdata.areas, osmdata.nodes, param or {})
	end,
	["areas.step"] = function(param)
		ensureMain()
		m.areas.step()
	end,
	["areas.buildForests"] = function(param)
		ensureMain()
		m.areas.buildForests(osmdata.areas.forests, osmdata.nodes, param or {})
	end,
	["areas.buildShrubs"] = function(param)
		ensureMain()
		m.areas.buildShrubs(osmdata.areas.shrubs, osmdata.nodes, param or {})
	end,
	["areas.paveGroundSurfaces"] = function(param)
		ensureMain()
		m.areas.paveGroundSurfaces(osmdata.areas.grounds, osmdata.nodes, param or {})
	end,
	["stage.towns_script"] = function(param)
		ensureMain()
		m.towns.setAllTownsDevActive(false)
		if param and param.delEdges then
			bulldoze.delEdges()
		end
		if param and param.delAssets then
			bulldoze.delAssets()
		end
	end,
	["towns.createTownLabels"] = function(param)
		ensureMain()
		m.towns.createTownLabels(osmdata.towns, param or {})
	end,
	["towns.step"] = function(param)
		ensureMain()
		m.towns.step()
	end,
	["buildings.buildBuildings"] = function(param)
		ensureMain()
		m.buildings.buildBuildings(osmdata.buildings, param or {})
	end,
	["buildings.step"] = function(param)
		ensureMain()
		m.buildings.step()
	end,
	["models.buildObjects"] = function(param)
		ensureMain()
		m.models.buildObjects(osmdata.objects)
	end,
	["edges.SimpleProposalSeq"] = function(param)
		ensureMain()
		m.simpleproposalseq.SimpleProposalSeq(osmdata, param or osm_importer.options)
	end,
	["m.reload"] = function(param)
		ensureMain()
		m.reload()
	end,
}

function data()
	return {
		handleEvent = function(src, id, name, param)
			if id=="osm_importer" then
				local event = events[name]
				if event then
					local status, err = pcall(event,param)
					if status==false then
						print("ERROR in handleEvent: ", err)
					end
				else
					print("osm_importer: Unknown Event !", name)
				end
			end
		end
    }
end
