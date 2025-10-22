# project/library.py
import oracledb
from datetime import datetime
from flask import Blueprint, request
from .db import get_db
from .helper import * # Assumes helper.py is now in the same directory

bp = Blueprint('library', __name__)

@bp.route('/borrow', methods=['POST'])
def borrow_book():
    """Borrows a book, decrementing its quantity."""
    # ... (code for borrow_book is identical, no changes needed)
    data = request.get_json()
    if not data or 'user_id' not in data or 'book_id' not in data:
        return create_response({"error": "Missing user_id or book_id"}, 400)

    user_id = data['user_id']
    book_id = data['book_id']
    db = get_db()
    
    try:
        with db.cursor() as cursor:
            cursor.execute('SELECT id FROM users WHERE id = :1', (user_id,))
            if not cursor.fetchone():
                return create_response({"error": "User not found"}, 404)

            cursor.execute('SELECT title FROM books WHERE id = :1', (book_id,))
            book_row = cursor.fetchone()
            if not book_row:
                return create_response({"error": "Book not found"}, 404)
            book_title = book_row[0]

            cursor.execute(
                'UPDATE books SET quantity = quantity - 1 WHERE id = :1 AND quantity > 0',
                (book_id,)
            )

            if cursor.rowcount == 0:
                db.rollback()
                return create_response({"error": "Book is out of stock"}, 400)

            cursor.execute('INSERT INTO borrow_records (user_id, book_id, borrow_date) VALUES (:1, :2, :3)',
                           (user_id, book_id, datetime.now()))
            db.commit()

    except oracledb.Error as e:
        db.rollback()
        return create_response({"error": f"Database error: {e}"}, 500)

    return create_response({"message": f"Successfully borrowed '{book_title}'"}, 200)


@bp.route('/return', methods=['POST'])
def return_book():
    """Returns a book, incrementing its quantity."""
    # ... (code for return_book is identical, no changes needed)
    data = request.get_json()
    if not data or 'user_id' not in data or 'book_id' not in data:
        return create_response({"error": "Missing user_id or book_id"}, 400)

    user_id = data['user_id']
    book_id = data['book_id']
    db = get_db()

    try:
        with db.cursor() as cursor:
            sql = 'SELECT id FROM borrow_records WHERE user_id = :1 AND book_id = :2 AND return_date IS NULL'
            cursor.execute(sql, (user_id, book_id))
            record = cursor.fetchone()

            if not record:
                return create_response({"error": "No active borrow record found for this user and book"}, 400)
            record_id = record[0]
            
            cursor.execute('SELECT title FROM books WHERE id = :1', (book_id,))
            book_title_row = cursor.fetchone()
            book_title = book_title_row[0] if book_title_row else "Unknown Book"

            cursor.execute('UPDATE books SET quantity = quantity + 1 WHERE id = :1', (book_id,))
            cursor.execute('UPDATE borrow_records SET return_date = :1 WHERE id = :2', (datetime.now(), record_id))
            db.commit()

    except oracledb.Error as e:
        db.rollback()
        return create_response({"error": f"Database error: {e}"}, 500)

    return create_response({"message": f"Successfully returned '{book_title}'"}, 200)


@bp.route('/borrow/history', methods=['GET'])
def get_borrow_history():
    """Retrieves the complete history of all borrow records."""
    db = get_db()
    query = """
        SELECT
            br.id, br.user_id, u.name as user_name,
            br.book_id, b.title as book_title,
            br.borrow_date, br.return_date
        FROM borrow_records br
        JOIN books b ON br.book_id = b.id
        JOIN users u ON br.user_id = u.id
        ORDER BY br.borrow_date DESC
    """
    with db.cursor() as cursor:
        cursor.execute(query)
        records = rows_to_dicts(cursor)
    
    # This helper MUST be updated. See notes below.
    records = [add_borrow_record_links(rec) for rec in records]

    return create_response(records, 200)