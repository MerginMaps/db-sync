# PostgreSQL Setup

## Creating a local database (Ubuntu 20.04)

Install PostgreSQL server and PostGIS extension:

```bash
sudo apt install postgresql postgis
```

Add a user `john` and create a database for the user:

```bash
sudo -u postgres createuser john
sudo -u postgres psql -c "CREATE DATABASE john OWNER john"
sudo -u postgres psql -d john -c "CREATE EXTENSION postgis;"
```

## Creating a working schema

One can use `psql` tool to create a new schema and a single table there:

```sql
CREATE SCHEMA sync_data;

CREATE TABLE sync_data.points (
  fid serial primary key,
  name text,
  rating integer, geom geometry(Point, 4326)
);
```

## Creating a dedicated PostgreSQL user to view/edit data

Assuming we have database named `mergin_dbsync` where `sync_main` is the name of the schema
which will be used for ordinary database users, here is how we can create and grant
permissions to those users:

```sql
CREATE USER db_user WITH PASSWORD 'TopSecretPassword';
GRANT ALL ON DATABASE mergin_dbsync TO db_user;
GRANT ALL ON SCHEMA sync_main TO db_user;
GRANT ALL ON ALL TABLES IN SCHEMA sync_main TO db_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA sync_main TO db_user;
```
