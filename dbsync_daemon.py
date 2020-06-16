
# keep running until killed by ctrl+c:
# - sleep N seconds
# - pull
# - push

import configparser
import time

import dbsync

filename = 'config.ini'

dbsync.load_config(filename)

# load daemon-specific bits
cfg = configparser.ConfigParser()
cfg.read(filename)
sleep_time = int(cfg['daemon']['sleep_time'])

while True:

    print("Trying to pull")
    dbsync.dbsync_pull()

    print("Trying to push")
    dbsync.dbsync_push()

    print("Going to sleep")
    time.sleep(sleep_time)
