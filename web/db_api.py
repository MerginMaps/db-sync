"""
PostgreSQL connection testing utilities for the web interface.
"""

import psycopg2


def test_connection(conn_info: str) -> dict:
    """
    Test PostgreSQL connection and return database info.

    Args:
        conn_info: PostgreSQL connection string

    Returns:
        dict with 'success' boolean and connection details or 'error' string
    """
    conn = None
    try:
        conn = psycopg2.connect(conn_info)
        cur = conn.cursor()

        # Get database name
        cur.execute("SELECT current_database()")
        db_name = cur.fetchone()[0]

        # Get PostgreSQL version
        cur.execute("SELECT version()")
        pg_version = cur.fetchone()[0]

        # Check for PostGIS extension
        cur.execute("""
            SELECT extversion FROM pg_extension WHERE extname = 'postgis'
        """)
        postgis_row = cur.fetchone()
        has_postgis = postgis_row is not None
        postgis_version = postgis_row[0] if has_postgis else None

        # List schemas
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY schema_name
        """)
        schemas = [row[0] for row in cur.fetchall()]

        cur.close()
        conn.close()

        return {
            "success": True,
            "database": db_name,
            "pg_version": pg_version,
            "has_postgis": has_postgis,
            "postgis_version": postgis_version,
            "schemas": schemas
        }

    except psycopg2.OperationalError as e:
        return {
            "success": False,
            "error": f"Connection failed: {str(e)}"
        }
    except psycopg2.Error as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def check_schema_exists(conn_info: str, schema_name: str) -> dict:
    """
    Check if a schema exists in the database.

    Args:
        conn_info: PostgreSQL connection string
        schema_name: Name of schema to check

    Returns:
        dict with 'success' boolean and 'exists' boolean or 'error' string
    """
    conn = None
    try:
        conn = psycopg2.connect(conn_info)
        cur = conn.cursor()

        cur.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata
                WHERE schema_name = %s
            )
        """, (schema_name,))
        exists = cur.fetchone()[0]

        cur.close()
        conn.close()

        return {
            "success": True,
            "exists": exists,
            "schema": schema_name
        }

    except psycopg2.Error as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
