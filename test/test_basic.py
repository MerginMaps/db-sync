import uuid

import pytest
import os
import shutil
import sqlite3
import tempfile

import psycopg2
from psycopg2 import sql

from mergin import MerginClient, ClientError
from dbsync import dbsync_init, dbsync_pull, dbsync_push, dbsync_status, config, DbSyncError, _geodiff_make_copy, \
    _get_db_project_comment, _get_mergin_project, _get_project_id, _validate_local_project_id, config, _add_quotes_to_schema_name

GEODIFF_EXE = os.environ.get('TEST_GEODIFF_EXE')
DB_CONNINFO = os.environ.get('TEST_DB_CONNINFO')
SERVER_URL = os.environ.get('TEST_MERGIN_URL')
API_USER = os.environ.get('TEST_API_USERNAME')
USER_PWD = os.environ.get('TEST_API_PASSWORD')
WORKSPACE = os.environ.get('TEST_API_WORKSPACE')
TMP_DIR = tempfile.gettempdir()
TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_data')


@pytest.fixture(scope='function')
def mc():
    assert SERVER_URL and API_USER and USER_PWD
    #assert SERVER_URL and SERVER_URL.rstrip('/') != 'https://app.merginmaps.com/' and API_USER and USER_PWD
    return MerginClient(SERVER_URL, login=API_USER, password=USER_PWD)


def cleanup(mc, project, dirs):
    """ cleanup leftovers from previous test if needed such as remote project and local directories """
    try:
        print("Deleting project on Mergin Maps server: " + project)
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
    cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema_base)))
    cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema_main)))
    cur.execute("COMMIT")


def init_sync_from_geopackage(mc, project_name, source_gpkg_path, ignored_tables=[], *extra_init_files):
    """
    Initialize sync from given GeoPackage file:
    - (re)create Mergin Maps project with the file
    - (re)create local project working directory and sync directory
    - configure DB sync and let it do the init (make copies to the database)
    """
    full_project_name = WORKSPACE + "/" + project_name
    project_dir = os.path.join(TMP_DIR, project_name + '_work')  # working directory
    sync_project_dir = os.path.join(TMP_DIR, project_name + '_dbsync')  # used by dbsync
    db_schema_main = project_name + '_main'
    db_schema_base = project_name + '_base'

    conn = psycopg2.connect(DB_CONNINFO)

    cleanup(mc, full_project_name, [project_dir, sync_project_dir])
    cleanup_db(conn, db_schema_base, db_schema_main)

    # prepare a new Mergin Maps project
    mc.create_project(project_name, namespace=WORKSPACE)
    mc.download_project(full_project_name, project_dir)
    shutil.copy(source_gpkg_path, os.path.join(project_dir, 'test_sync.gpkg'))
    for extra_filepath in extra_init_files:
        extra_filename = os.path.basename(extra_filepath)
        target_extra_filepath = os.path.join(project_dir, extra_filename)
        shutil.copy(extra_filepath, target_extra_filepath)
    mc.push_project(project_dir)

    # prepare dbsync config
    # patch config to fit testing purposes
    if ignored_tables:
        connection = {"driver": "postgres", "conn_info": DB_CONNINFO, "modified": db_schema_main, "base": db_schema_base, "mergin_project": full_project_name, "sync_file": "test_sync.gpkg", "skip_tables":ignored_tables}
    else:
        connection = {"driver": "postgres", "conn_info": DB_CONNINFO, "modified": db_schema_main, "base": db_schema_base, "mergin_project": full_project_name, "sync_file": "test_sync.gpkg"}

    config.update({
        'GEODIFF_EXE': GEODIFF_EXE,
        'WORKING_DIR': sync_project_dir,
        'MERGIN__USERNAME': API_USER,
        'MERGIN__PASSWORD': USER_PWD,
        'MERGIN__URL': SERVER_URL,
        'CONNECTIONS': [connection],
    })

    dbsync_init(mc, from_gpkg=True)


@pytest.mark.parametrize("project_name", ['test_init_1', 'Test_Init_2', "Test 3", "Test-4"])
def test_init_from_gpkg(mc: MerginClient, project_name: str):
    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base.gpkg')
    project_dir = os.path.join(TMP_DIR, project_name + '_work')
    db_schema_main = project_name + '_main'
    db_schema_base = project_name + '_base'

    init_sync_from_geopackage(mc, project_name, source_gpkg_path)

    # test that database schemas are created + tables are populated
    conn = psycopg2.connect(DB_CONNINFO)
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(conn))
    assert cur.fetchone()[0] == 3
    # run again, nothing should change
    dbsync_init(mc, from_gpkg=True)
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(conn))
    assert cur.fetchone()[0] == 3
    db_proj_info = _get_db_project_comment(conn, db_schema_base)
    assert db_proj_info["name"] == config.connections[0].mergin_project
    assert db_proj_info["version"] == 'v1'

    # rename base schema to mimic some mismatch
    cur.execute(sql.SQL("ALTER SCHEMA {} RENAME TO schema_tmp").format(sql.Identifier(db_schema_base)).as_string(conn))
    conn.commit()
    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc, from_gpkg=True)
    assert "The 'modified' schema exists but the base schema is missing" in str(err.value)
    # and revert back
    cur.execute(sql.SQL("ALTER SCHEMA schema_tmp RENAME TO {}").format(sql.Identifier(db_schema_base)).as_string(conn))
    conn.commit()

    # make change in GPKG and push to server to create pending changes, it should pass but not sync
    shutil.copy(os.path.join(TEST_DATA_DIR, 'inserted_1_A.gpkg'), os.path.join(project_dir, 'test_sync.gpkg'))
    mc.push_project(project_dir)
    #  remove local copy of project (to mimic loss at docker restart)
    shutil.rmtree(config.working_dir)
    dbsync_init(mc, from_gpkg=True)
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(conn))
    assert cur.fetchone()[0] == 3
    db_proj_info = _get_db_project_comment(conn, db_schema_base)
    assert db_proj_info["version"] == 'v1'

    # let's remove local working dir and download different version from server to mimic versions mismatch
    shutil.rmtree(config.working_dir)
    mc.download_project(config.connections[0].mergin_project, config.working_dir, 'v2')
    # run init again, it should handle local working dir properly (e.g. download correct version) and pass but not sync
    dbsync_init(mc, from_gpkg=True)
    db_proj_info = _get_db_project_comment(conn, db_schema_base)
    assert db_proj_info["version"] == 'v1'

    # pull server changes to db to make sure we can sync again
    dbsync_pull(mc)
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(conn))
    assert cur.fetchone()[0] == 4
    db_proj_info = _get_db_project_comment(conn, db_schema_base)
    assert db_proj_info["version"] == 'v2'

    # update some feature from 'modified' db to create mismatch with src geopackage, it should pass but not sync
    fid = 1
    cur.execute(sql.SQL("SELECT * from {}.simple WHERE fid=%s").format(sql.Identifier(db_schema_main)), (fid,))
    old_value = cur.fetchone()[3]
    cur.execute(sql.SQL("UPDATE {}.simple SET rating=100 WHERE fid=%s").format(sql.Identifier(db_schema_main)), (fid,))
    conn.commit()
    cur.execute(sql.SQL("SELECT * from {}.simple WHERE fid=%s").format(sql.Identifier(db_schema_main)), (fid,))
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
    gpkg_cur.execute(f"SELECT * FROM simple WHERE fid ={fid}")
    assert gpkg_cur.fetchone()[3] == 100
    db_proj_info = _get_db_project_comment(conn, db_schema_base)
    assert db_proj_info["version"] == 'v3'

    # update some feature from 'base' db to create mismatch with src geopackage and modified
    cur.execute(sql.SQL("SELECT * from {}.simple").format(sql.Identifier(db_schema_base)))
    fid = cur.fetchone()[0]
    old_value = cur.fetchone()[3]
    cur.execute(sql.SQL("UPDATE {}.simple SET rating=100 WHERE fid=%s").format(sql.Identifier(db_schema_base)), (fid,))
    conn.commit()
    cur.execute(sql.SQL("SELECT * from {}.simple WHERE fid=%s").format(sql.Identifier(db_schema_base)), (fid,))
    assert cur.fetchone()[3] == 100
    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc, from_gpkg=True)
    assert "The db schemas already exist but 'base' schema is not synchronized with source GPKG" in str(err.value)

    # make local changes to src file to introduce local changes
    shutil.copy(os.path.join(TEST_DATA_DIR, 'base.gpkg'), os.path.join(config.working_dir, project_name, config.connections[0].sync_file))
    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc, from_gpkg=True)
    assert "There are pending changes in the local directory - that should never happen" in str(err.value)


@pytest.mark.parametrize("project_name", ['test_init_incomplete_dir_1', 'Test_Init_Incomplete_Dir_2'])
def test_init_from_gpkg_with_incomplete_dir(mc: MerginClient, project_name: str):
    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base.gpkg')
    init_project_dir = os.path.join(TMP_DIR, project_name + '_dbsync', project_name)
    init_sync_from_geopackage(mc, project_name, source_gpkg_path)
    assert os.listdir(init_project_dir) == ['test_sync.gpkg', '.mergin']
    shutil.rmtree(init_project_dir)  # Remove dir with content
    os.makedirs(init_project_dir)  # Recreate empty project working dir
    assert os.listdir(init_project_dir) == []
    dbsync_init(mc, from_gpkg=True)
    assert os.listdir(init_project_dir) == ['test_sync.gpkg', '.mergin']


@pytest.mark.parametrize("project_name", ['test_sync_pull_1', 'Test_Sync_Pull_2'])
def test_basic_pull(mc: MerginClient, project_name: str):
    """
    Test initialization and one pull from Mergin Maps to DB
    1. create a Mergin Maps project using py-client with a testing gpkg
    2. run init, check that everything is fine
    3. make change in gpkg (copy new version), check everything is fine
    """
    db_schema_main = project_name + "_main"

    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base.gpkg')
    project_dir = os.path.join(TMP_DIR, project_name + '_work')  # working directory

    init_sync_from_geopackage(mc, project_name, source_gpkg_path)

    conn = psycopg2.connect(DB_CONNINFO)

    # test that database schemas are created + tables are populated
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 3

    # make change in GPKG and push
    shutil.copy(os.path.join(TEST_DATA_DIR, 'inserted_1_A.gpkg'), os.path.join(project_dir, 'test_sync.gpkg'))
    mc.push_project(project_dir)

    # pull the change from Mergin Maps to DB
    dbsync_pull(mc)

    # check that a feature has been inserted
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format((sql.Identifier(db_schema_main))))
    assert cur.fetchone()[0] == 4
    db_proj_info = _get_db_project_comment(conn, project_name + "_base")
    assert db_proj_info["version"] == 'v2'

    print("---")
    dbsync_status(mc)


@pytest.mark.parametrize("project_name", ['test_sync_push_1', 'Test_Sync_Push_2'])
def test_basic_push(mc: MerginClient, project_name: str):
    """ Initialize a project and test push of a new row from PostgreSQL to Mergin Maps"""
    db_schema_main = project_name + "_main"

    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base.gpkg')
    project_dir = os.path.join(TMP_DIR, project_name + '_work')  # working directory

    init_sync_from_geopackage(mc, project_name, source_gpkg_path)

    conn = psycopg2.connect(DB_CONNINFO)

    # test that database schemas are created + tables are populated
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 3

    # make a change in PostgreSQL
    cur = conn.cursor()
    cur.execute(sql.SQL("INSERT INTO {}.simple (name, rating) VALUES ('insert in postgres', 123)").format(sql.Identifier(db_schema_main)))
    cur.execute("COMMIT")
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 4

    # push the change from DB to PostgreSQL
    dbsync_push(mc)
    db_proj_info = _get_db_project_comment(conn, project_name + "_base")
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


@pytest.mark.parametrize("project_name", ['test_sync_both_1', 'Test_Sync_Both_2'])
def test_basic_both(mc: MerginClient, project_name: str):
    """ Initializes a sync project and does both a change in Mergin Maps and in the database,
    and lets DB sync handle it: changes in PostgreSQL need to be rebased on top of
    changes in Mergin Maps server.
    """
    db_schema_main = project_name + "_main"
    db_schema_base = project_name + "_base"

    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base.gpkg')
    project_dir = os.path.join(TMP_DIR, project_name + '_work')  # working directory

    init_sync_from_geopackage(mc, project_name, source_gpkg_path)

    conn = psycopg2.connect(DB_CONNINFO)

    # test that database schemas are created + tables are populated
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 3

    # make change in GPKG and push
    shutil.copy(os.path.join(TEST_DATA_DIR, 'inserted_1_A.gpkg'), os.path.join(project_dir, 'test_sync.gpkg'))
    mc.push_project(project_dir)

    # make a change in PostgreSQL
    cur = conn.cursor()
    cur.execute(sql.SQL("INSERT INTO {}.simple (name, rating) VALUES ('insert in postgres', 123)").format(sql.Identifier(db_schema_main)))
    cur.execute("COMMIT")
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 4

    # first pull changes from Mergin Maps to DB (+rebase changes in DB) and then push the changes from DB to Mergin Maps
    dbsync_pull(mc)
    db_proj_info = _get_db_project_comment(conn, db_schema_base)
    assert db_proj_info["version"] == 'v2'
    dbsync_push(mc)
    db_proj_info = _get_db_project_comment(conn, db_schema_base)
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
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 5

    print("---")
    dbsync_status(mc)


@pytest.mark.parametrize("project_name", ['test_init_skip_1', 'Test_Init_Skip_2'])
def test_init_with_skip(mc: MerginClient, project_name: str):

    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base_2tables.gpkg')
    project_dir = os.path.join(TMP_DIR, project_name + '_work')
    db_schema_main = project_name + '_main'
    db_schema_base = project_name + '_base'

    init_sync_from_geopackage(mc, project_name, source_gpkg_path, ["lines"])

    # test that database schemas does not have ignored table
    conn = psycopg2.connect(DB_CONNINFO)
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT EXISTS (SELECT FROM pg_tables WHERE  schemaname = '{}' AND tablename = 'lines');").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == False
    cur.execute(sql.SQL("SELECT count(*) from {}.points").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 0

    # run again, nothing should change
    dbsync_init(mc, from_gpkg=True)
    cur.execute(sql.SQL("SELECT EXISTS (SELECT FROM pg_tables WHERE  schemaname = '{}' AND tablename = 'lines');").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == False
    cur.execute(sql.SQL("SELECT count(*) from {}.points").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 0

    # make change in GPKG and push to server to create pending changes, it should pass but not sync
    shutil.copy(os.path.join(TEST_DATA_DIR, 'modified_all.gpkg'), os.path.join(project_dir, 'test_sync.gpkg'))
    mc.push_project(project_dir)

    # pull server changes to db to make sure only points table is updated
    dbsync_pull(mc)
    cur.execute(sql.SQL("SELECT EXISTS (SELECT FROM pg_tables WHERE  schemaname = '{}' AND tablename = 'lines');").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == False
    cur.execute(sql.SQL("SELECT count(*) from {}.points").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 4


@pytest.mark.parametrize("project_name", ['test_local_changes_1', 'Test_Local_Changes_2'])
def test_with_local_changes(mc: MerginClient, project_name: str):

    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base.gpkg')
    extra_files = [os.path.join(TEST_DATA_DIR, f) for f in ["note_1.txt", "note_3.txt", "modified_all.gpkg"]]
    dbsync_project_dir = os.path.join(TMP_DIR, project_name + '_dbsync',
                                      project_name)  # project location within dbsync working dir

    init_sync_from_geopackage(mc, project_name, source_gpkg_path, [], *extra_files)

    # update GPKG
    shutil.copy(os.path.join(TEST_DATA_DIR, 'inserted_1_A.gpkg'), os.path.join(dbsync_project_dir, 'test_sync.gpkg'))
    # update non-GPGK file
    shutil.copy(os.path.join(TEST_DATA_DIR, 'note_2.txt'), os.path.join(dbsync_project_dir, 'note_1.txt'))
    # add GPKG file
    shutil.copy(os.path.join(TEST_DATA_DIR, 'inserted_1_A.gpkg'), os.path.join(dbsync_project_dir, 'inserted_1_A.gpkg'))
    # add non-GPGK file
    shutil.copy(os.path.join(TEST_DATA_DIR, 'note_2.txt'), os.path.join(dbsync_project_dir, 'note_2.txt'))
    # remove GPKG file
    os.remove(os.path.join(dbsync_project_dir, 'modified_all.gpkg'))
    # remove non-GPKG file
    os.remove(os.path.join(dbsync_project_dir, 'note_3.txt'))
    # Check local changes in the sync project dir
    mp = _get_mergin_project(dbsync_project_dir)
    local_changes = mp.get_push_changes()
    del local_changes["renamed"]  # Not supported anymore
    assert all(local_changes.values()) is True
    dbsync_pull(mc)
    local_changes = mp.get_push_changes()
    assert any(local_changes.values()) is False
    dbsync_status(mc)

@pytest.mark.parametrize("project_name", ['test_recreated_project_ids_1', 'Test_Recreated_Project_Ids_2'])
def test_recreated_project_ids(mc: MerginClient, project_name: str):

    source_gpkg_path = os.path.join(TEST_DATA_DIR, 'base.gpkg')
    project_dir = os.path.join(TMP_DIR, project_name + '_work')  # working directory
    full_project_name = WORKSPACE + "/" + project_name
    init_sync_from_geopackage(mc, project_name, source_gpkg_path)
    # delete remote project
    mc.delete_project(full_project_name)
    # recreate project with the same name
    mc.create_project(project_name, namespace=WORKSPACE)
    # comparing project IDs after recreating it with the same name
    mp = _get_mergin_project(project_dir)
    local_project_id = _get_project_id(mp)
    server_info = mc.project_info(full_project_name)
    server_project_id = uuid.UUID(server_info["id"])
    assert local_project_id is not None
    assert server_project_id is not None
    assert local_project_id != server_project_id
    with pytest.raises(DbSyncError):
        dbsync_status(mc)
