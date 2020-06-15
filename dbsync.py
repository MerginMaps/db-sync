"""
Mergin DB Sync - a tool for two-way synchronization between Mergin and a PostGIS database

Copyright (C) 2020 Lutra Consulting

License: MIT
"""

import configparser
import json
import os
import shutil
import subprocess
import sys
import tempfile

import psycopg2

from mergin import MerginClient, MerginProject


config = configparser.ConfigParser()
config.read('config.ini')

project_working_dir = config['general']['working_dir']
geodiffinfo_exe = config['general']['geodiffinfo_exe']

mergin_url = 'https://public.cloudmergin.com'
mergin_project = config['mergin']['project']
mergin_username = config['mergin']['username']
mergin_password = config['mergin']['password']
mergin_sync_file = config['mergin']['sync_file']

db_driver = config['db']['driver']
db_conn_info = config['db']['conn_info']
db_schema_modified = config['db']['modified']   # where local editing happens
db_schema_base = config['db']['base']           # where only this script does changes

if db_driver != "postgres":
    raise ValueError("Only 'postgres' driver is currently supported")


def _check_schema_exists(conn, schema_name):
    cur = conn.cursor()
    cur.execute("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = %s)", (schema_name,))
    return cur.fetchone()[0]


def _geodiff_create_changeset(driver, conn_info, base, modified, changeset):
    subprocess.run(
        [geodiffinfo_exe, "createChangesetEx", driver, conn_info, base, modified, changeset],
        check=True, stderr=subprocess.PIPE)


def _geodiff_apply_changeset(driver, conn_info, base, changeset):
    subprocess.run(
        [geodiffinfo_exe, "applyChangesetEx", driver, conn_info, base, changeset],
        check=True, stderr=subprocess.PIPE)


def _geodiff_list_changes_summary(changeset):
    """ Returns a list with changeset summary:
     [ { 'table': 'foo', 'insert': 1, 'update': 2, 'delete': 3 }, ... ]
    """
    tmp_dir = tempfile.gettempdir()
    tmp_output = os.path.join(tmp_dir, 'dbsync-changeset-summary')
    if os.path.exists(tmp_output):
        os.remove(tmp_output)
    subprocess.run(
        [geodiffinfo_exe, "listChangesSummary", changeset, tmp_output],
        check=True, stderr=subprocess.PIPE)
    with open(tmp_output) as f:
        out = json.load(f)
    os.remove(tmp_output)
    return out["geodiff_summary"]


def _geodiff_make_copy(src_driver, src_conn_info, src, dst_driver, dst_conn_info, dst):
    subprocess.run(
        [geodiffinfo_exe, "makeCopy", src_driver, src_conn_info, src, dst_driver, dst_conn_info, dst],
        check=True, stderr=subprocess.PIPE)


def _print_changes_summary(summary):
    print("Changes:")
    for item in summary:
        print("{:20} {:4} {:4} {:4}".format(item['table'], item['insert'], item['update'], item['delete']))


def _get_project_version():
    """ Returns the current version of the project """
    mp = MerginProject(project_working_dir)
    return mp.metadata["version"]


def dbsync_pull():
    """ Downloads any changes from Mergin and applies them to the database """

    mc = MerginClient(mergin_url, login=mergin_username, password=mergin_password)

    status_pull, status_push, _ = mc.project_status(project_working_dir)
    if not status_pull['added'] and not status_pull['updated'] and not status_pull['removed']:
        print("No changes on Mergin.")
        return
    if status_push['added'] or status_push['updated'] or status_push['removed']:
        raise ValueError("There are pending changes in the local directory - that should never happen! " + str(status_push))

    gpkg_basefile = os.path.join(project_working_dir, '.mergin', mergin_sync_file)
    gpkg_basefile_old = gpkg_basefile + "-old"

    # make a copy of the basefile in the current version (base) - because after pull it will be set to "their"
    shutil.copy(gpkg_basefile, gpkg_basefile_old)

    tmp_dir = tempfile.gettempdir()
    tmp_base2our = os.path.join(tmp_dir, 'dbsync-pull-base2our')
    tmp_base2their = os.path.join(tmp_dir, 'dbsync-pull-base2their')

    # find out our local changes in the database (base2our)
    _geodiff_create_changeset(db_driver, db_conn_info, db_schema_base, db_schema_modified, tmp_base2our)

    if os.path.getsize(tmp_base2our) != 0:
        raise ValueError("Rebase not supported yet!")

    # TODO: when rebasing: apply local DB changes to gpkg  (base2our)

    mc.pull_project(project_working_dir)  # will do rebase as needed

    print("Pulled new version from Mergin: " + _get_project_version())

    # simple case when there are no pending local changes - just apply whatever changes are coming
    _geodiff_create_changeset("sqlite", "", gpkg_basefile_old, gpkg_basefile, tmp_base2their)

    # summarize changes
    summary = _geodiff_list_changes_summary(tmp_base2their)
    _print_changes_summary(summary)

    _geodiff_apply_changeset(db_driver, db_conn_info, db_schema_base, tmp_base2their)
    _geodiff_apply_changeset(db_driver, db_conn_info, db_schema_modified, tmp_base2their)

    # TODO: when rebasing:
    # - createChangesetEx - using gpkg (their2our)
    # - applyChangesetEx - using DB modified (inv base2our + base2their + their2our)
    # - applyChangesetEx - using DB base (base2their)

    os.remove(gpkg_basefile_old)


def dbsync_push():
    """ Take changes in the 'modified' schema in the database and push them to Mergin """

    tmp_dir = tempfile.gettempdir()
    tmp_changeset_file = os.path.join(tmp_dir, 'dbsync-push-base2our')

    gpkg_full_path = os.path.join(project_working_dir, mergin_sync_file)
    if not os.path.exists(gpkg_full_path):
        raise ValueError("The output GPKG file does not exist: " + gpkg_full_path)

    mc = MerginClient(mergin_url, login=mergin_username, password=mergin_password)

    # check there are no pending changes on server (or locally - which should never happen)
    status_pull, status_push, _ = mc.project_status(project_working_dir)
    if status_pull['added'] or status_pull['updated'] or status_pull['removed']:
        raise ValueError("There are pending changes on server - need to pull them first: " + str(status_pull))
    if status_push['added'] or status_push['updated'] or status_push['removed']:
        raise ValueError("There are pending changes in the local directory - that should never happen! " + str(status_push))

    conn = psycopg2.connect(db_conn_info)

    if not _check_schema_exists(conn, db_schema_base):
        raise ValueError("The base schema does not exist: " + db_schema_base)
    if not _check_schema_exists(conn, db_schema_modified):
        raise ValueError("The 'modified' schema does not exist: " + db_schema_modified)

    # get changes in the DB
    _geodiff_create_changeset(db_driver, db_conn_info, db_schema_base, db_schema_modified, tmp_changeset_file)

    if os.path.getsize(tmp_changeset_file) == 0:
        print("No changes in the database.")
        return

    # summarize changes
    summary = _geodiff_list_changes_summary(tmp_changeset_file)
    _print_changes_summary(summary)

    # write changes to the local geopackage
    _geodiff_apply_changeset("sqlite", "", gpkg_full_path, tmp_changeset_file)

    # write to the server
    mc.push_project(project_working_dir)

    print("Pushed new version to Mergin: " + _get_project_version())

    # update base schema in the DB
    _geodiff_apply_changeset(db_driver, db_conn_info, db_schema_base, tmp_changeset_file)


def dbsync_init():
    """ Initialize the dbsync so that it is possible to do two-way sync between Mergin and a database """

    if not os.path.exists(project_working_dir):
        raise ValueError("The project working directory does not exist: " + project_working_dir)

    if not os.path.exists(os.path.join(project_working_dir, '.mergin')):
        raise ValueError("The project working directory does not seem to contain Mergin project: " + project_working_dir)

    gpkg_full_path = os.path.join(project_working_dir, mergin_sync_file)
    if os.path.exists(gpkg_full_path):
        raise ValueError("The output GPKG file exists already: " + gpkg_full_path)

    mc = MerginClient(mergin_url, login=mergin_username, password=mergin_password)

    # check there are no pending changes on server (or locally - which should never happen)
    status_pull, status_push, _ = mc.project_status(project_working_dir)
    if status_pull['added'] or status_pull['updated'] or status_pull['removed']:
        raise ValueError("There are pending changes on server - need to pull them first: " + str(status_pull))
    if status_push['added'] or status_push['updated'] or status_push['removed']:
        raise ValueError("There are pending changes in the local directory - that should never happen! " + str(status_push))

    conn = psycopg2.connect(db_conn_info)

    if _check_schema_exists(conn, db_schema_base):
        raise ValueError("The base schema already exists: " + db_schema_base)

    if not _check_schema_exists(conn, db_schema_modified):
        raise ValueError("The 'modified' schema does not exist: " + db_schema_modified)

    # COPY: modified -> base
    _geodiff_make_copy(db_driver, db_conn_info, db_schema_modified,
                       db_driver, db_conn_info, db_schema_base)

    # COPY: modified -> gpkg
    _geodiff_make_copy(db_driver, db_conn_info, db_schema_modified,
                       "sqlite", "", gpkg_full_path)

    # upload gpkg to mergin (client takes care of storing metadata)
    mc.push_project(project_working_dir)


def show_usage():
    print("dbsync")
    print("")
    print("    dbsync init        = will create base schema in DB + create gpkg file in working copy")
    print("    dbsync push        = will push changes from DB to mergin")
    print("    dbsync pull        = will pull changes from mergin to DB")


def main():
    if len(sys.argv) < 2:
        show_usage()
        return

    if sys.argv[1] == 'init':
        dbsync_init()
    elif sys.argv[1] == 'push':
        dbsync_push()
    elif sys.argv[1] == 'pull':
        dbsync_pull()
    else:
        show_usage()


if __name__ == '__main__':
    main()
