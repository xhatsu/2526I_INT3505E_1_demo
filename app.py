# app.py
import sqlite3
from flask import Flask, request, jsonify
from datetime import datetime

DATABASE = 'library.db'

app = Flask(__name__)

def get_db_connection():
    """Tạo kết nối đến database"""
    conn = sqlite3.connect(DATABASE)
    # Trả về các hàng dưới dạng dictionary, tiện lợi hơn tuple
    conn.row_factory = sqlite3.Row
    return conn

# === API Endpoints cho Quản lý Sách (CRUD) ===

@app.route('/books', methods=['GET'])
def get_all_books():
    """Lấy danh sách tất cả các sách"""
    conn = get_db_connection()
    books = conn.execute('SELECT * FROM books').fetchall()
    conn.close()
    # Chuyển đổi list các đối tượng Row thành list các dictionary
    return jsonify([dict(row) for row in books])

@app.route('/books/<int:book_id>', methods=['GET'])
def get_book_by_id(book_id):
    """Lấy thông tin một cuốn sách cụ thể theo ID"""
    conn = get_db_connection()
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    conn.close()
    if book is None:
        return jsonify({"error": "Book not found"}), 404
    return jsonify(dict(book))

@app.route('/books', methods=['POST'])
def add_book():
    """Thêm một cuốn sách mới"""
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

# Các endpoint PUT và DELETE tương tự, bạn có thể tự mình xây dựng
# dựa trên các ví dụ trên để luyện tập thêm.

# === API Endpoints cho Mượn và Trả Sách ===

@app.route('/borrow', methods=['POST'])
def borrow_book():
    """Xử lý mượn sách"""
    data = request.get_json()
    if not data or 'user_id' not in data or 'book_id' not in data:
        return jsonify({"error": "Missing user_id or book_id"}), 400

    user_id = data['user_id']
    book_id = data['book_id']

    conn = get_db_connection()
    # Lấy thông tin sách và kiểm tra số lượng
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    if book is None:
        conn.close()
        return jsonify({"error": "Book not found"}), 404
    if book['quantity'] <= 0:
        conn.close()
        return jsonify({"error": "Book is out of stock"}), 400

    # Bắt đầu một transaction
    try:
        # Giảm số lượng sách
        conn.execute('UPDATE books SET quantity = quantity - 1 WHERE id = ?', (book_id,))
        # Ghi nhận lịch sử mượn
        conn.execute('INSERT INTO borrow_records (user_id, book_id, borrow_date) VALUES (?, ?, ?)',
                     (user_id, book_id, datetime.now().isoformat()))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback() # Hoàn tác nếu có lỗi
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        conn.close()

    return jsonify({"message": f"Successfully borrowed '{book['title']}'"}), 200

@app.route('/return', methods=['POST'])
def return_book():
    """Xử lý trả sách"""
    data = request.get_json()
    if not data or 'user_id' not in data or 'book_id' not in data:
        return jsonify({"error": "Missing user_id or book_id"}), 400
        
    user_id = data['user_id']
    book_id = data['book_id']

    conn = get_db_connection()
    # Tìm bản ghi mượn sách chưa trả
    record = conn.execute('SELECT * FROM borrow_records WHERE user_id = ? AND book_id = ? AND return_date IS NULL',
                          (user_id, book_id)).fetchone()
                          
    if record is None:
        conn.close()
        return jsonify({"error": "No active borrow record found for this user and book"}), 400
    
    book_title = conn.execute('SELECT title FROM books WHERE id = ?', (book_id,)).fetchone()['title']

    # Bắt đầu transaction
    try:
        # Tăng lại số lượng sách
        conn.execute('UPDATE books SET quantity = quantity + 1 WHERE id = ?', (book_id,))
        # Cập nhật lịch sử trả sách
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
    """Lấy toàn bộ lịch sử mượn/trả"""
    conn = get_db_connection()
    records = conn.execute('SELECT * FROM borrow_records').fetchall()
    conn.close()
    return jsonify([dict(row) for row in records])

# Chạy ứng dụng
if __name__ == '__main__':
    app.run(debug=True)