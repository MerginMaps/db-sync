# Quick start guide

In this quick start guide you will set up synchronization between your PostGIS database and new Mergin project.

## Prerequisites

- PostGIS database
- docker engine

## 1. Add data to DB
Create a new schema (`sync_data`) in your postgis database (here `db-sync`) with few points.
You can simply use this [file](../sample_data/test_data.sql) and run:

```
$ psql -h localhost -d db-sync -U postgres -f sample_data/test_data.sql
```
## 2. Create an empty mergin project
Go to [Mergin](https://public.cloudmergin.com/) website and create a new blank project.

![new_project](images/new_proj.png)

You should see there are not any files there.

![new_project_2](images/new_proj2.png)

and your full project name for later will be `<username>/<project-name>`, e.g. `john/db-sync`

## 3. Start syncing
Download and run db-sync docker image:

```
$ sudo docker run --rm --name mergin_db_sync -it \
  -e DB_CONN_INFO="host=myhost.com dbname=db-sync user=postgres password=top_secret" \
  -e DB_SCHEMA_MODIFIED=sync_data \
  -e DB_SCHEMA_BASE=sync_base \
  -e MERGIN_USERNAME=john \
  -e MERGIN_PASSWORD=myStrongPassword \
  -e MERGIN_PROJECT_NAME=john/db-sync \
  -e MERGIN_SYNC_FILE=sync_db.gpkg \
  lutraconsulting/mergin-db-sync:latest python3 dbsync_daemon.py --init-from-db
```
and you should see a new geopackage file in your Mergin project. To be able to use the Geopackage as a survey layer:

- Download the generated gpkg file
- Open it in QGIS
- Style it (if you wish)
- Save the QGIS project on the same folder as the downloaded gpkg file
- Upload the QGIS project to your Mergin project

The QGIS and Geopackage files will be a valid Mergin project ready for surveying. Read more about QGIS project configuration on [Mergin](https://help.cloudmergin.com/) and [Input](https://help.inputapp.io/) documentations.

![new_project_3](images/new_proj3.png)

In order to stop syncing simply stop docker container.

---
Note: If you run your db-sync docker on the same host as your database is, you need to set up correct [networking](https://docs.docker.com/network/).
For instance, on linux for testing purpose you can use default bridge, e.g IP address `172.17.0.1`
