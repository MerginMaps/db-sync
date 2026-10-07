import os
import shutil
import sqlite3
import pytest


import psycopg2
from psycopg2 import (
    sql,
)

from mergin import (
    MerginClient,
)

from dbsync import (
    dbsync_pull,
    dbsync_push,
    config,
    DbSyncError,
    dbsync_init,
    _get_db_project_comment,
    _set_db_project_comment,
)

from .conftest import (
    GEODIFF_EXE,
    API_USER,
    USER_PWD,
    SERVER_URL,
    DB_CONNINFO,
    WORKSPACE,
    init_sync_from_db,
    name_project_dir,
    complete_project_name,
    filename_sync_gpkg,
    path_test_data,
    name_project_sync_dir,
)


def test_init_from_db(mc: MerginClient, db_connection):
    """Test that init from db happens correctly, with the tables in sync GPKG created a populated correctly"""
    project_name = "test_db_init"
    project_full_name = complete_project_name(project_name)
    project_dir = name_project_dir(project_name)
    db_schema_main = "test_init_from_db_main"
    db_schema_base = "test_init_from_db_base"

    path_synced_gpkg = project_dir + "/" + filename_sync_gpkg()

    init_sync_from_db(mc, project_name, path_test_data("create_base.sql"))

    # test that database schemas are created + tables are populated
    cur = db_connection.cursor()

    cur.execute(
        sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(db_connection)
    )
    assert cur.fetchone()[0] == 3

    cur.execute(
        sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_base)).as_string(db_connection)
    )
    assert cur.fetchone()[0] == 3

    # download project and validate that the path synced file exist
    mc.download_project(project_full_name, project_dir)
    assert os.path.exists(path_synced_gpkg)

    # connect to sync file
    gpkg_conn = sqlite3.connect(path_synced_gpkg)
    gpkg_cur = gpkg_conn.cursor()

    # validate that simple table exists
    gpkg_cur.execute(
        "SELECT name FROM sqlite_schema WHERE type ='table' AND "
        " name NOT LIKE 'sqlite_%' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'rtree_%';"
    )
    assert gpkg_cur.fetchone()[0] == "simple"

    # validate number of elements in simple
    gpkg_cur.execute("SELECT count(*) FROM simple")
    assert gpkg_cur.fetchone()[0] == 3


def test_with_local_changes(mc: MerginClient, db_connection):
    """Test that after init and local changes the changes are correctly pushed to database"""
    project_name = "test_mergin_changes_to_db"
    project_full_name = complete_project_name(project_name)
    project_dir = name_project_dir(project_name)
    db_schema_main = "test_init_from_db_main"
    db_schema_base = "test_init_from_db_base"

    path_synced_gpkg = project_dir + "/" + filename_sync_gpkg()

    init_sync_from_db(mc, project_name, path_test_data("create_base.sql"))

    cur = db_connection.cursor()

    # check that there are 3 features prior to changes
    cur.execute(f'SELECT COUNT(*) from {db_schema_main}."simple"')
    assert cur.fetchone()[0] == 3

    mc.download_project(project_full_name, project_dir)

    # make changes in GPKG
    shutil.copy(path_test_data("inserted_point_from_db.gpkg"), path_synced_gpkg)

    # push project
    mc.push_project(project_dir)

    # run sync
    dbsync_pull(mc)
    dbsync_push(mc)

    # check that new feature was added
    cur.execute(f'SELECT COUNT(*) from {db_schema_main}."simple"')
    assert cur.fetchone()[0] == 4


def test_with_db_changes(mc: MerginClient, db_connection):
    """Test that after init and DB changes the changes are correctly pulled to the MM GPKG"""
    project_name = "test_db_changes_mergin"
    project_full_name = complete_project_name(project_name)
    project_dir = name_project_dir(project_name)
    db_schema_main = "test_init_from_db_main"
    db_schema_base = "test_init_from_db_base"

    init_sync_from_db(mc, project_name, path_test_data("create_base.sql"))

    cur = db_connection.cursor()

    cur.execute(
        f'INSERT INTO "{db_schema_main}"."simple" ("wkb_geometry" , "fid", "name", "rating") VALUES (\'0101000020E61000009CB92A724E60E7BFE0FDF1F774B6A53F\', 4, \'new feature\', 4);'
    )
    cur.execute("COMMIT")

    dbsync_pull(mc)
    dbsync_push(mc)

    mc.download_project(project_full_name, project_dir)

    # look at changes in in GPKG
    gpkg_conn = sqlite3.connect(project_dir + "/" + filename_sync_gpkg())
    gpkg_cur = gpkg_conn.cursor()
    gpkg_cur.execute("SELECT COUNT(*) FROM simple")
    assert gpkg_cur.fetchone()[0] == 4


def test_missing_table(mc: MerginClient):
    """Test that if the schema is missing in DB the sync init raises correct DbSyncError"""
    project_name = "test_db_missing_table"

    with pytest.raises(DbSyncError) as err:
        init_sync_from_db(mc, project_name, path_test_data("create_another_schema.sql"))

    assert "The 'modified' schema does not exist" in str(err.value)


def test_mm_project_change(mc: MerginClient, db_connection):
    """Test that after init and local changes the changes are correctly pushed to database"""
    project_name = "test_project_change"
    project_full_name = complete_project_name(project_name)
    project_dir = name_project_dir(project_name)
    db_schema_main = "test_init_from_db_main"
    db_schema_base = "test_init_from_db_base"

    path_synced_gpkg = project_dir + "/" + filename_sync_gpkg()

    init_sync_from_db(mc, project_name, path_test_data("create_base.sql"))

    cur = db_connection.cursor()

    # check that there are 3 features prior to changes
    cur.execute(f'SELECT COUNT(*) from {db_schema_main}."simple"')
    assert cur.fetchone()[0] == 3

    mc.download_project(project_full_name, project_dir)

    # make changes in GPKG to create new version of the project
    shutil.copy(path_test_data("inserted_point_from_db.gpkg"), path_synced_gpkg)

    # push project
    mc.push_project(project_dir)

    # run sync
    dbsync_pull(mc)
    dbsync_push(mc)

    # check that new feature was added
    cur.execute(f'SELECT COUNT(*) from {db_schema_main}."simple"')
    assert cur.fetchone()[0] == 4

    project_name = "test_project_change_2"
    project_full_name = complete_project_name(project_name)
    project_dir = name_project_dir(project_name)
    mc.create_project_and_push(project_full_name, project_dir)

    # change config to new project
    config.update(
        {
            "CONNECTIONS": [
                {
                    "driver": "postgres",
                    "conn_info": DB_CONNINFO,
                    "modified": db_schema_main,
                    "base": db_schema_base,
                    "mergin_project": project_full_name,
                    "sync_file": filename_sync_gpkg(),
                }
            ]
        }
    )

    # run init
    with pytest.raises(
        DbSyncError, match="Mergin Maps project ID doesn't match Mergin Maps project ID stored in the database"
    ):
        dbsync_init(mc)


def test_init_with_legacy_comment_without_project_id(mc: MerginClient, db_connection):
    """Test that init does not fail on base schema comment without project ID (created by older versions of db-sync)
    and that the project ID is added to the comment by next pull"""
    project_name = "test_legacy_comment"
    project_full_name = complete_project_name(project_name)
    project_dir = name_project_dir(project_name)
    sync_project_dir = name_project_sync_dir(project_name)
    db_schema_main = "test_init_from_db_main"
    db_schema_base = "test_init_from_db_base"

    init_sync_from_db(mc, project_name, path_test_data("create_base.sql"))

    # comment created by the current version contains project ID
    comment = _get_db_project_comment(db_connection, db_schema_base)
    server_project_id = mc.project_info(project_full_name)["id"]
    assert comment["project_id"] == server_project_id

    # simulate comment created by older version of db-sync - without project ID
    _set_db_project_comment(db_connection, db_schema_base, comment["name"], comment["version"])
    comment = _get_db_project_comment(db_connection, db_schema_base)
    assert "project_id" not in comment

    # init with existing working directory must not fail
    dbsync_init(mc)

    # init without working directory (e.g. after upgrade of docker container) must not fail
    shutil.rmtree(sync_project_dir)
    dbsync_init(mc)
    assert os.path.exists(sync_project_dir)
    comment = _get_db_project_comment(db_connection, db_schema_base)
    assert "project_id" not in comment

    # create new version of the project on server
    mc.download_project(project_full_name, project_dir)
    shutil.copy(path_test_data("inserted_point_from_db.gpkg"), os.path.join(project_dir, filename_sync_gpkg()))
    mc.push_project(project_dir)

    # after pulling the latest changes, the project ID should be existing
    dbsync_pull(mc)
    comment = _get_db_project_comment(db_connection, db_schema_base)
    assert comment["project_id"] == server_project_id
