
# keep running until killed by ctrl+c:
# - sleep N seconds
# - pull
# - push

import configparser
import datetime
import sys
import time

import dbsync


def main():

    filename = 'config.ini'
    dbsync.load_config(filename)

    # load daemon-specific bits
    cfg = configparser.ConfigParser()
    cfg.read(filename)
    sleep_time = int(cfg['daemon']['sleep_time'])

    if len(sys.argv) == 2:
        # optionally we can run initialization before starting the sync loop
        cmd = sys.argv[1]
        if cmd == '--init-from-gpkg':
            dbsync.dbsync_init(from_gpkg=True)
        elif cmd == '--init-from-db':
            dbsync.dbsync_init(from_gpkg=False)
        else:
            raise ValueError("Unknown command line option: " + cmd)

    while True:

        print(datetime.datetime.now())

        try:
            print("Trying to pull")
            dbsync.dbsync_pull()

            print("Trying to push")
            dbsync.dbsync_push()

        except dbsync.DbSyncError as e:
            print("Error: " + str(e))

        print("Going to sleep")
        time.sleep(sleep_time)


if __name__ == '__main__':
    main()
