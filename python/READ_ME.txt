------------------------------------------------------------------------------------------------------------------------------
This is a edited version of VacuumTube´s: OSM-Importer v1.5 to make larger maps then scale 1:1 (25x25km).
------------------------------------------------------------------------------------------------------------------------------
WHAT DOES IT DO:
****************
It prevents the converter from adding all information to the osmdata.lua file.

1. Only adds larger roads like "Highway" and just main Railway.
    highwaytypes = [  # https://wiki.openstreetmap.org/wiki/Key:highway
    "aeroway",
    # actual streets
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "tertiary",
    "tertiary_link".
AND
    railtypes = [  # https://wiki.openstreetmap.org/wiki/Key:railway
    "rail".

2. Removes "Golf_course" from PAVER.

3. Now only prints "city", "town" lables on map.

4. Adding realtime progress-statusbar in the terminal when converting the map.

HOW TO:
*******

#1 Unzip to your OSM-Importer/python folder.

#2 Run the Installer.exe.

#3 Use RUN.bat when you whant to convert an xml/osm file with limitations.

------------------------------------------------------------------------------------------------------------------------------
CREDITS: Creator of OSM-Imorter = VacuumTube: https://steamcommunity.com/id/Vacuum-Tube
------------------------------------------------------------------------------------------------------------------------------

 *###                     ##    ####************#####     ***************#**                         *****###         ###***++   
 ****##                ##***   *****+            *****    *****+      -=+****                          ==+*****     *****+=-     
 +++******          ********  *++++               ++++*   +++++=        -=++**                           -=+++*** ***+++=-:      
 =+++++++++**    **+++++++++  +++++  +++++++++++  +++++   ++===-         -=+++*   *****************       :-=+++++++++=-:        
 -===========++++===========  =====  ==++   ++++  =====   =====-          -==++++ *++++       +++++         -==========          
 -======-  ::::::::  -======  =====  ====   ====  =----   =====-           ====== =====       ==++=          =========           
 --====--     ::     :--====  =====  =----  ---=  -----   =====-          ==----  -----       -====         ====---=====         
 -------:            :------  -----   ---::::::::::::::   ----=-        ===--:.   ::---       -----       ===----:----===        
 :::--::.            .:::-::  ::::--                      ::----       =---:..    ..::-       -----     ==---::.   .::-----      
 ........            .......   ....:::::::::::::::::::    ...::::--==--::....       ...:-     :::..   -::::....      ...:::::    
 ........            .......     ......................   .................          ..............  ........         .......:  

