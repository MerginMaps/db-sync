
# keep running until killed by ctrl+c:
# - sleep N seconds
# - pull
# - push

import configparser
import datetime
import sys
import time

import dbsync
from version import __version__


def main():

    print(f"== starting mergin-db-sync daemon == version {__version__} ==")

    filename = 'config.ini'
    dbsync.load_config(filename)

    # load daemon-specific bits
    cfg = configparser.ConfigParser()
    cfg.read(filename)
    sleep_time = int(cfg['daemon']['sleep_time'])

    print("Logging in to Mergin...")
    mc = dbsync.create_mergin_client()

    if len(sys.argv) == 2:
        # optionally we can run initialization before starting the sync loop
        cmd = sys.argv[1]
        if cmd == '--init-from-gpkg':
            dbsync.dbsync_init(mc, from_gpkg=True)
        elif cmd == '--init-from-db':
            dbsync.dbsync_init(mc, from_gpkg=False)
        else:
            raise ValueError("Unknown command line option: " + cmd)

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
