# project/db.py
import os
import oracledb
from flask import g, current_app

def get_db():
    """Get a pooled connection for the current request."""
    if 'db' not in g:
        # Get the pool from the application context
        g.db = current_app.pool.acquire()
    return g.db


def close_db(e=None):
    """Release the connection back to the pool after each request."""
    db = g.pop('db', None)
    if db is not None:
        db.close() # returns to pool, not truly closed


def init_app(app):
    """Initialize the database pool and register teardown."""
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    CONNECT_STRING = os.getenv("CONNECT_STRING")

    if not DB_USER or not DB_PASSWORD or not CONNECT_STRING:
        raise RuntimeError("Database configuration environment variables are not set.")

    try:
        pool = oracledb.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=CONNECT_STRING,
            min=1,
            max=5,
            increment=1,
            timeout=60
        )
        # Attach the pool to the app object
        app.pool = pool
        print("Database connection pool created successfully.")
    except oracledb.Error as e:
        print("Error creating connection pool:", e)
        exit(1)

    # Register the close_db function to be called on app context teardown
    app.teardown_appcontext(close_db)