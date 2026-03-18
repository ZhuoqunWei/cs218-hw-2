import os
import psycopg2
import psycopg2.extras


def _dsn():
    return (
        f"host={os.environ['DATABASE_HOST']} "
        f"port={os.environ.get('DATABASE_PORT', '5432')} "
        f"user={os.environ['DATABASE_USER']} "
        f"password={os.environ['DATABASE_PASSWORD']} "
        f"dbname={os.environ['DATABASE_NAME']} "
        f"sslmode={os.environ.get('DATABASE_SSLMODE', 'prefer')}"
    )


def get_db():
    conn = psycopg2.connect(_dsn(), cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def check_db():
    try:
        conn = get_db()
        conn.close()
        return True
    except Exception:
        return False
