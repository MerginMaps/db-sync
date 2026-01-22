"""
YAML configuration file read/write utilities for the web interface.
"""

import os
import pathlib
import yaml


# Default config path - in project root
DEFAULT_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "web_config.yaml"


def get_config_path() -> pathlib.Path:
    """Get the configuration file path."""
    return DEFAULT_CONFIG_PATH


def load_config() -> dict:
    """
    Load configuration from YAML file.

    Returns:
        dict with configuration or empty dict if file doesn't exist
    """
    config_path = get_config_path()
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            return config if config else {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {e}")
    except IOError as e:
        raise IOError(f"Could not read config file: {e}")


def save_config(config_data: dict) -> dict:
    """
    Save configuration to YAML file.

    Args:
        config_data: dict containing:
            - mergin: {url, username, password}
            - init_from: 'gpkg' or 'db'
            - connection: {conn_info, modified, base, mergin_project, sync_file}
            - daemon: {sleep_time}

    Returns:
        dict with 'success' boolean and 'path' or 'error' string
    """
    config_path = get_config_path()

    # Build the config structure matching config.yaml.default format
    config = {
        "mergin": {
            "url": config_data.get("mergin", {}).get("url", "https://app.merginmaps.com"),
            "username": config_data.get("mergin", {}).get("username", ""),
            "password": config_data.get("mergin", {}).get("password", ""),
        },
        "init_from": config_data.get("init_from", "gpkg"),
        "connections": [
            {
                "driver": "postgres",
                "conn_info": config_data.get("connection", {}).get("conn_info", ""),
                "modified": config_data.get("connection", {}).get("modified", ""),
                "base": config_data.get("connection", {}).get("base", ""),
                "mergin_project": config_data.get("connection", {}).get("mergin_project", ""),
                "sync_file": config_data.get("connection", {}).get("sync_file", ""),
            }
        ],
        "daemon": {
            "sleep_time": config_data.get("daemon", {}).get("sleep_time", 10),
        },
    }

    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return {
            "success": True,
            "path": str(config_path)
        }
    except IOError as e:
        return {
            "success": False,
            "error": f"Could not write config file: {e}"
        }
    except yaml.YAMLError as e:
        return {
            "success": False,
            "error": f"Error generating YAML: {e}"
        }


def config_exists() -> bool:
    """Check if configuration file exists."""
    return get_config_path().exists()


def get_config_for_display() -> dict:
    """
    Load config and prepare it for display (mask password).

    Returns:
        dict with configuration, password masked
    """
    config = load_config()
    if not config:
        return {}

    # Mask password for display
    display_config = config.copy()
    if "mergin" in display_config and "password" in display_config["mergin"]:
        display_config["mergin"]["password"] = "********"

    return display_config
