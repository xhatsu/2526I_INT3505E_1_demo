# init_db.py
import sqlite3

# Kết nối đến database (nếu chưa có, file sẽ được tạo)
connection = sqlite3.connect('library.db')

# Dùng cursor để thực thi các câu lệnh SQL
cursor = connection.cursor()

# Xóa bảng nếu đã tồn tại để tránh lỗi khi chạy lại
cursor.execute("DROP TABLE IF EXISTS books")
cursor.execute("DROP TABLE IF EXISTS users")
cursor.execute("DROP TABLE IF EXISTS borrow_records")

# Tạo bảng books
cursor.execute("""
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    quantity INTEGER NOT NULL
)
""")

# Tạo bảng users
cursor.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)
""")

# Tạo bảng borrow_records để lưu lịch sử mượn trả
cursor.execute("""
CREATE TABLE borrow_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    borrow_date TEXT NOT NULL,
    return_date TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (book_id) REFERENCES books (id)
)
""")

# Thêm một vài dữ liệu mẫu
cursor.execute("INSERT INTO books (title, author, quantity) VALUES (?, ?, ?)", 
               ('Lão Hạc', 'Nam Cao', 5))
cursor.execute("INSERT INTO books (title, author, quantity) VALUES (?, ?, ?)",
               ('Số Đỏ', 'Vũ Trọng Phụng', 3))
cursor.execute("INSERT INTO books (title, author, quantity) VALUES (?, ?, ?)",
               ('Dế Mèn Phiêu Lưu Ký', 'Tô Hoài', 10))

cursor.execute("INSERT INTO users (name) VALUES (?)", ('Nguyễn Văn A',))
cursor.execute("INSERT INTO users (name) VALUES (?)", ('Trần Thị B',))


# Lưu thay đổi và đóng kết nối
connection.commit()
connection.close()

print("Database initialized successfully with sample data.")