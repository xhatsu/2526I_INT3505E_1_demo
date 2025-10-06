import sqlite3
from flask import Flask, request, g
from datetime import datetime
from helper import create_response

# --- Configuration ---
DATABASE = 'library.db'

app = Flask(__name__)


# --- Database Management ---

def get_db():
    """
    Opens a new database connection if there is none yet for the
    current application context.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    """Closes the database again at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


# --- User Management Endpoints ---

@app.route('/users', methods=['GET'])
def get_all_users():
    """Fetches all users."""
    db = get_db()
    users = db.execute('SELECT * FROM users ORDER BY name').fetchall()
    return create_response([dict(row) for row in users], 200)


@app.route('/users/<int:user_id>', methods=['GET'])
def get_user_by_id(user_id):
    """Fetches a single user by their ID."""
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user is None:
        return create_response({"error": "User not found"}, 404)
    return create_response(dict(user), 200)


@app.route('/users', methods=['POST'])
def add_user():
    """Adds a new user."""
    data = request.get_json()
    if not data or 'name' not in data:
        return create_response({"error": "Missing required field: name"}, 400)

    name = data['name']
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute('INSERT INTO users (name) VALUES (?)', (name,))
        new_user_id = cursor.lastrowid
        db.commit()
        new_user = {"id": new_user_id, "name": name}
        return create_response(new_user, 201)
    except sqlite3.IntegrityError:
        db.rollback()
        return create_response({"error": "User with this name already exists"}, 409)  # 409 Conflict


@app.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Updates an existing user's details."""
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user is None:
        return create_response({"error": "User not found"}, 404)

    data = request.get_json()
    if not data or 'name' not in data:
        return create_response({"error": "Missing required field: name"}, 400)

    name = data.get('name', user['name'])

    try:
        db.execute('UPDATE users SET name = ? WHERE id = ?', (name, user_id))
        db.commit()
        updated_user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        return create_response(dict(updated_user), 200)
    except sqlite3.IntegrityError:
        db.rollback()
        return create_response({"error": "User with this name already exists"}, 409)


@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Deletes a user."""
    db = get_db()
    cursor = db.cursor()
    # The ON DELETE CASCADE in the DB schema will handle deleting associated borrow_records
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))

    if cursor.rowcount == 0:
        return create_response({"error": "User not found"}, 404)

    db.commit()
    return create_response({"message": f"User with id {user_id} has been deleted."}, 200)


# --- Book Management Endpoints (CRUD) ---

@app.route('/books', methods=['GET'])
def get_all_books():
    """Fetches all books from the library."""
    db = get_db()
    books = db.execute('SELECT * FROM books ORDER BY title').fetchall()
    header = {'Cache-Control': 'public, max-age=300'}
    return create_response([dict(row) for row in books], 200, header)


@app.route('/books/<int:book_id>', methods=['GET'])
def get_book_by_id(book_id):
    """Fetches a single book by its ID."""
    db = get_db()
    book = db.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    if book is None:
        return create_response({"error": "Book not found"}, 404)
    header = {'Cache-Control': 'public, max-age=300'}
    return create_response(dict(book), 200, header)


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
    cursor = db.cursor()
    cursor.execute('INSERT INTO books (title, author, quantity) VALUES (?, ?, ?)',
                   (title, author, quantity))
    new_book_id = cursor.lastrowid
    db.commit()

    new_book = {"id": new_book_id, "title": title, "author": author, "quantity": quantity}
    return create_response(new_book, 201)


@app.route('/books/<int:book_id>', methods=['PUT'])
def update_book(book_id):
    """Updates an existing book's details."""
    db = get_db()
    book = db.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    if book is None:
        return create_response({"error": "Book not found"}, 404)

    data = request.get_json()
    if not data:
        return create_response({"error": "Request body cannot be empty"}, 400)

    # Coalesce new values with existing ones
    title = data.get('title', book['title'])
    author = data.get('author', book['author'])
    quantity = data.get('quantity', book['quantity'])

    db.execute('UPDATE books SET title = ?, author = ?, quantity = ? WHERE id = ?',
               (title, author, quantity, book_id))
    db.commit()

    updated_book = db.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    return create_response(dict(updated_book), 200)


@app.route('/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    """Deletes a book from the library."""
    db = get_db()
    cursor = db.cursor()
    # The ON DELETE CASCADE in the DB schema will handle deleting associated borrow_records
    cursor.execute('DELETE FROM books WHERE id = ?', (book_id,))

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

    # Check if the user and book exist
    user = db.execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        return create_response({"error": "User not found"}, 404)

    book = db.execute('SELECT title FROM books WHERE id = ?', (book_id,)).fetchone()
    if not book:
        return create_response({"error": "Book not found"}, 404)

    try:
        # Atomically check and decrement quantity to prevent race conditions
        cursor = db.execute(
            'UPDATE books SET quantity = quantity - 1 WHERE id = ? AND quantity > 0',
            (book_id,)
        )

        if cursor.rowcount == 0:
            db.rollback()
            return create_response({"error": "Book is out of stock"}, 400)

        # If the update was successful, create the borrow record
        db.execute('INSERT INTO borrow_records (user_id, book_id, borrow_date) VALUES (?, ?, ?)',
                   (user_id, book_id, datetime.now().isoformat()))
        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        return create_response({"error": f"Database error: {e}"}, 500)

    return create_response({"message": f"Successfully borrowed '{book['title']}'"}, 200)


@app.route('/return', methods=['POST'])
def return_book():
    """Returns a book, incrementing its quantity."""
    data = request.get_json()
    if not data or 'user_id' not in data or 'book_id' not in data:
        return create_response({"error": "Missing user_id or book_id"}, 400)

    user_id = data['user_id']
    book_id = data['book_id']

    db = get_db()
    record = db.execute('SELECT * FROM borrow_records WHERE user_id = ? AND book_id = ? AND return_date IS NULL',
                        (user_id, book_id)).fetchone()

    if record is None:
        return create_response({"error": "No active borrow record found for this user and book"}, 400)

    book_title_row = db.execute('SELECT title FROM books WHERE id = ?', (book_id,)).fetchone()
    book_title = book_title_row['title'] if book_title_row else "Unknown Book"

    try:
        db.execute('UPDATE books SET quantity = quantity + 1 WHERE id = ?', (book_id,))
        db.execute('UPDATE borrow_records SET return_date = ? WHERE id = ?',
                   (datetime.now().isoformat(), record['id']))
        db.commit()
    except sqlite3.Error as e:
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
    records = db.execute(query).fetchall()
    return create_response([dict(row) for row in records], 200)


@app.route('/users/<int:user_id>/history', methods=['GET'])
def get_user_borrow_history(user_id):
    """Retrieves the borrow history for a specific user."""
    db = get_db()

    user = db.execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        return create_response({"error": "User not found"}, 404)

    query = """
        SELECT
            br.id,
            br.book_id,
            b.title as book_title,
            br.borrow_date,
            br.return_date
        FROM borrow_records br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = ?
        ORDER BY br.borrow_date DESC
    """
    records = db.execute(query, (user_id,)).fetchall()
    return create_response([dict(row) for row in records], 200)


# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True)

