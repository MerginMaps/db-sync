# DB Sync Script

This tool takes care of two-way synchronization between [Mergin Maps](https://merginmaps.com/) and another database (currently supporting PostGIS).

That means you can:

- insert / update / delete features in PostGIS database - and the changes will get automatically
  pushed to a configured Mergin Maps project
- insert / update / delete features in a GeoPackage in Mergin Maps project - and the changes will get
  automatically pushed to the PostGIS database

**IMPORTANT**: structure of the config file was changed in the latest version. Therefore old .ini config files need to be updated.

## How does it work

- a single GeoPackage file in a Mergin Maps project is treated as an equivalent of a database schema - both can contain
  multiple tables with data
- after the initialization, DB sync tool uses "main" schema in database (where any user editing may happen)
  and "base" schema (where only DB sync tool is allowed to do changes)
- the "base" schema contains the same data as the most recently known project version in Mergin Maps, and it is used
  to figure out whether there have been any changes in the database - if there were, they will be pushed
  to the appropriate GeoPackage in Mergin Maps project

## Quick start

Not sure where to start? Check out our [quick start](docs/quick_start.md) guide to set up sync between your database and a new Mergin Maps project.

<div><img align="left" width="45" height="45" src="https://raw.githubusercontent.com/MerginMaps/docs/main/src/.vuepress/public/slack.svg"><a href="https://merginmaps.com/community/join">Join our community chat</a><br/>and ask questions!</div><br />

## Installation

### Windows

For Windows we provide prebuild exe file for [download](fill-link).

## Other Systems

If you would like to avoid the manual installation steps, please follow the guide on using
DB sync with [Docker](docs/docker.md).

To manually install and build the required libraries follow these steps:

1. Install Mergin Maps client: `pip3 install mergin-client`

   If you get `ModuleNotFoundError: No module named 'skbuild'` error, try to update pip with command
`python -m pip install --upgrade pip`

1. Install PostgreSQL client (for Python and for C): `sudo apt install libpq-dev python3-psycopg2`

1. Install Dynaconf library: `sudo apt install python3-dynaconf`

1. Compile [geodiff](https://github.com/MerginMaps/geodiff) from master branch with PostgreSQL support:

   ```bash
   git clone https://github.com/MerginMaps/geodiff.git
   cd geodiff
   mkdir build && cd build
   cmake -DWITH_POSTGRESQL=TRUE ../geodiff
   make
   ```

1. download this git repository: `git clone https://github.com/MerginMaps/mergin-db-sync.git`

1. run file `python3 dbsync_daemon.py [config_file.yaml]`

## How to use

DB Sync should be run using the `dbsync_daemon.py` script.

1. set up configuration in config.yaml  (see config.yaml.default for a sample)

2. run `dbsync_daemon.py`. There are several parameters to control the way the tool runs.

   A. `config_file_name.yaml` The file name with path of yaml config can be provided. By default the `dbsync_daemon.py` loads `config.yaml` file.

   B. `--force-init` forces reinitialization of the sync. Drops dbsync schemas from database and the sync file and inits them all from scratch. This should be used to fix issues with dbsync init.

   C. `--single-run` instead of running the daemon indefinitely, performs just one single run. Such run consists of initialization, pull and push steps.

   D. `--skip-init` allows skipping the initialization of sync step. Should be only used if you know, what you are doing, otherwise issues are likely to occur.

   E. `--log-file` specify file to store log info into. If it is not set the log info will only be printed to the console.

   F. `--log-verbosity` use `errors` or `messages` to specify what should be logged. Default is `messages`.

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

