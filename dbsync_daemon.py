# keep running until killed by ctrl+c:
# - sleep N seconds
# - pull
# - push

import argparse
import datetime
import logging
import os
import pathlib
import platform
import pprint
import sys
import time

import dbsync
from config import ConfigError, config, update_config_path, validate_config
from log_functions import handle_error_and_exit, setup_logger
from smtp_functions import send_email
from version import __version__

# upper limit (in seconds) of the wait time between retries after repeated failures
MAX_RETRY_WAIT = 600
# default number of consecutive failed retries of startup (login / init) or unexpected errors before the daemon exits
DEFAULT_MAX_RETRIES = 10


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
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "FATAL",
            "CRITICAL",
        ],
        default="DEBUG",
        help="Set level of logging into log-file.",
    )
    parser.add_argument(
        "--test-notification-email",
        action="store_true",
        help="Send test notification email using the `notification` settings. Should be used to validate settings.",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show runtime config, useful when using env vars in config file.",
    )

    args = parser.parse_args()

    if args.log_file:
        log_file = pathlib.Path(args.log_file)
        setup_logger(log_file, args.log_verbosity)
    else:
        setup_logger()

    try:
        update_config_path(args.config_file)
    except IOError as e:
        handle_error_and_exit(e)

    if args.show_config:
        pprint.pprint(config.as_dict())
        sys.exit(0)

    logging.debug(f"== starting mergin-db-sync daemon == version {__version__} ==")

    sleep_time = config.as_int("daemon.sleep_time")
    try:
        validate_config(config)
    except ConfigError as e:
        handle_error_and_exit(e)
    max_retries = config.get("daemon.max_retries", DEFAULT_MAX_RETRIES)

    send_notifications = "notification" in config

    if not send_notifications:
        logging.debug(
            "Email notifications for sync failures are not set up. It is recommended to use them. Please see documentation."
        )

    if args.test_notification_email:
        if not send_notifications:
            logging.debug("Unable to send test email because notifications are not configured!")
            sys.exit(1)
        send_email("Mergin DB Sync test email.", config)
        sys.exit(0)

    if args.force_init and args.skip_init:
        handle_error_and_exit("Cannot use `--force-init` with `--skip-init` Initialization is required. ")

    if args.single_run:
        try:
            logging.debug("Logging in to Mergin...")
            mc = dbsync.create_mergin_client()

            if args.force_init:
                dbsync.dbsync_clean(mc)

            if not args.skip_init:
                dbsync.dbsync_init(mc)

            logging.debug("Trying to pull")
            dbsync.dbsync_pull(mc)

            logging.debug("Trying to push")
            dbsync.dbsync_push(mc)

        except dbsync.DbSyncError as e:
            handle_error_and_exit(e)

    else:
        run_daemon(args, sleep_time, max_retries, send_notifications)


def retry_wait_time(sleep_time: int, failures: int) -> int:
    """Seconds to wait before the next attempt after `failures` consecutive failed attempts.

    Doubles with each failure up to MAX_RETRY_WAIT, but never less than sleep_time."""
    wait_time = sleep_time * 2 ** (failures - 1)
    return min(wait_time, max(sleep_time, MAX_RETRY_WAIT))


def run_daemon(args, sleep_time: int, max_retries: int, send_notifications: bool) -> None:
    """Keep syncing until killed. Failures (including login and init) are retried within
    this process with exponential backoff instead of exiting, so the daemon does not
    log in again on every restart by the container / service manager.

    Sync errors after a successful start are retried indefinitely. Startup failures (login, clean, init)
    and unexpected errors make the daemon exit after `max_retries` consecutive failed retries (0 = never exit)."""
    mc = None
    cleaned = not args.force_init
    initialized = args.skip_init
    started = False
    failures = 0
    fatal_failures = 0
    last_email_sent = None

    while True:
        print(datetime.datetime.now())

        try:
            if mc is None:
                logging.debug("Logging in to Mergin...")
                mc = dbsync.create_mergin_client()

            if not cleaned:
                dbsync.dbsync_clean(mc)
                cleaned = True

            if not initialized:
                dbsync.dbsync_init(mc)
                initialized = True

            logging.debug("Trying to pull")
            dbsync.dbsync_pull(mc)

            logging.debug("Trying to push")
            dbsync.dbsync_push(mc)
            started = True

            # check mergin client token expiration
            if dbsync.auth_token_expires_soon(mc):
                mc = dbsync.create_mergin_client()

            failures = 0
            fatal_failures = 0

        except Exception as e:
            failures += 1
            if not started or not isinstance(e, dbsync.DbSyncError):
                fatal_failures += 1
            if isinstance(e, dbsync.DbSyncError):
                error_msg = str(e)
                logging.error(error_msg)
            else:
                error_msg = f"Unexpected error: {e!r}"
                logging.exception(error_msg)

            giving_up = max_retries and fatal_failures > max_retries
            if giving_up:
                error_msg = f"Giving up after {max_retries} retries, the daemon will exit: {error_msg}"

            if send_notifications:
                if "minimal_email_interval" in config.notification:
                    min_time_delta_hr = config.notification.minimal_email_interval
                else:
                    min_time_delta_hr = 4

                if (
                    giving_up
                    or last_email_sent is None
                    or (datetime.datetime.now() - last_email_sent).total_seconds() > min_time_delta_hr * 3600
                ):
                    send_email(error_msg, config)
                    last_email_sent = datetime.datetime.now()

            if giving_up:
                handle_error_and_exit(error_msg)

        if failures:
            wait_time = retry_wait_time(sleep_time, failures)
            logging.debug(f"Failed attempt #{failures}, going to sleep for {wait_time} seconds before retrying")
        else:
            wait_time = sleep_time
            logging.debug("Going to sleep")
        time.sleep(wait_time)


if __name__ == "__main__":
    main()
