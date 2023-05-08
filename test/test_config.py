"""
Mergin Maps DB Sync - a tool for two-way synchronization between Mergin Maps and a PostGIS database

Copyright (C) 2022 Lutra Consulting

License: MIT
"""
import pytest

from config import config, ConfigError, validate_config, get_ignored_tables

from .conftest import _reset_config


def test_config():
    # valid config
    _reset_config()
    validate_config(config)

    with pytest.raises(ConfigError, match="Config error: Incorrect mergin settings"):
        config.update({'MERGIN__USERNAME': None})
        validate_config(config)

    _reset_config()
    with pytest.raises(ConfigError, match="Config error: Missing parameter `init_from` in the configuration"):
        config.unset('init_from', force=True)
        validate_config(config)

    _reset_config()
    with pytest.raises(ConfigError, match="Config error: `init_from` parameter must be either `gpkg` or `db`"):
        config.update({'init_from': "anywhere"})
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
        config.update({'CONNECTIONS': [{"driver": "oracle", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "john/dbsync", "sync_file": "sync.gpkg"}]})
        validate_config(config)

    _reset_config()
    with pytest.raises(ConfigError, match="Config error: Name of the Mergin Maps project should be provided in the namespace/name format."):
        config.update({'CONNECTIONS': [{"driver": "postgres", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "dbsync", "sync_file": "sync.gpkg"}]})
        validate_config(config)


def test_skip_tables():
    _reset_config()

    config.update({'CONNECTIONS': [{"driver": "postgres", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "john/dbsync", "sync_file": "sync.gpkg", "skip_tables": None}]})
    validate_config(config)

    config.update({'CONNECTIONS': [{"driver": "postgres", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "john/dbsync", "sync_file": "sync.gpkg", "skip_tables": []}]})
    validate_config(config)

    config.update({'CONNECTIONS': [{"driver": "postgres", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "john/dbsync", "sync_file": "sync.gpkg", "skip_tables": "table"}]})
    validate_config(config)

    config.update({'CONNECTIONS': [{"driver": "postgres", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "john/dbsync", "sync_file": "sync.gpkg", "skip_tables": ["table"]}]})


def test_get_ignored_tables():
    _reset_config()

    config.update({'CONNECTIONS': [{"driver": "postgres", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "john/dbsync", "sync_file": "sync.gpkg", "skip_tables": None}]})
    ignored_tables = get_ignored_tables(config.connections[0])
    assert ignored_tables == []

    config.update({'CONNECTIONS': [{"driver": "postgres", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "john/dbsync", "sync_file": "sync.gpkg", "skip_tables": []}]})
    ignored_tables = get_ignored_tables(config.connections[0])
    assert ignored_tables == []

    config.update({'CONNECTIONS': [{"driver": "postgres", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "john/dbsync", "sync_file": "sync.gpkg", "skip_tables": "table"}]})
    validate_config(config)
    ignored_tables = get_ignored_tables(config.connections[0])
    assert ignored_tables == ["table"]

    config.update({'CONNECTIONS': [{"driver": "postgres", "conn_info": "", "modified": "mergin_main", "base": "mergin_base", "mergin_project": "john/dbsync", "sync_file": "sync.gpkg", "skip_tables": ["table"]}]})
    validate_config(config)
    ignored_tables = get_ignored_tables(config.connections[0])
    assert ignored_tables == ["table"]
