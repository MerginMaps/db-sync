# Mergin Maps Database Sync

This tool takes care of two-way synchronization between [Mergin Maps](https://merginmaps.com/) and another database (currently supporting PostGIS).

That means you can:

- insert / update / delete features in PostGIS database - and the changes will get automatically
  pushed to a configured Mergin Maps project
- insert / update / delete features in a GeoPackage in Mergin Maps project - and the changes will get
  automatically pushed to the PostGIS database

![DB sync illustration](docs/db-sync-drawing.png)


## Getting started

There are three steps to get DB Sync up and running:

1. Install the tool. See the [installation guide](docs/install.md)

2. Set up YAML configuration file. See [Using DB Sync](docs/using.md).

3. Run the tool. There are several parameters to control the way the tool runs (see [Using DB Sync](docs/using.md))

Not sure where to start? Check out our [quick start](docs/quick_start.md) guide to set up sync between your database and a new Mergin Maps project.

## Documentation

- [How to install](docs/install.md)
- [Using DB Sync](docs/using.md)
- [For developers](docs/development.md)

<div><img align="left" width="45" height="45" src="https://raw.githubusercontent.com/MerginMaps/docs/main/src/public/slack.svg"><a href="https://merginmaps.com/community/join">Join our community chat</a><br/>and ask questions!</div>
