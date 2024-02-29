![](doc/osmtpf.png)

# OSM-TPF2 Importer

This is an OpenStreetMap Import Tool for [Transport Fever 2](https://www.transportfever2.com/) for the automated reconstruction of real world places.

Few TPF2 players have dared to start a "Replication" project (virtual reconstruction of real environments) and maybe you already thought of rebuilding your home town.
However, often motivation runs out after a while, simply because of the sheer number of tracks, roads, buildings, vegetation, etc to rebuild, quickly becoming monotonous.

OpenStreetMap (OSM) provides worldwide, detailed, and accessible map data, including streets, railways, buildings, vegetation and much more.
This tool aims at using this data to bring it into TPF2 in an automated way.
Currently, tracks, streets, forests, town labels, and some point objects can be imported.

Therefore, this tool can be used as a starting point to accelerate the replication of a real world area.
Having the basic infrastructure and vegetation already in the game might help to keep the motivation on continuing with the reconstruction project.

**Despite the automation, this is no "one-click" tool!**
You need to have basic TPF2 knowlegde and a bit of LUA experience. 
I created a comprehensive tutorial, but I don't cover TPF2 basics.

While dealing with OSM data and the TPF2 modding interface, several challenges have been encountered and approached in this tool in order to convert, transform, and optimize the OSM data accordingly and make it usable in a sandbox transport game, as Transport Fever 2.

Demonstration Video: https://youtu.be/V_L-CaPWk1Y
  --  More pictures [here](https://www.transportfever.net/gallery/album/3768)

[![OSM Importer Demonstration Video](https://img.youtube.com/vi/V_L-CaPWk1Y/maxresdefault.jpg)](https://youtu.be/V_L-CaPWk1Y)


## Basics for Map creation

Before using this tool, you should be familiar with the basics of TPF2 and map creation in general.
Basic information, considerations, and requirements for "Replication" projects can be found in my [article in the forum](https://www.transportfever.net/lexicon/entry/398-real-nachbau-in-tpf-2/) (german).
Steam guide (english) will follow soon.

Before applying OSM-Importer, you need to define your area of interest, create an ingame overlay, and get a heightmap (optional for flat regions).


## OpenStreetMap
[OpenStreetMap (OSM)](https://www.openstreetmap.org/) has been a successful project since 2004 to establish a free, open map database that anyone can contribute to. 
The database consists of streets, footpaths, railway lines, building outlines, power lines, land use (e.g. forests), ... and even objects such as garbage cans. 
Not all data is displayed on the main page.
Some may know [OpenRailwayMap](https://www.openrailwaymap.org/), which uses the same data basis, but a different visualization (e.g. signals or demolished tracks).

There are 3 basic element types in OSM: 
- Nodes (points with coordinates)
- Ways (list of connected nodes), closed ways represent areas
- Relations (additional information on nodes and ways)

The associated XML tags contain further information to describe the object. 
In practice however, the degree of mapping detail can vary.
You can take a closer look via the object query using right-click to explore the underlying elements and their tags (e.g. [way 48905770](https://www.openstreetmap.org/way/48905770)).
There is an extensive documentation about the meaning of tags and values.

The different representation of streets and tracks requires some adjustments.
For example, maps like OSM do not contain real curves, in contrast to games like TPF2.
The OSM data needs to be processed and some optimizations are necessary to make the data usable in the game.
More details [here](/python/README.md#details).


## OSM data used for Automation
The following information from OSM data is used and extracted for the automated import:

- Streets and footpaths
    - type of street (e.g. urban, rural, motorway)
    - number of lanes, one-way
    - sidewalk
    - surface
- Railway tracks
    - catenary/powerrail
    - gauge
    - max speed
    - signals
- Bridges
- Rivers/Streams
- Forests
    - leaf type
- Towns/Quarters location (names are displayed as fake town labels)
- Point objects
    - fountains
    - single trees
    - bollards
    - Litfaßsäulen

Not all data can be used for automation.
For example, stations are mapped in detail in OSM, but have to be manually built in TPF2.
Building contours are extensively mapped, but there is no simple way to create appropriate automation for this.
The OSM landuse data cannot be used due to a missing interface in TPF2 to draw ground textures.


## Toolchain
This is the toolchain visualizing the approach.
The tool is split in two parts.

![toolchain](doc/toolchain.png)

OSM data is provided in an XML format. 
To facilitate the data filtering, processing, and transformation, the intermediate processing steps are carried out in a Python tool, the "Converter".

The Converter reads the OSM data, filters it according to the relevant data needed for TPF2, does some optimizations, and generates a convenient Lua file for TPF2 with the data in a suitable form.
For example, the world coordinates are transformed into map coordinates. 
Moreover, edges are optimized and tangent vectors are calculated for appropriate curves. 

On the TPF2 side, there is a script mod to read the generated Lua file and conduct the import in TPF2.
The whole project folder is basically a mod that needs to be activated.
In the game, the console is used to start the automated construction process.
The TPF2 modding API is used to build the streets, tracks, single models and more. 


## Documentation/Tutorial
[Here is a full tutorial](/doc/Tutorial.md) on how to use the tool.
It explains all steps, how to obtain OSM data, prepare the map, how to use the toolchain, and the postprocessing.

The two main tools are documented seperately:
- [OSM-TPF Converter](/python) (Python)
- [OSM Builder](/res/scripts/osm_importer) (Lua/Mod)


## Mods
OSM-Importer is designed to make use of some brilliant TPF2 Mods in order to increase realism and use dedicated objects/types more appropriate than the vanilla resources.
With the data and details provided in OSM, suitable street/track/bridge/signal types can be determined.
I have carefully selected those mods and searched for the best solution.
Many of them will become useful for Replication projects anyway.

Find the [required mods here](/doc/Mods.md).


## Limitations
- Not everything can be automated.
Replication projects still require significant manual preperation.
Also, postprocessing after the import is needed to clean up and optimize the result.

- The accuracy of the result depends on the accuracy/details of the OSM data. 
Mapping accuracy differs locally and worldwide. 
Maps don't have the same accuracy as games, which can be seen especially in railway curves.

- Often, not all streets/tracks can be built successfully, especially when there are many short segments within a small area, like complex intersections. 
These have to be built in TPF2 in another way anway.

- The process of importing streets and tracks can take a lot of time (several hours, depending on the map size and density).
This is because the single edges need to be built subsequently and the game has a tick speed of 0.2 seconds.


## Performance Impacts
Performance is a thing that needs to be carefully considered in TPF2.
Bringing a huge number of elements into the game at once presents a new type of impact that barely anyone has experienced yet.
Also I am just at the beginning of a replication at large scale, so stay tuned for new findings about this topic.

In TPF2, performance can be [divided into 2 almost independent kinds](https://www.transportfever.net/lexicon/index.php?entry/309-fps-display-measurement-analysis/).
The graphic performance is represented by FPS and is influenced mainly by the graphics card and the number of models to visualize. 
Thus, rebuilding dense cities with lots of mods can quickly get critical.
The script/engine performance refers to the simulation part, which is dependent on the number of agents/persons and vehicles to simulate.
If the simulation is not fast enough, this leads to stutters of the movements.
It turned out that car connection search on the street graph is a crucial factor.
Therefore, I strongly recommend to **not** use AI towns, but rather place person magnets so that houses are connected by foot only and people use public transport.

RAM turned out to be a critical factor because of the extreme number of track/street segments (edges) added by the OSM import.
As an example, my meglomaniac Frankfurt map [includes 500 000 edges, resulting in 53 GB RAM!](https://www.transportfever.net/thread/20034-osm-importer-automatisierter-nachbau-mit-openstreetmap/)
In usual TPF2 games, even 50 000 would nearly be reached only in big savegames.
If RAM usage is higher than the physical memory, the page file is heavily used, leading to stutters, especially when moving the map.
Also, the savegame size becomes very large and the saving times get higher.

Therefore, consider this impact and make tests early on to estimate if your savegame will still run smoothly on your hardware after the import!
If not, you either need to buy more RAM, choose a smaller map size, or reduce the number of edges by excluding certain types (more info in the tutorial).
[In the guide](https://www.transportfever.net/lexicon/entry/398-real-nachbau-in-tpf-2/), I tried to estimate the required RAM (column 'high').
Furthermore, the infrastructure density has a major influence on this, i.e. rural areas are less affected by this issue compared to urban areas.


## More Info
History and further information of OSM-Importer can be found in the [forum thread (german)](https://www.transportfever.net/thread/20034-osm-importer-automatisierter-nachbau-mit-openstreetmap/).

My development on this tool started 2021, in combination with the project of reconstructing Frankfurt and vicinity.
Progress was slow, including several breaks, and much [trial and error](https://www.youtube.com/watch?v=lsg3J13nJbE), but here we are.
During the development, other mods emerged.
Most notably, [Build with Collision](https://steamcommunity.com/sharedfiles/filedetails/?id=2660921894) was actually a spontaneous idea coming from my "research" with the street proposal API.


## Issues & Contact
For issues, questions, and feedback, please use the Issues Tab or Discussions in Github, the [forum thread](https://www.transportfever.net/thread/20034-osm-importer-automatisierter-nachbau-mit-openstreetmap/) or [Steam](https://steamcommunity.com/app/1066780/discussions/0/4344355442314070256/). 

For other requests: vacuumtubetrain@gmail.com 
(but I cannot provide support for TPF2 basics, please use Steam or [transportfever.net](https://www.transportfever.net/) for that)

## Support
[![](https://raw.githubusercontent.com/Vacuum-Tube/Advanced_Statistics_1/main/pictures/paypal.png)](https://www.paypal.com/paypalme/VacuumTubeTPF)