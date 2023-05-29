# How to install DB Sync

## Windows executable

For Windows we provide pre-built exe file for [download](fill-link).

TODO: example

## Docker

You can use `lutraconsulting/mergin-db-sync` container from Docker hub.

The container can be used also on Windows, see [instructions on how to use with WSL](install_wsl.md), but generally it is recommended to use the executable linked above.

TODO: example

## Manual build

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
