-- provide an interface for running some commands in the script thread

local events = {
	["require-osm_importer.main"] = function(param)
		require"osm_importer.main"
	end,
	["setAllTownsDevActive-false"] = function(param)
		m.towns.setAllTownsDevActive(false)
	end,
	["bulldoze.delEdges"] = function(param)
		bulldoze.delEdges()
	end,
	["areas.buildAreas"] = function(param)
		m.areas.buildAreas(osmdata.areas, osmdata.nodes)
	end,
	["m.reload"] = function(param)
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
