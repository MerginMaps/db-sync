import pytest
import os
import tempfile
import shutil

import psycopg2
import psycopg2.extensions
from psycopg2 import sql

from mergin import MerginClient, ClientError

from dbsync import dbsync_init
from config import config

GEODIFF_EXE = os.environ.get('TEST_GEODIFF_EXE')
DB_CONNINFO = os.environ.get('TEST_DB_CONNINFO')
SERVER_URL = os.environ.get('TEST_MERGIN_URL')
API_USER = os.environ.get('TEST_API_USERNAME')
USER_PWD = os.environ.get('TEST_API_PASSWORD')
WORKSPACE = os.environ.get('TEST_API_WORKSPACE')
TMP_DIR = tempfile.gettempdir()
TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_data')


def _reset_config(project_name: str = "mergin"):
    """ helper to reset config settings to ensure valid config """
    db_schema_main = project_name + '_main'
    db_schema_base = project_name + '_base'
    full_project_name = WORKSPACE + "/" + project_name

    config.update({
        'MERGIN__USERNAME': API_USER,
        'MERGIN__PASSWORD': USER_PWD,
        'MERGIN__URL': SERVER_URL,
        'init_from': "gpkg",
        'CONNECTIONS': [{"driver": "postgres",
                         "conn_info": DB_CONNINFO,
                         "modified": db_schema_main,
                         "base": db_schema_base,
                         "mergin_project": full_project_name,
                         "sync_file": "test_sync.gpkg"}]
    })


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
        connection = {"driver": "postgres",
                      "conn_info": DB_CONNINFO,
                      "modified": db_schema_main,
                      "base": db_schema_base,
                      "mergin_project": full_project_name,
                      "sync_file": "test_sync.gpkg",
                      "skip_tables": ignored_tables}
    else:
        connection = {"driver": "postgres",
                      "conn_info": DB_CONNINFO,
                      "modified": db_schema_main,
                      "base": db_schema_base,
                      "mergin_project": full_project_name,
                      "sync_file": "test_sync.gpkg"}

    config.update({
        'GEODIFF_EXE': GEODIFF_EXE,
        'WORKING_DIR': sync_project_dir,
        'MERGIN__USERNAME': API_USER,
        'MERGIN__PASSWORD': USER_PWD,
        'MERGIN__URL': SERVER_URL,
        'CONNECTIONS': [connection],
        'init_from': "gpkg"
    })

    dbsync_init(mc)


@pytest.fixture(scope='function')
def mc():
    assert SERVER_URL and API_USER and USER_PWD
    #assert SERVER_URL and SERVER_URL.rstrip('/') != 'https://app.merginmaps.com/' and API_USER and USER_PWD
    return MerginClient(SERVER_URL, login=API_USER, password=USER_PWD)


@pytest.fixture(scope='function')
def db_connection() -> psycopg2.extensions.connection:
    return psycopg2.connect(DB_CONNINFO)
