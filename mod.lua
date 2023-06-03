function data()
	return {
		info = {
			name = "OSM Importer",
			description = _("mod_desc"),
			minorVersion = 0,
			severityAdd = "NONE",
			severityRemove = "NONE",
			tags = {},
			authors = {
				{
					name = "VacuumTube",
					role = "CREATOR",
					tfnetId = 29264,
				},
			},
		},
		-- runFn = function (settings)
		postRunFn = function (settings)
			(require"osm_importer.models").postRunFnScript()
		end
	}
end
