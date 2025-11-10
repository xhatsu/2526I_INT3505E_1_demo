# project/auth.py
import oracledb
import jwt
from datetime import datetime, timedelta
from flask import Blueprint, request, current_app, Response, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from .db import get_db
from .helper import * # Assumes helper.py is now in the same directory

# Create a Blueprint. 'auth' is the name, __name__ is the import name.
bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['POST'])
def register():
    """Registers a new user."""
    data = request.get_json()
    if not data or not all(k in data for k in ('name', 'email', 'password')):
        return create_response({"error": "Missing name, email, or password"}, 400)

    name = data['name']
    email = data['email']
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')

    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                'INSERT INTO users (name, email, password_hash) VALUES (:1, :2, :3)',
                (name, email, hashed_password)
            )
            db.commit()
    except oracledb.IntegrityError as e:
        db.rollback()
        return create_response({"error": f"Database Integrity Error: {e}"}, 409)
    except oracledb.Error as e:
        db.rollback()
        return create_response({"error": f"Database error: {e}"}, 500)

    return create_response({"message": "User registered successfully"}, 201)


@bp.route('/login', methods=['POST'])
def login():
    """Logs in a user and returns a JWT."""
    data = request.get_json()
    if not data or not all(k in data for k in ('email', 'password')):
        return create_response({"error": "Missing email or password"}, 400)

    email = data['email']
    password = data['password']
    db = get_db()

    with db.cursor() as cursor:
        cursor.execute('SELECT id, password_hash FROM users WHERE email = :1', (email,))
        user_list = rows_to_dicts(cursor)

    if not user_list:
        return create_response({"message": "Authentication failed"}, 401)
    
    user = user_list[0]

    if check_password_hash(user['password_hash'], password):
        payload = {
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow(),
            'sub': str(user['id'])
        }
        token = jwt.encode(
            payload,
            # Use current_app to access app config from within a blueprint
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        return create_response({'token': token}, 200,)

    return create_response({"message": "Authentication failed"}, 401)