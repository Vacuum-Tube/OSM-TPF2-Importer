-- OSM Importer in-game control window (GUI thread).
-- Script-thread work is sent through osm_importer.lua events (see receive_script_events.lua).

local OPTION_ROWS = {
	{ "build_streets", "Streets" },
	{ "build_tracks", "Tracks" },
	{ "build_subwaytracks", "Subway / light rail" },
	{ "build_tramtracks", "Tram as tracks" },
	{ "build_bridges", "Bridges" },
	{ "build_tunnels", "Tunnels" },
	{ "build_signals", "Signals" },
	{ "build_autobahn", "Motorways" },
	{ "build_streets_street_types", "Street types" },
	{ "build_streets_footway_types", "Footways" },
	{ "build_streets_water", "Water streets" },
	{ "build_streets_airport", "Airport roads" },
	{ "build_buildings_residential", "Houses" },
	{ "build_buildings_commercial", "Shops / offices" },
	{ "build_buildings_industrial", "Industry buildings" },
	{ "skip_nodes_outofbounds", "Skip out of bounds" },
	{ "crash_type_not_found", "Abort if vanilla type missing" },
}

local ui = {
	window = nil,
	status = nil,
	checks = {},
	loaded = false,
	menuAdded = false,
}

local function sendEvent(name, param)
	api.cmd.sendCommand(api.cmd.make.sendScriptEvent("osm_importer.lua", "osm_importer", name, param or {}))
end

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

local function loadOptions()
	local opts = defaultOptions()
	local ok, user = pcall(require, "osm_importer.user_options")
	if ok and type(user) == "table" then
		for k, v in pairs(user) do
			opts[k] = v
		end
	end
	return opts
end

local function collectOptions()
	local opts = defaultOptions()
	for key, box in pairs(ui.checks) do
		opts[key] = box:isSelected()
	end
	opts.log_level = 1
	return opts
end

local function setStatus(text)
	if ui.status then
		ui.status:setText(text)
	end
	print("OSM Studio: " .. tostring(text))
end

local function ensureLoaded()
	if ui.loaded and rawget(_G, "osm_importer") then
		return true
	end
	local ok, err = pcall(function()
		require "osm_importer.main"
	end)
	if not ok then
		setStatus("Could not load osmdata. Install/convert first. " .. tostring(err))
		return false
	end
	sendEvent("require-osm_importer.main")
	ui.loaded = true
	setStatus("Importer loaded. Pause the game, then run stages 1→5.")
	return true
end

local function addMenuButton()
	if ui.menuAdded then
		return true
	end
	local menu = api.gui.util.getById("menuUI")
	if not menu then
		return false
	end
	local existing = api.gui.util.getById("osm_importer.studioButton")
	if existing then
		ui.menuAdded = true
		return true
	end
	local label = api.gui.comp.TextView.new("OSM")
	local button = api.gui.comp.Button.new(label, true)
	button:setId("osm_importer.studioButton")
	button:setTooltip("OSM Importer — build stages and options")
	button:onClick(function()
		if ui.window then
			ui.window:setVisible(true, false)
		else
			createOsmStudioWindow()
		end
	end)
	menu:getLayout():addItem(button, 0, 1)
	ui.menuAdded = true
	return true
end

function createOsmStudioWindow()
	if ui.window then
		ui.window:setVisible(true, false)
		return
	end

	local opts = loadOptions()
	local root = api.gui.layout.BoxLayout.new("VERTICAL")

	ui.status = api.gui.comp.TextView.new("Pause the game. Load data, then run stages in order.")
	root:addItem(ui.status)

	local loadBtn = api.gui.comp.Button.new(api.gui.comp.TextView.new("Load osmdata"), true)
	loadBtn:onClick(function()
		ensureLoaded()
	end)
	root:addItem(loadBtn)
	root:addItem(api.gui.comp.Component.new("HorizontalLine"))

	local cols = api.gui.layout.BoxLayout.new("HORIZONTAL")
	local col1 = api.gui.layout.BoxLayout.new("VERTICAL")
	local col2 = api.gui.layout.BoxLayout.new("VERTICAL")
	ui.checks = {}
	for i, row in ipairs(OPTION_ROWS) do
		local box = api.gui.comp.CheckBox.new(row[2])
		box:setSelected(opts[row[1]] and true or false, false)
		ui.checks[row[1]] = box
		if i <= math.ceil(#OPTION_ROWS / 2) then
			col1:addItem(box)
		else
			col2:addItem(box)
		end
	end
	local c1 = api.gui.comp.Component.new("")
	c1:setLayout(col1)
	local c2 = api.gui.comp.Component.new("")
	c2:setLayout(col2)
	cols:addItem(c1)
	cols:addItem(c2)
	local colsComp = api.gui.comp.Component.new("")
	colsComp:setLayout(cols)
	root:addItem(colsComp)
	root:addItem(api.gui.comp.Component.new("HorizontalLine"))

	ui.delEdges = api.gui.comp.CheckBox.new("Also bulldoze ALL streets (dummy towns)")
	ui.delEdges:setSelected(false, false)
	ui.delAssets = api.gui.comp.CheckBox.new("Also delete trees/assets")
	ui.delAssets:setSelected(false, false)
	root:addItem(ui.delEdges)
	root:addItem(ui.delAssets)
	root:addItem(api.gui.comp.Component.new("HorizontalLine"))

	local function stageButton(title, fn)
		local b = api.gui.comp.Button.new(api.gui.comp.TextView.new(title), true)
		b:onClick(fn)
		root:addItem(b)
		return b
	end

	stageButton("1  Town labels + disable towns", function()
		if not ensureLoaded() then return end
		setStatus("Stage 1: town labels (script thread)…")
		sendEvent("towns.createTownLabels", {
			delEdges = ui.delEdges and ui.delEdges:isSelected() or false,
			delAssets = ui.delAssets and ui.delAssets:isSelected() or false,
		})
	end)

	stageButton("2  Areas (forests, shrubs, ground)", function()
		if not ensureLoaded() then return end
		setStatus("Stage 2: areas (script continues if window is closed)…")
		sendEvent("areas.buildAreas", collectOptions())
	end)

	stageButton("3  Streets and tracks (resumes if stopped)", function()
		if not ensureLoaded() then return end
		setStatus("Stage 3: streets and tracks (script thread; resumes if stopped)…")
		sendEvent("edges.SimpleProposalSeq", collectOptions())
	end)

	stageButton("4  Buildings (houses / shops / industry)", function()
		if not ensureLoaded() then return end
		setStatus("Stage 4: buildings (skip if no matching TPF2 size)…")
		sendEvent("buildings.buildBuildings", collectOptions())
	end)

	stageButton("5  Objects (trees, fountains, bollards)", function()
		if not ensureLoaded() then return end
		setStatus("Stage 5: objects (script thread)…")
		sendEvent("models.buildObjects", collectOptions())
	end)

	root:addItem(api.gui.comp.Component.new("HorizontalLine"))

	local row = api.gui.layout.BoxLayout.new("HORIZONTAL")
	local stopBtn = api.gui.comp.Button.new(api.gui.comp.TextView.new("Stop towns / areas / edges / buildings"), true)
	stopBtn:onClick(function()
		if rawget(_G, "osm_importer") then
			m.simpleproposalseq.stop = true
			if m.buildings then
				m.buildings.stop = true
			end
			if m.towns then
				m.towns.stop = true
			end
			if m.areas then
				m.areas.stop = true
			end
			setStatus("Stop requested.")
		end
	end)
	local reloadBtn = api.gui.comp.Button.new(api.gui.comp.TextView.new("Reload scripts"), true)
	reloadBtn:onClick(function()
		sendEvent("m.reload")
		ui.loaded = false
		local ok, err = pcall(function()
			if rawget(_G, "osm_importer") then
				m.reload()
			else
				require "osm_importer.main"
			end
		end)
		ui.loaded = ok
		setStatus(ok and "Reloaded." or ("Reload failed: " .. tostring(err)))
	end)
	row:addItem(stopBtn)
	row:addItem(reloadBtn)
	local rowComp = api.gui.comp.Component.new("")
	rowComp:setLayout(row)
	root:addItem(rowComp)

	local window = api.gui.comp.Window.new("OSM Importer", root)
	window:addHideOnCloseHandler()
	window:setPosition(60, 80)
	pcall(function()
		window:setSize(api.gui.util.Size.new(460, 760))
	end)
	pcall(function()
		if window.setResizable then
			window:setResizable(true)
		end
	end)
	window:onClose(function()
		-- hidden via addHideOnCloseHandler; keep handle for reopen
	end)
	ui.window = window
end

function data()
	return {
		guiInit = function()
			pcall(addMenuButton)
		end,
		guiUpdate = function()
			if not ui.menuAdded then
				pcall(addMenuButton)
			end
		end,
	}
end
