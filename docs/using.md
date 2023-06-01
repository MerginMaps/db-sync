# Using DB Sync

## How does it work

A single GeoPackage file in a Mergin Maps project is treated as an equivalent of a database schema - both
GeoPackage and a database schema can contain  multiple tables with data - and the DB Sync tool keeps
content of the tables in the database and in the GeoPackage the same.

There are two ways how the synchronization can be started:
 1. Init from GeoPackage: if you have a Mergin Maps project with an existing GeoPackage, the tool will
    create the destination schema and tables in the database (and populate those with data from GeoPackage).
 2. Init from database: if you have database already populated with tables and data, the tool will
    create the destination GeoPackage in your Mergin Maps project and initialize it.

More technical details:
- to keep track of the changes in the database, the DB sync tool adds an extra schema in your database
  (called "base" schema). This schema contains another copy of the data and it should not be touched,
  otherwise the sync may get to invalid state.
- the "base" schema contains the same data as the most recently seen project version in Mergin Maps. Whenever
  the tool attempts to synchronize data, it looks up any pending changes in the database by comparing data
  between the "base" schema and the "modified" schema (used by editing) - if any changes are detacted,
  they will be pushed to the appropriate GeoPackage in Mergin Maps project.

## Sample configuration file

The configuration of the tool is done using a simple YAML file - that file is then passed as a command line
argument to the DB Sync tool.

Here's a sample configuration:

```yaml
# How to connect to Mergin Maps server
mergin:
  url: https://app.merginmaps.com
  username: john
  password: mysecret

# How to initialize the sync - one of the two options:
# - "gpkg" - use existing GeoPackage from given Mergin Maps project (and create database schema during init)
# - "db" - use existing database schema (and create GeoPackage in Mergin Maps project during init)
init_from: gpkg

connections:
   - driver: postgres
     # Parameters to PostgreSQL database
     conn_info: "host=localhost dbname=mydb user=myuser password=mypassword"
     # Database schema that will be synchronized with Mergin Maps project
     # (it must exist if doing init from database, it must not exist if doing init from geopackage)
     modified: myproject_data
     # Extra database schema that will contain internal data and should never be edited
     # (it must not exist before the sync starts - it will be created automatically)
     base: myproject_data_base
     
     # Mergin Maps project to use (<workspace>/<project>)
     mergin_project: john/myproject
     # Path to the GeoPackage within the Mergin Maps project above
     # (it must exist if doing init from geopackage, it must not exist if doing init from database)
     sync_file: data.gpkg

daemon:
  # How often to synchronize (in seconds)
  sleep_time: 10
```

## Useful command line options

- `config_file_name.yaml` The file name with path of yaml config can be provided. By default the tool uses `config.yaml` file from the current directory.

- `--force-init` forces reinitialization of the sync. Drops dbsync schemas from database and the sync file and inits them all from scratch. This should be used to fix issues with dbsync init.

- `--single-run` instead of running the daemon indefinitely, performs just one single run. Such run consists of initialization, pull and push steps.

- `--skip-init` allows skipping the initialization of sync step. Should be only used if you know, what you are doing, otherwise issues are likely to occur.

- `--log-file` specify file to store log info into. If it is not set the log info will only be printed to the console.

- `--log-verbosity` use `errors` or `messages` to specify what should be logged. Default is `messages`.


## Excluding tables from sync

Sometimes in the database there are tables that should not be synchronised to Mergin Maps projects. It is possible to ignore
these tables and not sync them. To do so add `skip_tables` setting to the corresponding `connections` entry in the config
file:

```yaml
connections:
   - driver: postgres
     # ...
     mergin_project: john/myproject
     sync_file: sync.gpkg
     skip_tables:
      - table1
      - table2
```
