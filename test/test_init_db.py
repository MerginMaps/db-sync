import os
import shutil
import sqlite3


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
)

from .conftest import (
    DB_CONNINFO,
    init_sync_from_db,
    name_project_dir,
    name_db_schema_main,
    name_db_schema_base,
    complete_project_name,
    path_sync_gpkg,
    path_test_data,
)


def test_init_from_db(
    mc: MerginClient,
):
    project_name = "test_db_init"
    project_full_name = complete_project_name(project_name)
    project_dir = name_project_dir(project_name)
    db_schema_main = name_db_schema_main(project_name)
    db_schema_base = name_db_schema_base(project_name)

    path_synced_gpkg = project_dir + "/" + path_sync_gpkg()

    init_sync_from_db(mc, project_name)

    # test that database schemas are created + tables are populated
    conn = psycopg2.connect(DB_CONNINFO)
    cur = conn.cursor()

    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_main)).as_string(conn))
    assert cur.fetchone()[0] == 3

    cur.execute(sql.SQL("SELECT count(*) from {}.simple").format(sql.Identifier(db_schema_base)).as_string(conn))
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


def test_local_changes_to_db(
    mc: MerginClient,
):
    project_name = "test_mergin_changes_to_db"
    project_full_name = complete_project_name(project_name)
    project_dir = name_project_dir(project_name)
    db_schema_main = name_db_schema_main(project_name)
    db_schema_base = name_db_schema_base(project_name)

    path_synced_gpkg = project_dir + "/" + path_sync_gpkg()

    init_sync_from_db(mc, project_name)

    # connecto to db
    conn = psycopg2.connect(DB_CONNINFO)
    cur = conn.cursor()

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


def test_db_changes_to_mergin(
    mc: MerginClient,
):
    project_name = "test_db_changes_mergin"
    project_full_name = complete_project_name(project_name)
    project_dir = name_project_dir(project_name)
    db_schema_main = name_db_schema_main(project_name)
    db_schema_base = name_db_schema_base(project_name)

    init_sync_from_db(mc, project_name)

    # connecto to db
    conn = psycopg2.connect(DB_CONNINFO)
    cur = conn.cursor()

    cur.execute(
        f'INSERT INTO "{db_schema_main}"."simple" ("wkb_geometry" , "fid", "name", "rating") VALUES (\'0101000020E61000009CB92A724E60E7BFE0FDF1F774B6A53F\', 4, \'new feature\', 4);'
    )
    cur.execute("COMMIT")

    dbsync_pull(mc)
    dbsync_push(mc)

    mc.download_project(project_full_name, project_dir)

    # look at changes in in GPKG
    gpkg_conn = sqlite3.connect(project_dir + "/" + path_sync_gpkg())
    gpkg_cur = gpkg_conn.cursor()
    gpkg_cur.execute("SELECT COUNT(*) FROM simple")
    assert gpkg_cur.fetchone()[0] == 4
