# DB Sync Script

This tool takes care of two-way synchronization between Mergin and another database (currently supporting PostGIS).

That means you can:
- insert / update / delete features in PostGIS database - and the changes will get automatically
  pushed to a configured Mergin project
- insert / update / delete features in a GeoPackage in Mergin project - and the changes will get
  automatically pushed to the PostGIS database 

### How does it work

- a single GeoPackage file in a Mergin project is treated as an equivalent of a database schema - both can contain
  multiple tables with data
- after the initialization, DB sync tool uses "main" schema in database (where any user editing may happen)
  and "base" schema (where only DB sync tool is allowed to do changes)
- the "base" schema contains the same data as the most recently known project version in Mergin, and it is used
  to figure out whether there have been any changes in the database - if there were, they will be pushed
  to the appropriate GeoPackage in Mergin project

### Installation

1. Install Mergin client: `pip3 install mergin-client`
2. Download [geodiff](https://github.com/lutraconsulting/geodiff) (master branch) and compile it 
2. download/clone this git repo

### How to use

Initialization:

1. set up configuration in config.ini  (see config.ini.default for a sample)
2. run dbsync initialization. There are two options:

   A. Init from Mergin project: if you have an existing Mergin project with a GeoPackage
      that already contains tables with data, this command will create schemas in your database:
      ```
      python3 dbsync.py init-from-gpkg
      ```
      This will create 'base' and 'modified' schemas in the database and populate them with data.
    
   B. Init from database: if you have tables with data in your database (in the schema marked as 'modified'
      in DB sync configuration) and want to create a GeoPackage based on that in your Mergin project:
      ```
      python3 dbsync.py init-from-db
      ```
      This will create 'base' schema in the database, create GeoPackage in the working dir and push it to Mergin.
   
Once initialized:

- run `python3 dbsync.py status' to see if there are any changes on Mergin server or in the database
- run `python3 dbsync.py pull` to fetch data from Mergin and apply them to the database
- run `python3 dbsync.py push` to fetch data from the database and push to Mergin


### Creating a local database (Ubuntu 20.04)

Install PostgreSQL server and PostGIS extension:
```
sudo apt install postgresql postgis
```

Add a user `john` and create a database for the user:
```
sudo -u postgres createuser john
sudo -u postgres psql -c "CREATE DATABASE john OWNER john"
sudo -u postgres psql -d john -c "CREATE EXTENSION postgis;"
``` 

### Creating a working schema

One can use `psql` tool to create a new schema and a single table there:

```
CREATE SCHEMA sync_data;

CREATE TABLE sync_data.points (
  fid serial primary key,
  name text,
  rating integer, geom geometry(Point, 4326)
);
```

### Running Tests

To run automatic tests:

    cd mergin
    export TEST_GEODIFFINFO_EXE=<geodiffinfo>   # path to geodiffinfo executable
    export TEST_DB_CONNINFO=<conninfo>          # connection info for DB
    export TEST_MERGIN_URL=<url>                # testing server
    export TEST_API_USERNAME=<username>
    export TEST_API_PASSWORD=<pwd>
    pytest-3 test/
