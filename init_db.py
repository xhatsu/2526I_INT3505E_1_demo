
import sqlite3

connection = sqlite3.connect('library.db')

cursor = connection.cursor()

cursor.execute("DROP TABLE IF EXISTS books")
cursor.execute("DROP TABLE IF EXISTS users")
cursor.execute("DROP TABLE IF EXISTS borrow_records")

cursor.execute("""
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    quantity INTEGER NOT NULL
)
""")

cursor.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)
""")

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

cursor.execute("INSERT INTO books (title, author, quantity) VALUES (?, ?, ?)", 
               ('Book1', 'Author1', 5))
cursor.execute("INSERT INTO books (title, author, quantity) VALUES (?, ?, ?)",
               ('Book2', 'Author2', 3))
cursor.execute("INSERT INTO books (title, author, quantity) VALUES (?, ?, ?)",
               ('Book3', 'Author3', 10))

cursor.execute("INSERT INTO users (name) VALUES (?)", ('User Name One',))
cursor.execute("INSERT INTO users (name) VALUES (?)", ('Two User Name',))


connection.commit()
connection.close()

print("Database initialized successfully with sample data.")