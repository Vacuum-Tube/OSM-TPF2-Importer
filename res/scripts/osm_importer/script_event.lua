local e = {}

function e.ScriptEventId(id,name,param)
	api.cmd.sendCommand(api.cmd.make.sendScriptEvent("osm_importer.lua", id, name, param))
end

function e.ScriptEvent(name,param)
	e.ScriptEventId("osm_importer", name, param)
end

return e