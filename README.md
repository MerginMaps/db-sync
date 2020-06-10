# DB Sync Script

This tool takes care of two-way synchronization between Mergin and another database (currently supporting PostGIS)

Initialization:

1. set up configuration in config.ini  (see config.ini.default for a sample)
2. make your database schema ready (the one marked as 'modified')
3. download mergin project to the local working directory specified
4. run `python3 dbsync.py init` to create 'base' schema in the database, create GeoPackage in the working dir and push it to Mergin

Once initialized:

- run `python3 dbsync.py pull` to fetch data from Mergin and apply them to the database
- run `python3 dbsync.py push` to fetch data from the database and push to Mergin
