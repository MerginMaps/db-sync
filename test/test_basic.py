import uuid

import pytest
import os
import shutil
import sqlite3
import tempfile
import pathlib

import psycopg2
from psycopg2 import (
    sql,
)

from mergin import (
    MerginClient,
)

from dbsync import (
    dbsync_init,
    dbsync_pull,
    dbsync_push,
    dbsync_status,
    config,
    DbSyncError,
    _geodiff_make_copy,
    _get_db_project_comment,
    _get_mergin_project,
    _get_project_id,
    _validate_local_project_id,
    config,
    _add_quotes_to_schema_name,
    dbsync_clean,
    _check_schema_exists,
)

from .conftest import (
    WORKSPACE,
    TMP_DIR,
    DB_CONNINFO,
    GEODIFF_EXE,
    API_USER,
    USER_PWD,
    SERVER_URL,
    TEST_DATA_DIR,
    init_sync_from_geopackage,
)


def test_init_from_gpkg(
    mc: MerginClient,
):
    project_name = "test_init"
    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base.gpkg",
    )
    project_dir = os.path.join(
        TMP_DIR,
        project_name + "_work",
    )
    db_schema_main = project_name + "_main"
    db_schema_base = project_name + "_base"

    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )

    # test that database schemas are created + tables are populated
    conn = psycopg2.connect(DB_CONNINFO)
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(conn))
    assert cur.fetchone()[0] == 3
    # run again, nothing should change
    dbsync_init(mc)
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(conn))
    assert cur.fetchone()[0] == 3
    db_proj_info = _get_db_project_comment(
        conn,
        db_schema_base,
    )
    assert db_proj_info["name"] == config.connections[0].mergin_project
    assert db_proj_info["version"] == "v1"

    # make change in GPKG and push to server to create pending changes, it should pass but not sync
    shutil.copy(
        os.path.join(
            TEST_DATA_DIR,
            "inserted_1_A.gpkg",
        ),
        os.path.join(
            project_dir,
            "test_sync.gpkg",
        ),
    )
    mc.push_project(project_dir)
    #  remove local copy of project (to mimic loss at docker restart)
    shutil.rmtree(config.working_dir)
    dbsync_init(mc)
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(conn))
    assert cur.fetchone()[0] == 3
    db_proj_info = _get_db_project_comment(
        conn,
        db_schema_base,
    )
    assert db_proj_info["version"] == "v1"

    # let's remove local working dir and download different version from server to mimic versions mismatch
    shutil.rmtree(config.working_dir)
    mc.download_project(
        config.connections[0].mergin_project,
        config.working_dir,
        "v2",
    )
    # run init again, it should handle local working dir properly (e.g. download correct version) and pass but not sync
    dbsync_init(mc)
    db_proj_info = _get_db_project_comment(
        conn,
        db_schema_base,
    )
    assert db_proj_info["version"] == "v1"

    # pull server changes to db to make sure we can sync again
    dbsync_pull(mc)
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(conn))
    assert cur.fetchone()[0] == 4
    db_proj_info = _get_db_project_comment(
        conn,
        db_schema_base,
    )
    assert db_proj_info["version"] == "v2"

    # update some feature from 'modified' db to create mismatch with src geopackage, it should pass but not sync
    fid = 1
    cur.execute(
        sql.SQL("SELECT * from {}.simple WHERE fid=%s").format(sql.Identifier(db_schema_main)),
        (fid,),
    )
    old_value = cur.fetchone()[3]
    cur.execute(
        sql.SQL("UPDATE {}.simple SET rating=100 WHERE fid=%s").format(sql.Identifier(db_schema_main)),
        (fid,),
    )
    conn.commit()
    cur.execute(
        sql.SQL("SELECT * from {}.simple WHERE fid=%s").format(sql.Identifier(db_schema_main)),
        (fid,),
    )
    assert cur.fetchone()[3] == 100
    dbsync_init(mc)
    # check geopackage has not been modified - after init we are not synced!
    gpkg_conn = sqlite3.connect(
        os.path.join(
            project_dir,
            "test_sync.gpkg",
        )
    )
    gpkg_cur = gpkg_conn.cursor()
    gpkg_cur.execute(f"SELECT * FROM simple WHERE fid={fid}")
    assert gpkg_cur.fetchone()[3] == old_value
    # push db changes to server (and download new version to local working dir) to make sure we can sync again
    dbsync_push(mc)
    mc.pull_project(project_dir)
    gpkg_cur.execute(f"SELECT * FROM simple WHERE fid ={fid}")
    assert gpkg_cur.fetchone()[3] == 100
    db_proj_info = _get_db_project_comment(
        conn,
        db_schema_base,
    )
    assert db_proj_info["version"] == "v3"

    # update some feature from 'base' db to create mismatch with src geopackage and modified
    cur.execute(sql.SQL("SELECT * from {}.simple").format(sql.Identifier(db_schema_base)))
    fid = cur.fetchone()[0]
    old_value = cur.fetchone()[3]
    cur.execute(
        sql.SQL("UPDATE {}.simple SET rating=100 WHERE fid=%s").format(sql.Identifier(db_schema_base)),
        (fid,),
    )
    conn.commit()
    cur.execute(
        sql.SQL("SELECT * from {}.simple WHERE fid=%s").format(sql.Identifier(db_schema_base)),
        (fid,),
    )
    assert cur.fetchone()[3] == 100
    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc)
    assert "The db schemas already exist but 'base' schema is not synchronized with source GPKG" in str(err.value)

    # make local changes to src file to introduce local changes
    shutil.copy(
        os.path.join(
            TEST_DATA_DIR,
            "base.gpkg",
        ),
        os.path.join(
            config.working_dir,
            project_name,
            config.connections[0].sync_file,
        ),
    )
    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc)
    assert "There are pending changes in the local directory - that should never happen" in str(err.value)


def test_init_from_gpkg_with_incomplete_dir(
    mc: MerginClient,
):
    project_name = "test_init_incomplete_dir"
    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base.gpkg",
    )
    init_project_dir = os.path.join(
        TMP_DIR,
        project_name + "_dbsync",
        project_name,
    )
    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )
    assert set(os.listdir(init_project_dir)) == set(
        [
            "test_sync.gpkg",
            ".mergin",
        ]
    )
    shutil.rmtree(init_project_dir)  # Remove dir with content
    os.makedirs(init_project_dir)  # Recreate empty project working dir
    assert os.listdir(init_project_dir) == []
    dbsync_init(mc)
    assert set(os.listdir(init_project_dir)) == set(
        [
            "test_sync.gpkg",
            ".mergin",
        ]
    )


def test_basic_pull(
    mc: MerginClient,
):
    """
    Test initialization and one pull from Mergin Maps to DB
    1. create a Mergin Maps project using py-client with a testing gpkg
    2. run init, check that everything is fine
    3. make change in gpkg (copy new version), check everything is fine
    """
    project_name = "test_sync_pull"
    db_schema_main = project_name + "_main"

    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base.gpkg",
    )
    project_dir = os.path.join(
        TMP_DIR,
        project_name + "_work",
    )  # working directory

    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )

    conn = psycopg2.connect(DB_CONNINFO)

    # test that database schemas are created + tables are populated
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 3

    # make change in GPKG and push
    shutil.copy(
        os.path.join(
            TEST_DATA_DIR,
            "inserted_1_A.gpkg",
        ),
        os.path.join(
            project_dir,
            "test_sync.gpkg",
        ),
    )
    mc.push_project(project_dir)

    # pull the change from Mergin Maps to DB
    dbsync_pull(mc)

    # check that a feature has been inserted
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format((sql.Identifier(db_schema_main))))
    assert cur.fetchone()[0] == 4
    db_proj_info = _get_db_project_comment(
        conn,
        project_name + "_base",
    )
    assert db_proj_info["version"] == "v2"

    print("---")
    dbsync_status(mc)


def test_basic_push(
    mc: MerginClient,
):
    """Initialize a project and test push of a new row from PostgreSQL to Mergin Maps"""
    project_name = "test_sync_push"
    db_schema_main = project_name + "_main"

    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base.gpkg",
    )
    project_dir = os.path.join(
        TMP_DIR,
        project_name + "_work",
    )  # working directory

    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )

    conn = psycopg2.connect(DB_CONNINFO)

    # test that database schemas are created + tables are populated
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 3

    # make a change in PostgreSQL
    cur = conn.cursor()
    cur.execute(
        sql.SQL("INSERT INTO {}.simple (name, rating) VALUES ('insert in postgres', 123)").format(
            sql.Identifier(db_schema_main)
        )
    )
    cur.execute("COMMIT")
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 4

    # push the change from DB to PostgreSQL
    dbsync_push(mc)
    db_proj_info = _get_db_project_comment(
        conn,
        project_name + "_base",
    )
    assert db_proj_info["version"] == "v2"

    # pull new version of the project to the work project directory
    mc.pull_project(project_dir)

    # check that the insert has been applied to our GeoPackage
    gpkg_conn = sqlite3.connect(
        os.path.join(
            project_dir,
            "test_sync.gpkg",
        )
    )
    gpkg_cur = gpkg_conn.cursor()
    gpkg_cur.execute("SELECT count(*) FROM simple")
    assert gpkg_cur.fetchone()[0] == 4

    print("---")
    dbsync_status(mc)


def test_basic_both(
    mc: MerginClient,
):
    """Initializes a sync project and does both a change in Mergin Maps and in the database,
    and lets DB sync handle it: changes in PostgreSQL need to be rebased on top of
    changes in Mergin Maps server.
    """
    project_name = "test_sync_both"
    db_schema_main = project_name + "_main"
    db_schema_base = project_name + "_base"

    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base.gpkg",
    )
    project_dir = os.path.join(
        TMP_DIR,
        project_name + "_work",
    )  # working directory

    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )

    conn = psycopg2.connect(DB_CONNINFO)

    # test that database schemas are created + tables are populated
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 3

    # make change in GPKG and push
    shutil.copy(
        os.path.join(
            TEST_DATA_DIR,
            "inserted_1_A.gpkg",
        ),
        os.path.join(
            project_dir,
            "test_sync.gpkg",
        ),
    )
    mc.push_project(project_dir)

    # make a change in PostgreSQL
    cur = conn.cursor()
    cur.execute(
        sql.SQL("INSERT INTO {}.simple (name, rating) VALUES ('insert in postgres', 123)").format(
            sql.Identifier(db_schema_main)
        )
    )
    cur.execute("COMMIT")
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 4

    # first pull changes from Mergin Maps to DB (+rebase changes in DB) and then push the changes from DB to Mergin Maps
    dbsync_pull(mc)
    db_proj_info = _get_db_project_comment(
        conn,
        db_schema_base,
    )
    assert db_proj_info["version"] == "v2"
    dbsync_push(mc)
    db_proj_info = _get_db_project_comment(
        conn,
        db_schema_base,
    )
    assert db_proj_info["version"] == "v3"

    # pull new version of the project to the work project directory
    mc.pull_project(project_dir)

    # check that the insert has been applied to our GeoPackage
    gpkg_conn = sqlite3.connect(
        os.path.join(
            project_dir,
            "test_sync.gpkg",
        )
    )
    gpkg_cur = gpkg_conn.cursor()
    gpkg_cur.execute("SELECT count(*) FROM simple")
    assert gpkg_cur.fetchone()[0] == 5

    # check that the insert has been applied to the DB
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 5

    print("---")
    dbsync_status(mc)


def test_init_with_skip(
    mc: MerginClient,
):
    project_name = "test_init_skip"
    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base_2tables.gpkg",
    )
    project_dir = os.path.join(
        TMP_DIR,
        project_name + "_work",
    )
    db_schema_main = project_name + "_main"
    db_schema_base = project_name + "_base"

    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
        ["lines"],
    )

    # test that database schemas does not have ignored table
    conn = psycopg2.connect(DB_CONNINFO)
    cur = conn.cursor()
    cur.execute(
        sql.SQL("SELECT EXISTS (SELECT FROM pg_tables WHERE  schemaname = '{}' AND tablename = 'lines');").format(
            sql.Identifier(db_schema_main)
        )
    )
    assert cur.fetchone()[0] == False
    cur.execute(sql.SQL("SELECT count(*) from {}.points").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 0

    # run again, nothing should change
    dbsync_init(mc)
    cur.execute(
        sql.SQL("SELECT EXISTS (SELECT FROM pg_tables WHERE  schemaname = '{}' AND tablename = 'lines');").format(
            sql.Identifier(db_schema_main)
        )
    )
    assert cur.fetchone()[0] == False
    cur.execute(sql.SQL("SELECT count(*) from {}.points").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 0

    # make change in GPKG and push to server to create pending changes, it should pass but not sync
    shutil.copy(
        os.path.join(
            TEST_DATA_DIR,
            "modified_all.gpkg",
        ),
        os.path.join(
            project_dir,
            "test_sync.gpkg",
        ),
    )
    mc.push_project(project_dir)

    # pull server changes to db to make sure only points table is updated
    dbsync_pull(mc)
    cur.execute(
        sql.SQL("SELECT EXISTS (SELECT FROM pg_tables WHERE  schemaname = '{}' AND tablename = 'lines');").format(
            sql.Identifier(db_schema_main)
        )
    )
    assert cur.fetchone()[0] == False
    cur.execute(sql.SQL("SELECT count(*) from {}.points").format(sql.Identifier(db_schema_main)))
    assert cur.fetchone()[0] == 4


def test_with_local_changes(
    mc: MerginClient,
):
    project_name = "test_local_changes"
    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base.gpkg",
    )
    extra_files = [
        os.path.join(
            TEST_DATA_DIR,
            f,
        )
        for f in [
            "note_1.txt",
            "note_3.txt",
            "modified_all.gpkg",
        ]
    ]
    dbsync_project_dir = os.path.join(
        TMP_DIR,
        project_name + "_dbsync",
        project_name,
    )  # project location within dbsync working dir

    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
        [],
        *extra_files,
    )

    # update GPKG
    shutil.copy(
        os.path.join(
            TEST_DATA_DIR,
            "inserted_1_A.gpkg",
        ),
        os.path.join(
            dbsync_project_dir,
            "test_sync.gpkg",
        ),
    )
    # update non-GPGK file
    shutil.copy(
        os.path.join(
            TEST_DATA_DIR,
            "note_2.txt",
        ),
        os.path.join(
            dbsync_project_dir,
            "note_1.txt",
        ),
    )
    # add GPKG file
    shutil.copy(
        os.path.join(
            TEST_DATA_DIR,
            "inserted_1_A.gpkg",
        ),
        os.path.join(
            dbsync_project_dir,
            "inserted_1_A.gpkg",
        ),
    )
    # add non-GPGK file
    shutil.copy(
        os.path.join(
            TEST_DATA_DIR,
            "note_2.txt",
        ),
        os.path.join(
            dbsync_project_dir,
            "note_2.txt",
        ),
    )
    # remove GPKG file
    os.remove(
        os.path.join(
            dbsync_project_dir,
            "modified_all.gpkg",
        )
    )
    # remove non-GPKG file
    os.remove(
        os.path.join(
            dbsync_project_dir,
            "note_3.txt",
        )
    )
    # Check local changes in the sync project dir
    mp = _get_mergin_project(dbsync_project_dir)
    local_changes = mp.get_push_changes()
    del local_changes["renamed"]  # Not supported anymore
    assert all(local_changes.values()) is True
    dbsync_pull(mc)
    local_changes = mp.get_push_changes()
    assert any(local_changes.values()) is False
    dbsync_status(mc)


def test_recreated_project_ids(
    mc: MerginClient,
):
    project_name = "test_recreated_project_ids"
    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base.gpkg",
    )
    project_dir = os.path.join(
        TMP_DIR,
        project_name + "_work",
    )  # working directory
    full_project_name = WORKSPACE + "/" + project_name
    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )
    # delete remote project
    mc.delete_project_now(full_project_name)
    # recreate project with the same name
    mc.create_project(
        project_name,
        namespace=WORKSPACE,
    )
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


@pytest.mark.parametrize(
    "project_name",
    [
        "test_init_1",
        "Test_Init_2",
        "Test 3",
        "Test-4",
    ],
)
def test_project_names(
    mc: MerginClient,
    project_name: str,
):
    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base.gpkg",
    )
    project_dir = os.path.join(
        TMP_DIR,
        project_name + "_work",
    )
    db_schema_main = project_name + "_main"
    db_schema_base = project_name + "_base"

    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )

    # test that database schemas are created + tables are populated
    conn = psycopg2.connect(DB_CONNINFO)
    cur = conn.cursor()
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(conn))
    assert cur.fetchone()[0] == 3

    # make change in GPKG and push
    shutil.copy(
        os.path.join(
            TEST_DATA_DIR,
            "inserted_1_A.gpkg",
        ),
        os.path.join(
            project_dir,
            "test_sync.gpkg",
        ),
    )
    mc.push_project(project_dir)

    # pull server changes to db to make sure we can sync again
    dbsync_pull(mc)
    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(conn))
    assert cur.fetchone()[0] == 4
    db_proj_info = _get_db_project_comment(
        conn,
        db_schema_base,
    )
    assert db_proj_info["version"] == "v2"

    # update some feature from 'modified' db to create mismatch with src geopackage, it should pass but not sync
    fid = 1
    cur.execute(
        sql.SQL("SELECT * from {}.simple WHERE fid=%s").format(sql.Identifier(db_schema_main)),
        (fid,),
    )
    old_value = cur.fetchone()[3]
    cur.execute(
        sql.SQL("UPDATE {}.simple SET rating=100 WHERE fid=%s").format(sql.Identifier(db_schema_main)),
        (fid,),
    )
    conn.commit()
    cur.execute(
        sql.SQL("SELECT * from {}.simple WHERE fid=%s").format(sql.Identifier(db_schema_main)),
        (fid,),
    )
    assert cur.fetchone()[3] == 100
    dbsync_init(mc)
    # check geopackage has not been modified - after init we are not synced!
    gpkg_conn = sqlite3.connect(
        os.path.join(
            project_dir,
            "test_sync.gpkg",
        )
    )
    gpkg_cur = gpkg_conn.cursor()
    gpkg_cur.execute(f"SELECT * FROM simple WHERE fid={fid}")
    assert gpkg_cur.fetchone()[3] == old_value
    # push db changes to server (and download new version to local working dir) to make sure we can sync again
    dbsync_push(mc)
    mc.pull_project(project_dir)
    gpkg_cur.execute(f"SELECT * FROM simple WHERE fid ={fid}")
    assert gpkg_cur.fetchone()[3] == 100
    db_proj_info = _get_db_project_comment(
        conn,
        db_schema_base,
    )
    assert db_proj_info["version"] == "v3"


def test_init_from_gpkg_missing_schema(
    mc: MerginClient,
):
    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base.gpkg",
    )
    project_name = "test_init_missing_schema"
    db_schema_base = project_name + "_base"
    db_schema_main = project_name + "_main"

    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )

    conn = psycopg2.connect(DB_CONNINFO)
    cur = conn.cursor()

    # drop base schema to mimic some mismatch
    cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(db_schema_base)))
    conn.commit()

    # check that removed schema does not exists
    cur.execute(f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{db_schema_base}'")
    cur.fetchone() is None

    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc)
    assert "The 'modified' schema exists but the base schema is missing" in str(err.value)
    assert "This may be a result of a previously failed attempt to initialize DB sync" in str(err.value)

    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )

    # drop main schema to mimic some mismatch
    cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(db_schema_main)))
    conn.commit()

    # check that removed schema does not exists
    cur.execute(f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{db_schema_main}'")
    cur.fetchone() is None

    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc)
    assert "The base schema exists but the modified schema is missing" in str(err.value)
    assert "This may be a result of a previously failed attempt to initialize DB sync" in str(err.value)


def test_init_from_gpkg_missing_comment(
    mc: MerginClient,
):
    project_name = "test_init_missing_comment"
    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base.gpkg",
    )
    schema_name = project_name + "_base"

    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )

    conn = psycopg2.connect(DB_CONNINFO)
    cur = conn.cursor()

    # sql query for schema
    sql_cmd = f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{schema_name}'"

    # check that schema exists
    cur.execute(sql_cmd)
    cur.fetchone()[0] == schema_name

    # drop base schema to mimic some mismatch
    query = sql.SQL("COMMENT ON SCHEMA {} IS %s").format(sql.Identifier(schema_name))
    cur.execute(
        query.as_string(conn),
        ("",),
    )
    conn.commit()

    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc)
    assert "Base schema exists but missing which project it belongs to" in str(err.value)

    # check that schema does not exists anymore
    cur.execute(sql_cmd)
    cur.fetchone() is None


def test_dbsync_clean_from_gpkg(
    mc: MerginClient,
):
    project_name = "test_clean"
    source_gpkg_path = os.path.join(
        TEST_DATA_DIR,
        "base.gpkg",
    )
    db_schema_base = project_name + "_base"
    db_schema_main = project_name + "_main"
    full_project_name = WORKSPACE + "/" + project_name
    sync_project_dir = os.path.join(
        TMP_DIR,
        project_name + "_dbsync",
    )

    connection = {
        "driver": "postgres",
        "conn_info": DB_CONNINFO,
        "modified": db_schema_main,
        "base": db_schema_base,
        "mergin_project": full_project_name,
        "sync_file": "test_sync.gpkg",
    }

    config.update(
        {
            "GEODIFF_EXE": GEODIFF_EXE,
            "WORKING_DIR": sync_project_dir,
            "MERGIN__USERNAME": API_USER,
            "MERGIN__PASSWORD": USER_PWD,
            "MERGIN__URL": SERVER_URL,
            "CONNECTIONS": [connection],
            "init_from": "gpkg",
        }
    )

    conn = psycopg2.connect(DB_CONNINFO)

    # we can run clean even before init
    dbsync_clean(mc)

    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )

    # edit sync GPKG and push to server
    con = sqlite3.connect(
        os.path.join(
            sync_project_dir,
            project_name,
            "test_sync.gpkg",
        )
    )
    cur = con.cursor()
    cur.execute('ALTER TABLE simple ADD COLUMN "new_field" TEXT;')
    cur.execute("CREATE TABLE new_table (id INTEGER PRIMARY KEY, number INTEGER DEFAULT 0);")
    cur.execute("INSERT INTO new_table (number) VALUES (99);")
    con.commit()
    con.close()
    mc.push_project(
        os.path.join(
            sync_project_dir,
            project_name,
        )
    )

    # replace it locally back with previous version - so there is mismatch, on server there is a column, that does not exist locally
    os.remove(
        os.path.join(
            sync_project_dir,
            project_name,
            "test_sync.gpkg",
        )
    )
    shutil.copy(
        source_gpkg_path,
        os.path.join(
            sync_project_dir,
            project_name,
            "test_sync.gpkg",
        ),
    )

    # try init then pull and push, causing geodiff failed error
    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc)
        dbsync_pull(mc)
        dbsync_push(mc)
    assert "geodiff failed" in str(err.value)

    # prior to dbsync_clean everything exists
    assert _check_schema_exists(
        conn,
        db_schema_base,
    )
    assert _check_schema_exists(
        conn,
        db_schema_main,
    )
    assert pathlib.Path(config.working_dir).exists()

    dbsync_clean(mc)

    # after the dbsync_clean nothing exists
    assert pathlib.Path(config.working_dir).exists() is False
    assert (
        _check_schema_exists(
            conn,
            db_schema_base,
        )
        is False
    )
    assert (
        _check_schema_exists(
            conn,
            db_schema_main,
        )
        is False
    )

    # make sure that running the clean second time does not cause issue
    dbsync_clean(mc)

    # after clean we can init
    init_sync_from_geopackage(
        mc,
        project_name,
        source_gpkg_path,
    )

    # test that after clean everything works
    dbsync_init(mc)
    dbsync_pull(mc)
    dbsync_push(mc)
