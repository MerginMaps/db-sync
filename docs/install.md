# How to install DB Sync

## Windows executable

For Windows we provide pre-built exe file for [download](fill-link).

To run the tool, open the terminal and run the executable with your config file:

```bash
mergin-db-sync.exe config_settings.yaml
```

## Docker

This is the easiest way to run DB sync if you are not on Windows - simply use `lutraconsulting/mergin-db-sync` container from Docker hub:

```bash
sudo docker run -it -v /path/to/folder_with_config:/settings lutraconsulting/mergin-db-sync:latest \
       python3 dbsync_daemon.py /settings/config_settings.yaml
```

The container can be used also on Windows, see [instructions on how to use with WSL](install_wsl.md), but generally it is recommended to use the executable linked above.


## Manual build

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

1. run file `python3 dbsync_daemon.py config_settings.yaml`
