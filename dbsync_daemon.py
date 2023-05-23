# keep running until killed by ctrl+c:
# - sleep N seconds
# - pull
# - push

import datetime
import sys
import time
import argparse
import platform
import logging
import os
import pathlib
import typing

import dbsync
from version import (
    __version__,
)
from config import (
    config,
    validate_config,
    ConfigError,
    update_config_path,
)


def is_pyinstaller() -> bool:
    if (
        getattr(
            sys,
            "frozen",
            False,
        )
        and platform.system() == "Windows"
    ):
        return True
    return False


def pyinstaller_update_path() -> None:
    path = pathlib.Path(__file__).parent / "lib"
    os.environ["PATH"] += os.pathsep + path.as_posix()


def pyinstaller_path_fix() -> None:
    if is_pyinstaller():
        pyinstaller_update_path()


def setup_logger(
    log_path: pathlib.Path = None, log_verbosity: str = logging.DEBUG, with_time=True, with_level=True
) -> logging.Logger:
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)

    print_handler = logging.StreamHandler(stream=sys.stdout)
    print_handler.setLevel(logging.DEBUG)
    log.addHandler(print_handler)

    if log_path:
        log_handler = logging.FileHandler(log_path, mode="a")

        if log_verbosity == "messages":
            log_handler.setLevel(logging.DEBUG)
        elif log_verbosity == "errors":
            log_handler.setLevel(logging.WARNING)
        else:
            log_handler.setLevel(logging.WARNING)

        format = "%(asctime)s -" if with_time else ""
        format += "%(levelname)s - %(message)s" if with_level else "%(message)s"
        log_handler.setFormatter(logging.Formatter(format))

        log.addHandler(log_handler)


def handle_error_and_exit(error: typing.Union[str, Exception]):
    logging.error(str(error))
    sys.exit(1)


def main():
    pyinstaller_path_fix()

    parser = argparse.ArgumentParser(
        prog="dbsync_deamon.py",
        description="Synchronization tool between Mergin Maps project and database.",
        epilog="www.merginmaps.com",
    )

    parser.add_argument(
        "config_file",
        nargs="?",
        default="config.yaml",
        help="Path to file with configuration. Default value is config.yaml in current working directory.",
    )
    parser.add_argument(
        "--skip-init",
        action="store_true",
        help="Skip DB sync init step to make the tool start faster. It is not recommend to use it unless you are really sure you can skip the initial sanity checks.",
    )
    parser.add_argument(
        "--single-run",
        action="store_true",
        help="Run just once performing single pull and push operation, instead of running in infinite loop.",
    )
    parser.add_argument(
        "--force-init",
        action="store_true",
        help="Force removing working directory and schemas from DB to initialize from scratch.",
    )
    parser.add_argument(
        "--log-file",
        default="",
        action="store",
        help="Store logging to file.",
    )
    parser.add_argument(
        "--log-verbosity",
        choices=[
            "errors",
            "messages",
        ],
        default="messages",
        help="Log messages, not only errors.",
    )

    args = parser.parse_args()

    if args.log_file:
        log_file = pathlib.Path(args.log_file)
        setup_logger(log_file, args.log_verbosity)
    else:
        setup_logger()

    logging.debug(f"== starting mergin-db-sync daemon == version {__version__} ==")

    try:
        update_config_path(args.config_file)
    except IOError as e:
        handle_error_and_exit(e)

    sleep_time = config.as_int("daemon.sleep_time")
    try:
        validate_config(config)
    except ConfigError as e:
        handle_error_and_exit(e)

    if args.force_init and args.skip_init:
        handle_error_and_exit("Cannot use `--force-init` with `--skip-init` Initialization is required. ")

    logging.debug("Logging in to Mergin...")

    mc = dbsync.create_mergin_client()

    if args.force_init:
        dbsync.dbsync_clean(mc)

    if args.single_run:
        if not args.skip_init:
            try:
                dbsync.dbsync_init(mc)
            except dbsync.DbSyncError as e:
                handle_error_and_exit(e)

        try:
            logging.debug("Trying to pull")
            dbsync.dbsync_pull(mc)

            logging.debug("Trying to push")
            dbsync.dbsync_push(mc)

        except dbsync.DbSyncError as e:
            handle_error_and_exit(e)

    else:
        if not args.skip_init:
            try:
                dbsync.dbsync_init(mc)
            except dbsync.DbSyncError as e:
                handle_error_and_exit(e)

        while True:
            print(datetime.datetime.now())

            try:
                logging.debug("Trying to pull")
                dbsync.dbsync_pull(mc)

                logging.debug("Trying to push")
                dbsync.dbsync_push(mc)

                # check mergin client token expiration
                delta = mc._auth_session["expire"] - datetime.datetime.now(datetime.timezone.utc)
                if delta.total_seconds() < 3600:
                    mc = dbsync.create_mergin_client()

            except dbsync.DbSyncError as e:
                handle_error_and_exit(e)

            logging.debug("Going to sleep")
            time.sleep(sleep_time)


if __name__ == "__main__":
    main()
