
local p = {}

function p.unload()
	for path,pack in pairs(package.loaded) do
		if path:starts("osm_importer.") then
			package.loaded[path]=nil
			print("Unloaded",path)
		end
	end
end

function p.reload()
	p.unload()
	require"osm_importer.main"
end

return p