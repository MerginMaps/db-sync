
# keep running until killed by ctrl+c:
# - sleep N seconds
# - pull
# - push

import datetime
import sys
import time

import dbsync
from version import __version__
from config import config, validate_config, ConfigError


def main():
    print(f"== starting mergin-db-sync daemon == version {__version__} ==")

    sleep_time = config.as_int("daemon.sleep_time")
    try:
        validate_config(config)
    except ConfigError as e:
        print("Error: " + str(e))
        return

    print("Logging in to Mergin...")
    mc = dbsync.create_mergin_client()

    # run initialization before starting the sync loop
    dbsync.dbsync_init(mc)

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
            print("Error: " + str(e))

        print("Going to sleep")
        time.sleep(sleep_time)


if __name__ == '__main__':
    main()
