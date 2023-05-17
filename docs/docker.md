# Running with Docker

The easiest way to run DB sync is with Docker. To run the container, use a command like the following one:

```bash
sudo docker run -it \
  -v /path/to/folder_with_config_files:/settings \
  lutraconsulting/mergin-db-sync:latest \
  python3 dbsync_daemon.py /settings/config_settings.yaml
```

This will create `base` and `modified` schemas in the PostgreSQL database, based on the table
schemas and from the `sync_file` GeoPackage in `mergin_project` Mergin Maps project, and they will
get populated by the existing data. Afterwards, the sync process will start, regularly checking both
Mergin Maps service and your PostgreSQL for any new changes. The values of variables mentioned above are
read from the config file.

Please make sure the PostgreSQL user in the database connection info has sufficient permissions
to create schemas and tables.
