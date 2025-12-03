# project/__init__.py
import os
from flask import Flask
from .db import get_db
from .logger import api_logger, rate_limit_logger

def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # --- Configuration ---
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY'),
        # Add other app-wide configs here
    )

    app.config['SERVER_NAME'] = 'http:/152.69.214.109'

    if not app.config['SECRET_KEY']:
        raise RuntimeError("SECRET_KEY environment variable is not set.")

    if test_config:
        app.config.from_mapping(test_config)
    
    # --- Initialize Prometheus Metrics ---
    from .metrics import REGISTRY, record_request_start, record_request_end
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    
    @app.before_request
    def before_request():
        """Record metrics before request processing."""
        endpoint = request.endpoint or 'unknown'
        record_request_start(endpoint)
    
    @app.after_request
    def after_request(response):
        """Record metrics after request processing."""
        endpoint = request.endpoint or 'unknown'
        record_request_end(response.status_code, endpoint)
        return response
    
    # --- Initialize Rate Limiter with Redis ---
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    from redis import Redis
    from flask import request
    
    redis_host = os.environ.get('REDIS_HOST', 'localhost')
    redis_port = int(os.environ.get('REDIS_PORT', 6379))
    redis_db = int(os.environ.get('REDIS_DB', 0))
    
    try:
        redis_client = Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True,
            socket_connect_timeout=5
        )
        # Test connection
        redis_client.ping()
        api_logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
    except Exception as e:
        api_logger.error(f"Failed to connect to Redis: {e}")
        redis_client = None
    
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        storage_uri=f"redis://{redis_host}:{redis_port}/{redis_db}" if redis_client else None,
        default_limits=["200 per day", "50 per hour"]
    )
    
    # Store limiter in app context
    app.limiter = limiter
    
    # Define metrics endpoint with rate limit exemption
    @app.route('/metrics')
    @limiter.exempt
    def metrics():
        """Prometheus metrics endpoint."""
        return generate_latest(REGISTRY), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    
    # --- Initialize Database ---
    from . import db
    db.init_app(app)

    # --- Register Blueprints ---
    
    # Auth Blueprint (for /register, /login)
    from . import auth
    # All routes in auth.py will be prefixed with /api/v1
    app.register_blueprint(auth.bp, url_prefix='/api/v1') 
    # All routes in auth_v2.py will be prefixed with /api/v2
    from . import auth_v2
    app.register_blueprint(auth_v2.bp, url_prefix='/api/v2')

    # Users Blueprint (for /users/...)
    from . import users
    # All routes in users.py will be prefixed with /api/v1/users
    app.register_blueprint(users.bp, url_prefix='/api/v1/users')
    # All routes in users_v2.py will be prefixed with /api/v2/users
    from . import users_v2
    app.register_blueprint(users_v2.bp, url_prefix='/api/v2/users')
    
    # Books Blueprint (for /books/...)
    from . import books
    # All routes in books.py will be prefixed with /api/v1/books
    app.register_blueprint(books.bp, url_prefix='/api/v1/books')
    from . import books_v2
    # All routes in books_v2.py will be prefixed with /api/v2/books
    app.register_blueprint(books_v2.bp, url_prefix='/api/v2/books')

    # Library Blueprint (for /borrow, /return, ...)
    from . import library
    # All routes in library.py will be prefixed with /api/v1
    app.register_blueprint(library.bp, url_prefix='/api/v1')
    from . import library_v2
    # All routes in library_v2.py will be prefixed with /api/v2
    app.register_blueprint(library_v2.bp, url_prefix='/api/v2')

    @app.route('/health')
    @limiter.exempt
    def health_check():
        """A simple health check endpoint."""
        db = get_db()
        api_logger.info("Health check called")
        return {"status": "ok"}, 200
    return app