# project/__init__.py
import os
from flask import Flask

def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # --- Configuration ---
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY'),
        # Add other app-wide configs here
    )

    if not app.config['SECRET_KEY']:
        raise RuntimeError("SECRET_KEY environment variable is not set.")

    if test_config:
        app.config.from_mapping(test_config)
    
    # --- Initialize Database ---
    from . import db
    db.init_app(app)

    # --- Register Blueprints ---
    
    # Auth Blueprint (for /register, /login)
    from . import auth
    # All routes in auth.py will be prefixed with /api/v1
    app.register_blueprint(auth.bp, url_prefix='/api/v1') 

    # Users Blueprint (for /users/...)
    from . import users
    # All routes in users.py will be prefixed with /api/v1/users
    app.register_blueprint(users.bp, url_prefix='/api/v1/users')

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
    def health_check():
        """A simple health check endpoint."""
        return {"status": "ok"}, 200

    return app