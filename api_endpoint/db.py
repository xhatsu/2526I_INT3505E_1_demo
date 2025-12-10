# project/db.py
import os
import oracledb
from flask import g, current_app
from .circuit_breaker import db_breaker
from .logger import api_logger

def get_db():
    """Get a pooled connection for the current request with circuit breaker protection."""
    if 'db' not in g:
        try:
            # Use circuit breaker to protect database connection
            g.db = db_breaker.call(current_app.pool.acquire)
        except Exception as e:
            api_logger.error(f"Failed to acquire database connection: {str(e)}")
            raise
    return g.db


def close_db(e=None):
    """Release the connection back to the pool after each request."""
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()  # returns to pool, not truly closed
        except Exception as ex:
            api_logger.error(f"Error closing database connection: {str(ex)}")


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
        api_logger.info("Database connection pool created successfully.")
    except oracledb.Error as e:
        api_logger.error(f"Error creating connection pool: {e}")
        exit(1)

    # Register the close_db function to be called on app context teardown
    app.teardown_appcontext(close_db)