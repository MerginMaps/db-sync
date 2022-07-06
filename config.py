"""
Mergin Maps DB Sync - a tool for two-way synchronization between Mergin Maps and a PostGIS database

Copyright (C) 2022 Lutra Consulting

License: MIT
"""

from dynaconf import Dynaconf

config = Dynaconf(
    envvar_prefix=False,
    settings_files=['config.yaml'],
)


class ConfigError(Exception):
    pass


def validate_config(config):
    """ Validate config - make sure values are consistent """

    if not config.working_dir:
        raise ConfigError("Config error: Working directory is not set")

    if not config.geodiff_exe:
        raise ConfigError("Config error: Path to geodiff executable is not set")

    if not (config.mergin.url and config.mergin.username and config.mergin.password):
        raise ConfigError("Config error: Incorrect mergin settings")

    if not (config.connections and len(config.connections)):
        raise ConfigError("Config error: Connections list can not be empty")

    for conn in config.connections:
        if not all(hasattr(conn, attr) for attr in ["driver", "conn_info", "modified", "base", "mergin_project", "sync_file"]):
            raise ConfigError("Config error: Incorrect connection settings")

        if conn.driver != "postgres":
            raise ConfigError("Config error: Only 'postgres' driver is currently supported.")

        if "/" not in conn.mergin_project:
            raise ConfigError("Config error: Name of the Mergin Maps project should be provided in the namespace/name format.")
