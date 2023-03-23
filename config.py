"""
Mergin Maps DB Sync - a tool for two-way synchronization between Mergin Maps and a PostGIS database

Copyright (C) 2022 Lutra Consulting

License: MIT
"""

from dynaconf import Dynaconf
import platform
import tempfile
import pathlib
import subprocess

config = Dynaconf(
    envvar_prefix=False,
    settings_files=['config.yaml'],
    geodiff_exe="geodiff.exe" if platform.system() == "Windows" else "geodiff",
    working_dir=(pathlib.Path(tempfile.gettempdir()) / "dbsync").as_posix()
)


class ConfigError(Exception):
    pass


def validate_config(config):
    """ Validate config - make sure values are consistent """

    # validate that geodiff can be found, otherwise it does not make sense to run DB Sync
    try:
        subprocess.run([config.geodiff_exe, "help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise ConfigError("Config error: Geodiff executable not found. Is it installed and on available in `PATH` environmental variable?")

    if not (config.mergin.url and config.mergin.username and config.mergin.password):
        raise ConfigError("Config error: Incorrect mergin settings")

    if not (config.connections and len(config.connections)):
        raise ConfigError("Config error: Connections list can not be empty")

    for conn in config.connections:
        for attr in ["driver", "conn_info", "init_from", "modified", "base", "mergin_project", "sync_file"]:
            if not hasattr(conn, attr):
                raise ConfigError(f"Config error: Incorrect connection settings. Required parameter `{attr}` is missing.")

        if conn.driver != "postgres":
            raise ConfigError("Config error: Only 'postgres' driver is currently supported.")

        if conn.init_from not in ["gpkg", "db"]:
            raise ConfigError(f"Config error: `init_from` parameter must be either `gpkg` or `db`. Current value is `{conn.init_from}`.")

        if "/" not in conn.mergin_project:
            raise ConfigError("Config error: Name of the Mergin Maps project should be provided in the namespace/name format.")

        if "skip_tables" in conn:
            if not isinstance(conn.skip_tables, list):
                raise ConfigError("Config error: Ignored tables parameter should be a list")


def get_ignored_tables(connection):
    return connection.skip_tables if "skip_tables" in connection else []
