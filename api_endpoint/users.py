# project/users.py
import oracledb
import hashlib
import json
from flask import Blueprint, request, Response, url_for
from math import ceil
from .db import get_db
from .helper import * # Assumes helper.py is now in the same directory

bp = Blueprint('users', __name__)

@bp.route('', methods=['GET'])
def get_all_users():
    """Fetches all users."""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        if page < 1 or limit < 1:
            raise ValueError    
    except ValueError:
        return create_response({"error": "Invalid 'page' or 'limit'. Must be positive integers."}, 400)

    offset = (page - 1) * limit
    db = get_db()
    
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM users')
            total_items = cursor.fetchone()[0]
            if total_items == 0:
                return create_response({'data': [], 'total_items': 0}, 200)

            total_pages = ceil(total_items / limit)

            query = """
                SELECT * FROM users 
                ORDER BY id 
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """
            cursor.execute(query, {'offset': offset, 'limit': limit})
            users = rows_to_dicts(cursor)
            
            # This helper MUST be updated. See notes below.
            users = [add_user_links(user) for user in users]

            response_data = {
                'total_items': total_items,
                'total_pages': total_pages,
                'current_page': page,
                'data': users
            }

            # url_for MUST be namespaced with the blueprint name: 'users.get_all_users'
            if page < total_pages:
                response_data['next_page_url'] = url_for('users.get_all_users', page=page + 1, limit=limit, _external=True)
            if page > 1:
                response_data['prev_page_url'] = url_for('users.get_all_users', page=page - 1, limit=limit, _external=True)

            header = {'Cache-Control': 'public, max-age=300'}
            return create_response(response_data, 200, header)
            
    except oracledb.Error as e:
        return create_response({"error": f"Database error: {e}"}, 500)


@bp.route('/<int:user_id>', methods=['GET'])
def get_user_by_id(user_id):
    """Fetches a single user by their ID."""
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('SELECT * FROM users WHERE id = :1', (user_id,))
        user_list = rows_to_dicts(cursor)

    if len(user_list) == 0:
        return create_response({"error": "User not found"}, 404)
    
    # This helper MUST be updated. See notes below.
    user = add_user_links(user_list[0])

    if not user:
        return create_response({"error": "User not found"}, 404)

    user_json_str = json.dumps(user, sort_keys=True).encode('utf-8')
    etag = hashlib.sha1(user_json_str).hexdigest()

    if request.headers.get('If-None-Match') == etag:
        return Response(status=304)

    headers = {'ETag': etag}
    return create_response(user, 200, headers)


@bp.route('', methods=['POST'])
def add_user():
    """Adds a new user."""
    # ... (code for add_user is identical, no changes needed)
    data = request.get_json()
    if not data or 'name' not in data:
        return create_response({"error": "Missing required field: name"}, 400)

    name = data['name']
    db = get_db()
    try:
        with db.cursor() as cursor:
            new_id_var = cursor.var(oracledb.DB_TYPE_NUMBER)
            cursor.execute('INSERT INTO users (name) VALUES (:name) RETURNING id INTO :new_id',
                           {'name': name, 'new_id': new_id_var})
            new_user_id = int(new_id_var.getvalue()[0])
            db.commit()
            new_user = {"id": new_user_id, "name": name}
            return create_response(new_user, 201)
    except oracledb.IntegrityError:
        db.rollback()
        return create_response({"error": "User with this name already exists"}, 409)
    except oracledb.Error as e:
        db.rollback()
        return create_response({"error": f"Database error: {e}"}, 500)


@bp.route('/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Updates an existing user's details."""
    # ... (code for update_user is identical, no changes needed)
    db = get_db()
    data = request.get_json()
    if not data or 'name' not in data:
        return create_response({"error": "Missing required field: name"}, 400)

    name = data['name']
    try:
        with db.cursor() as cursor:
            cursor.execute('UPDATE users SET name = :1 WHERE id = :2', (name, user_id))
            if cursor.rowcount == 0:
                return create_response({"error": "User not found"}, 404)
            db.commit()

        with db.cursor() as cursor:
             cursor.execute('SELECT * FROM users WHERE id = :1', (user_id,))
             updated_user = rows_to_dicts(cursor)[0]
        return create_response(updated_user, 200)

    except oracledb.IntegrityError:
        db.rollback()
        return create_response({"error": "User with this name already exists"}, 409)
    except oracledb.Error as e:
        db.rollback()
        return create_response({"error": f"Database error: {e}"}, 500)


@bp.route('/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Deletes a user."""
    # ... (code for delete_user is identical, no changes needed)
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('DELETE FROM users WHERE id = :1', (user_id,))
        if cursor.rowcount == 0:
            return create_response({"error": "User not found"}, 404)
    db.commit()
    return create_response({"message": f"User with id {user_id} has been deleted."}, 200)


@bp.route('/<int:user_id>/history', methods=['GET'])
def get_user_borrow_history(user_id):
    """Retrieves the borrow history for a specific user."""
    db = get_db()

    with db.cursor() as cursor:
        cursor.execute('SELECT id FROM users WHERE id = :1', (user_id,))
        if not cursor.fetchone():
            return create_response({"error": "User not found"}, 404)

    query = """
        SELECT
            br.id, br.book_id, br.user_id,
            b.title as book_title,
            br.borrow_date, br.return_date
        FROM borrow_records br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = :1
        ORDER BY br.borrow_date DESC
    """
    with db.cursor() as cursor:
        cursor.execute(query, (user_id,))
        records = rows_to_dicts(cursor)

    if len(records) == 0:
        return create_response({"message": "No borrow history found for this user"}, 201)

    # This helper MUST be updated. See notes below.
    # records = [add_borrow_record_links(rec) for rec in records]

    return create_response(records, 200)