import oracledb
import os
import hashlib
import jwt
import json
from dotenv import load_dotenv
from flask import Flask, request, g, jsonify, Response, url_for
from datetime import datetime, timedelta
from functools import wraps
from helper import *
from math import ceil
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
# --- Configuration ---

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
CONNECT_STRING = os.getenv("CONNECT_STRING")

if not DB_USER or not DB_PASSWORD or not CONNECT_STRING:
    raise RuntimeError("Database configuration environment variables are not set.")

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise RuntimeError("SECRET_KEY environment variable is not set.")

# --- Connection Pool Setup ---
try:
    pool = oracledb.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=CONNECT_STRING,
        min=1,          # keep 1 idle connection
        max=5,          # up to 5 concurrent connections
        increment=1,    # grow by 1 when needed
        timeout=60      # close unused after 60s
    )
except oracledb.Error as e:
    print("Error creating connection pool:", e)
    # Exit if the pool cannot be created
    exit(1)


# --- Database Management ---
def get_db():
    """Get a pooled connection for the current request."""
    if 'db' not in g:
        g.db = pool.acquire()
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    """Release the connection back to the pool after each request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()  # returns to pool, not truly closed


# --- Authentication Endpoints ---

@app.route('/register', methods=['POST'])
def register():
    """Registers a new user."""
    data = request.get_json()
    if not data or not all(k in data for k in ('name', 'email', 'password')):
        return create_response({"error": "Missing name, email, or password"}, 400)

    name = data['name']
    email = data['email']
    # Hash the password for security
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


@app.route('/login', methods=['POST'])
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
        # Password is correct, generate JWT
        payload = {
            'exp': datetime.utcnow() + timedelta(hours=24), # Expiration time
            'iat': datetime.utcnow(), # Issued at time
            'sub': user['id'] # Subject (the user's ID)
        }
        token = jwt.encode(
            payload,
            app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        return create_response({'token': token}, 200,)

    return create_response({"message": "Authentication failed"}, 401)

# --- User Management Endpoints ---

@app.route('/users', methods=['GET'])
def get_all_users():
    """Fetches all users."""

    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        if page < 1 or limit < 1:
            raise ValueError    
    except ValueError:
        return create_response({"error": "Invalid 'page' or 'limit'. Must be positive integers."}, 400)

    # 2. Calculate the offset for the SQL query
    offset = (page - 1) * limit

    db = get_db()
    try:
        with db.cursor() as cursor:
            # Get the total number of books to calculate total pages
            cursor.execute('SELECT COUNT(*) FROM users')
            total_items = cursor.fetchone()[0]
            if total_items == 0:
                return create_response({'data': [], 'total_items': 0}, 200)

            total_pages = ceil(total_items / limit)

            # 3. Fetch the requested page of books using OFFSET and FETCH
            # SQL syntax for pagination
            query = """
                SELECT * FROM users 
                ORDER BY id 
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """
            cursor.execute(query, {'offset': offset, 'limit': limit})
            users = rows_to_dicts(cursor)
            users = [add_user_links(user) for user in users]
    
    
        # 4. Build a response object that includes pagination metadata
        response_data = {
            'total_items': total_items,
            'total_pages': total_pages,
            'current_page': page,
            'data': users
        }

        # Add HATEOAS links for next and previous pages
        if page < total_pages:
            response_data['next_page_url'] = url_for('get_all_users', page=page + 1, limit=limit, _external=True)
        if page > 1:
            response_data['prev_page_url'] = url_for('get_all_users', page=page - 1, limit=limit, _external=True)

        header = {'Cache-Control': 'public, max-age=300'}

        return create_response(response_data, 200, header)
    except oracledb.Error as e:
        return create_response({"error": f"Database error: {e}"}, 500)


@app.route('/users/<int:user_id>', methods=['GET'])
def get_user_by_id(user_id):
    """Fetches a single user by their ID."""
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('SELECT * FROM users WHERE id = :1', (user_id,))
        user_list = rows_to_dicts(cursor)

    if len(user_list) == 0:
        return create_response({"error": "User not found"}, 404)
    else: 
        user = add_user_links(user_list[0])

    if not user:
        return create_response({"error": "User not found"}, 404)

    user_json_str = json.dumps(user, sort_keys=True).encode('utf-8')
    etag = hashlib.sha1(user_json_str).hexdigest()

    # Check if client's ETag matches the current one
    if request.headers.get('If-None-Match') == etag:
        return Response(status=304) # Resource is not modified

    

    headers = {'ETag': etag}

    return create_response(user, 200, headers)


@app.route('/users', methods=['POST'])
def add_user():
    """Adds a new user."""
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


@app.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Updates an existing user's details."""
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


@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Deletes a user."""
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('DELETE FROM users WHERE id = :1', (user_id,))
        if cursor.rowcount == 0:
            return create_response({"error": "User not found"}, 404)
    db.commit()
    return create_response({"message": f"User with id {user_id} has been deleted."}, 200)


# --- Book Management Endpoints ---

@app.route('/books', methods=['GET'])
def get_all_books():
    """Fetches a paginated list of all books from the library."""
    
    # 1. Get page and limit from query parameters, with default values
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        if page < 1 or limit < 1:
            raise ValueError
    except ValueError:
        return create_response({"error": "Invalid 'page' or 'pageSize'. Must be positive integers."}, 400)

    # 2. Calculate the offset for the SQL query
    offset = (page - 1) * limit

    db = get_db()
    try:
        with db.cursor() as cursor:
            # Get the total number of books to calculate total pages
            cursor.execute('SELECT COUNT(*) FROM books')
            total_items = cursor.fetchone()[0]
            if total_items == 0:
                return create_response({'data': [], 'total_items': 0}, 200)

            total_pages = ceil(total_items / limit)

            # 3. Fetch the requested page of books using OFFSET and FETCH
            # SQL syntax for pagination
            query = """
                SELECT * FROM books 
                ORDER BY id 
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """
            cursor.execute(query, {'offset': offset, 'limit': limit})
            books = rows_to_dicts(cursor)
            books = [add_book_links(book) for book in books]

        # 4. Build a response object that includes pagination metadata
        response_data = {
            'total_items': total_items,
            'total_pages': total_pages,
            'current_page': page,
            'data': books
        }
        
        # Add HATEOAS links for next and previous pages
        if page < total_pages:
            response_data['next_page_url'] = url_for('get_all_books', page=page + 1, limit=limit, _external=True)
        if page > 1:
            response_data['prev_page_url'] = url_for('get_all_books', page=page - 1, limit=limit, _external=True)

        header = {'Cache-Control': 'public, max-age=300'}
        return create_response(response_data, 200, header)
        
    except oracledb.Error as e:
        return create_response({"error": f"Database error: {e}"}, 500)


@app.route('/books/<int:book_id>', methods=['GET'])
def get_book_by_id(book_id):
    """Fetches a single book by its ID."""
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('SELECT * FROM books WHERE id = :1', (book_id,))
        book_list = rows_to_dicts(cursor)
    if not book_list:
        return create_response({"error": "Book not found"}, 404)
    
    

    book = add_book_links(book_list[0])

    # Generate ETag from a stable JSON representation of the book data
    book_json_str = json.dumps(book, sort_keys=True).encode('utf-8')
    etag = hashlib.sha1(book_json_str).hexdigest()

    # Check if client's ETag matches the current one
    if request.headers.get('If-None-Match') == etag:
        return Response(status=304) # Resource is not modified

    headers = {
        'ETag': etag
    }

    return create_response(book, 200, headers)


@app.route('/books', methods=['POST'])
def add_book():
    """Adds a new book to the library."""
    data = request.get_json()
    if not data or not all(k in data for k in ('title', 'author', 'quantity')):
        return create_response({"error": "Missing required fields: title, author, quantity"}, 400)

    try:
        title = data['title']
        author = data['author']
        quantity = int(data['quantity'])
    except (ValueError, TypeError):
        return create_response({"error": "Invalid data types for fields"}, 400)

    db = get_db()
    try:
        with db.cursor() as cursor:
            new_id_var = cursor.var(oracledb.DB_TYPE_NUMBER)
            sql = 'INSERT INTO books (title, author, quantity) VALUES (:1, :2, :3) RETURNING id INTO :4'
            cursor.execute(sql, (title, author, quantity, new_id_var))
            new_book_id = int(new_id_var.getvalue()[0])
            db.commit()

        new_book = {"id": new_book_id, "title": title, "author": author, "quantity": quantity}
        return create_response(new_book, 201)
    except oracledb.Error as e:
        db.rollback()
        return create_response({"error": f"Database error: {e}"}, 500)


@app.route('/books/<int:book_id>', methods=['PUT'])
def update_book(book_id):
    """Updates an existing book's details."""
    db = get_db()
    book_to_update = db.cursor()
    book_to_update.execute('SELECT * FROM books WHERE id = :1', (book_id,))
    existing_book_data = rows_to_dicts(book_to_update)
    book_to_update.close()

    if not existing_book_data:
        return create_response({"error": "Book not found"}, 404)

    data = request.get_json()
    if not data:
        return create_response({"error": "Request body cannot be empty"}, 400)

    title = data.get('title', existing_book_data[0]['title'])
    author = data.get('author', existing_book_data[0]['author'])
    quantity = data.get('quantity', existing_book_data[0]['quantity'])

    with db.cursor() as cursor:
        cursor.execute('UPDATE books SET title = :1, author = :2, quantity = :3 WHERE id = :4',
                       (title, author, quantity, book_id))
    db.commit()

    with db.cursor() as cursor:
        cursor.execute('SELECT * FROM books WHERE id = :1', (book_id,))
        updated_book = rows_to_dicts(cursor)[0]

    return create_response(updated_book, 200)


@app.route('/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    """Deletes a book from the library."""
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('DELETE FROM books WHERE id = :1', (book_id,))
        if cursor.rowcount == 0:
            return create_response({"error": "Book not found"}, 404)
    db.commit()
    return create_response({"message": f"Book with id {book_id} has been deleted."}, 200)


# --- Core Library API Endpoints ---

@app.route('/borrow', methods=['POST'])
def borrow_book():
    """Borrows a book, decrementing its quantity."""
    data = request.get_json()
    if not data or 'user_id' not in data or 'book_id' not in data:
        return create_response({"error": "Missing user_id or book_id"}, 400)

    user_id = data['user_id']
    book_id = data['book_id']
    db = get_db()
    
    try:
        with db.cursor() as cursor:
            # Check if the user and book exist
            cursor.execute('SELECT id FROM users WHERE id = :1', (user_id,))
            if not cursor.fetchone():
                return create_response({"error": "User not found"}, 404)

            cursor.execute('SELECT title FROM books WHERE id = :1', (book_id,))
            book_row = cursor.fetchone()
            if not book_row:
                return create_response({"error": "Book not found"}, 404)
            book_title = book_row[0]

            # Atomically check and decrement quantity
            cursor.execute(
                'UPDATE books SET quantity = quantity - 1 WHERE id = :1 AND quantity > 0',
                (book_id,)
            )

            if cursor.rowcount == 0:
                db.rollback()
                return create_response({"error": "Book is out of stock"}, 400)

            # Create the borrow record
            cursor.execute('INSERT INTO borrow_records (user_id, book_id, borrow_date) VALUES (:1, :2, :3)',
                           (user_id, book_id, datetime.now()))
            db.commit()

    except oracledb.Error as e:
        db.rollback()
        return create_response({"error": f"Database error: {e}"}, 500)

    return create_response({"message": f"Successfully borrowed '{book_title}'"}, 200)


@app.route('/return', methods=['POST'])
def return_book():
    """Returns a book, incrementing its quantity."""
    data = request.get_json()
    if not data or 'user_id' not in data or 'book_id' not in data:
        return create_response({"error": "Missing user_id or book_id"}, 400)

    user_id = data['user_id']
    book_id = data['book_id']
    db = get_db()

    try:
        with db.cursor() as cursor:
            # Find the active borrow record
            sql = 'SELECT id FROM borrow_records WHERE user_id = :1 AND book_id = :2 AND return_date IS NULL'
            cursor.execute(sql, (user_id, book_id))
            record = cursor.fetchone()

            if not record:
                return create_response({"error": "No active borrow record found for this user and book"}, 400)
            record_id = record[0]
            
            # Get book title for the success message
            cursor.execute('SELECT title FROM books WHERE id = :1', (book_id,))
            book_title_row = cursor.fetchone()
            book_title = book_title_row[0] if book_title_row else "Unknown Book"

            # Perform updates
            cursor.execute('UPDATE books SET quantity = quantity + 1 WHERE id = :1', (book_id,))
            cursor.execute('UPDATE borrow_records SET return_date = :1 WHERE id = :2', (datetime.now(), record_id))
            db.commit()

    except oracledb.Error as e:
        db.rollback()
        return create_response({"error": f"Database error: {e}"}, 500)

    return create_response({"message": f"Successfully returned '{book_title}'"}, 200)


@app.route('/borrow/history', methods=['GET'])
def get_borrow_history():
    """Retrieves the complete history of all borrow records."""
    db = get_db()
    query = """
        SELECT
            br.id,
            br.user_id,
            u.name as user_name,
            br.book_id,
            b.title as book_title,
            br.borrow_date,
            br.return_date
        FROM borrow_records br
        JOIN books b ON br.book_id = b.id
        JOIN users u ON br.user_id = u.id
        ORDER BY br.borrow_date DESC
    """
    with db.cursor() as cursor:
        cursor.execute(query)
        records = rows_to_dicts(cursor)

    records = [add_borrow_record_links(rec) for rec in records]

    return create_response(records, 200)


@app.route('/users/<int:user_id>/history', methods=['GET'])
def get_user_borrow_history(user_id):
    """Retrieves the borrow history for a specific user."""
    db = get_db()

    # Check if user exists first
    with db.cursor() as cursor:
        cursor.execute('SELECT id FROM users WHERE id = :1', (user_id,))
        if not cursor.fetchone():
            return create_response({"error": "User not found"}, 404)

    query = """
        SELECT
            br.id,
            br.book_id,
            br.user_id,
            b.title as book_title,
            br.borrow_date,
            br.return_date
        FROM borrow_records br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = :1
        ORDER BY br.borrow_date DESC
    """
    with db.cursor() as cursor:
        cursor.execute(query, (user_id,))
        records = rows_to_dicts(cursor)

    if len(records) == 0:
        return create_response({"message": "No borrow history found for this user"}, 200)

    records = [add_borrow_record_links(rec) for rec in records]

    return create_response(records, 200)


# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True)
