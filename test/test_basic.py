
import pytest
import os
import shutil
import sqlite3
import tempfile

import psycopg2

from mergin import MerginClient, ClientError
from dbsync import dbsync_init, dbsync_pull, dbsync_push, dbsync_status, config, DbSyncError, _geodiff_make_copy, \
    _get_db_project_comment

GEODIFFINFO_EXE = os.environ.get('TEST_GEODIFFINFO_EXE')
DB_CONNINFO = os.environ.get('TEST_DB_CONNINFO')
SERVER_URL = os.environ.get('TEST_MERGIN_URL')
API_USER = os.environ.get('TEST_API_USERNAME')
USER_PWD = os.environ.get('TEST_API_PASSWORD')
TMP_DIR = tempfile.gettempdir()
TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_data')


@pytest.fixture(scope='function')
def mc():
    assert SERVER_URL and API_USER and USER_PWD
    #assert SERVER_URL and SERVER_URL.rstrip('/') != 'https://public.cloudmergin.com' and API_USER and USER_PWD
    return MerginClient(SERVER_URL, login=API_USER, password=USER_PWD)


def cleanup(mc, project, dirs):
    """ cleanup leftovers from previous test if needed such as remote project and local directories """
    try:
        print("Deleting project on Mergin server: " + project)
        mc.delete_project(project)
    except ClientError as e:
        print("Deleting project error: " + str(e))
        pass
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d)


def cleanup_db(conn, schema_base, schema_main):
    """ Removes test schemas from previous tests """
    cur = conn.cursor()
    cur.execute("DROP SCHEMA IF EXISTS {} CASCADE".format(schema_base))
    cur.execute("DROP SCHEMA IF EXISTS {} CASCADE".format(schema_main))
    cur.execute("COMMIT")


def init_sync_from_geopackage(mc, project_name, source_gpkg_path):
    """
    Initialize sync from given GeoPackage file:
    - (re)create Mergin project with the file
    - (re)create local project working directory and sync directory
    - configure DB sync and let it do the init (make copies to the database)
    """

    full_project_name = API_USER + "/" + project_name
    project_dir = os.path.join(TMP_DIR, project_name + '_work')  # working directory
    sync_project_dir = os.path.join(TMP_DIR, project_name + '_dbsync')  # used by dbsync
    db_schema_main = project_name + '_main'
    db_schema_base = project_name + '_base'

    conn = psycopg2.connect(DB_CONNINFO)

    cleanup(mc, full_project_name, [project_dir, sync_project_dir])
    cleanup_db(conn, db_schema_base, db_schema_main)

    # prepare a new Mergin project
    mc.create_project(project_name)
    mc.download_project(full_project_name, project_dir)
    shutil.copy(source_gpkg_path, os.path.join(project_dir, 'test_sync.gpkg'))
    mc.push_project(project_dir)

    # prepare dbsync config
    config.geodiffinfo_exe = GEODIFFINFO_EXE
    config.mergin_username = API_USER
    config.mergin_password = USER_PWD
    config.mergin_url = SERVER_URL
    config.db_conn_info = DB_CONNINFO
    config.project_working_dir = sync_project_dir
    config.mergin_project_name = full_project_name
    config.mergin_sync_file = 'test_sync.gpkg'
    config.db_driver = 'postgres'
    config.db_schema_modified = db_schema_main
    config.db_schema_base = db_schema_base

    dbsync_init(mc, from_gpkg=True)


def test_init_from_gpkg(mc):
    project_name = 'test_init'
    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base.gpkg')
    project_dir = os.path.join(TMP_DIR, project_name + '_work')
    db_schema_main = project_name + '_main'
    db_schema_base = project_name + '_base'

    init_sync_from_geopackage(mc, project_name, source_gpkg_path)

    # test that database schemas are created + tables are populated
    conn = psycopg2.connect(DB_CONNINFO)
    cur = conn.cursor()
    cur.execute(f"SELECT count(*) from {db_schema_main}.simple")
    assert cur.fetchone()[0] == 3
    # run again, nothing should change
    dbsync_init(mc, from_gpkg=True)
    cur.execute(f"SELECT count(*) from {db_schema_main}.simple")
    assert cur.fetchone()[0] == 3
    db_proj_info = _get_db_project_comment(conn, db_schema_base)
    assert db_proj_info["name"] == config.mergin_project_name
    assert db_proj_info["version"] == 'v1'

    # rename base schema to mimic some mismatch
    cur.execute(f"ALTER SCHEMA {db_schema_base} RENAME TO schema_tmp")
    conn.commit()
    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc, from_gpkg=True)
    assert "The 'modified' schema exists but the base schema is missing" in str(err.value)
    # and revert back
    cur.execute(f"ALTER SCHEMA schema_tmp RENAME TO {db_schema_base}")
    conn.commit()

    # make change in GPKG and push to server to create pending changes, it should pass but not sync
    shutil.copy(os.path.join(TEST_DATA_DIR, 'inserted_1_A.gpkg'), os.path.join(project_dir, 'test_sync.gpkg'))
    mc.push_project(project_dir)
    #  remove local copy of project (to mimic loss at docker restart)
    shutil.rmtree(config.project_working_dir)
    dbsync_init(mc, from_gpkg=True)
    cur.execute(f"SELECT count(*) from {db_schema_main}.simple")
    assert cur.fetchone()[0] == 3
    # pull server changes to db to make sure we can sync again
    dbsync_pull(mc)
    cur.execute(f"SELECT count(*) from {db_schema_main}.simple")
    assert cur.fetchone()[0] == 4

    # update some feature from 'modified' db to create mismatch with src geopackage, it should pass but not sync
    fid = 1
    cur.execute(f"SELECT * from {db_schema_main}.simple WHERE fid={fid}")
    old_value = cur.fetchone()[3]
    cur.execute(f"UPDATE {db_schema_main}.simple SET rating=100 WHERE fid={fid}")
    conn.commit()
    cur.execute(f"SELECT * from {db_schema_main}.simple WHERE fid={fid}")
    assert cur.fetchone()[3] == 100
    dbsync_init(mc, from_gpkg=True)
    # check geopackage has not been modified - after init we are not synced!
    gpkg_conn = sqlite3.connect(os.path.join(project_dir, 'test_sync.gpkg'))
    gpkg_cur = gpkg_conn.cursor()
    gpkg_cur.execute(f"SELECT * FROM simple WHERE fid={fid}")
    assert gpkg_cur.fetchone()[3] == old_value
    # push db changes to server (and download new version to local working dir) to make sure we can sync again
    dbsync_push(mc)
    mc.pull_project(project_dir)
    gpkg_cur.execute(f"SELECT * FROM simple WHERE fid={fid}")
    assert gpkg_cur.fetchone()[3] == 100

    # update some feature from 'base' db to create mismatch with src geopackage and modified
    cur.execute(f"SELECT * from {db_schema_base}.simple")
    fid = cur.fetchone()[0]
    old_value = cur.fetchone()[3]
    cur.execute(f"UPDATE {db_schema_base}.simple SET rating=100 WHERE fid={fid}")
    conn.commit()
    cur.execute(f"SELECT * from {db_schema_base}.simple WHERE fid={fid}")
    assert cur.fetchone()[3] == 100
    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc, from_gpkg=True)
    assert "The db schemas already exist but 'base' schema is not synchronized with source GPKG" in str(err.value)

    # make local changes to src file to introduce local changes
    shutil.copy(os.path.join(TEST_DATA_DIR, 'base.gpkg'), os.path.join(config.project_working_dir, config.mergin_sync_file))
    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc, from_gpkg=True)
    assert "There are pending changes in the local directory - that should never happen" in str(err.value)


def test_basic_pull(mc):
    """
    Test initialization and one pull from Mergin to DB
    1. create a Mergin project using py-client with a testing gpkg
    2. run init, check that everything is fine
    3. make change in gpkg (copy new version), check everything is fine
    """

    project_name = 'test_sync_pull'
    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base.gpkg')
    project_dir = os.path.join(TMP_DIR, project_name + '_work')  # working directory

    init_sync_from_geopackage(mc, project_name, source_gpkg_path)

    conn = psycopg2.connect(DB_CONNINFO)

    # test that database schemas are created + tables are populated
    cur = conn.cursor()
    cur.execute("SELECT count(*) from test_sync_pull_main.simple")
    assert cur.fetchone()[0] == 3

    # make change in GPKG and push
    shutil.copy(os.path.join(TEST_DATA_DIR, 'inserted_1_A.gpkg'), os.path.join(project_dir, 'test_sync.gpkg'))
    mc.push_project(project_dir)

    # pull the change from Mergin to DB
    dbsync_pull(mc)

    # check that a feature has been inserted
    cur = conn.cursor()
    cur.execute("SELECT count(*) from test_sync_pull_main.simple")
    assert cur.fetchone()[0] == 4
    db_proj_info = _get_db_project_comment(conn, 'test_sync_pull_base')
    assert db_proj_info["version"] == 'v2'

    print("---")
    dbsync_status(mc)


def test_basic_push(mc):
    """ Initialize a project and test push of a new row from PostgreSQL to Mergin """

    project_name = 'test_sync_push'
    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base.gpkg')
    project_dir = os.path.join(TMP_DIR, project_name + '_work')  # working directory

    init_sync_from_geopackage(mc, project_name, source_gpkg_path)

    conn = psycopg2.connect(DB_CONNINFO)

    # test that database schemas are created + tables are populated
    cur = conn.cursor()
    cur.execute("SELECT count(*) from test_sync_push_main.simple")
    assert cur.fetchone()[0] == 3

    # make a change in PostgreSQL
    cur = conn.cursor()
    cur.execute("INSERT INTO test_sync_push_main.simple (name, rating) VALUES ('insert in postgres', 123)")
    cur.execute("COMMIT")
    cur.execute("SELECT count(*) from test_sync_push_main.simple")
    assert cur.fetchone()[0] == 4

    # push the change from DB to PostgreSQL
    dbsync_push(mc)
    db_proj_info = _get_db_project_comment(conn, 'test_sync_push_base')
    assert db_proj_info["version"] == 'v2'

    # pull new version of the project to the work project directory
    mc.pull_project(project_dir)

    # check that the insert has been applied to our GeoPackage
    gpkg_conn = sqlite3.connect(os.path.join(project_dir, 'test_sync.gpkg'))
    gpkg_cur = gpkg_conn.cursor()
    gpkg_cur.execute("SELECT count(*) FROM simple")
    assert gpkg_cur.fetchone()[0] == 4

    print("---")
    dbsync_status(mc)


def test_basic_both(mc):
    """ Initializes a sync project and does both a change in Mergin and in the database,
    and lets DB sync handle it: changes in PostgreSQL need to be rebased on top of
    changes in Mergin server.
    """

    project_name = 'test_sync_both'
    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base.gpkg')
    project_dir = os.path.join(TMP_DIR, project_name + '_work')  # working directory

    init_sync_from_geopackage(mc, project_name, source_gpkg_path)

    conn = psycopg2.connect(DB_CONNINFO)

    # test that database schemas are created + tables are populated
    cur = conn.cursor()
    cur.execute(f"SELECT count(*) from {project_name}_main.simple")
    assert cur.fetchone()[0] == 3

    # make change in GPKG and push
    shutil.copy(os.path.join(TEST_DATA_DIR, 'inserted_1_A.gpkg'), os.path.join(project_dir, 'test_sync.gpkg'))
    mc.push_project(project_dir)

    # make a change in PostgreSQL
    cur = conn.cursor()
    cur.execute(f"INSERT INTO {project_name}_main.simple (name, rating) VALUES ('insert in postgres', 123)")
    cur.execute("COMMIT")
    cur.execute(f"SELECT count(*) from {project_name}_main.simple")
    assert cur.fetchone()[0] == 4

    # first pull changes from Mergin to DB (+rebase changes in DB) and then push the changes from DB to Mergin
    dbsync_pull(mc)
    db_proj_info = _get_db_project_comment(conn, 'test_sync_both_base')
    assert db_proj_info["version"] == 'v2'
    dbsync_push(mc)
    db_proj_info = _get_db_project_comment(conn, 'test_sync_both_base')
    assert db_proj_info["version"] == 'v3'

    # pull new version of the project to the work project directory
    mc.pull_project(project_dir)

    # check that the insert has been applied to our GeoPackage
    gpkg_conn = sqlite3.connect(os.path.join(project_dir, 'test_sync.gpkg'))
    gpkg_cur = gpkg_conn.cursor()
    gpkg_cur.execute("SELECT count(*) FROM simple")
    assert gpkg_cur.fetchone()[0] == 5

    # check that the insert has been applied to the DB
    cur = conn.cursor()
    cur.execute(f"SELECT count(*) from {project_name}_main.simple")
    assert cur.fetchone()[0] == 5

    print("---")
    dbsync_status(mc)
