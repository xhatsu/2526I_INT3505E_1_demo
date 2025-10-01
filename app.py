
import sqlite3
from flask import Flask, request, jsonify
from datetime import datetime

DATABASE = 'library.db'

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# == Manage Books ==

@app.route('/books', methods=['GET'])
def get_all_books():
    conn = get_db_connection()
    books = conn.execute('SELECT * FROM books').fetchall()
    conn.close()
    return jsonify([dict(row) for row in books])

@app.route('/books/<int:book_id>', methods=['GET'])
def get_book_by_id(book_id):
    conn = get_db_connection()
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    conn.close()
    if book is None:
        return jsonify({"error": "Book not found"}), 404
    return jsonify(dict(book))

@app.route('/books', methods=['POST'])
def add_book():
    data = request.get_json()
    if not data or not all(k in data for k in ('title', 'author', 'quantity')):
        return jsonify({"error": "Missing required fields: title, author, quantity"}), 400

    title = data['title']
    author = data['author']
    quantity = data['quantity']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO books (title, author, quantity) VALUES (?, ?, ?)',
                   (title, author, quantity))
    new_book_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    new_book = {"id": new_book_id, "title": title, "author": author, "quantity": quantity}
    return jsonify(new_book), 201

@app.route('/books/update/<int:book_id>', methods=['PUT'])
def update_book(book_id):
    conn = get_db_connection()
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    if book is None:
        conn.close()
        return jsonify({"error": "Book not found"}), 404

    data = request.get_json()
    if not data:
        conn.close()
        return jsonify({"error": "Request body cannot be empty"}), 400

    title = data.get('title', book['title'])
    author = data.get('author', book['author'])
    quantity = data.get('quantity', book['quantity'])

    conn.execute('UPDATE books SET title = ?, author = ?, quantity = ? WHERE id = ?',
                 (title, author, quantity, book_id))
    conn.commit()
    
    updated_book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    conn.close()

    return jsonify(dict(updated_book))

@app.route('/books/delete/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    conn = get_db_connection()
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    if book is None:
        conn.close()
        return jsonify({"error": "Book not found"}), 404
    
    conn.execute('DELETE FROM books WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"message": f"Book with id {book_id} has been deleted."})

# === Main API Endpoints ===

@app.route('/borrow', methods=['POST'])
def borrow_book():
    data = request.get_json()
    if not data or 'user_id' not in data or 'book_id' not in data:
        return jsonify({"error": "Missing user_id or book_id"}), 400

    user_id = data['user_id']
    book_id = data['book_id']

    conn = get_db_connection()
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    if book is None:
        conn.close()
        return jsonify({"error": "Book not found"}), 404
    if book['quantity'] <= 0:
        conn.close()
        return jsonify({"error": "Book is out of stock"}), 400

    try:
        conn.execute('UPDATE books SET quantity = quantity - 1 WHERE id = ?', (book_id,))
        conn.execute('INSERT INTO borrow_records (user_id, book_id, borrow_date) VALUES (?, ?, ?)',
                     (user_id, book_id, datetime.now().isoformat()))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        conn.close()

    return jsonify({"message": f"Successfully borrowed '{book['title']}'"}), 200

@app.route('/return', methods=['POST'])
def return_book():
    data = request.get_json()
    if not data or 'user_id' not in data or 'book_id' not in data:
        return jsonify({"error": "Missing user_id or book_id"}), 400
        
    user_id = data['user_id']
    book_id = data['book_id']

    conn = get_db_connection()
    record = conn.execute('SELECT * FROM borrow_records WHERE user_id = ? AND book_id = ? AND return_date IS NULL',
                          (user_id, book_id)).fetchone()
                          
    if record is None:
        conn.close()
        return jsonify({"error": "No active borrow record found for this user and book"}), 400
    
    book_title = conn.execute('SELECT title FROM books WHERE id = ?', (book_id,)).fetchone()['title']

    try:
        conn.execute('UPDATE books SET quantity = quantity + 1 WHERE id = ?', (book_id,))
        conn.execute('UPDATE borrow_records SET return_date = ? WHERE id = ?',
                     (datetime.now().isoformat(), record['id']))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        conn.close()
    
    return jsonify({"message": f"Successfully returned '{book_title}'"}), 200

@app.route('/borrow/history', methods=['GET'])
def get_borrow_history():
    conn = get_db_connection()
    records = conn.execute('SELECT * FROM borrow_records').fetchall()
    conn.close()
    return jsonify([dict(row) for row in records])

if __name__ == '__main__':
    app.run(debug=True)