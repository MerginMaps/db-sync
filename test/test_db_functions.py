import psycopg2

from dbsync import _check_postgis_available, _try_install_postgis


def test_check_postgis_available(db_connection: psycopg2.connection):
    cur = db_connection.cursor()

    assert _check_postgis_available(db_connection)

    cur.execute("DROP EXTENSION IF EXISTS postgis CASCADE;")

    assert _check_postgis_available(db_connection) is False


def test_try_install_postgis(db_connection: psycopg2.connection):
    cur = db_connection.cursor()

    cur.execute("DROP EXTENSION IF EXISTS postgis CASCADE;")

    assert _check_postgis_available(db_connection) is False

    _try_install_postgis(db_connection)

    assert _check_postgis_available(db_connection)
