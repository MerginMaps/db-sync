# How to install DB Sync

## Windows executable

For Windows we provide pre-built exe file for download since version 2.0 - there are [download links attached to releases](https://github.com/MerginMaps/mergin-db-sync/releases).

To run the tool, open the terminal and run the executable with your config file (`config.yaml`):

```bash
mergin-db-sync.exe config.yaml
```

## Docker

This is the easiest way to run DB sync if you are not on Windows - simply use `lutraconsulting/mergin-db-sync` container from Docker hub.
Assuming you want to use `config.yaml` from the current directory:

```bash
docker run -it -v ${PWD}:/config lutraconsulting/mergin-db-sync:latest /config/config.yaml
```

If you are testing with a PostgreSQL instance on your localhost, add `--network host` option to the Docker command so that
the container can reach the database on localhost.

The container can be used also on Windows, see [instructions on how to use with WSL](install_wsl.md), but generally it is recommended to use the executable linked above.


## Manual build

To manually install and build the required libraries follow these steps:

1. Download this git repo: `git clone https://github.com/MerginMaps/mergin-db-sync.git`

1. Install Python dependencies: `pip3 install -r requirements.txt`

   If you get `ModuleNotFoundError: No module named 'skbuild'` error, try to update pip with command
`python -m pip install --upgrade pip`

1. Install PostgreSQL client (for Python and for C): `sudo apt install libpq-dev python3-psycopg2`

1. Compile [geodiff](https://github.com/MerginMaps/geodiff) with PostgreSQL support:

   ```bash
   git clone --branch 2.0.2 https://github.com/MerginMaps/geodiff.git
   cd geodiff
   mkdir build && cd build
   cmake -DWITH_POSTGRESQL=TRUE ../geodiff
   make
   ```

   Then add the compiled `geodiff` executable to your PATH.

1. Run the tool: `python3 dbsync_daemon.py config.yaml`  (assuming `config.yaml` is where your configuration is stored)
