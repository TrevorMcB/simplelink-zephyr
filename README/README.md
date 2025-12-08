# Hardware Map Generation

In order to run Twister tests on multiple devices, a hardware map must be generated.
While in the virtual enviroment, generate a hardware map from `/zephyr` subfolder:

`python .\scripts\twister --generate-hardware-map map.yml`

\
This will create a new map.yml file in the same directory as you ran the command, or if one already exists update it with any new plugged-in boards. Any boards that were disconnected will remain in the map, but be listed as `Connected: False`, and will not be used in Twister execution.

## REQUIRED File Dependency

In order for `hardwaremap.py` to work, board_ids folder with its contents must be added to a folder under `.venv/`:

`.venv/Lib/site-packages/board_ids`.

This ensures that hardware maps generate with the correct contents necessary for Twister to utilize them. 
