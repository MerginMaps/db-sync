"""
Mergin Maps DB Sync - a tool for two-way synchronization between Mergin Maps and a PostGIS database

Copyright (C) 2022 Lutra Consulting

License: MIT
"""

import pathlib
import platform
import smtplib
import subprocess
import tempfile

from dynaconf import Dynaconf
import dynaconf

from smtp_functions import create_connection_and_log_user

config = Dynaconf(
    envvar_prefix=False,
    settings_files=[],
    geodiff_exe="geodiff.exe" if platform.system() == "Windows" else "geodiff",
    working_dir=(pathlib.Path(tempfile.gettempdir()) / "dbsync").as_posix(),
)


class ConfigError(Exception):
    pass


def validate_config(config):
    """Validate config - make sure values are consistent"""

    # validate that geodiff can be found, otherwise it does not make sense to run DB Sync
    try:
        subprocess.run(
            [
                config.geodiff_exe,
                "help",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise ConfigError(
            "Config error: Geodiff executable not found. Is it installed and available in `PATH` environment variable?"
        )

    if not (config.mergin.url and config.mergin.username and config.mergin.password):
        raise ConfigError("Config error: Incorrect mergin settings")

    if not (config.connections and len(config.connections)):
        raise ConfigError("Config error: Connections list can not be empty")

    if "init_from" not in config:
        raise ConfigError("Config error: Missing parameter `init_from` in the configuration.")

    if config.init_from not in [
        "gpkg",
        "db",
    ]:
        raise ConfigError(
            f"Config error: `init_from` parameter must be either `gpkg` or `db`. Current value is `{config.init_from}`."
        )

    for conn in config.connections:
        for attr in [
            "driver",
            "conn_info",
            "modified",
            "base",
            "mergin_project",
            "sync_file",
        ]:
            if not hasattr(
                conn,
                attr,
            ):
                raise ConfigError(
                    f"Config error: Incorrect connection settings. Required parameter `{attr}` is missing."
                )

        if conn.driver != "postgres":
            raise ConfigError("Config error: Only 'postgres' driver is currently supported.")

        if "/" not in conn.mergin_project:
            raise ConfigError(
                "Config error: Name of the Mergin Maps project should be provided in the namespace/name format."
            )

        if "skip_tables" in conn:
            if conn.skip_tables is None:
                continue
            elif isinstance(
                conn.skip_tables,
                str,
            ):
                continue
            elif not isinstance(
                conn.skip_tables,
                list,
            ):
                raise ConfigError("Config error: Ignored tables parameter should be a list")

    if "notification" in config:
        settings = [
            "smtp_server",
            "email_sender",
            "email_subject",
            "email_recipients",
        ]

        for setting in settings:
            if setting not in config.notification:
                raise ConfigError(f"Config error: `{setting}` is missing from `notification`.")

        if not isinstance(config.notification.email_recipients, list):
            raise ConfigError("Config error: `email_recipients` should be a list of addresses.")

        if "use_ssl" in config.notification:
            if not isinstance(config.notification.use_ssl, bool):
                raise ConfigError("Config error: `use_ssl` must be set to either `true` or `false`.")

        if "use_tls" in config.notification:
            if not isinstance(config.notification.use_tls, bool):
                raise ConfigError("Config error: `use_tls` must be set to either `true` or `false`.")

        if "smtp_port" in config.notification:
            if not isinstance(config.notification.smtp_port, int):
                raise ConfigError("Config error: `smtp_port` must be set to an integer.")

        if "minimal_email_interval" in config.notification:
            if not isinstance(config.notification.minimal_email_interval, (int, float)):
                raise ConfigError("Config error: `minimal_email_interval` must be set to a number.")

        try:
            smtp_conn = create_connection_and_log_user(config)
            smtp_conn.quit()
        except (OSError, smtplib.SMTPConnectError, smtplib.SMTPAuthenticationError) as e:
            err = str(e)
            if isinstance(e, (smtplib.SMTPConnectError, smtplib.SMTPAuthenticationError)):
                err = str(e.smtp_error)
            raise ConfigError(f"Config SMTP Error: {err}.")


def get_ignored_tables(
    connection,
):
    if "skip_tables" in connection:
        if connection.skip_tables is None:
            return []
        elif isinstance(
            connection.skip_tables,
            str,
        ):
            return [connection.skip_tables]
        elif isinstance(
            connection.skip_tables,
            list,
        ):
            if len(connection.skip_tables) < 1:
                return []
            elif isinstance(connection.skip_tables, dynaconf.vendor.box.box_list.BoxList):
                return connection.skip_tables.to_list()
            return connection.skip_tables
    else:
        return []


def update_config_path(
    path_param: str,
) -> None:
    config_file_path = pathlib.Path(path_param)

    if config_file_path.exists():
        print(f"Using config file: {path_param}")
        user_file_config = Dynaconf(
            envvar_prefix=False,
            settings_files=[config_file_path],
        )
        config.update(user_file_config)
    else:
        raise IOError(f"Config file {config_file_path} does not exist.")
