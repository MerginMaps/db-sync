
### Running with Docker

The easiest way to run DB sync is with Docker. To run the container, use a command like the following one:

```
sudo docker run -it \
  -e MERGIN__USERNAME=john \
  -e MERGIN__PASSWORD=myStrongPassword \
  -e CONNECTIONS="[{driver='postgres', conn_info='host=myhost.com dbname=mergin_dbsync user=postgres password=top_secret', modified='sync_main', base='sync_base', mergin_project='john/my_project', sync_file='sync_db.gpkg'}]" \
  lutraconsulting/mergin-db-sync:latest \
  python3 dbsync_daemon.py --init-from-gpkg
```

This will create `sync_main` and `sync_base` schemas in the PostgreSQL database based on the table
schemas and from the `sync_db.gpkg` GeoPackage in `john/my_project` Mergin Maps project, and they will
get populated by the existing data. Afterwards, the sync process will start, regularly checking both
Mergin Maps service and your PostgreSQL for any new changes.

Please make sure the PostgreSQL user in the database connection info has sufficient permissions
to create schemas and tables.

**Please note double underscore `__` is used to separate [config](config.yaml.default) group and item.**
