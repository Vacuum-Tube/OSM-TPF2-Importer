function data()
	return {
		info = {
			name = "OSM Importer",
			description = _("mod_desc"),
			minorVersion = 5,
			severityAdd = "NONE",
			severityRemove = "NONE",
			tags = {"Script Mod","Misc"},
			authors = {
				{
					name = "VacuumTube",
					role = "CREATOR",
					tfnetId = 29264,
				},
			},
			url = "https://github.com/Vacuum-Tube/OSM-TPF2-Importer",
		},
		-- runFn = function (settings)
		postRunFn = function (settings)
			(require"osm_importer.models").postRunFnScript()
		end
	}
end
