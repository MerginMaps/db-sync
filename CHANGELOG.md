# Changelog

## 2.1.1

- Fix failure to start when notifications were not enabled
- Fix Docker container

## 2.1.0

- Optionally send notification emails on sync failure (#56)

## 2.0.1

- Do not stop sync after a temporary network/server issue (#124)
- Clean up temporary files in the .mergin folder (#52)

## 2.0

This is a major release with many improvements aiming towards better robustness and ease of use.

We are starting to provide a Windows executable (#99) that can be used from terminal,
so that Windows users do not need to worry about Docker or manual compilation anymore!

- Minor changes in the YAML configuration file (#98):
  - New required entry: `init_from` specifies whether the initialization is done from a database (`db`)
    or from a GeoPackage in a Mergin Maps project (`gpkg`). Previously this was specified on the command
    line when running the tool.
  - Removed entries: `geodiff_exe` (now using geodiff from PATH) and `working_dir` (now using TEMP/dbsync)

- Much easier way to restart synchronization (when the data schema has changed, or when initialization failed) - simply
  add `--force-init` command line option to let db-sync do the cleanup (#16)

- Configuration file can be specified on command line instead of the default `config.yaml` (#97)

- Logging improvements
  - Make it possible to log to a file (`--log-file <filename>`) and configure verbosity (`--log-verbosity WARNING`)
  - Write output to standard error stream instead of standard output (#91)
  - Avoid printing database passwords in the outputs (#108)

- Robustness fixes and improvements
  - Check that PostGIS extension is available on init (#113)
  - Clean up database if initialization fails (#90, #95)
  - Quote schema names correctly, e.g. when using upper case characters (#54)
  - Use project ID to check that the project is the same (#76)
  - Handle push errors to avoid broken sync (#60)
  - Warn if the working dir exists but it is empty on init (#75)
  - Provide better error messages

- Infrastructure improvements:
  - Documentation improvements
  - Set up continuous integration to run tests (#8)
  - Fix versions of py-client and geodiff (#92)
  - Unified code formatting

## 1.1.2

- Fixed increasing memory consumption (#78)

## 1.1.1

- Fixed an error in "skip tables" functionality (#73)

## 1.1.0

- Changed config file format from INI to YAML
- Support for UUID, decimal, numeric, char(N) and character(N) data types
- Support for multiple schemas synchronization
- Excluding tables from synchronization

## 1.0.7

- Updated public server URL (#63)
- Updated to mergin-client 0.7.3

## 1.0.6

- Updated to geodiff 1.0.4 and mergin-client 0.6.5 (#50)

## 1.0.5

- Switched to geodiff 1.0 and mergin-client 0.6 (#49)
- Robustness improvement: mark base schema as invalid if init fails (#46)

## 1.0.4

- More fixes for loss of precision of floating point numbers
- Fixed support for character varying(X) data type (#44)

## 1.0.3

- Fixed loss of precision of floating point numbers (geodiff #110)
- Fixed writing of "empty" flag of geometries (geodiff #112)
- Support for more PostgreSQL data types - bigint, smallint, character varying (#41, geodiff #111)
- Fixed initialization from database (#42)

## 1.0.2

- Fixed two bugs related to copying of data between GPKG and PostgreSQL (geodiff #108, #109)
- Added an extra check during the init to verify data got copied correctly (#37)
- Added display of mergin-db-sync version when the daemon starts

## 1.0.1
 -  Fixed handling of local working directory in init function

## 1.0  (2021/03/25)

The first official release of mergin-db-sync! It includes all the essential functionality to set up and maintain
sync between a Mergin project and a PostgreSQL database.

The tool can be run from CLI on demand with low-level commands (init, pull, push) or it can be started as a daemon
to continuously maintain data in sync. It can be also run using a Docker container: lutraconsulting/mergin-db-sync
