
# keep running until killed by ctrl+c:
# - sleep N seconds
# - pull
# - push

import datetime
import sys
import time
import argparse

import dbsync
from version import __version__
from config import config, validate_config, ConfigError, update_config_path


def main():

    parser = argparse.ArgumentParser(prog='dbsync_deamon.py',
                                     description='Synchronization tool between Mergin Maps project and database.',
                                     epilog='www.merginmaps.com')

    parser.add_argument("config_file", nargs="?", default="config.yaml", help="Path to file with configuration. Default value is config.yaml in current working directory.")
    parser.add_argument("--skip-init", action="store_true", help="Skip DB sync init step to make the tool start faster. It is not recommend to use it unless you are really sure you can skip the initial sanity checks.")
    parser.add_argument("--single-run", action="store_true", help="Run just once performing single pull and push operation, instead of running in infinite loop.")
    parser.add_argument("--force", action="store_true", help="Force removing working directory and schemas from DB to initialize from scratch.")

    args = parser.parse_args()

    print(f"== starting mergin-db-sync daemon == version {__version__} ==")

    try:
        update_config_path(args.config_file)
    except IOError as e:
        print("Error: " + str(e), file=sys.stderr)
        sys.exit(1)

    sleep_time = config.as_int("daemon.sleep_time")
    try:
        validate_config(config)
    except ConfigError as e:
        print("Error: " + str(e), file=sys.stderr)
        sys.exit(1)

    print("Logging in to Mergin...")
    mc = dbsync.create_mergin_client()

    if args.force:
        dbsync.dbsync_clean(mc)
        dbsync.dbsync_init(mc)

    if args.single_run:

        if not args.skip_init:
            try:
                dbsync.dbsync_init(mc)
            except dbsync.DbSyncError as e:
                print("Error: " + str(e), file=sys.stderr)
                sys.exit(1)

        try:
            print("Trying to pull")
            dbsync.dbsync_pull(mc)

            print("Trying to push")
            dbsync.dbsync_push(mc)
        except dbsync.DbSyncError as e:
            print("Error: " + str(e), file=sys.stderr)
            sys.exit(1)

    else:

        if not args.skip_init:
            try:
                dbsync.dbsync_init(mc)
            except dbsync.DbSyncError as e:
                print("Error: " + str(e), file=sys.stderr)
                sys.exit(1)

        while True:

            print(datetime.datetime.now())

            try:
                print("Trying to pull")
                dbsync.dbsync_pull(mc)

                print("Trying to push")
                dbsync.dbsync_push(mc)

                # check mergin client token expiration
                delta = mc._auth_session['expire'] - datetime.datetime.now(datetime.timezone.utc)
                if delta.total_seconds() < 3600:
                    mc = dbsync.create_mergin_client()

            except dbsync.DbSyncError as e:
                print("Error: " + str(e), file=sys.stderr)

            print("Going to sleep")
            time.sleep(sleep_time)


if __name__ == '__main__':
    main()
