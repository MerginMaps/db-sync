import select
import psycopg2
import psycopg2.extensions

DSN=""

conn = psycopg2.connect(DSN)
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

curs = conn.cursor()
curs.execute("LISTEN geodiff;")

print("Waiting for notifications on channel 'geodiff'")


import dbsync

sleep_time = dbsync.config['daemon']['sleep_time']


while True:
    if select.select([conn],[],[],5) == ([],[],[]):
        print("Timeout")

        print("Trying to pull")
        dbsync.dbsync_pull()

    else:
        conn.poll()
        while conn.notifies:
            notify = conn.notifies.pop(0)
            print("Got NOTIFY:", notify.pid, notify.channel, notify.payload)

        # new stuff in the database - let's push a new version

        # how about if the transaction is not committed yet?
        # Docs: "if a NOTIFY is executed inside a transaction, the notify events
        # are not delivered until and unless the transaction is committed"

        # TODO: need to wait before the changes are accessible?

        print("Trying to push")
        dbsync.dbsync_push()



# TODO: create on init
# CREATE RULE geodiff_rule_update_simple AS ON UPDATE TO gd_sync_base.simple DO ALSO NOTIFY geodiff;
# CREATE RULE geodiff_rule_insert_simple AS ON INSERT TO gd_sync_base.simple DO ALSO NOTIFY geodiff;
# CREATE RULE geodiff_rule_delete_simple AS ON DELETE TO gd_sync_base.simple DO ALSO NOTIFY geodiff;
