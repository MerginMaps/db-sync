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
  
### Quick start

Not sure where to start? Check out our [quick start](docs/quick_start.md) guide to set up sync between your database and a new Mergin project.

### Running with Docker

The easiest way to run DB sync is with Docker.

To build the container:
```
docker build -t mergin_db_sync .
```

To run the container, use a command like the following one: 
```
sudo docker run -it \
  -e DB_CONN_INFO="host=myhost.com dbname=mergin_dbsync user=postgres password=top_secret" \
  -e DB_SCHEMA_MODIFIED=sync_main \
  -e DB_SCHEMA_BASE=sync_base \
  -e MERGIN_USERNAME=john \
  -e MERGIN_PASSWORD=myStrongPassword \
  -e MERGIN_PROJECT_NAME=john/my_project \
  -e MERGIN_SYNC_FILE=sync_db.gpkg \
  mergin_db_sync python3 dbsync_daemon.py --init-from-gpkg
```
This will create `sync_main` and `sync_base` schemas in the PostgreSQL database based on the table
schemas and from the `sync_db.gpkg` GeoPackage in `john/my_project` Mergin project, and they will
get populated by the existing data. Afterwards, the sync process will start, regularly checking both
Mergin service and your PostgreSQL for any new changes.

Please make sure the PostgreSQL user in the database connection info has sufficient permissions
to create schemas and tables.  

### Installation

If you would like to avoid the manual installation steps, please follow the guide on using
DB sync with Docker above.

1. Install Mergin client: `pip3 install mergin-client`

   If you get `ModuleNotFoundError: No module named 'skbuild'` error, try to update pip with command
`python -m pip install --upgrade pip`

2. Install PostgreSQL client (for Python and for C): `sudo apt install libpq-dev python3-psycopg2`

3. Compile [geodiff](https://github.com/lutraconsulting/geodiff) from master branch with PostgreSQL support:
   ```
   git clone https://github.com/lutraconsulting/geodiff.git
   cd geodiff
   mkdir build && cd build
   cmake -DWITH_POSTGRESQL=TRUE ../geodiff
   make
   ```

4. download this git repository: `git clone https://github.com/lutraconsulting/mergin-db-sync.git`

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
    export TEST_GEODIFF_EXE=<geodiff>           # path to geodiff executable
    export TEST_DB_CONNINFO=<conninfo>          # connection info for DB
    export TEST_MERGIN_URL=<url>                # testing server
    export TEST_API_USERNAME=<username>
    export TEST_API_PASSWORD=<pwd>
    pytest-3 test/


### Creating a dedicated PostgreSQL user to view/edit data

Assuming we have database named `mergin_dbsync` where `sync_main` is the name of the schema
which will be used for ordinary database users, here is how we can create and grant
permissions to those users:

```
CREATE USER db_user WITH PASSWORD 'TopSecretPassword';
GRANT ALL ON DATABASE mergin_dbsync TO db_user;
GRANT ALL ON SCHEMA sync_main TO db_user;
GRANT ALL ON ALL TABLES IN SCHEMA sync_main TO db_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA sync_main TO db_user;
```

### Running the sync daemon in tmux

If we SSH somewhere and want to leave the daemon (`dbsync_daemon.py`) running there
even after logging out, we can use `tmux` utility. After starting SSH session, run
`tmux` which will start new terminal session where you can start the script
(`python3 dbsync_daemon.py`) and then with `Ctrl-B` followed by `d` leave the script
running in a detached tmux session. Logging out will not affect the daemon. At some
point later one can run `tmux attach` to bring the session back to the foreground.   


### Releasing new version

1. Update `version.py` and `CHANGELOG.md`
2. Tag the new version in git repo
3. Build and upload the new container (both with the new version tag and as the latest tag)
   ```
   docker build --no-cache -t lutraconsulting/mergin-db-sync .
   docker tag lutraconsulting/mergin-db-sync lutraconsulting/mergin-db-sync:1.0.3
   docker push lutraconsulting/mergin-db-sync:1.0.3
   docker push lutraconsulting/mergin-db-sync:latest
   ```
