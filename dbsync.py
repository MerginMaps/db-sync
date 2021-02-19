"""
Mergin DB Sync - a tool for two-way synchronization between Mergin and a PostGIS database

Copyright (C) 2020 Lutra Consulting

License: MIT
"""

import configparser
import getpass
import json
import os
import shutil
import string
import subprocess
import sys
import tempfile
import random

import psycopg2

from mergin import MerginClient, MerginProject, LoginError, ClientError
from version import __version__


# set high logging level for geodiff (used by geodiffinfo executable)
# so we get as much information as possible
os.environ["GEODIFF_LOGGER_LEVEL"] = '4'   # 0 = nothing, 1 = errors, 2 = warning, 3 = info, 4 = debug


class DbSyncError(Exception):
    pass


class Config:
    """ Contains configuration of the sync """

    def __init__(self):
        self.project_working_dir = None
        self.geodiffinfo_exe = None

        self.mergin_url = 'https://public.cloudmergin.com'

        self.mergin_username = None
        self.mergin_password = None
        self.mergin_project_name = None
        self.mergin_sync_file = None

        self.db_driver = None
        self.db_conn_info = None
        self.db_schema_modified = None
        self.db_schema_base = None

        if 'MERGIN_URL' in os.environ:
            self.mergin_url = os.environ['MERGIN_URL']
        if 'MERGIN_USERNAME' in os.environ:
            self.mergin_username = os.environ['MERGIN_USERNAME']
        if 'MERGIN_PASSWORD' in os.environ:
            self.mergin_password = os.environ['MERGIN_PASSWORD']
        if 'MERGIN_PROJECT_NAME' in os.environ:
            self.mergin_project_name = os.environ['MERGIN_PROJECT_NAME']
        if 'MERGIN_SYNC_FILE' in os.environ:
            self.mergin_sync_file = os.environ['MERGIN_SYNC_FILE']

        if 'DB_DRIVER' in os.environ:
            self.db_driver = os.environ['DB_DRIVER']
        if 'DB_CONN_INFO' in os.environ:
            self.db_conn_info = os.environ['DB_CONN_INFO']
        if 'DB_SCHEMA_MODIFIED' in os.environ:
            self.db_schema_modified = os.environ['DB_SCHEMA_MODIFIED']
        if 'DB_SCHEMA_BASE' in os.environ:
            self.db_schema_base = os.environ['DB_SCHEMA_BASE']

    def load(self, filename):
        cfg = configparser.ConfigParser()
        cfg.read(filename)

        self.project_working_dir = cfg['general']['working_dir']
        self.geodiffinfo_exe = cfg['general']['geodiffinfo_exe']

        if 'mergin' in cfg:
            cfg_mergin = cfg['mergin']
            if 'url' in cfg_mergin:
                self.mergin_url = cfg_mergin['url']
            if 'username' in cfg_mergin:
                self.mergin_username = cfg_mergin['username']
            if 'password' in cfg_mergin:
                # password can be optionally stored in config.ini, but it is not recommended
                self.mergin_password = cfg_mergin['password']
            if 'project_name' in cfg_mergin:
                self.mergin_project_name = cfg_mergin['project_name']
            if 'sync_file' in cfg_mergin:
                self.mergin_sync_file = cfg_mergin['sync_file']

        if 'db' in cfg:
            cfg_db = cfg['db']
            if 'driver' in cfg_db:
                self.db_driver = cfg_db['driver']
            if 'conn_info' in cfg_db:
                self.db_conn_info = cfg_db['conn_info']
            if 'modified' in cfg_db:
                self.db_schema_modified = cfg_db['modified']   # where local editing happens
            if 'base' in cfg_db:
                self.db_schema_base = cfg_db['base']           # where only this script does changes


config = Config()


def _check_config():
    """ Makes sure that the configuration is valid, raises exceptions if not """
    if config.db_driver != "postgres":
        raise DbSyncError("Only 'postgres' driver is currently supported")


def _check_has_working_dir():
    if not os.path.exists(config.project_working_dir):
        raise DbSyncError("The project working directory does not exist: " + config.project_working_dir)

    if not os.path.exists(os.path.join(config.project_working_dir, '.mergin')):
        raise DbSyncError("The project working directory does not seem to contain Mergin project: " + config.project_working_dir)


def _check_has_sync_file():
    """ Checks whether the dbsync environment is initialized already (so that we can pull/push).
     Emits an exception if not initialized yet. """

    gpkg_full_path = os.path.join(config.project_working_dir, config.mergin_sync_file)
    if not os.path.exists(gpkg_full_path):
        raise DbSyncError("The output GPKG file does not exist: " + gpkg_full_path)


def _check_schema_exists(conn, schema_name):
    cur = conn.cursor()
    cur.execute("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = %s)", (schema_name,))
    return cur.fetchone()[0]


def _check_has_password():
    """ Checks whether we have password for Mergin user - if not, we will ask for it """
    if config.mergin_password is None:
        config.mergin_password = getpass.getpass(prompt="Mergin password for '{}': ".format(config.mergin_username))


def _run_geodiff(cmd):
    """ will run a command (with geodiffinfo) and report what got to stderr and raise exception
    if the command returns non-zero exit code """
    res = subprocess.run(cmd, stderr=subprocess.PIPE)
    geodiff_stderr = res.stderr.decode()
    if geodiff_stderr:
        print("GEODIFF: " + geodiff_stderr)
    if res.returncode != 0:
        raise DbSyncError("geodiffinfo failed!\n" + str(cmd))


def _geodiff_create_changeset(driver, conn_info, base, modified, changeset):
    _run_geodiff([config.geodiffinfo_exe, "createChangesetEx", driver, conn_info, base, modified, changeset])


def _geodiff_apply_changeset(driver, conn_info, base, changeset):
    _run_geodiff([config.geodiffinfo_exe, "applyChangesetEx", driver, conn_info, base, changeset])


def _geodiff_rebase(driver, conn_info, base, modified, base2their, conflicts):
    _run_geodiff([config.geodiffinfo_exe, "rebaseEx", driver, conn_info, base, modified, base2their, conflicts])


def _geodiff_list_changes_summary(changeset):
    """ Returns a list with changeset summary:
     [ { 'table': 'foo', 'insert': 1, 'update': 2, 'delete': 3 }, ... ]
    """
    tmp_dir = tempfile.gettempdir()
    tmp_output = os.path.join(tmp_dir, 'dbsync-changeset-summary')
    if os.path.exists(tmp_output):
        os.remove(tmp_output)
    _run_geodiff([config.geodiffinfo_exe, "listChangesSummary", changeset, tmp_output])
    with open(tmp_output) as f:
        out = json.load(f)
    os.remove(tmp_output)
    return out["geodiff_summary"]


def _geodiff_make_copy(src_driver, src_conn_info, src, dst_driver, dst_conn_info, dst):
    _run_geodiff([config.geodiffinfo_exe, "makeCopy", src_driver, src_conn_info, src, dst_driver, dst_conn_info, dst])


def _geodiff_create_changeset_dr(src_driver, src_conn_info, src, dst_driver, dst_conn_info, dst, changeset):
    _run_geodiff([config.geodiffinfo_exe, "createChangesetDr", src_driver, src_conn_info, src, dst_driver, dst_conn_info, dst, changeset])


def _compare_datasets(src_driver, src_conn_info, src, dst_driver, dst_conn_info, dst):
    """ Compare content of two datasets (from various drivers) and return geodiff JSON summary of changes """
    tmp_dir = tempfile.gettempdir()
    tmp_changeset = os.path.join(tmp_dir, ''.join(random.choices(string.ascii_letters, k=8)))

    _geodiff_create_changeset_dr(src_driver, src_conn_info, src, dst_driver, dst_conn_info, dst, tmp_changeset)
    summary = _geodiff_list_changes_summary(tmp_changeset)
    return summary


def _print_changes_summary(summary, label=None):
    """ Takes a geodiff JSON summary of changes and prints them """
    print("Changes:" if label is None else label)
    for item in summary:
        print("{:20} {:4} {:4} {:4}".format(item['table'], item['insert'], item['update'], item['delete']))


def _print_mergin_changes(diff_dict):
    """ Takes a dictionary with format { 'added': [...], 'removed': [...], 'updated': [...] }
    where each item is another dictionary with file details, e.g.:
      { 'path': 'myfile.gpkg', size: 123456, ... }
    and prints it in a way that's easy to parse for a human :-)
    """
    for item in diff_dict['added']:
        print("  added:   " + item['path'])
    for item in diff_dict['updated']:
        print("  updated: " + item['path'])
    for item in diff_dict['removed']:
        print("  removed: " + item['path'])


def _get_project_version():
    """ Returns the current version of the project """
    mp = MerginProject(config.project_working_dir)
    return mp.metadata["version"]


def create_mergin_client():
    """ Create instance of MerginClient"""
    _check_has_password()
    try:
        return MerginClient(config.mergin_url, login=config.mergin_username, password=config.mergin_password, plugin_version=f"DB-sync {__version__}")
    except LoginError as e:
        # this could be auth failure, but could be also server problem (e.g. worker crash)
        raise DbSyncError(f"Unable to log in to Mergin: {str(e)} \n\n" +
                          "Have you specified correct credentials in configuration file?")
    except ClientError as e:
        # this could be e.g. DNS error
        raise DbSyncError("Mergin client error: " + str(e))


def dbsync_pull(mc):
    """ Downloads any changes from Mergin and applies them to the database """

    _check_has_working_dir()
    _check_has_sync_file()

    try:
        status_pull, status_push, _ = mc.project_status(config.project_working_dir)
    except ClientError as e:
        # this could be e.g. DNS error
        raise DbSyncError("Mergin client error: " + str(e))

    if not status_pull['added'] and not status_pull['updated'] and not status_pull['removed']:
        print("No changes on Mergin.")
        return
    if status_push['added'] or status_push['updated'] or status_push['removed']:
        raise DbSyncError("There are pending changes in the local directory - that should never happen! " + str(status_push))

    gpkg_basefile = os.path.join(config.project_working_dir, '.mergin', config.mergin_sync_file)
    gpkg_basefile_old = gpkg_basefile + "-old"

    # make a copy of the basefile in the current version (base) - because after pull it will be set to "their"
    shutil.copy(gpkg_basefile, gpkg_basefile_old)

    tmp_dir = tempfile.gettempdir()
    tmp_base2our = os.path.join(tmp_dir, 'dbsync-pull-base2our')
    tmp_base2their = os.path.join(tmp_dir, 'dbsync-pull-base2their')

    # find out our local changes in the database (base2our)
    _geodiff_create_changeset(config.db_driver, config.db_conn_info, config.db_schema_base, config.db_schema_modified, tmp_base2our)

    needs_rebase = False
    if os.path.getsize(tmp_base2our) != 0:
        needs_rebase = True
        summary = _geodiff_list_changes_summary(tmp_base2our)
        _print_changes_summary(summary, "DB Changes:")

    try:
        mc.pull_project(config.project_working_dir)  # will do rebase as needed
    except ClientError as e:
        # TODO: do we need some cleanup here?
        raise DbSyncError("Mergin client error on pull: " + str(e))

    print("Pulled new version from Mergin: " + _get_project_version())

    # simple case when there are no pending local changes - just apply whatever changes are coming
    _geodiff_create_changeset("sqlite", "", gpkg_basefile_old, gpkg_basefile, tmp_base2their)

    # summarize changes
    summary = _geodiff_list_changes_summary(tmp_base2their)
    _print_changes_summary(summary, "Mergin Changes:")

    if not needs_rebase:
        print("Applying new version [no rebase]")
        _geodiff_apply_changeset(config.db_driver, config.db_conn_info, config.db_schema_base, tmp_base2their)
        _geodiff_apply_changeset(config.db_driver, config.db_conn_info, config.db_schema_modified, tmp_base2their)
    else:
        print("Applying new version [WITH rebase]")
        tmp_conflicts = os.path.join(tmp_dir, 'dbsync-pull-conflicts')
        _geodiff_rebase(config.db_driver, config.db_conn_info, config.db_schema_base,
                        config.db_schema_modified, tmp_base2their, tmp_conflicts)
        _geodiff_apply_changeset(config.db_driver, config.db_conn_info, config.db_schema_base, tmp_base2their)

    os.remove(gpkg_basefile_old)

    print("Pull done!")


def dbsync_status(mc):
    """ Figure out if there are any pending changes in the database or in Mergin """

    _check_has_working_dir()
    _check_has_sync_file()

    # get basic information
    mp = MerginProject(config.project_working_dir)
    if mp.geodiff is None:
        raise DbSyncError("Mergin client installation problem: geodiff not available")
    status_push = mp.get_push_changes()
    if status_push['added'] or status_push['updated'] or status_push['removed']:
        raise DbSyncError("Pending changes in the local directory - that should never happen! " + str(status_push))

    project_path = mp.metadata["name"]
    local_version = mp.metadata["version"]
    print("Working directory " + config.project_working_dir)
    print("Mergin project " + project_path + " at local version " + local_version)
    print("")
    print("Checking status...")

    # check if there are any pending changes on server
    try:
        server_info = mc.project_info(project_path, since=local_version)
    except ClientError as e:
        raise DbSyncError("Mergin client error: " + str(e))

    print("Server is at version " + server_info["version"])

    status_pull = mp.get_pull_changes(server_info["files"])
    if status_pull['added'] or status_pull['updated'] or status_pull['removed']:
        print("There are pending changes on server:")
        _print_mergin_changes(status_pull)
    else:
        print("No pending changes on server.")

    print("")
    conn = psycopg2.connect(config.db_conn_info)

    if not _check_schema_exists(conn, config.db_schema_base):
        raise DbSyncError("The base schema does not exist: " + config.db_schema_base)
    if not _check_schema_exists(conn, config.db_schema_modified):
        raise DbSyncError("The 'modified' schema does not exist: " + config.db_schema_modified)

    # get changes in the DB
    tmp_dir = tempfile.gettempdir()
    tmp_changeset_file = os.path.join(tmp_dir, 'dbsync-status-base2our')
    if os.path.exists(tmp_changeset_file):
        os.remove(tmp_changeset_file)
    _geodiff_create_changeset(config.db_driver, config.db_conn_info, config.db_schema_base, config.db_schema_modified, tmp_changeset_file)

    if os.path.getsize(tmp_changeset_file) == 0:
        print("No changes in the database.")
    else:
        print("There are changes in DB")
        # summarize changes
        summary = _geodiff_list_changes_summary(tmp_changeset_file)
        _print_changes_summary(summary)


def dbsync_push(mc):
    """ Take changes in the 'modified' schema in the database and push them to Mergin """

    tmp_dir = tempfile.gettempdir()
    tmp_changeset_file = os.path.join(tmp_dir, 'dbsync-push-base2our')
    if os.path.exists(tmp_changeset_file):
        os.remove(tmp_changeset_file)

    _check_has_working_dir()
    _check_has_sync_file()

    try:
        status_pull, status_push, _ = mc.project_status(config.project_working_dir)
    except ClientError as e:
        raise DbSyncError("Mergin client error: " + str(e))

    # check there are no pending changes on server (or locally - which should never happen)
    if status_pull['added'] or status_pull['updated'] or status_pull['removed']:
        raise DbSyncError("There are pending changes on server - need to pull them first: " + str(status_pull))
    if status_push['added'] or status_push['updated'] or status_push['removed']:
        raise DbSyncError("There are pending changes in the local directory - that should never happen! " + str(status_push))

    conn = psycopg2.connect(config.db_conn_info)

    if not _check_schema_exists(conn, config.db_schema_base):
        raise DbSyncError("The base schema does not exist: " + config.db_schema_base)
    if not _check_schema_exists(conn, config.db_schema_modified):
        raise DbSyncError("The 'modified' schema does not exist: " + config.db_schema_modified)

    # get changes in the DB
    _geodiff_create_changeset(config.db_driver, config.db_conn_info, config.db_schema_base, config.db_schema_modified, tmp_changeset_file)

    if os.path.getsize(tmp_changeset_file) == 0:
        print("No changes in the database.")
        return

    # summarize changes
    summary = _geodiff_list_changes_summary(tmp_changeset_file)
    _print_changes_summary(summary)

    # write changes to the local geopackage
    print("Writing DB changes to working dir...")
    gpkg_full_path = os.path.join(config.project_working_dir, config.mergin_sync_file)
    _geodiff_apply_changeset("sqlite", "", gpkg_full_path, tmp_changeset_file)

    # write to the server
    try:
        mc.push_project(config.project_working_dir)
    except ClientError as e:
        # TODO: should we do some cleanup here? (undo changes in the local geopackage?)
        raise DbSyncError("Mergin client error on push: " + str(e))

    print("Pushed new version to Mergin: " + _get_project_version())

    # update base schema in the DB
    print("Updating DB base schema...")
    _geodiff_apply_changeset(config.db_driver, config.db_conn_info, config.db_schema_base, tmp_changeset_file)

    print("Push done!")


def dbsync_init(mc, from_gpkg=True):
    """ Initialize the dbsync so that it is possible to do two-way sync between Mergin and a database """

    # let's start with various environment checks to make sure
    # the environment is set up correctly before doing any work
    gpkg_full_path = os.path.join(config.project_working_dir, config.mergin_sync_file)
    if not os.path.exists(config.project_working_dir):
        # download the Mergin project
        print("Download Mergin project " + config.mergin_project_name + " to " + config.project_working_dir)
        mc.download_project(config.mergin_project_name, config.project_working_dir)
        # make sure we have working directory now
        _check_has_working_dir()

    print("Connecting to the database...")
    try:
        conn = psycopg2.connect(config.db_conn_info)
    except psycopg2.Error as e:
        raise DbSyncError("Unable to connect to the database: " + str(e))

    # check there are no pending changes on server (or locally - which should never happen)
    status_pull, status_push, _ = mc.project_status(config.project_working_dir)
    if status_pull['added'] or status_pull['updated'] or status_pull['removed']:
        raise DbSyncError("There are pending changes on server - need to pull them first: " + str(status_pull))
    if status_push['added'] or status_push['updated'] or status_push['removed']:
        raise DbSyncError("There are pending changes in the local directory - that should never happen! " + str(status_push))

    base_schema_exists = _check_schema_exists(conn, config.db_schema_base)
    modified_schema_exists = _check_schema_exists(conn, config.db_schema_modified)
    if from_gpkg:
        if not os.path.exists(gpkg_full_path):
            raise DbSyncError("The input GPKG file does not exist: " + gpkg_full_path)

        if modified_schema_exists and base_schema_exists:
            # if db schema already exists make sure it is already synchronized with source gpkg or fail
            summary_modified = _compare_datasets("sqlite", "", gpkg_full_path, config.db_driver,
                                                 config.db_conn_info, config.db_schema_modified)
            summary_base = _compare_datasets("sqlite", "", gpkg_full_path, config.db_driver,
                                             config.db_conn_info, config.db_schema_base)
            if len(summary_modified) or len(summary_base):
                raise DbSyncError("The db schemas already exist but they are not synchronized with source GPKG")
            else:
                print("The GPKG file, base and modified schemas are already initialized and in sync")
                return  # nothing to do
        elif modified_schema_exists:
            raise DbSyncError(f"The 'modified' schema exists but the base schema is missing: {config.db_schema_base}")
        elif base_schema_exists:
            raise DbSyncError(f"The base schema exists but the modified schema is missing: {config.db_schema_modified}")

        # initialize: we have an existing GeoPackage in our Mergin project and we want to initialize database
        print("The base and modified schemas do not exist yet, going to initialize them ...")
        # COPY: gpkg -> modified
        _geodiff_make_copy("sqlite", "", gpkg_full_path,
                           config.db_driver, config.db_conn_info, config.db_schema_modified)

        # COPY: modified -> base
        _geodiff_make_copy(config.db_driver, config.db_conn_info, config.db_schema_modified,
                           config.db_driver, config.db_conn_info, config.db_schema_base)
    else:
        if not modified_schema_exists:
            raise DbSyncError("The 'modified' schema does not exist: " + config.db_schema_modified)

        if os.path.exists(gpkg_full_path) and base_schema_exists:
            # make sure output gpkg is in sync with db or fail
            summary_modified = _compare_datasets(config.db_conn_info, config.db_schema_modified,
                                                "sqlite", "", gpkg_full_path, config.db_driver)
            summary_base = _compare_datasets(config.db_conn_info, config.db_schema_base,
                                            "sqlite", "", gpkg_full_path, config.db_driver)
            if len(summary_modified) or len(summary_base):
                raise DbSyncError("The output GPKG file exists already but it is not synchronized with db schemas")
            else:
                print("The GPKG file, base and modified schemas are already initialized and in sync")
                return  # nothing to do
        elif os.path.exists(gpkg_full_path):
            raise DbSyncError(f"The output GPKG exists but the base schema is missing: {config.db_schema_base}")
        elif base_schema_exists:
            raise DbSyncError(f"The base schema exists but the output GPKG exists is missing: {gpkg_full_path}")

        # initialize: we have an existing schema in database with tables and we want to initialize geopackage
        # within our Mergin project
        print("The base schema and the output GPKG do not exist yet, going to initialize them ...")
        # COPY: modified -> base
        _geodiff_make_copy(config.db_driver, config.db_conn_info, config.db_schema_modified,
                           config.db_driver, config.db_conn_info, config.db_schema_base)

        # COPY: modified -> gpkg
        _geodiff_make_copy(config.db_driver, config.db_conn_info, config.db_schema_modified,
                           "sqlite", "", gpkg_full_path)

        # upload gpkg to mergin (client takes care of storing metadata)
        mc.push_project(config.project_working_dir)


def show_usage():
    print("dbsync")
    print("")
    print("    dbsync init-from-db   = will create base schema in DB + create gpkg file in working copy")
    print("    dbsync init-from-gpkg = will create base and main schema in DB from gpkg file in working copy")
    print("    dbsync status      = will check whether there is anything to pull or push")
    print("    dbsync push        = will push changes from DB to mergin")
    print("    dbsync pull        = will pull changes from mergin to DB")


def load_config(config_filename):
    if not os.path.exists(config_filename):
        raise DbSyncError("The configuration file does not exist: " + config_filename)
    config.load(config_filename)
    _check_config()


def main():
    if len(sys.argv) < 2:
        show_usage()
        return

    config_filename = 'config.ini'

    try:
        load_config(config_filename)
        print("Logging in to Mergin...")
        mc = create_mergin_client()

        if sys.argv[1] == 'init-from-gpkg':
            print("Initializing from an existing GeoPackage...")
            dbsync_init(mc, True)
        elif sys.argv[1] == 'init-from-db':
            print("Initializing from an existing DB schema...")
            dbsync_init(mc, False)
        elif sys.argv[1] == 'status':
            dbsync_status(mc)
        elif sys.argv[1] == 'push':
            print("Pushing...")
            dbsync_push(mc)
        elif sys.argv[1] == 'pull':
            print("Pulling...")
            dbsync_pull(mc)
        else:
            show_usage()
    except DbSyncError as e:
        print("Error: " + str(e))


if __name__ == '__main__':
    main()
