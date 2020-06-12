
# keep running until killed by ctrl+c:
# - sleep N seconds
# - pull
# - push

import time

import dbsync

sleep_time = dbsync.config['daemon']['sleep_time']

while True:

    print("Trying to pull")
    dbsync.dbsync_pull()

    print("Trying to push")
    dbsync.dbsync_push()

    print("Going to sleep")
    time.sleep(sleep_time)
