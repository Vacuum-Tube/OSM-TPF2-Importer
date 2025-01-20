# Mod Dependencies
OSM Importer is designed to make use of some brilliant TPF2 Mods in order to increase realism and use dedicated objects/types more suitable than the vanilla resources.
I have carefully selected those mods and searched for the best solution.
Many of them will become useful for Replication projects anyway.

I recommend using them all.
Nevertheless, you are free to use different models/track/street types.
They can be changed with a little bit of Lua knowledge.
In the respective files (see links to definitions), the object types to be used is determined based on the details provided by OSM tags.
If you don't want to use a certain mod, edit the track/street/bridge/signal types file and replace all filenames belonging to this mod with the filenames of other mods or vanilla files.

You may skip mods related to a function if you don't use all functions of OSM Importer.
For example, if you do not use the Forest import, you can skip the Forester and the tree models.
Also, if you use `build_bridges=false` or `build_signals=false`, there should be no issues when the respective mods are not activated.
You can skip "Berlin Stadtbahn Viaduct Construction" if you are sure that [your area does not contain power rails](https://overpass-turbo.eu/?template=key-value&key=electrified&value=rail).

## Track types ([definition](/res/scripts/osm_importer/types_track.lua))
- Natural Environment Professional 2 https://www.transportfever.net/filebase/entry/5942-natural-environment-professional-2/
- NEP Addon https://github.com/Vacuum-Tube/NEP-Addon
- Gleispaket mit 750mm 1000mm https://www.transportfever.net/filebase/entry/4808-gleispaket-mit-750mm-1000mm-f%C3%BCr-tpf2/
- Feldbahn Infrastruktur https://www.transportfever.net/filebase/entry/6512-feldbahn-infrastruktur/
- Vienna Fever: Infrastructure https://steamcommunity.com/sharedfiles/filedetails/?id=2060012969
- Berlin Stadtbahn Viaduct Construction - Basic Segmets https://steamcommunity.com/sharedfiles/filedetails/?id=2258619623
- Old Track https://steamcommunity.com/sharedfiles/filedetails/?id=1983390040
- Ballast https://steamcommunity.com/workshop/filedetails/?id=2072274420

## Street types ([definition](/res/scripts/osm_importer/types_street.lua))
- ext.roads footpaths standalone https://steamcommunity.com/sharedfiles/filedetails/?id=1968514713
- Street fine tuning https://steamcommunity.com/sharedfiles/filedetails/?id=2021038808
- Freestyle train station https://steamcommunity.com/sharedfiles/filedetails/?id=2363493916
- Marc's Street and Trampack https://steamcommunity.com/sharedfiles/filedetails/?id=1933747406
- Airport Roads (EXPERIMENTAL) https://steamcommunity.com/sharedfiles/filedetails/?id=2232249704 
- Roads´n Trams Projekt (RTP) https://www.transportfever.net/filebase/entry/5675-roads-n-trams-projekt-rtp/
- SMP 2.0 https://steamcommunity.com/workshop/filedetails/?id=1943578742
- Joe Fried Straßenpaket: Straßengeschichte (joefried_roadstrassen_em_2) https://www.transportfever.net/filebase/entry/5264-joe-fried-stra%C3%9Fenpaket-stra%C3%9Fengeschichte/
- Autobahnkreuz TpF2 https://www.transportfever.net/filebase/entry/5157-autobahnkreuz-tpf2/
- Water Textures - Natural Water Surfaces (activate Water 4 (4.2,4.3,4.4) and Street 4 with blue water) https://steamcommunity.com/workshop/filedetails/?id=2014569888

## Bridge types ([definition](/res/scripts/osm_importer/types_bridge.lua))
- TFMR2.0 Bridge (Transport Fever Modular Road) https://steamcommunity.com/sharedfiles/filedetails/?id=2187434173 
- Freestyle train station https://steamcommunity.com/sharedfiles/filedetails/?id=2363493916
- Bridge Type-1 https://steamcommunity.com/sharedfiles/filedetails/?id=1939805466
- Vienna Fever: Bridge and Retaining Wall https://steamcommunity.com/sharedfiles/filedetails/?id=2060132685
- Gitterträger-Fachwerkbrücke [until v1.3] https://www.transportfever.net/filebase/entry/5425-gittertr%C3%A4ger-fachwerkbr%C3%BCcke/
- Autobahnkreuz TpF2 https://www.transportfever.net/filebase/entry/5157-autobahnkreuz-tpf2/

## Signals ([definition](/res/scripts/osm_importer/types_signal.lua))
- Natural Environment Professional 2 https://www.transportfever.net/filebase/entry/5942-natural-environment-professional-2/
- H/V-Signale Einheitsbauform² (sebbe_hv69signale_basis_1, sebbe_hv69signale_erw1_1 + erw2 + erw3) https://www.transportfever.net/filebase/entry/5209-h-v-signale-einheitsbauform%C2%B2/
- Signalkomponenten https://steamcommunity.com/sharedfiles/filedetails/?id=2770909719
- Ks-Signalsystem https://steamcommunity.com/sharedfiles/filedetails/?id=2920749928
- Level crossing signals https://steamcommunity.com/sharedfiles/filedetails/?id=2770910636
- The Signal placement assumes that [Signal Distance](https://steamcommunity.com/sharedfiles/filedetails/?id=2294246900) is used.

## Objects ([definition](/res/scripts/osm_importer/models.lua))
- Connum's German Traffic Assets https://steamcommunity.com/sharedfiles/filedetails/?id=1963592311
- Litfaßsäulen (sabon_litfass_era_c_1) https://www.transportfever.net/filebase/entry/6218-litfa%C3%9Fs%C3%A4ulen-f%C3%BCr-%C3%A4ra-b-und-c/

## Tree models ([definition](/res/scripts/osm_importer/forester.lua))
- Spacky_Trees conifers https://steamcommunity.com/sharedfiles/filedetails/?id=2247194383

## Forest Placement Function
- Forester (use version **"vt_snowball_forester_1.4_Interface"**) https://www.transportfever.net/filebase/entry/4856-f%C3%B6rster/

## Default
- Sandbox
- and enable Debug Mode

## Additional useful mods for Replication projects that should be activated BEFORE the osm import

- Realistic Railway Slopes; to reduce embankment to avoid trouble with height differences (Embankment Slope: 1, Embankment Slope High: off) https://steamcommunity.com/sharedfiles/filedetails/?id=2161175689
- Maximum Street Slopes; to reduce embankment to avoid trouble with height differences (Embankment Slope: 1, Embankment Slope High: off) https://steamcommunity.com/sharedfiles/filedetails/?id=2206802861
- Realistic Track Curve Speeds (uncheck "No superelevation at speed restricted tracks") https://steamcommunity.com/sharedfiles/filedetails/?id=2558586098
- Sidewalk Lowerer (uncheck "Adjust Small Streets 'town new'") https://www.transportfever.net/filebase/entry/7446-gehweg-absenker/ (there is an updater tool but takes time and can create issues)
