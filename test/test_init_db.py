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

from dbsync import dbsync_pull, dbsync_push, dbsync_init, config, DbSyncError

from .conftest import (
    GEODIFF_EXE,
    API_USER,
    USER_PWD,
    SERVER_URL,
    DB_CONNINFO,
    WORKSPACE,
    init_sync_from_db,
    name_project_dir,
    name_db_schema_main,
    name_db_schema_base,
    complete_project_name,
    filename_sync_gpkg,
    path_test_data,
    cleanup,
    cleanup_db,
    name_project_sync_dir,
)


def test_init_from_db(mc: MerginClient, db_connection):
    """Test that init from db happens correctly, with the tables in sync GPKG created a populated correctly"""
    project_name = "test_db_init"
    project_full_name = complete_project_name(project_name)
    project_dir = name_project_dir(project_name)
    db_schema_main = name_db_schema_main(project_name)
    db_schema_base = name_db_schema_base(project_name)

    path_synced_gpkg = project_dir + "/" + filename_sync_gpkg()

    init_sync_from_db(mc, project_name)

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
    db_schema_main = name_db_schema_main(project_name)
    db_schema_base = name_db_schema_base(project_name)

    path_synced_gpkg = project_dir + "/" + filename_sync_gpkg()

    init_sync_from_db(mc, project_name)

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
    db_schema_main = name_db_schema_main(project_name)
    db_schema_base = name_db_schema_base(project_name)

    init_sync_from_db(mc, project_name)

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


def test_missing_table(mc: MerginClient, db_connection):
    project_name = "test_db_missing_table"
    project_full_name = complete_project_name(project_name)
    project_dir = name_project_dir(project_name)
    db_schema_main = name_db_schema_main(project_name)
    db_schema_base = name_db_schema_base(project_name)
    sync_project_dir = name_project_sync_dir(project_name)  # used by dbsync

    cleanup(
        mc,
        project_full_name,
        [
            project_dir,
            sync_project_dir,
        ],
    )
    cleanup_db(
        db_connection,
        db_schema_base,
        db_schema_main,
    )

    with open(
        path_test_data("create_base.sql"),
        encoding="utf-8",
    ) as file:
        base_table_dump = file.read()

    base_table_dump = base_table_dump.replace("default-schema-name", db_schema_main)
    base_table_dump = base_table_dump.replace("default-table-name", "simple")

    cur = db_connection.cursor()
    cur.execute(base_table_dump)

    # prepare a new Mergin Maps project
    mc.create_project(
        project_name,
        namespace=WORKSPACE,
    )

    connection = {
        "driver": "postgres",
        "conn_info": DB_CONNINFO,
        "modified": "non_existing_schema",
        "base": db_schema_base,
        "mergin_project": project_full_name,
        "sync_file": filename_sync_gpkg(),
    }

    config.update(
        {
            "GEODIFF_EXE": GEODIFF_EXE,
            "WORKING_DIR": sync_project_dir,
            "MERGIN__USERNAME": API_USER,
            "MERGIN__PASSWORD": USER_PWD,
            "MERGIN__URL": SERVER_URL,
            "CONNECTIONS": [connection],
            "init_from": "db",
        }
    )

    with pytest.raises(DbSyncError) as err:
        dbsync_init(mc)
    assert "The 'modified' schema does not exist" in str(err.value)
