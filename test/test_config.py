"""
Mergin Maps DB Sync - a tool for two-way synchronization between Mergin Maps and a PostGIS database

Copyright (C) 2022 Lutra Consulting

License: MIT
"""
import os
import pytest

from config import config, ConfigError, validate_config

SERVER_URL = os.environ.get('TEST_MERGIN_URL')
API_USER = os.environ.get('TEST_API_USERNAME')
USER_PWD = os.environ.get('TEST_API_PASSWORD')


def _reset_config():
    """ helper to reset config settings to ensure valid config """
    config.update({
        'MERGIN__USERNAME': API_USER,
        'MERGIN__PASSWORD': USER_PWD,
        'MERGIN__URL': SERVER_URL,
        'CONNECTIONS': [{"driver": "postgres", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "john/dbsync", "sync_file": "sync.gpkg", "init_from": "gpkg"}]
    })


def test_config():
    # valid config
    _reset_config()
    validate_config(config)

    with pytest.raises(ConfigError, match="Config error: Incorrect mergin settings"):
        config.update({'MERGIN__USERNAME': None})
        validate_config(config)

    _reset_config()
    with pytest.raises(ConfigError, match="Config error: Connections list can not be empty"):
        config.update({'CONNECTIONS': []})
        validate_config(config)

    _reset_config()
    with pytest.raises(ConfigError, match="Config error: Incorrect connection settings"):
        config.update({'CONNECTIONS': [{"modified": "mergin_main"}]})
        validate_config(config)

    _reset_config()
    with pytest.raises(ConfigError, match="Config error: Only 'postgres' driver is currently supported."):
        config.update({'CONNECTIONS': [{"driver": "oracle", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "john/dbsync", "sync_file": "sync.gpkg", "init_from": "gpkg"}]})
        validate_config(config)

    _reset_config()
    with pytest.raises(ConfigError, match="Config error: Name of the Mergin Maps project should be provided in the namespace/name format."):
        config.update({'CONNECTIONS': [{"driver": "postgres", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "dbsync", "sync_file": "sync.gpkg", "init_from": "gpkg"}]})
        validate_config(config)
